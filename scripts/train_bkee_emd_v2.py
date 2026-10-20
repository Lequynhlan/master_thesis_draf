"""Controlled EMD v2 continuation run: train only on BKEE train, select on dev."""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from train_bkee_event_detection import IndexedJsonl, batch_examples, token_classification_loss, save_checkpoint
from train_bkee_auxiliary import encode, labels_for
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector

DATA = ROOT / "data/external/BKEE_official_20261019/processed"
V1 = ROOT / "models/phobert_bkee_emd_v1"
V2 = ROOT / "models/phobert_bkee_emd_v2"
RUN = ROOT / "runs/phobert_bkee_emd_v2"
EPOCHS = 3
SEED = 42
MAX_LENGTH = 192
ACCUMULATION = 8
LEARNING_RATE = 5e-6
ENTITY_WEIGHT = 4.0


def exact_metrics(gold: set, predicted: set) -> dict:
    tp = len(gold & predicted); fp = len(predicted - gold); fn = len(gold - predicted)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2*p*r/(p+r) if p+r else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "predicted": len(predicted)}


def evaluate_inference(model, tokenizer, label_data, segmenter, rows, device, torch):
    """Run the production detector decoding/offset logic against gold dev spans."""
    detector = PhoBERTEventDetector.__new__(PhoBERTEventDetector)
    detector.checkpoint_path = V1
    detector.label_data = label_data
    detector.id2label = {int(k): str(v) for k, v in label_data["id2label"].items()}
    detector.device = device; detector.tokenizer = tokenizer; detector.model = model
    detector.inference_config = {}
    detector.torch = torch; detector.max_length = MAX_LENGTH
    detector.stride = int(label_data.get("inference_stride", 48)); detector._segmenter = segmenter
    detector.model.eval()
    gold, predicted = set(), set()
    predicted_with_confidence = []
    for index, row in enumerate(rows):
        sid, text = str(row.get("sent_id", index)), str(row["sentence"])
        for ent in row.get("entity_mentions", []):
            gold.add((sid, int(ent["start_char"]), int(ent["end_char"]), str(ent["entity_type"])))
        for item in detector.predict(text):
            sp = item["triggerSpan"]
            key = (sid, int(sp["startChar"]), int(sp["endChar"]), str(item["eventType"]))
            predicted.add(key); predicted_with_confidence.append((key, float(item["confidence"])))
        if index and index % 1000 == 0:
            print(f"dev inference {index}/{len(rows)}", flush=True)
    baseline = exact_metrics(gold, predicted)
    thresholded = {key for key, score in predicted_with_confidence if score >= 0.65}
    return baseline, exact_metrics(gold, thresholded)


def validate_train_alignment(train, tokenizer, label2id):
    stats = {"rows": len(train), "entities": 0, "overlappingEntityPairs": 0,
             "invalidTokenSpans": 0, "encodedRows": 0, "overlengthRows": 0,
             "bioLabelsChecked": 0, "specialTokenLabelsCorrect": True}
    for row in train:
        entities = row.get("entity_mentions", [])
        stats["entities"] += len(entities)
        spans = []
        for ent in entities:
            start, end = int(ent["start"]), int(ent["end"])
            if not 0 <= start < end <= len(row["tokens"]):
                stats["invalidTokenSpans"] += 1
            spans.append((start, end))
        ordered = sorted(spans)
        for (_, end1), (start2, _) in zip(ordered, ordered[1:]):
            if start2 < end1:
                stats["overlappingEntityPairs"] += 1
        ex = encode(row, tokenizer, label2id, "emd")
        if ex is None:
            stats["overlengthRows"] += 1
            continue
        stats["encodedRows"] += 1
        stats["specialTokenLabelsCorrect"] &= ex["labels"][0] == -100 and ex["labels"][-1] == -100
        tags = labels_for(row, "emd")
        cursor = 1
        for token, tag in zip(row["tokens"], tags):
            pieces = tokenizer.tokenize(str(token).replace(" ", "_"))
            expected = []
            if tag.startswith("B-"):
                suffix = tag[2:]
                expected = [label2id[tag]] + [label2id["I-" + suffix]] * (len(pieces) - 1)
            else:
                expected = [label2id[tag]] * len(pieces)
            observed = ex["labels"][cursor:cursor + len(pieces)]
            if observed != expected:
                raise RuntimeError(f"BPE/BIO alignment mismatch at {row.get('sent_id')} token {token!r}")
            cursor += len(pieces); stats["bioLabelsChecked"] += len(pieces)
        if cursor != len(ex["labels"]) - 1:
            raise RuntimeError(f"CLS/SEP or piece-count alignment mismatch at {row.get('sent_id')}")
    if stats["invalidTokenSpans"] or stats["overlappingEntityPairs"] or not stats["specialTokenLabelsCorrect"]:
        raise RuntimeError(f"BKEE train BIO audit failed: {stats}")
    return stats


