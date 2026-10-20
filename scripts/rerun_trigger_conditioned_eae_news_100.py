"""Apply only trigger-conditioned EAE to saved ED/EMD predictions for the fixed 100 articles."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.text_input import prepare_extraction_input
from wfkg.event_processing.trigger_conditioned_eae import TriggerConditionedEAE

RUN = ROOT / "runs/news_event_vertical_slice_20261019"
DEFAULT_MODEL = ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1"
DEFAULT_OUT = RUN / "eae_trigger_conditioned_v1"


def sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = max(text.rfind(mark, 0, start) for mark in (".", "?", "!", ";", "\n"))
    right = [pos for mark in (".", "?", "!", ";", "\n") if (pos := text.find(mark, end)) >= 0]
    return left + 1, min(right) + 1 if right else len(text)


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--input-staging", type=Path, default=RUN / "staging_review.json")
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve()
    args.output_dir = args.output_dir.resolve()
    args.input_staging = args.input_staging.resolve()
    if not (args.checkpoint / "config.json").exists():
        raise SystemExit(f"Missing trigger-conditioned EAE checkpoint: {args.checkpoint}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {args.output_dir}")

    articles = {str(row["articleId"]): row for row in read_jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(row["articleId"]): row for row in read_jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    prepared = {aid: prepare_extraction_input(article, enriched.get(aid)).text for aid, article in articles.items()}
    baseline = json.loads(args.input_staging.read_text(encoding="utf-8"))
    staged = copy.deepcopy(baseline)
    for event in staged:
        for mention in event.get("entities", []):
            key = f"{event.get('articleId')}|{mention.get('startChar')}|{mention.get('endChar')}|{mention.get('entityType')}"
            mention["mentionId"] = "EMD_MENTION:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    model = TriggerConditionedEAE(args.checkpoint)
    bkee_train = [json.loads(line) for line in (ROOT / "data/external/BKEE_official_20261019/processed/train.json").read_text(encoding="utf-8").splitlines() if line.strip()]
    event_roles, role_entity_types = {}, {}
    for row in bkee_train:
        entity_by_id = {str(entity["id"]): entity for entity in row.get("entity_mentions", [])}
        for gold_event in row.get("event_mentions", []):
            for gold_arg in gold_event.get("arguments", []):
                role = str(gold_arg["role"]); event_type = str(gold_event["event_type"])
                event_roles.setdefault(event_type, set()).add(role)
                linked_entity = entity_by_id.get(str(gold_arg.get("entity_id")))
                if linked_entity:
                    role_entity_types.setdefault(role, set()).add(str(linked_entity.get("entity_type", "")))
    counts = Counter(); event_participants = Counter(); pair_rows = []
    for event in staged:
        article_id = str(event["articleId"]); text = prepared.get(article_id, "")
        trigger = event.get("trigger", {}); ts, te = trigger.get("startChar"), trigger.get("endChar")
        if not (isinstance(ts, int) and isinstance(te, int) and text[ts:te] == trigger.get("text")):
            counts["trigger_span_unverified"] += 1; event["arguments"] = []; continue
        event_sentence = sentence_bounds(text, ts, te)
        entities = [m for m in event.get("entities", [])
                    if isinstance(m.get("startChar"), int) and isinstance(m.get("endChar"), int)
                    and text[m["startChar"]:m["endChar"]] == m.get("text")
                    and sentence_bounds(text, m["startChar"], m["endChar"]) == event_sentence]
        pair_input = []
        for mention in entities:
            pair_input.append({"sentence": text[event_sentence[0]:event_sentence[1]],
                               "triggerSpan": (ts-event_sentence[0], te-event_sentence[0]),
                               "eventType": event["eventType"],
                               "entitySpan": (mention["startChar"]-event_sentence[0], mention["endChar"]-event_sentence[0]),
                               "entityType": mention.get("entityType", "UNK")})
        predictions = model.predict_pairs(pair_input)
        args_for_event = []
        for mention, prediction in zip(entities, predictions):
            counts["candidatePairs"] += 1
            record = {"articleId": article_id, "eventId": event["eventId"], "triggerText": trigger.get("text"),
                      "eventType": event["eventType"], "entityText": mention.get("text"),
                      "entityType": mention.get("entityType"), "entityStartChar": mention.get("startChar"),
                      "entityEndChar": mention.get("endChar"), "predictedLabel": prediction.get("label", prediction.get("status")),
                      "confidence": prediction.get("confidence"), "sourceMethod": "PHOBERT_TRIGGER_CONDITIONED_BKEE_EAE_V1"}
            if prediction.get("status") != "OK":
                counts[prediction.get("status", "INVALID")] += 1
            elif prediction["label"] == "NONE":
                counts["NONE"] += 1
            else:
                counts["predictedRolePairs"] += 1
                event_role_ok = prediction["label"] in event_roles.get(str(event["eventType"]), set())
                entity_type_ok = mention.get("entityType") in role_entity_types.get(prediction["label"], set())
                compatible = event_role_ok and entity_type_ok
                argument = {"text": mention["text"], "role": prediction["label"],
                            "startChar": mention["startChar"], "endChar": mention["endChar"],
                            "confidence": prediction["confidence"], "entityMention": mention,
                            "entityMentionId": mention["mentionId"],
                            "entityMatchStatus": mention.get("entityMatchStatus", "UNRESOLVED"),
                            "triggerLinkStatus": "LINKED_TO_TRIGGER" if compatible else "ROLE_COMPATIBILITY_REVIEW",
                            "conditionedOnEventId": event["eventId"],
                            "conditionedOnTriggerSpan": {"startChar": ts, "endChar": te},
                            "triggerConditioned": True,
                            "roleCompatibilityAccepted": compatible,
                            "eventRoleCompatible": event_role_ok,
                            "entityRoleCompatible": entity_type_ok,
                            "eventRoleObservedInBkeeTrain": event_role_ok,
                            "entityTypeObservedForRoleInBkeeTrain": entity_type_ok,
                            "evidenceText": event.get("evidence", {}).get("evidenceText"),
                            "sourceMethod": "PHOBERT_TRIGGER_CONDITIONED_BKEE_EAE_V1",
                            "reviewStatus": "REVIEW_REQUIRED"}
                args_for_event.append(argument)
                event_participants[event["eventId"]] += int(compatible)
                counts["role_compatible" if compatible else "role_compatibility_review"] += 1
                record["roleCompatibilityAccepted"] = compatible
                record["eventRoleObservedInBkeeTrain"] = event_role_ok
                record["entityTypeObservedForRoleInBkeeTrain"] = entity_type_ok
                record["participantCandidate"] = True
            pair_rows.append(record)
        event["arguments"] = args_for_event
        event["eaeModel"] = "phobert_bkee_eae_trigger_conditioned_v1"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "staging_review_eae.json").write_text(json.dumps(staged, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (args.output_dir / "event_entity_pair_predictions.json").write_text(json.dumps(pair_rows, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    def confidence_summary(label_filter):
        values = sorted(float(row["confidence"]) for row in pair_rows
                        if row.get("confidence") is not None and label_filter(row))
        if not values:
            return {"count": 0}
        mid = len(values) // 2
        median = values[mid] if len(values) % 2 else (values[mid-1] + values[mid]) / 2
        return {"count": len(values), "mean": sum(values)/len(values), "median": median,
                "min": values[0], "max": values[-1]}
    summary = {"articleCount": 100, "stagedEventCount": len(staged), "eventsWithPredictedCompatibleParticipant": len(event_participants),
               "pairCounts": dict(counts), "checkpoint": str(args.checkpoint.relative_to(ROOT)),
               "confidence": {"predictedRole": confidence_summary(lambda row: row.get("predictedLabel") not in {"NONE", "OK", "INVALID_OR_OVERLAPPING_SPANS", "OVER_MAX_LENGTH"}),
                              "predictedNone": confidence_summary(lambda row: row.get("predictedLabel") == "NONE")},
               "edEmeReusedFrom": "runs/news_event_vertical_slice_20261019/staging_review.json",
               "trainingRun": False, "edRerun": False, "emdRerun": False, "crawlRun": False,
               "confidenceCalibrated": False,
               "rawKgOntologyShaclAnnotationModified": False,
               "note": "Predictions remain review-only in staging; no KG relation is written."}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
