"""Fine-tune a PhoBERT BIO trigger detector on the official BKEE train/dev split."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import math
import random
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

MODEL_ID = "vinai/phobert-base-v2"
MODEL_REVISION = "86cd7fd4c148980922ac11a2cf5e257f2ba639e1"
DATASET_DIR = ROOT / "data/external/BKEE_official_20261019/processed"
RUN_DIR = ROOT / "runs/phobert_bkee_event_detection_v2"
BEST_DIR = ROOT / "models/phobert_bkee_event_detection_v2"
VNCORP_ASSETS = ROOT / "runs/phobert_mvp_news_100_v1/vncorenlp"
MAX_LENGTH = 192
SEED = 42
DATASET_COMMIT = "e8b3c66958e2b2d693f4c1f65993c7d0178fe67a"
DEVICE_BATCH = 1
GRAD_ACCUMULATION = 8
LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01


class IndexedJsonl:
    """Keep only byte offsets in memory; decode one source row when requested."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offsets: list[int] = []
        with path.open("rb") as source:
            while True:
                offset = source.tell()
                line = source.readline()
                if not line:
                    break
                if line.strip():
                    self.offsets.append(offset)

    def __len__(self) -> int:
        return len(self.offsets)

    def get(self, index: int, source: Any) -> dict[str, Any]:
        source.seek(self.offsets[index])
        return json.loads(source.readline())

    def __iter__(self):
        with self.path.open("rb") as source:
            for index in range(len(self)):
                yield self.get(index, source)


def prepare_example(row: dict[str, Any], tokenizer: Any, label2id: dict[str, int]) -> dict[str, Any]:
    tokens = row["tokens"]
    tokenized_words = [
        tokenizer.tokenize(unicodedata.normalize("NFC", str(token)).replace(" ", "_"))
        for token in tokens
    ]
    token_lens = [len(word_pieces) for word_pieces in tokenized_words]
    if any(length <= 0 for length in token_lens):
        raise ValueError(f"{row.get('sent_id')}: PhoBERT produced an empty tokenization for a BKEE token.")
    pieces = [piece for word_pieces in tokenized_words for piece in word_pieces]
    piece_ids = tokenizer.convert_tokens_to_ids(pieces)
    unknown_piece_count = sum(token_id == tokenizer.unk_token_id for token_id in piece_ids)

    piece_labels = [label2id["O"]] * len(pieces)
    token_offsets = [0]
    for count in token_lens:
        token_offsets.append(token_offsets[-1] + count)
    for event in row.get("event_mentions", []):
        trigger = event["trigger"]
        start_token, end_token = int(trigger["start"]), int(trigger["end"])
        if not 0 <= start_token < end_token <= len(tokens):
            raise ValueError(f"{row.get('sent_id')}: invalid BKEE trigger token span {trigger}")
        event_type = str(event["event_type"])
        first_piece = token_offsets[start_token]
        end_piece = token_offsets[end_token]
        label_ids = [label2id[f"B-{event_type}"]] + [label2id[f"I-{event_type}"]] * (end_piece - first_piece - 1)
        for piece_index, label_id in zip(range(first_piece, end_piece), label_ids):
            if piece_labels[piece_index] != label2id["O"]:
                raise ValueError(f"{row.get('sent_id')}: overlapping trigger spans cannot be represented in BIO.")
            piece_labels[piece_index] = label_id

    input_ids = [tokenizer.cls_token_id] + piece_ids + [tokenizer.sep_token_id]
    labels = [-100] + piece_labels + [-100]
    if len(input_ids) > MAX_LENGTH:
        raise ValueError(f"{row.get('sent_id')}: {len(input_ids)} tokens exceeds MAX_LENGTH={MAX_LENGTH}")
    return {"input_ids": input_ids, "labels": labels, "sent_id": row.get("sent_id", ""),
            "piece_count": len(pieces), "unknown_piece_count": unknown_piece_count}


