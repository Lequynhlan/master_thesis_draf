"""Inference for the BKEE-supervised PhoBERT BIO event detector."""

from __future__ import annotations

import json
import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import Any


class PhoBERTEventDetector:
    """Load a fine-tuned token classifier and return trigger spans from new text."""

    def __init__(self, checkpoint_path: Path, *, label_mapping_path: Path | None = None,
                 device: str | None = None, inference_config_path: Path | None = None) -> None:
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "PhoBERT inference requires the optional extractor dependencies. "
                "Install torch and transformers in the active Python environment."
            ) from exc

        self.checkpoint_path = Path(checkpoint_path).resolve()
        if not self.checkpoint_path.is_dir():
            raise FileNotFoundError(f"PhoBERT checkpoint directory not found: {self.checkpoint_path}")
        labels_path = Path(label_mapping_path).resolve() if label_mapping_path else self.checkpoint_path / "label_mapping.json"
        if not labels_path.is_file():
            raise FileNotFoundError(f"PhoBERT label map not found: {labels_path}")
        self.label_data = json.loads(labels_path.read_text(encoding="utf-8"))
        self.id2label = {int(key): value for key, value in self.label_data["id2label"].items()}
        self.inference_config: dict[str, Any] = {}
        if inference_config_path is not None:
            config_path = Path(inference_config_path).resolve()
            self.inference_config = json.loads(config_path.read_text(encoding="utf-8"))
            expected_name = self.inference_config.get("checkpointName")
            if expected_name and self.checkpoint_path.name != expected_name:
                raise ValueError(
                    f"Inference config targets checkpoint {expected_name!r}, "
                    f"but loaded {self.checkpoint_path.name!r}."
                )
            threshold = self.inference_config.get("minConfidence")
            if threshold is not None and not 0.0 <= float(threshold) <= 1.0:
                raise ValueError("Inference config minConfidence must be between 0 and 1.")
            for relative_path, expected_hash in self.inference_config.get("checkpointSha256", {}).items():
                target = self.checkpoint_path / relative_path
                hasher = hashlib.sha256()
                with target.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        hasher.update(chunk)
                digest = hasher.hexdigest().upper()
                if digest != str(expected_hash).upper():
                    raise ValueError(f"Checkpoint integrity check failed for {relative_path}.")
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.tokenizer = AutoTokenizer.from_pretrained(self.checkpoint_path, use_fast=False)
        self.model = AutoModelForTokenClassification.from_pretrained(self.checkpoint_path)
        self.model.to(self.device)
        self.model.eval()
        self.torch = torch
        self.max_length = int(self.label_data.get("max_length", 192))
        self.stride = int(self.label_data.get("inference_stride", 48))

    def predict(self, text: str, *, max_length: int | None = None) -> list[dict[str, Any]]:
        """Return event type, trigger, confidence, and sentence-level evidence spans.

        Long text is sentence-split and token-windowed with overlap. Returned
        character offsets always point into the exact ``text`` argument.
        """

        if not text or not text.strip():
            return []
        maximum = max_length or self.max_length
        sentence_spans = _sentence_spans(text)
        windows: list[dict[str, Any]] = []
        for sentence_start, sentence_end in sentence_spans:
            sentence = text[sentence_start:sentence_end]
            pieces, piece_spans = self._tokenize_segmented(sentence)
            payload_length = maximum - 2
            step = max(1, payload_length - self.stride)
            for offset in range(0, max(1, len(pieces)), step):
                stop = min(len(pieces), offset + payload_length)
                input_ids = [self.tokenizer.cls_token_id] + pieces[offset:stop] + [self.tokenizer.sep_token_id]
                spans = [(0, 0)] + piece_spans[offset:stop] + [(0, 0)]
                windows.append({
                    "input_ids": input_ids,
                    "attention_mask": [1] * len(input_ids),
                    "offsets": spans,
                    "sentence_start": sentence_start,
                    "sentence_end": sentence_end,
                    "sentence": sentence,
                })
                if stop >= len(pieces):
                    break

        predictions: dict[tuple[int, int, str], dict[str, Any]] = {}
        with self.torch.inference_mode():
            for item in windows:
                input_ids = self.torch.tensor([item["input_ids"]], device=self.device)
                attention = self.torch.tensor([item["attention_mask"]], device=self.device)
                logits = self.model(input_ids=input_ids, attention_mask=attention).logits[0]
                probabilities = self.torch.softmax(logits.float(), dim=-1)
                label_ids = probabilities.argmax(dim=-1).tolist()
                scores = probabilities.max(dim=-1).values.tolist()
                for start, end, event_type, confidence in _decode_bio(
                    label_ids, scores, item["offsets"], self.id2label
                ):
                    absolute_start = item["sentence_start"] + start
                    absolute_end = item["sentence_start"] + end
                    key = (absolute_start, absolute_end, event_type)
                    record = {
                        "eventType": event_type,
                        "trigger": text[absolute_start:absolute_end],
                        "confidence": round(float(confidence), 6),
                        "evidenceSpan": {
                            "text": item["sentence"],
                            "startChar": item["sentence_start"],
                            "endChar": item["sentence_end"],
                        },
                        "triggerSpan": {"startChar": absolute_start, "endChar": absolute_end},
                        "eventTaxonomy": "BKEE_33_TYPES",
                    }
                    prior = predictions.get(key)
                    if prior is None or record["confidence"] > prior["confidence"]:
                        predictions[key] = record
        ordered = sorted(predictions.values(), key=lambda item: (item["triggerSpan"]["startChar"], item["eventType"]))
        threshold = self.inference_config.get("minConfidence")
        if threshold is not None:
            ordered = [item for item in ordered if item["confidence"] >= float(threshold)]
        return ordered

    def _tokenize_segmented(self, sentence: str) -> tuple[list[int], list[tuple[int, int]]]:
        segmenter = getattr(self, "_segmenter", None)
        if segmenter is None:
            import py_vncorenlp

            assets = self.label_data.get("vncorenlp_assets")
            if not assets:
                raise RuntimeError("Checkpoint metadata does not specify the VnCoreNLP word segmenter assets.")
            asset_path = Path(assets)
            if not asset_path.is_absolute():
                asset_path = self.checkpoint_path / asset_path
            cwd = os.getcwd()
            try:
                segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(asset_path.resolve()))
            finally:
                os.chdir(cwd)
            self._segmenter = segmenter
        segmented_sentences = segmenter.word_segment(sentence)
        tokens = [token for line in segmented_sentences for token in line.split() if token]
        source_cursor = 0
        normalized_sentence, source_offsets = _normalized_offset_map(sentence)
        piece_ids: list[int] = []
        piece_spans: list[tuple[int, int]] = []
        for token in tokens:
            normalized_token = _normalize_for_alignment(token)
            if normalized_token:
                normalized_cursor = 0
                while normalized_cursor < len(source_offsets) and source_offsets[normalized_cursor][1] <= source_cursor:
                    normalized_cursor += 1
                match_start = normalized_sentence.find(normalized_token, normalized_cursor)
                if match_start < 0:
                    raise RuntimeError(f"Could not align VnCoreNLP token {token!r} to source sentence.")
                source_start = source_offsets[match_start][0]
                source_end = source_offsets[match_start + len(normalized_token) - 1][1]
            else:
                # Standalone underscores are real source punctuation in some
                # crawled attachments and disappear from normalized matching.
                source_start = sentence.find(token, source_cursor)
                if source_start < 0:
                    raise RuntimeError(f"Could not align VnCoreNLP token {token!r} to source sentence.")
                source_end = source_start + len(token)
            token_pieces = self.tokenizer.tokenize(unicodedata.normalize("NFC", token))
            token_ids = self.tokenizer.convert_tokens_to_ids(token_pieces)
            piece_ids.extend(token_ids)
            # Each BPE piece is tied to its source word token; decoding a BIO
            # span therefore returns exact original token boundaries.
            piece_spans.extend([(source_start, source_end)] * len(token_ids))
            source_cursor = source_end
        return piece_ids, piece_spans


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for index, character in enumerate(text):
        boundary = character in "\r\n" or (
            character in ".!?" and (index + 1 == len(text) or text[index + 1].isspace())
        )
        if not boundary:
            continue
        end = index + 1
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
        start = index + 1
    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end))
    if not spans and text.strip():
        start = len(text) - len(text.lstrip())
        end = len(text.rstrip())
        spans.append((start, end))
    return spans


