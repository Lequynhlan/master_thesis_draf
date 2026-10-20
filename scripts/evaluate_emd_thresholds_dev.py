"""Evaluate span-confidence filtering for the saved BKEE EMD checkpoint (dev only)."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector

DEV = ROOT / "data/external/BKEE_official_20261019/processed/dev.json"
CKPT = ROOT / "models/phobert_bkee_emd_v1"
OUT = ROOT / "runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1/emd_v2_readiness"
THRESHOLDS = [round(x / 100, 2) for x in range(0, 100, 5)] + [0.99]


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def prf(gold: set, pred: set):
    tp = len(gold & pred)
    fp, fn = len(pred - gold), len(gold - pred)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2*p*r/(p+r) if p+r else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def main():
    detector = PhoBERTEventDetector(CKPT, device="cuda")
    gold, predictions = set(), []
    spans_out, alignment = [], Counter()
    row_count = 0
    with DEV.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line); row_count += 1
            sid, text = str(row.get("sent_id", row_count)), str(row["sentence"])
            gold_mentions = row.get("entity_mentions", [])
            ordered = sorted(gold_mentions, key=lambda x: (int(x["start_char"]), int(x["end_char"])))
            for left, right in zip(ordered, ordered[1:]):
                if int(right["start_char"]) < int(left["end_char"]):
                    alignment["overlappingGoldPairsDev"] += 1
            training_tokens = [str(t).replace(" ", "_") for t in row["tokens"]]
            for ent in gold_mentions:
                s, e, typ = int(ent["start_char"]), int(ent["end_char"]), str(ent["entity_type"])
                gold.add((sid, s, e, typ))
                if text[s:e] == str(ent["text"]): alignment["goldCharOffsetsExact"] += 1
                else: alignment["goldCharOffsetsMismatch"] += 1
            detected = detector.predict(text)
            segmented = [token for line2 in detector._segmenter.word_segment(text) for token in line2.split() if token]
            norm = lambda x: x.casefold()
            if [norm(x) for x in training_tokens] == [norm(x) for x in segmented]:
                alignment["trainInferenceWordSegmentationExact"] += 1
            else:
                alignment["trainInferenceWordSegmentationMismatch"] += 1
                if alignment["segmentationMismatchExamples"] < 3:
                    alignment["segmentationMismatchExamples"] += 1
            for pred in detected:
                span = pred["triggerSpan"]
                s, e, typ = int(span["startChar"]), int(span["endChar"]), str(pred["eventType"])
                if text[s:e] == pred["trigger"]: alignment["predCharOffsetsExact"] += 1
                else: alignment["predCharOffsetsMismatch"] += 1
                item = {"sentId": sid, "start": s, "end": e, "entityType": typ,
                        "text": pred["trigger"], "confidence": float(pred["confidence"])}
                predictions.append(item)
                spans_out.append(item)
            if row_count % 500 == 0:
                print(f"threshold dev inference {row_count}/4301", flush=True)

    base = {(p["sentId"], p["start"], p["end"], p["entityType"]) for p in predictions}
    baseline = prf(gold, base)
    table = []
    for threshold in THRESHOLDS:
        pred = {(p["sentId"], p["start"], p["end"], p["entityType"])
                for p in predictions if p["confidence"] >= threshold}
        row = {"threshold": threshold, **prf(gold, pred), "predicted": len(pred)}
        table.append(row)
    best = max(table, key=lambda r: (r["f1"], r["precision"], -r["threshold"]))

    # Confidence histogram separates exactly correct predictions from errors.
    bins = Counter(); correct_conf = []; wrong_conf = []
    for p in predictions:
        key = (p["sentId"], p["start"], p["end"], p["entityType"])
        outcome = "EXACT_CORRECT" if key in gold else "NOT_EXACT"
        conf = p["confidence"]
        bins[(outcome, min(9, int(conf * 10)))] += 1
        (correct_conf if outcome == "EXACT_CORRECT" else wrong_conf).append(conf)

    (OUT / "emd_dev_threshold_metrics.json").write_text(json.dumps({
        "checkpoint": str(CKPT.relative_to(ROOT)), "split": "dev", "testUsed": False,
        "sentenceCount": row_count, "goldUniqueSpanTypeCount": len(gold),
        "predictionCount": len(base), "confidenceDefinition": "mean of argmax softmax probability for subwords emitted in one decoded entity span; uncalibrated",
        "baselineThreshold": None, "baseline": baseline, "bestDevThreshold": best["threshold"],
        "bestDev": {k: v for k, v in best.items() if k != "threshold"},
        "thresholdGrid": table,
        "confidenceDistribution": {"exactCorrect": {"count": len(correct_conf), "mean": sum(correct_conf)/len(correct_conf) if correct_conf else None,
              "q10": quantile(correct_conf, .1), "q50": quantile(correct_conf, .5), "q90": quantile(correct_conf, .9)},
              "notExact": {"count": len(wrong_conf), "mean": sum(wrong_conf)/len(wrong_conf) if wrong_conf else None,
              "q10": quantile(wrong_conf, .1), "q50": quantile(wrong_conf, .5), "q90": quantile(wrong_conf, .9)},
              "histogramByTenth": {f"{k[0]}:{k[1]/10:.1f}-{(k[1]+1)/10:.1f}": v for k,v in bins.items()}},
        "alignment": dict(alignment),
        "thresholdSelection": "Maximum exact span+type micro F1 on BKEE dev; ties prefer higher precision then lower threshold.",
        "caveat": "Threshold is tuned to BKEE dev and its general-domain label distribution; confidence is uncalibrated and finance-domain performance must be reviewed separately."
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(OUT / "emd_dev_threshold_metrics.csv", table,
              ["threshold", "precision", "recall", "f1", "tp", "fp", "fn", "predicted"])
    with (OUT / "emd_dev_raw_predictions.jsonl").open("w", encoding="utf-8") as f:
        for p in spans_out:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(json.dumps({"baseline": baseline, "best": best, "alignment": dict(alignment),
                      "predictions": len(base), "gold": len(gold)}, indent=2))


def quantile(values, q):
    if not values:
        return None
    xs = sorted(values)
    index = round((len(xs) - 1) * q)
    return xs[index]


if __name__ == "__main__":
    main()