def batch_examples(examples: list[dict[str, Any]], pad_id: int, device: Any, torch: Any) -> dict[str, Any]:
    width = max(len(row["input_ids"]) for row in examples)
    ids, masks, labels = [], [], []
    for row in examples:
        pad = width - len(row["input_ids"])
        ids.append(row["input_ids"] + [pad_id] * pad)
        masks.append([1] * len(row["input_ids"]) + [0] * pad)
        labels.append(row["labels"] + [-100] * pad)
    return {
        "input_ids": torch.tensor(ids, dtype=torch.long, device=device),
        "attention_mask": torch.tensor(masks, dtype=torch.long, device=device),
        "labels": torch.tensor(labels, dtype=torch.long, device=device),
    }


def make_class_weights(counts: list[int], torch: Any, device: Any) -> Any:
    """Down-weight the dominant O class and mildly balance rare BIO labels."""
    outside_count = max(1, counts[0])
    positive_total = max(1, sum(counts[1:]))
    positive_base = min(32.0, max(8.0, math.sqrt(outside_count / positive_total)))
    largest_positive_class = max(counts[1:], default=1)
    weights = [1.0]
    for count in counts[1:]:
        rarity_adjustment = min(2.0, math.sqrt(largest_positive_class / max(1, count)))
        weights.append(positive_base * rarity_adjustment)
    return torch.tensor(weights, dtype=torch.float32, device=device), {
        "outsideTokenCount": outside_count,
        "positiveTokenCount": positive_total,
        "positiveBaseWeight": positive_base,
        "labelWeights": weights,
    }


def token_classification_loss(logits: Any, labels: Any, class_weights: Any, torch: Any) -> Any:
    return torch.nn.functional.cross_entropy(
        logits.reshape(-1, logits.shape[-1]), labels.reshape(-1),
        weight=class_weights, ignore_index=-100,
    )


def spans_from_labels(ids: list[int], id2label: dict[int, str]) -> set[tuple[int, int, str]]:
    spans: set[tuple[int, int, str]] = set()
    active_type: str | None = None
    active_start = 0
    for index, label_id in enumerate(ids):
        label = id2label.get(label_id, "O")
        if label == "O":
            if active_type is not None:
                spans.add((active_start, index, active_type))
            active_type = None
            continue
        prefix, _, event_type = label.partition("-")
        if prefix == "B" or active_type != event_type:
            if active_type is not None:
                spans.add((active_start, index, active_type))
            active_type, active_start = event_type, index
    if active_type is not None:
        spans.add((active_start, len(ids), active_type))
    return spans


def scan_dataset(dataset: IndexedJsonl, tokenizer: Any, label2id: dict[str, int],
                 train_limit: int = 0) -> tuple[list[int], int, int]:
    """Compute class counts and unknown-token diagnostics without caching rows."""
    counts = [0] * len(label2id)
    unknown_count = 0
    limit = min(len(dataset), train_limit) if train_limit else len(dataset)
    with dataset.path.open("rb") as source:
        for index in range(limit):
            row = dataset.get(index, source)
            example = prepare_example(row, tokenizer, label2id)
            unknown_count += example["unknown_piece_count"]
            for label_id in example["labels"]:
                if label_id >= 0:
                    counts[label_id] += 1
    return counts, unknown_count, limit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate(model: Any, dataset: IndexedJsonl, tokenizer: Any, label2id: dict[str, int],
             id2label: dict[int, str], device: Any, torch: Any,
             class_weights: Any) -> dict[str, float]:
    model.eval()
    correct = predicted = gold = 0
    losses = []
    with torch.inference_mode(), dataset.path.open("rb") as source:
        for index in range(len(dataset)):
            row = dataset.get(index, source)
            example = prepare_example(row, tokenizer, label2id)
            batch = batch_examples([example], tokenizer.pad_token_id, device, torch)
            outputs = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"])
            losses.append(float(token_classification_loss(outputs.logits, batch["labels"], class_weights, torch).item()))
            piece_count = example["piece_count"]
            pred_ids = outputs.logits[0, 1:piece_count + 1].argmax(-1).tolist()
            gold_ids = example["labels"][1:-1]
            pred_spans = spans_from_labels(pred_ids, id2label)
            gold_spans = spans_from_labels(gold_ids, id2label)
            correct += len(pred_spans & gold_spans)
            predicted += len(pred_spans)
            gold += len(gold_spans)
    precision = correct / predicted if predicted else 0.0
    recall = correct / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"loss": sum(losses) / max(1, len(losses)), "event_precision": precision,
            "event_recall": recall, "event_f1": f1, "true_events": gold, "predicted_events": predicted}


