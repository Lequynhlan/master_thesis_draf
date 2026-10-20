"""Break down ED/EMD/EAE errors on BKEE dev under four span conditions."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector
from wfkg.event_processing.trigger_conditioned_eae import TriggerConditionedEAE

DEV = ROOT / "data/external/BKEE_official_20261019/processed/dev.json"
ED = ROOT / "models/phobert_bkee_event_detection_v2"
EMD = ROOT / "models/phobert_bkee_emd_v1"
EAE = ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1"
OUT = ROOT / "runs/phobert_bkee_eae_trigger_conditioned_v1"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2*p*r/(p+r) if p+r else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def metric(gold: set, pred: set) -> dict:
    return prf(len(gold & pred), len(pred - gold), len(gold - pred))


def main():
    rows = read_jsonl(DEV)
    ed = PhoBERTEventDetector(ED, device="cuda")
    emd = PhoBERTEventDetector(EMD, device="cuda")
    eae = TriggerConditionedEAE(EAE, device="cuda")
    eae.model.eval()

    all_gold_events, all_pred_events = set(), set()
    all_gold_entities, all_pred_entities = set(), set()
    condition_tp = Counter(); condition_pred = Counter(); role_count = 0
    invalid = Counter(); pair_diagnostics = Counter()
    for index, row in enumerate(rows):
        text = str(row["sentence"])
        sid = str(row.get("sent_id", index))
        gold_events = []
        gold_entities = []
        entity_by_id = {str(x["id"]): x for x in row.get("entity_mentions", [])}
        gold_roles = set()
        for event in row.get("event_mentions", []):
            t = event["trigger"]
            ev = {"eventType": str(event["event_type"]), "span": (int(t["start_char"]), int(t["end_char"])), "text": str(t["text"])}
            gold_events.append(ev)
            all_gold_events.add((sid, *ev["span"], ev["eventType"]))
            for arg in event.get("arguments", []):
                ent = entity_by_id.get(str(arg.get("entity_id")))
                if ent is None:
                    continue
                es = (int(ent["start_char"]), int(ent["end_char"]))
                etype = str(ent["entity_type"])
                gold_roles.add((ev["span"], ev["eventType"], es, etype, str(arg["role"])))
        for ent in row.get("entity_mentions", []):
            gold_entities.append({"eventType": str(ent["entity_type"]), "span": (int(ent["start_char"]), int(ent["end_char"])), "text": str(ent["text"])})
            all_gold_entities.add((sid, int(ent["start_char"]), int(ent["end_char"]), str(ent["entity_type"])))

        raw_pred_events = ed.predict(text)
        if index == 0:
            emd._segmenter = ed._segmenter
        pred_events = [{"eventType": p["eventType"], "span": (p["triggerSpan"]["startChar"], p["triggerSpan"]["endChar"]), "text": p["trigger"]}
                       for p in raw_pred_events]
        pred_entities = [{"eventType": p["eventType"], "span": (p["triggerSpan"]["startChar"], p["triggerSpan"]["endChar"]), "text": p["trigger"]}
                         for p in emd.predict(text)]
        for ev in pred_events:
            all_pred_events.add((sid, *ev["span"], ev["eventType"]))
        for ent in pred_entities:
            all_pred_entities.add((sid, *ent["span"], ent["eventType"]))

        modes = {
            "gold_trigger_gold_entity": (gold_events, gold_entities),
            "gold_trigger_pred_entity": (gold_events, pred_entities),
            "pred_trigger_gold_entity": (pred_events, gold_entities),
            "pred_trigger_pred_entity": (pred_events, pred_entities),
        }
        for mode, (events, entities) in modes.items():
            pairs, pair_meta = [], []
            for event in events:
                for entity in entities:
                    pairs.append({"sentence": text, "triggerSpan": event["span"], "eventType": event["eventType"],
                                  "entitySpan": entity["span"], "entityType": entity["eventType"]})
                    pair_meta.append((event, entity))
            outputs = eae.predict_pairs(pairs) if pairs else []
            predicted_roles = set()
            for (event, entity), out in zip(pair_meta, outputs):
                if out.get("status") != "OK":
                    invalid[(mode, out.get("status", "INVALID"))] += 1
                    continue
                if out["label"] == "NONE":
                    continue
                predicted_roles.add((event["span"], event["eventType"], entity["span"], entity["eventType"], out["label"]))
            tp = len(predicted_roles & gold_roles)
            condition_tp[mode] += tp
            condition_pred[mode] += len(predicted_roles)
            pair_diagnostics[(mode, "gold_roles")] += len(gold_roles)
            role_count += len(gold_roles) if mode == "gold_trigger_gold_entity" else 0
        if index and index % 500 == 0:
            print(f"dev sentences {index}/{len(rows)}", flush=True)

    gold_arg_count = role_count
    conditions = {}
    for mode in ("gold_trigger_gold_entity", "gold_trigger_pred_entity", "pred_trigger_gold_entity", "pred_trigger_pred_entity"):
        tp = condition_tp[mode]
        conditions[mode] = prf(tp, condition_pred[mode]-tp, gold_arg_count-tp)
        conditions[mode]["predictedRoleCount"] = condition_pred[mode]
    summary = {
        "devSentenceCount": len(rows), "goldEventCount": len(all_gold_events), "goldEntityCount": len(all_gold_entities),
        "goldArgumentCount": gold_arg_count,
        "eventDetectionExactSpanType": metric(all_gold_events, all_pred_events),
        "entityMentionDetectionExactSpanType": metric(all_gold_entities, all_pred_entities),
        "eaeRoleMetrics": conditions,
        "invalidPairCounts": {f"{mode}:{status}": count for (mode, status), count in invalid.items()},
        "definitions": {
            "spanMatch": "exact character start/end and event/entity type",
            "EAE": "role micro P/R/F1 excludes NONE; every gold argument is in recall denominator",
            "mixedModes": "The selected gold/predicted trigger and entity spans form candidate pairs within each sentence; pair predictions are scored only on exact gold event/entity/role tuples.",
            "testSplitUsed": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pipeline_condition_breakdown.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
