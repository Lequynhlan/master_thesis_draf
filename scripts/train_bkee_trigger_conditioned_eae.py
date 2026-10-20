"""Train trigger-conditioned PhoBERT EAE on BKEE event/entity pairs.

Positive pairs come only from an event's annotated arguments. Negative pairs are
annotated entities in the same sentence that are not arguments of that event.
Unannotated text spans are never treated as NONE.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from train_bkee_event_detection import (  # noqa: E402
    DATASET_DIR, MODEL_ID, MODEL_REVISION, VNCORP_ASSETS,
)

DEFAULT_RUN = ROOT / "runs/phobert_bkee_eae_trigger_conditioned_v1"
DEFAULT_MODEL = ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1"
MAX_LENGTH = 192
NONE = "NONE"


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def insert_markers(sentence: str, trigger: dict, entity: dict, event_type: str) -> str | None:
    ts, te = int(trigger["start_char"]), int(trigger["end_char"])
    es, ee = int(entity["start_char"]), int(entity["end_char"])
    if not (0 <= ts < te <= len(sentence) and 0 <= es < ee <= len(sentence)):
        return None
    if sentence[ts:te] != str(trigger["text"]) or sentence[es:ee] != str(entity["text"]):
        return None
    if max(ts, es) < min(te, ee):
        return None
    tagged = [
        (ts, " <TRIGGER> "), (te, " </TRIGGER> "),
        (es, " <ENTITY> "), (ee, " </ENTITY> "),
    ]
    # At an identical boundary, closing marker precedes opening marker.
    for pos, marker in sorted(tagged, key=lambda x: (x[0], 0 if x[1].startswith(" </") else 1), reverse=True):
        sentence = sentence[:pos] + marker + sentence[pos:]
    return f"EventType: {event_type} EntityType: {entity.get('entity_type', 'UNK')} Sentence: {sentence}"


def make_pairs(rows: list[dict], tokenizer, label2id: dict[str, int], split: str) -> tuple[list[dict], Counter]:
    examples, stats = [], Counter()
    for row in rows:
        sentence = str(row["sentence"])
        entities = {str(entity["id"]): entity for entity in row.get("entity_mentions", [])}
        for event in row.get("event_mentions", []):
            trigger = event["trigger"]
            roles_by_entity: dict[str, set[str]] = defaultdict(set)
            for arg in event.get("arguments", []):
                eid = str(arg.get("entity_id", ""))
                if eid in entities:
                    roles_by_entity[eid].add(str(arg["role"]))
                else:
                    stats["argument_missing_entity_reference"] += 1
            for entity_id, entity in entities.items():
                roles = roles_by_entity.get(entity_id, set())
                if len(roles) > 1:
                    stats["multi_role_pair_skipped"] += 1
                    continue
                marked = insert_markers(sentence, trigger, entity, str(event["event_type"]))
                if marked is None:
                    stats["span_mismatch_or_overlap_skipped"] += 1
                    continue
                encoded = tokenizer(marked, truncation=False, add_special_tokens=True)
                if len(encoded["input_ids"]) > MAX_LENGTH:
                    stats["over_max_length_skipped"] += 1
                    continue
                label = next(iter(roles)) if roles else NONE
                examples.append({"input_ids": encoded["input_ids"], "attention_mask": encoded["attention_mask"],
                                 "label": label2id[label], "label_name": label,
                                 "pair_id": (str(event["id"]), entity_id), "split": split})
                stats["positive_pairs" if label != NONE else "negative_pairs"] += 1
    return examples, stats


def metric(gold: list[int], pred: list[int], none_id: int) -> dict:
    tp = sum(g == p and g != none_id for g, p in zip(gold, pred))
    fp = sum(p != none_id and p != g for g, p in zip(gold, pred))
    fn = sum(g != none_id and p != g for g, p in zip(gold, pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    none_tp = sum(g == none_id and p == none_id for g, p in zip(gold, pred))
    none_fp = sum(g != none_id and p == none_id for g, p in zip(gold, pred))
    none_fn = sum(g == none_id and p != none_id for g, p in zip(gold, pred))
    none_precision = none_tp / (none_tp + none_fp) if none_tp + none_fp else 0.0
    none_recall = none_tp / (none_tp + none_fn) if none_tp + none_fn else 0.0
    return {"precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "correctRolePairs": tp, "falsePositiveRolePairs": fp, "missedOrWrongRolePairs": fn,
            "nonePrecision": none_precision, "noneRecall": none_recall,
            "noneF1": 2 * none_precision * none_recall / (none_precision + none_recall) if none_precision + none_recall else 0.0,
            "noneTruePositive": none_tp, "noneFalsePositive": none_fp, "noneFalseNegative": none_fn,
            "pairAccuracy": sum(g == p for g, p in zip(gold, pred)) / max(len(gold), 1)}


def collate(items, pad_id: int, device, torch):
    width = max(len(x["input_ids"]) for x in items)
    ids = [x["input_ids"] + [pad_id] * (width - len(x["input_ids"])) for x in items]
    masks = [x["attention_mask"] + [0] * (width - len(x["attention_mask"])) for x in items]
    return (torch.tensor(ids, device=device), torch.tensor(masks, device=device),
            torch.tensor([x["label"] for x in items], dtype=torch.long, device=device))


def predict(model, examples, tokenizer, torch, device, batch_size=2):
    model.eval(); result = []
    with torch.inference_mode():
        for start in range(0, len(examples), batch_size):
            batch = examples[start:start + batch_size]
            ids, mask, _ = collate(batch, tokenizer.pad_token_id, device, torch)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(input_ids=ids, attention_mask=mask).logits
            result.extend(logits.float().argmax(-1).cpu().tolist())
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--trainable-layers", type=int, default=4,
                        help="Fine-tune only the final N PhoBERT encoder layers plus classifier to fit small GPUs")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="Optional train sentence cap for a smoke run")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()
    if args.run_dir.exists() and any(args.run_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty run directory: {args.run_dir}")
    if args.checkpoint_dir.exists() and any(args.checkpoint_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty checkpoint directory: {args.checkpoint_dir}")

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this run")
    random.seed(42); torch.manual_seed(42); torch.cuda.manual_seed_all(42)
    device = torch.device("cuda")
    data_dir = Path(DATASET_DIR)
    train_rows, dev_rows = read_rows(data_dir / "train.json"), read_rows(data_dir / "dev.json")
    if args.limit:
        train_rows = train_rows[:args.limit]
    label_names = [NONE] + sorted({str(a["role"]) for row in train_rows for event in row.get("event_mentions", []) for a in event.get("arguments", [])})
    label2id = {label: i for i, label in enumerate(label_names)}
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=False, revision=MODEL_REVISION)
    train, train_stats = make_pairs(train_rows, tokenizer, label2id, "train")
    dev, dev_stats = make_pairs(dev_rows, tokenizer, label2id, "dev")
    if not train or not dev:
        raise RuntimeError("No valid train/dev event-entity pairs")
    counts = Counter(x["label"] for x in train)
    # Mild inverse-sqrt weighting keeps NONE from dominating without amplifying rare roles excessively.
    weights = torch.tensor([min(4.0, (max(counts.values()) / max(1, counts[i])) ** 0.25) for i in range(len(label_names))],
                           dtype=torch.float32, device=device)
    id2label = {i: name for name, i in label2id.items()}
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, num_labels=len(label_names),
        label2id=label2id, id2label=id2label,
    ).to(device)
    model.config.use_cache = False
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    encoder_layers = model.roberta.encoder.layer
    if not 1 <= args.trainable_layers <= len(encoder_layers):
        raise ValueError(f"trainable-layers must be between 1 and {len(encoder_layers)}")
    for layer in encoder_layers[-args.trainable_layers:]:
        for parameter in layer.parameters():
            parameter.requires_grad_(True)
    for parameter in model.classifier.parameters():
        parameter.requires_grad_(True)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-5, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda")
    batch_size, accumulation = args.batch_size, max(1, 8 // args.batch_size)
    args.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    best_f1, history, best_state = -1.0, [], None
    run_stats = {"trainPairs": len(train), "devPairs": len(dev), "trainPairCounts": dict(train_stats),
                 "devPairCounts": dict(dev_stats), "labels": label_names, "device": torch.cuda.get_device_name(0),
                 "cuda": torch.version.cuda, "torch": torch.__version__, "maxLength": MAX_LENGTH,
                 "batchSize": batch_size, "gradientAccumulation": accumulation,
                 "fineTuneStrategy": "final PhoBERT layers plus classification head",
                 "trainableEncoderLayers": args.trainable_layers, "encoderLayerCount": len(encoder_layers), "encoder": MODEL_ID,
                 "encoderRevision": MODEL_REVISION, "trainSplit": "BKEE train", "selectionSplit": "BKEE dev",
                 "testSplitUsed": False, "negativeSampling": "gold event x annotated entity in the same sentence; NONE only if no gold argument link"}
    for epoch in range(args.epochs):
        model.train(); random.Random(42 + epoch).shuffle(train); optimizer.zero_grad(set_to_none=True)
        loss_sum, steps = 0.0, 0
        for i in range(0, len(train), batch_size):
            chunk = train[i:i + batch_size]
            ids, mask, labels = collate(chunk, tokenizer.pad_token_id, device, torch)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(input_ids=ids, attention_mask=mask).logits
                loss = torch.nn.functional.cross_entropy(logits.float(), labels, weight=weights) / accumulation
            scaler.scale(loss).backward(); loss_sum += float(loss.item()) * accumulation; steps += 1
            if steps % accumulation == 0 or i + batch_size >= len(train):
                scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
            if steps % 1000 == 0:
                print(f"epoch={epoch+1} batch={steps}/{(len(train)+batch_size-1)//batch_size} pairs_seen={min(steps*batch_size,len(train))}/{len(train)} loss={loss_sum/steps:.4f} gpu_alloc={torch.cuda.max_memory_allocated()/1024**3:.2f}GiB", flush=True)
        dev_pred = predict(model, dev, tokenizer, torch, device)
        dev_gold = [x["label"] for x in dev]
        scores = metric(dev_gold, dev_pred, label2id[NONE])
        record = {"epoch": epoch + 1, "trainLoss": loss_sum / max(steps, 1), "devGoldSpanRoleMetrics": scores}
        history.append(record); print(json.dumps(record), flush=True)
        if scores["f1"] > best_f1:
            best_f1 = scores["f1"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            model.save_pretrained(args.checkpoint_dir, safe_serialization=True)
            tokenizer.save_pretrained(args.checkpoint_dir)
        interim = {**run_stats, "epochs": history,
                   "bestDevGoldSpan": max(history, key=lambda x: x["devGoldSpanRoleMetrics"]["f1"]),
                   "classCounts": {label_names[k]: v for k, v in sorted(counts.items())},
                   "peakGpuAllocatedGiB": torch.cuda.max_memory_allocated() / 1024**3,
                   "checkpoint": str(args.checkpoint_dir.relative_to(ROOT))}
        (args.run_dir / "training_report.json.tmp").write_text(json.dumps(interim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.run_dir / "training_report.json.tmp").replace(args.run_dir / "training_report.json")
    if best_state is None:
        raise RuntimeError("No checkpoint selected on dev")
    model.load_state_dict(best_state)
    model.save_pretrained(args.checkpoint_dir, safe_serialization=True)
    tokenizer.save_pretrained(args.checkpoint_dir)
    (args.checkpoint_dir / "vncorenlp_assets").mkdir(exist_ok=True)
    report = {**run_stats, "epochs": history, "bestDevGoldSpan": max(history, key=lambda x: x["devGoldSpanRoleMetrics"]["f1"]),
              "classCounts": {label_names[k]: v for k, v in sorted(counts.items())},
              "peakGpuAllocatedGiB": torch.cuda.max_memory_allocated() / 1024**3,
              "checkpoint": str(args.checkpoint_dir.relative_to(ROOT))}
    (args.checkpoint_dir / "training_metadata.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.run_dir / "training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {args.checkpoint_dir}; best dev role F1={best_f1:.4f}", flush=True)


if __name__ == "__main__":
    main()