def train_epoch(model: Any, dataset: IndexedJsonl | list[dict[str, Any]], tokenizer: Any, label2id: dict[str, int],
                optimizer: Any, scaler: Any, device: Any, torch: Any, class_weights: Any, *,
                row_count: int, batch_size: int, accumulation: int, seed: int) -> float:
    model.train()
    order = list(range(row_count))
    random.Random(seed).shuffle(order)
    optimizer.zero_grad(set_to_none=True)
    losses = []
    batch_count = math.ceil(len(order) / batch_size)
    source_context = dataset.path.open("rb") if isinstance(dataset, IndexedJsonl) else nullcontext(None)
    with source_context as source:
        for batch_index, start in enumerate(range(0, len(order), batch_size)):
            indexes = order[start:start + batch_size]
            examples = [
                prepare_example(dataset.get(index, source), tokenizer, label2id)
                if isinstance(dataset, IndexedJsonl) else dataset[index]
                for index in indexes
            ]
            batch = batch_examples(examples, tokenizer.pad_token_id, device, torch)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device.type == "cuda"):
                outputs = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"])
                loss = token_classification_loss(outputs.logits, batch["labels"], class_weights, torch) / accumulation
            scaler.scale(loss).backward()
            losses.append(float(loss.detach().item()) * accumulation)
            if (batch_index + 1) % accumulation == 0 or batch_index + 1 == batch_count:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            if device.type == "cuda" and batch_index % 500 == 0:
                torch.cuda.empty_cache()
            if batch_index % 250 == 0 or batch_index + 1 == batch_count:
                print(f"train batch {batch_index + 1}/{batch_count}", flush=True)
            del examples, batch, outputs, loss
    return sum(losses) / max(1, len(losses))