def main():
    if not V1.is_dir():
        raise SystemExit(f"Missing EMD v1 checkpoint: {V1}")
    if V2.exists() and any(V2.iterdir()):
        raise SystemExit(f"Refusing to overwrite EMD v2 checkpoint: {V2}")
    if RUN.exists() and any(p.name != "alignment_audit.json" for p in RUN.iterdir()):
        raise SystemExit(f"Refusing to overwrite EMD v2 run: {RUN}")
    if not (DATA / "train.json").is_file() or not (DATA / "dev.json").is_file():
        raise SystemExit("Official BKEE train/dev files are required")

    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; refusing CPU training")
    device = torch.device("cuda")
    print(f"GPU={torch.cuda.get_device_name(0)} VRAM={torch.cuda.get_device_properties(0).total_memory/2**30:.2f} GiB", flush=True)
    if torch.cuda.get_device_properties(0).total_memory > 4.2 * 2**30:
        print("Note: detected VRAM differs from expected 4GB T1200; continuing with memory-safe settings.", flush=True)

    RUN.mkdir(parents=True, exist_ok=True)
    train, dev = IndexedJsonl(DATA / "train.json"), IndexedJsonl(DATA / "dev.json")
    label_data = json.loads((V1 / "label_mapping.json").read_text(encoding="utf-8"))
    label2id = {str(k): int(v) for k, v in label_data["label2id"].items()}
    tokenizer = AutoTokenizer.from_pretrained(V1, use_fast=False)
    alignment = validate_train_alignment(train, tokenizer, label2id)
    (RUN / "alignment_audit.json").write_text(json.dumps(alignment, indent=2) + "\n", encoding="utf-8")

    # Segmenter is reused for train-time dev evaluation; the model weights stay
    # in one process and one GPU allocation (no second model copy).
    import py_vncorenlp
    assets = V1 / label_data["vncorenlp_assets"]
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(V1)
        segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(assets.resolve()))
    finally:
        os.chdir(old_cwd)

    random.seed(SEED); torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    model = AutoModelForTokenClassification.from_pretrained(V1).to(device)
    model.gradient_checkpointing_enable(); model.config.use_cache = False
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    class_weights = torch.tensor([1.0] + [ENTITY_WEIGHT] * (model.config.num_labels - 1), dtype=torch.float32, device=device)
    torch.cuda.reset_peak_memory_stats(device)

    baseline, baseline_thr = evaluate_inference(model, tokenizer, label_data, segmenter, dev, device, torch)
    (RUN / "baseline_comparison.json").write_text(json.dumps({
        "emdV1NoFilter": baseline, "emdV1Threshold065": baseline_thr,
        "source": "same in-memory PhoBERTEventDetector decoding on BKEE dev"
    }, indent=2) + "\n", encoding="utf-8")
    print(f"baseline v1: {baseline}; v1@0.65: {baseline_thr}", flush=True)

    epoch_rows = []; best_f1 = -1.0; best_epoch = None; losses = []
    for epoch in range(1, EPOCHS + 1):
        start_time = time.time(); model.train(); optimizer.zero_grad(set_to_none=True)
        batch_losses = []; steps = math.ceil(len(train) / ACCUMULATION)
        with train.path.open("rb") as source:
            for i in range(len(train)):
                row = train.get(i, source)
                ex = encode(row, tokenizer, label2id, "emd")
                if ex is None:
                    raise RuntimeError(f"Training row exceeds max length: {row.get('sent_id')}")
                batch = batch_examples([ex], tokenizer.pad_token_id, device, torch)
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    output = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"])
                    loss = token_classification_loss(output.logits, batch["labels"], class_weights, torch) / ACCUMULATION
                scaler.scale(loss).backward(); batch_losses.append(float(loss.detach().item()) * ACCUMULATION)
                if (i + 1) % ACCUMULATION == 0 or (i + 1) == len(train):
                    scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
                if i % 500 == 0:
                    print(f"epoch={epoch}/{EPOCHS} row={i}/{len(train)} loss={batch_losses[-1]:.4f}", flush=True)
                del batch, output, loss
        epoch_loss = sum(batch_losses) / max(1, len(batch_losses)); losses.append(epoch_loss)
        v1_metrics, v1_threshold_metrics = evaluate_inference(model, tokenizer, label_data, segmenter, dev, device, torch)
        record = {"epoch": epoch, "trainLoss": epoch_loss, "dev": v1_metrics,
                  "devAtV1Threshold065": v1_threshold_metrics,
                  "seconds": round(time.time() - start_time, 2)}
        epoch_rows.append(record)
        print(f"epoch={epoch} trainLoss={epoch_loss:.5f} dev={v1_metrics}", flush=True)
        if v1_metrics["f1"] > best_f1:
            best_f1 = v1_metrics["f1"]; best_epoch = epoch
            metadata = dict(label_data)
            metadata.update({"task": "BKEE_EMD_BIO_TOKEN_CLASSIFICATION_V2",
                "modelId": "vinai/phobert-base-v2", "initializedFrom": "models/phobert_bkee_emd_v1",
                "trainingSplit": "train", "selectionSplit": "dev", "testSplitUsed": False,
                "max_length": MAX_LENGTH, "inference_stride": 48,
                "trainingConfig": {"epochsPlanned": EPOCHS, "selectedEpoch": epoch, "batchSize": 1,
                    "gradientAccumulation": ACCUMULATION, "learningRate": LEARNING_RATE,
                    "weightDecay": 0.01, "fp16": True, "gradientCheckpointing": True,
                    "classWeights": {"O": 1.0, "allEntityBIO": ENTITY_WEIGHT}, "seed": SEED},
                "trainLosses": losses, "bestDevMetrics": v1_metrics})
            save_checkpoint(model, tokenizer, V2, metadata)
            print(f"saved new best v2 checkpoint at epoch {epoch}: F1={best_f1:.6f}", flush=True)
        # Keep the evolving experiment manifest current even if interrupted.
        manifest = {"task": "BKEE EMD v2 controlled continuation", "device": torch.cuda.get_device_name(0),
            "vramGiB": torch.cuda.get_device_properties(0).total_memory / 2**30,
            "trainRows": len(train), "devRows": len(dev), "alignmentAudit": alignment,
            "baseline": {"v1NoFilter": baseline, "v1Threshold065": baseline_thr},
            "epochMetrics": epoch_rows, "bestEpoch": best_epoch, "bestDevF1": best_f1,
            "testSplitUsed": False, "cohortUsedForTraining": False}
        (RUN / "training_report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        model.train()

    model.eval()
    manifest = json.loads((RUN / "training_report.json").read_text(encoding="utf-8"))
    manifest["peakAllocatedGpuBytes"] = int(torch.cuda.max_memory_allocated(device))
    manifest["selectedCheckpoint"] = str(V2.relative_to(ROOT))
    (RUN / "training_report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"bestEpoch": best_epoch, "bestDevF1": best_f1,
                      "checkpoint": str(V2), "run": str(RUN)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
