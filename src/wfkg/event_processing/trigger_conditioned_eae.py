"""Trigger-conditioned event/entity argument role classification."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class TriggerConditionedEAE:
    """Classify one event/entity pair using marked trigger and entity spans."""

    def __init__(self, checkpoint_path: Path, device: str | None = None) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_path, use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(checkpoint_path).to(self.device)
        self.model.eval()
        self.label2id = {str(key): int(value) for key, value in self.model.config.label2id.items()}
        self.id2label = {int(key): str(value) for key, value in self.model.config.id2label.items()}
        self.none_id = self.label2id["NONE"]
        self.max_length = int(getattr(self.model.config, "max_position_embeddings", 514))

    @staticmethod
    def marked_text(sentence: str, trigger_span: tuple[int, int], event_type: str,
                    entity_span: tuple[int, int], entity_type: str) -> str | None:
        ts, te = trigger_span
        es, ee = entity_span
        if not (0 <= ts < te <= len(sentence) and 0 <= es < ee <= len(sentence)):
            return None
        if max(ts, es) < min(te, ee):
            return None
        trigger, entity = sentence[ts:te], sentence[es:ee]
        tagged = [(ts, " <TRIGGER> "), (te, " </TRIGGER> "),
                  (es, " <ENTITY> "), (ee, " </ENTITY> ")]
        for pos, marker in sorted(tagged, key=lambda item: (item[0], 0 if item[1].startswith(" </") else 1), reverse=True):
            sentence = sentence[:pos] + marker + sentence[pos:]
        return (f"EventType: {event_type} EntityType: {entity_type} Sentence: {sentence}", trigger, entity)

    def predict_pairs(self, pairs: list[dict[str, Any]], batch_size: int = 4,
                      crop_overlength: bool = False) -> list[dict[str, Any]]:
        """Each pair has sentence, triggerSpan, eventType, entitySpan, entityType."""
        torch = self.torch
        valid, encodings = [], []
        for pair in pairs:
            marked = self.marked_text(str(pair["sentence"]), tuple(pair["triggerSpan"]),
                                      str(pair["eventType"]), tuple(pair["entitySpan"]),
                                      str(pair["entityType"]))
            if marked is None:
                valid.append({"status": "INVALID_OR_OVERLAPPING_SPANS"})
                encodings.append(None)
                continue
            value, trigger_text, entity_text = marked
            encoding = self.tokenizer(value, truncation=False, add_special_tokens=True)
            window_span = None
            if len(encoding["input_ids"]) > 192 and crop_overlength:
                sentence = str(pair["sentence"])
                ts, te = tuple(pair["triggerSpan"]); es, ee = tuple(pair["entitySpan"])
                left, right = min(ts, es), max(te, ee)
                # If both complete mentions and markers do not fit, no contiguous
                # context window can preserve their original offsets safely.
                minimal = self.marked_text(sentence[left:right], (ts-left, te-left),
                                           str(pair["eventType"]), (es-left, ee-left),
                                           str(pair["entityType"]))
                if minimal is not None:
                    minimal_encoding = self.tokenizer(minimal[0], truncation=False, add_special_tokens=True)
                    if len(minimal_encoding["input_ids"]) <= 192:
                        low, high, best = 0, max(left, len(sentence)-right), 0
                        while low <= high:
                            padding = (low + high) // 2
                            window_start = max(0, left-padding)
                            window_end = min(len(sentence), right+padding)
                            window = self.marked_text(sentence[window_start:window_end],
                                                      (ts-window_start, te-window_start),
                                                      str(pair["eventType"]),
                                                      (es-window_start, ee-window_start),
                                                      str(pair["entityType"]))
                            window_encoding = self.tokenizer(window[0], truncation=False, add_special_tokens=True)
                            if len(window_encoding["input_ids"]) <= 192:
                                best = padding; low = padding + 1
                            else:
                                high = padding - 1
                        window_start = max(0, left-best)
                        window_end = min(len(sentence), right+best)
                        value = self.marked_text(sentence[window_start:window_end],
                                                 (ts-window_start, te-window_start),
                                                 str(pair["eventType"]),
                                                 (es-window_start, ee-window_start),
                                                 str(pair["entityType"]))[0]
                        encoding = self.tokenizer(value, truncation=False, add_special_tokens=True)
                        window_span = {"startChar": window_start, "endChar": window_end,
                                       "triggerSpanPreserved": (window_start <= ts < te <= window_end),
                                       "entitySpanPreserved": (window_start <= es < ee <= window_end)}
            if len(encoding["input_ids"]) > 192:
                valid.append({"status": "OVER_MAX_LENGTH"})
                encodings.append(None)
                continue
            valid.append({"status": "OK", "triggerText": trigger_text, "entityText": entity_text})
            if window_span is not None:
                valid[-1]["contextWindowSpan"] = window_span
            encodings.append(encoding)
        indices = [i for i, item in enumerate(encodings) if item is not None]
        for start in range(0, len(indices), batch_size):
            current = indices[start:start + batch_size]
            batch = [encodings[i] for i in current]
            width = max(len(item["input_ids"]) for item in batch)
            pad_id = self.tokenizer.pad_token_id
            ids = [item["input_ids"] + [pad_id] * (width - len(item["input_ids"])) for item in batch]
            masks = [item["attention_mask"] + [0] * (width - len(item["attention_mask"])) for item in batch]
            input_ids = torch.tensor(ids, device=self.device)
            attention = torch.tensor(masks, device=self.device)
            with torch.inference_mode():
                if self.device.type == "cuda":
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                        logits = self.model(input_ids=input_ids, attention_mask=attention).logits.float()
                else:
                    logits = self.model(input_ids=input_ids, attention_mask=attention).logits
                probs = torch.softmax(logits, dim=-1)
                scores, labels = probs.max(dim=-1)
            for local, index in enumerate(current):
                label = self.id2label[int(labels[local])]
                valid[index].update({"label": label, "confidence": float(scores[local]),
                                     "roleProbabilities": {self.id2label[j]: float(probs[local, j])
                                                           for j in range(probs.shape[1]) if j != self.none_id}})
        return valid
