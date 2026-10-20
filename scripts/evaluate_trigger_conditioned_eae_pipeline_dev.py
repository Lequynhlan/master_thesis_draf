"""Evaluate trigger-conditioned EAE on BKEE dev with existing predicted ED/EMD spans."""
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
LEGACY_EAE = ROOT / "models/phobert_bkee_eae_v1"
OUT = ROOT / "runs/phobert_bkee_eae_trigger_conditioned_v1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def exact_metric(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2*p*r/(p+r) if p+r else 0.0,
            "truePositive": tp, "falsePositive": fp, "falseNegative": fn}


def main():
    rows = load_jsonl(DEV)
    ed = PhoBERTEventDetector(ED, device="cuda")
    emd = PhoBERTEventDetector(EMD, device="cuda")
    legacy_eae = PhoBERTEventDetector(LEGACY_EAE, device="cuda")
    eae = TriggerConditionedEAE(EAE, device="cuda")
    counts = Counter(); legacy_counts = Counter(); prediction_rows = []
    for index, row in enumerate(rows):
        text = str(row["sentence"])
        gold_events = row.get("event_mentions", [])
        gold_entities = {str(entity["id"]): entity for entity in row.get("entity_mentions", [])}
        gold_links = set()
        gold_trigger_to_event = {}
        for event in gold_events:
            trigger = event["trigger"]
            key = (trigger["start_char"], trigger["end_char"], str(event["event_type"]))
            gold_trigger_to_event[key] = event
            for arg in event.get("arguments", []):
                entity = gold_entities.get(str(arg.get("entity_id")))
                if entity:
                    gold_links.add((key, entity["start_char"], entity["end_char"],
                                    str(entity["entity_type"]), str(arg["role"])))
        ed_predictions = ed.predict(text)
        if index == 0:
            emd._segmenter = ed._segmenter
            legacy_eae._segmenter = ed._segmenter
        emd_predictions = emd.predict(text)
        legacy_role_predictions = legacy_eae.predict(text)
        events = [{"eventType": p["eventType"], "span": p["triggerSpan"], "text": p["trigger"], "confidence": p["confidence"]}
                  for p in ed_predictions]
        entities = [{"entityType": p["eventType"], "span": p["triggerSpan"], "text": p["trigger"], "confidence": p["confidence"]}
                    for p in emd_predictions]
        # Legacy role spans have no trigger input. Attach only when both entity-span
        # alignment and the nearest ED trigger are unique.
        for role_prediction in legacy_role_predictions:
            role_span = role_prediction["triggerSpan"]
            start, end = role_span["startChar"], role_span["endChar"]
            exact_entities = [entity for entity in entities
                              if entity["span"]["startChar"] == start and entity["span"]["endChar"] == end]
            distances = [(max(0, max(event["span"]["startChar"] - end,
                                     start - event["span"]["endChar"])), event) for event in events]
            closest = min((distance for distance, _ in distances), default=None)
            nearest = [event for distance, event in distances if distance == closest] if closest is not None else []
            if not exact_entities or len(nearest) != 1:
                legacy_counts["unlinkedRoleSpans"] += 1
                legacy_counts["ambiguousTriggerRoleSpans"] += int(len(nearest) > 1)
                continue
            event, entity = nearest[0], exact_entities[0]
            event_key = (event["span"]["startChar"], event["span"]["endChar"], event["eventType"])
            correct = any(link[0] == event_key and link[1] == start and link[2] == end
                          and link[3] == entity["entityType"] and link[4] == role_prediction["eventType"]
                          for link in gold_links)
            legacy_counts["linkedRolePredictions"] += 1
            legacy_counts["exactSpanRoleTruePositive"] += int(correct)
        candidates = []
        metadata = []
        for event in events:
            for entity in entities:
                candidates.append({"sentence": text,
                                   "triggerSpan": (event["span"]["startChar"], event["span"]["endChar"]),
                                   "eventType": event["eventType"],
                                   "entitySpan": (entity["span"]["startChar"], entity["span"]["endChar"]),
                                   "entityType": entity["entityType"]})
                metadata.append((event, entity))
        pair_predictions = eae.predict_pairs(candidates) if candidates else []
        for (event, entity), prediction in zip(metadata, pair_predictions):
            if prediction.get("status") != "OK":
                counts[prediction.get("status", "INVALID")] += 1
                continue
            if prediction["label"] == "NONE":
                counts["predicted_none"] += 1
                continue
            pred_t = event["span"]
            event_key = (pred_t["startChar"], pred_t["endChar"], event["eventType"])
            gold_role_match = any(link[0] == event_key and
                                  link[1] == entity["span"]["startChar"] and
                                  link[2] == entity["span"]["endChar"] and
                                  link[3] == entity["entityType"] and link[4] == prediction["label"]
                                  for link in gold_links)
            gold_pair_exists = any(link[0] == event_key and
                                    link[1] == entity["span"]["startChar"] and
                                    link[2] == entity["span"]["endChar"] and link[3] == entity["entityType"]
                                    for link in gold_links)
            counts["predicted_role"] += 1
            counts["exact_span_role_tp"] += int(gold_role_match)
            counts["wrong_role_on_gold_pair"] += int(gold_pair_exists and not gold_role_match)
            prediction_rows.append({"sentId": row.get("sent_id"), "eventType": event["eventType"],
                                    "trigger": event["text"], "triggerSpan": event["span"],
                                    "entityType": entity["entityType"], "entity": entity["text"],
                                    "entitySpan": entity["span"], "role": prediction["label"],
                                    "confidence": prediction["confidence"],
                                    "exactGoldArgument": gold_role_match})
        if index and index % 500 == 0:
            print(f"dev sentences {index}/{len(rows)}", flush=True)
    tp = counts["exact_span_role_tp"]
    predicted = counts["predicted_role"]
    # Gold argument denominator includes all annotations, including arguments whose ED/EMD span was missed.
    gold_args = sum(len(event.get("arguments", [])) for row in rows for event in row.get("event_mentions", []))
    fp = predicted - tp; fn = gold_args - tp
    legacy_tp = legacy_counts["exactSpanRoleTruePositive"]
    legacy_predicted = legacy_counts["linkedRolePredictions"]
    summary = {"devSentenceCount": len(rows), "goldArgumentCount": gold_args,
               "pipelinePredictedRoleCount": predicted, "pipelineExactSpanRoleMetrics": exact_metric(tp, fp, fn),
               "legacySentenceBioLinkedRolePredictionCount": legacy_predicted,
               "legacySentenceBioPipelineExactSpanRoleMetrics": exact_metric(legacy_tp, legacy_predicted-legacy_tp, gold_args-legacy_tp),
               "legacySentenceBioPipelineCounts": dict(legacy_counts),
               "predictionCounts": dict(counts), "pipeline": "existing ED v2 + existing EMD v1 + trigger-conditioned EAE v1",
               "edCheckpoint": str(ED.relative_to(ROOT)), "emdCheckpoint": str(EMD.relative_to(ROOT)),
               "eaeCheckpoint": str(EAE.relative_to(ROOT)), "testSplitUsed": False,
               "warning": "Role F1 is exact across trigger type/span, entity type/span, and role; it is not directly comparable to gold-span role-only F1."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pipeline_dev_predictions.json").write_text(json.dumps(prediction_rows, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    (OUT / "pipeline_dev_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