def _normalize_for_alignment(value: str) -> str:
    """Normalize tokenizer spelling differences without changing source offsets."""
    output: list[str] = []
    for character in unicodedata.normalize("NFD", value.replace("_", " ")).casefold():
        if unicodedata.category(character) == "Mn" or character.isspace():
            continue
        output.append("d" if character == "đ" else character)
    return "".join(output)


def _normalized_offset_map(value: str) -> tuple[str, list[tuple[int, int]]]:
    normalized: list[str] = []
    offsets: list[tuple[int, int]] = []
    for index, character in enumerate(value):
        for part in unicodedata.normalize("NFD", character).casefold():
            if unicodedata.category(part) == "Mn" or part.isspace() or part == "_":
                continue
            normalized.append("d" if part == "đ" else part)
            offsets.append((index, index + 1))
    return "".join(normalized), offsets


def _decode_bio(
    label_ids: list[int],
    confidences: list[float],
    offsets: list[tuple[int, int]],
    id2label: dict[int, str],
) -> list[tuple[int, int, str, float]]:
    spans: list[tuple[int, int, str, float]] = []
    active_type: str | None = None
    active_start = active_end = 0
    active_scores: list[float] = []

    def flush() -> None:
        if active_type is not None and active_end > active_start:
            spans.append((active_start, active_end, active_type, sum(active_scores) / len(active_scores)))

    for label_id, confidence, (start, end) in zip(label_ids, confidences, offsets):
        label = id2label.get(label_id, "O")
        if start == end or label == "O":
            flush()
            active_type = None
            active_scores = []
            continue
        prefix, _, event_type = label.partition("-")
        if prefix not in {"B", "I"} or not event_type:
            flush()
            active_type = None
            active_scores = []
            continue
        if prefix == "B" or active_type != event_type:
            flush()
            active_type = event_type
            active_start, active_end = start, end
            active_scores = [confidence]
        else:
            active_end = end
            active_scores.append(confidence)
    flush()
    return spans