def save_checkpoint(model: Any, tokenizer: Any, directory: Path, label_data: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(directory, safe_serialization=True)
    tokenizer.save_pretrained(directory)
    (directory / "label_mapping.json").write_text(
        json.dumps(label_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if VNCORP_ASSETS.is_dir():
        shutil.copytree(VNCORP_ASSETS, directory / "vncorenlp_assets", dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--checkpoint-dir", type=Path, default=BEST_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--smoke-examples", type=int, default=24)
    parser.add_argument("--smoke-epochs", type=int, default=3)
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--smoke-only", action="store_true", help="Validate the weighted training/checkpoint path, then exit.")
    parser.add_argument("--train-limit", type=int, default=0, help="Development only; 0 means full train split.")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    checkpoint_dir = args.checkpoint_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty run directory: {run_dir}")
    if checkpoint_dir.exists() and any(checkpoint_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty checkpoint directory: {checkpoint_dir}")
    if not args.dataset_dir.is_dir():
        raise SystemExit(f"BKEE dataset not found: {args.dataset_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise SystemExit("A CUDA GPU is required for this requested run; refusing silent CPU training.")
    print(f"GPU={torch.cuda.get_device_name(0)} VRAM={torch.cuda.get_device_properties(0).total_memory / 2**30:.2f} GiB")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=False, revision=MODEL_REVISION)
    splits = {name: IndexedJsonl(args.dataset_dir / f"{name}.json") for name in ("train", "dev")}
    event_types = sorted({str(event["event_type"]) for row in splits["train"] for event in row.get("event_mentions", [])})
    dev_types = {str(event["event_type"]) for row in splits["dev"] for event in row.get("event_mentions", [])}
    if set(event_types) != dev_types:
        raise RuntimeError("Train/dev event type inventories differ; label mapping would be incomplete.")
    labels = ["O"] + [label for event_type in event_types for label in (f"B-{event_type}", f"I-{event_type}")]
    label2id = {label: index for index, label in enumerate(labels)}
    id2label = {index: label for label, index in label2id.items()}
    train_counts, train_unknown_count, train_row_count = scan_dataset(
        splits["train"], tokenizer, label2id, args.train_limit
    )
    _, dev_unknown_count, _ = scan_dataset(splits["dev"], tokenizer, label2id)
    label_data = {
        "task": "BKEE_EVENT_DETECTION_BIO_TOKEN_CLASSIFICATION",
        "modelId": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "eventTypes": event_types,
        "label2id": label2id,
        "id2label": {str(key): value for key, value in id2label.items()},
        "max_length": MAX_LENGTH,
        "inference_stride": 48,
        "trainingSplit": "train",
        "selectionSplit": "dev",
        "testSplitUsed": False,
        "triggerIndexConvention": "BKEE token start inclusive, end exclusive; each source token is tokenized with pinned PhoBERT BPE after internal spaces become underscores",
        "bkeeProvidedPiecesUsed": False,
        "bkeePieceNote": "BKEE pieces use a different subword vocabulary (for example ▁Ngày is absent from PhoBERT); trigger spans are remapped from source tokens through the pinned PhoBERT tokenizer.",
        "vncorenlp_assets": "vncorenlp_assets",
    }
    (run_dir / "label_mapping.json").write_text(json.dumps(label_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report: dict[str, Any] = {
        "runStartedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset_dir.resolve()),
        "datasetRepository": "https://github.com/nhungnt7/BKEE",
        "datasetCommit": DATASET_COMMIT,
        "datasetLicense": "CC BY-NC 4.0",
        "datasetSplitSha256": {
            split: sha256_file(args.dataset_dir / f"{split}.json")
            for split in ("train", "dev")
        },
        "modelId": MODEL_ID,
        "device": str(device),
        "gpuName": torch.cuda.get_device_name(0),
        "gpuVramBytes": torch.cuda.get_device_properties(0).total_memory,
        "python": sys.version,
        "torch": torch.__version__,
        "cudaRuntime": torch.version.cuda,
        "splitCounts": {name: len(rows) for name, rows in splits.items()},
        "trainRowsUsed": train_row_count,
        "phoBERTUnknownSubwordCounts": {
            "train": train_unknown_count,
            "dev": dev_unknown_count,
        },
        "eventTypeCount": len(event_types),
        "eventTypes": event_types,
        "labelCount": len(labels),
        "maxSequenceLength": MAX_LENGTH,
        "testSetUsed": False,
        "lossFunction": "weighted token cross-entropy; O weight 1, positive BIO weights derived from O/positive prevalence and label frequency",
        "smokeTest": None,
        "epochs": [],
    }

    if not args.skip_smoke:
        smoke_data = []
        with splits["train"].path.open("rb") as source:
            for index in range(train_row_count):
                row = splits["train"].get(index, source)
                if row.get("event_mentions"):
                    smoke_data.append(prepare_example(row, tokenizer, label2id))
                    if len(smoke_data) >= args.smoke_examples:
                        break
        smoke_counts = [0] * len(labels)
        for example in smoke_data:
            for label_id in example["labels"]:
                if label_id >= 0:
                    smoke_counts[label_id] += 1
        smoke_weights, smoke_weight_stats = make_class_weights(smoke_counts, torch, device)
        smoke_model = AutoModelForTokenClassification.from_pretrained(
            MODEL_ID, num_labels=len(labels), id2label=id2label, label2id=label2id,
            ignore_mismatched_sizes=True, revision=MODEL_REVISION,
        )
        smoke_model.gradient_checkpointing_enable()
        smoke_model.config.use_cache = False
        smoke_model.to(device)
        smoke_optimizer = torch.optim.AdamW(smoke_model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
        scaler = torch.amp.GradScaler("cuda", enabled=True)
        smoke_losses = []
        for epoch in range(args.smoke_epochs):
            smoke_losses.append(train_epoch(
                smoke_model, smoke_data, tokenizer, label2id, smoke_optimizer, scaler, device, torch,
                smoke_weights, row_count=len(smoke_data), batch_size=DEVICE_BATCH,
                accumulation=4, seed=SEED + epoch,
            ))
        smoke_dir = run_dir / "smoke_checkpoint"
        save_checkpoint(smoke_model, tokenizer, smoke_dir, label_data)
        del smoke_model, smoke_optimizer
        torch.cuda.empty_cache()
        reloaded = AutoModelForTokenClassification.from_pretrained(smoke_dir).to(device)
        check_batch = batch_examples(smoke_data[:1], tokenizer.pad_token_id, device, torch)
        with torch.inference_mode():
            reload_logits = reloaded(**{k: v for k, v in check_batch.items() if k != "labels"}).logits
        if not torch.isfinite(reload_logits).all():
            raise RuntimeError("Saved smoke checkpoint did not reload to finite inference outputs.")
        del reloaded
        shutil.rmtree(smoke_dir)
        torch.cuda.empty_cache()
        if smoke_losses[-1] >= smoke_losses[0]:
            raise RuntimeError(f"Smoke-test loss did not decrease: {smoke_losses}")
        report["smokeTest"] = {"examples": len(smoke_data), "epochLosses": smoke_losses,
                                "lossDecreased": True, "checkpointReloaded": True,
                                "lossWeights": {"positiveBaseWeight": smoke_weight_stats["positiveBaseWeight"]}}
        if args.smoke_only:
            report["runFinishedAt"] = datetime.now(timezone.utc).isoformat()
            report["smokeOnly"] = True
            (run_dir / "training_report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"Weighted smoke report: {run_dir / 'training_report.json'}")
            return 0
        print(f"Smoke test loss: {smoke_losses[0]:.4f} -> {smoke_losses[-1]:.4f}; checkpoint reload OK")

    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_ID, num_labels=len(labels), id2label=id2label, label2id=label2id,
        ignore_mismatched_sizes=True, revision=MODEL_REVISION,
    )
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    class_weights, weight_stats = make_class_weights(train_counts, torch, device)
    report["classWeightStats"] = {
        "outsideTokenCount": weight_stats["outsideTokenCount"],
        "positiveTokenCount": weight_stats["positiveTokenCount"],
        "positiveBaseWeight": weight_stats["positiveBaseWeight"],
        "labelWeights": {label: round(weight, 5) for label, weight in zip(labels, weight_stats["labelWeights"])},
    }
    best_f1 = -1.0
    for epoch in range(args.epochs):
        train_loss = train_epoch(
            model, splits["train"], tokenizer, label2id, optimizer, scaler, device, torch,
            class_weights, row_count=train_row_count, batch_size=DEVICE_BATCH,
            accumulation=GRAD_ACCUMULATION, seed=SEED + 100 + epoch,
        )
        dev_metrics = evaluate(model, splits["dev"], tokenizer, label2id, id2label,
                               device, torch, class_weights)
        result = {"epoch": epoch + 1, "trainLoss": train_loss, **dev_metrics}
        report["epochs"].append(result)
        print(json.dumps(result, ensure_ascii=False))
        if dev_metrics["event_f1"] > best_f1:
            best_f1 = dev_metrics["event_f1"]
            save_checkpoint(model, tokenizer, checkpoint_dir, label_data)
            report["bestCheckpointEpoch"] = epoch + 1
            report["bestDevEventF1"] = best_f1
        (run_dir / "training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["runFinishedAt"] = datetime.now(timezone.utc).isoformat()
    report["checkpointPath"] = str(checkpoint_dir)
    report["selectionMetric"] = "exact trigger span and event type micro-F1 on dev"
    report["eventMetricConvention"] = "exact piece-index span + event type; no argument extraction"
    (run_dir / "training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Best checkpoint: {checkpoint_dir}")
    print(f"Training report: {run_dir / 'training_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
