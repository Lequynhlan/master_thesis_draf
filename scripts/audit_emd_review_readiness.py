"""Audit BKEE-dev EMD span errors and prepare non-gold finance review artifacts.

This script performs inference only. It never updates models, RAW data, KG, or
ontology. Human annotation fields are deliberately emitted blank.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector

RUN = ROOT / "runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1"
OUT = RUN / "emd_v2_readiness"
DEV = ROOT / "data/external/BKEE_official_20261019/processed/dev.json"
EMD = ROOT / "models/phobert_bkee_emd_v1"


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    detector = PhoBERTEventDetector(EMD, device="cuda")
    counts = Counter()
    gold_by_type, pred_by_type = Counter(), Counter()
    error_examples = []
    sentence_count = 0
    for row in read_jsonl(DEV):
        sentence_count += 1
        sid, text = str(row.get("sent_id", "")), str(row["sentence"])
        gold = []
        for ent in row.get("entity_mentions", []):
            gold.append({"start": int(ent["start_char"]), "end": int(ent["end_char"]),
                         "type": str(ent["entity_type"]), "text": str(ent["text"]), "id": str(ent["id"])})
            gold_by_type[ent["entity_type"]] += 1
        pred = []
        for ent in detector.predict(text):
            sp = ent["triggerSpan"]
            pred.append({"start": int(sp["startChar"]), "end": int(sp["endChar"]),
                         "type": str(ent["eventType"]), "text": str(ent["trigger"]),
                         "confidence": ent["confidence"]})
            pred_by_type[ent["eventType"]] += 1

        # One-to-one matching: exact boundaries first (irrespective of type),
        # then remaining maximum-overlap pairs. This separates boundary errors
        # from type errors without double-counting nested/overlapping mentions.
        unmatched_g, unmatched_p = set(range(len(gold))), set(range(len(pred)))
        pairs = []
        exact_candidates = [(gi, pi) for gi in unmatched_g for pi in unmatched_p
                            if (gold[gi]["start"], gold[gi]["end"]) == (pred[pi]["start"], pred[pi]["end"])]
        exact_candidates.sort(key=lambda z: (gold[z[0]]["type"] != pred[z[1]]["type"], z))
        for gi, pi in exact_candidates:
            if gi in unmatched_g and pi in unmatched_p:
                pairs.append((gi, pi, "EXACT")); unmatched_g.remove(gi); unmatched_p.remove(pi)
        overlap_candidates = []
        for gi in unmatched_g:
            for pi in unmatched_p:
                amount = overlap((gold[gi]["start"], gold[gi]["end"]), (pred[pi]["start"], pred[pi]["end"]))
                if amount:
                    overlap_candidates.append((amount, gi, pi))
        overlap_candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
        for amount, gi, pi in overlap_candidates:
            if gi in unmatched_g and pi in unmatched_p:
                pairs.append((gi, pi, "OVERLAP")); unmatched_g.remove(gi); unmatched_p.remove(pi)

        for gi, pi, match_kind in pairs:
            g, p = gold[gi], pred[pi]
            if match_kind == "EXACT" and g["type"] == p["type"]:
                counts["exact_correct"] += 1
                continue
            if match_kind == "EXACT":
                category = "WRONG_ENTITY_TYPE"
            else:
                category = "WRONG_BOUNDARY_AND_TYPE" if g["type"] != p["type"] else "WRONG_BOUNDARY"
            counts[category] += 1
            error_examples.append({"errorType": category, "sentId": sid, "sentence": text,
                "goldEntityId": g["id"], "goldText": g["text"], "goldType": g["type"],
                "goldStart": g["start"], "goldEnd": g["end"], "predictedText": p["text"],
                "predictedType": p["type"], "predictedStart": p["start"], "predictedEnd": p["end"],
                "predictedConfidence": p["confidence"]})
        for gi in sorted(unmatched_g):
            g = gold[gi]; counts["MISSED_ENTITY"] += 1
            error_examples.append({"errorType": "MISSED_ENTITY", "sentId": sid, "sentence": text,
                "goldEntityId": g["id"], "goldText": g["text"], "goldType": g["type"],
                "goldStart": g["start"], "goldEnd": g["end"]})
        for pi in sorted(unmatched_p):
            p = pred[pi]; counts["SPURIOUS_ENTITY"] += 1
            error_examples.append({"errorType": "SPURIOUS_ENTITY", "sentId": sid, "sentence": text,
                "predictedText": p["text"], "predictedType": p["type"],
                "predictedStart": p["start"], "predictedEnd": p["end"],
                "predictedConfidence": p["confidence"]})
        if sentence_count % 500 == 0:
            print(f"EMD dev inference {sentence_count}/4301", flush=True)

    tp, npred, ngold = counts["exact_correct"], sum(pred_by_type.values()), sum(gold_by_type.values())
    precision = tp / npred if npred else 0
    recall = tp / ngold if ngold else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    summary = {
        "split": "BKEE dev only", "sentenceCount": sentence_count,
        "goldEntityCount": ngold, "predictedEntityCount": npred,
        "exactSpanAndType": {"precision": precision, "recall": recall, "f1": f1,
                              "tp": tp, "fp": npred - tp, "fn": ngold - tp},
        "errorBreakdown": dict(counts), "goldCountByType": dict(gold_by_type),
        "predictedCountByType": dict(pred_by_type),
        "matchingDefinition": "Exact character boundaries and type are correct; exact-boundary type disagreements count as WRONG_ENTITY_TYPE; remaining spans are paired one-to-one by maximum overlap; unmatched gold is MISSED_ENTITY; unmatched prediction is SPURIOUS_ENTITY.",
        "limitations": ["Overlap pairing is a diagnostic taxonomy, not a standard benchmark metric.",
                        "BKEE is general-domain Vietnamese; these metrics do not establish financial-domain EMD quality.",
                        "No test split or cohort review annotations used as gold."],
        "trainingRun": False,
    }
    (OUT / "emd_dev_error_breakdown.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    err_fields = ["errorType", "sentId", "sentence", "goldEntityId", "goldText", "goldType", "goldStart", "goldEnd", "predictedText", "predictedType", "predictedStart", "predictedEnd", "predictedConfidence"]
    write_csv(OUT / "emd_dev_error_examples.csv", error_examples, err_fields)

    # Finance cohort: preserve 58 review rows and add blank, independent
    # adjudication fields. No model prediction is copied into a reviewer field.
    queue = read_csv(RUN / "entity_linking_review_queue.csv")
    stage = json.loads((RUN / "staging_review_eae.json").read_text(encoding="utf-8"))
    stage_by_id = {str(x.get("eventId")): x for x in stage}
    fulltext_by_article = {str(x.get("articleId")): x for x in read_jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    annotation_fields = [
        "annotationStatus", "annotatorId", "annotationDate",
        "reviewEvent", "correctEventType", "reviewTrigger", "correctTriggerText", "correctTriggerStart", "correctTriggerEnd",
        "reviewEntitySpan", "correctEntityText", "correctEntityStart", "correctEntityEnd",
        "reviewEntityType", "correctEntityType", "reviewArgumentRole", "correctArgumentRole",
        "reviewKGURI", "correctKGURI", "reviewOverall", "annotationNotes",
    ]
    review_rows = []
    for q in queue:
        ev = stage_by_id.get(q.get("eventId", ""), {})
        row = dict(q)
        article_text = fulltext_by_article.get(q.get("articleId", ""), {})
        body = str(article_text.get("bodyText") or "")
        row["reviewFullText"] = (str(q.get("articleTitle", "")) + "\n" + body) if body else ""
        row["reviewFullTextOffsetBasis"] = "articleTitle + newline + saved bodyText" if body else "UNAVAILABLE_USE_SOURCE_URL"
        row["reviewBodyStatus"] = article_text.get("status", "NO_SAVED_BODY")
        row["reviewBodyOrigin"] = article_text.get("bodyOrigin", "")
        row["reviewBodyCapturedAt"] = article_text.get("capturedAt", "")
        row["reviewBodySha256"] = article_text.get("bodySha256", "")
        row["sourceMethod"] = ev.get("sourceMethod", "")
        row["eaeModel"] = ev.get("eaeModel", "")
        row["evidenceStartOffset"] = ev.get("evidence", {}).get("startOffset", "")
        row["evidenceEndOffset"] = ev.get("evidence", {}).get("endOffset", "")
        row["offsetBasis"] = ev.get("evidence", {}).get("offsetBasis", "")
        ent = next((x for x in ev.get("entities", []) if x.get("text") == q.get("entityMention") and x.get("entityType") == q.get("mentionType")), {})
        row["entityStartOffset"] = ent.get("startChar", "")
        row["entityEndOffset"] = ent.get("endChar", "")
        row["entityMentionId"] = ent.get("mentionId", "")
        arg = next((x for x in ev.get("arguments", []) if x.get("text") == q.get("entityMention") and x.get("role") == q.get("argumentRole")), {})
        row["argumentSourceMethod"] = arg.get("sourceMethod", "")
        row["argumentEntityMentionId"] = arg.get("entityMentionId", "")
        row["triggerConditioned"] = arg.get("triggerConditioned", "")
        for name in annotation_fields:
            row[name] = ""
        row["annotationStatus"] = "UNREVIEWED"
        for name in ["missedEntityFound", "missedEntityText", "missedEntityStart", "missedEntityEnd",
                     "missedEntityType", "missedEntityForEventId", "missedEntityRole", "missedEntityKGURI", "missedEntityNotes"]:
            row[name] = ""
        row["omissionReviewStatus"] = "UNREVIEWED"
        review_rows.append(row)
    source_fields = list(queue[0].keys()) + ["reviewFullText", "reviewFullTextOffsetBasis", "reviewBodyStatus", "reviewBodyOrigin", "reviewBodyCapturedAt", "reviewBodySha256", "sourceMethod", "eaeModel", "evidenceStartOffset", "evidenceEndOffset", "offsetBasis", "entityStartOffset", "entityEndOffset", "entityMentionId", "argumentSourceMethod", "argumentEntityMentionId", "triggerConditioned"]
    omission_fields = ["omissionReviewStatus", "missedEntityFound", "missedEntityText", "missedEntityStart", "missedEntityEnd", "missedEntityType", "missedEntityForEventId", "missedEntityRole", "missedEntityKGURI", "missedEntityNotes"]
    write_csv(OUT / "entity_linking_manual_annotation_template.csv", review_rows, source_fields + annotation_fields + omission_fields)

    unresolved = read_csv(RUN / "entity_linking_unresolved_causes.csv")
    resolution = read_csv(RUN / "entity_linking_v3/entity_resolution_audit.csv")
    arg_audit = read_csv(RUN / "entity_linking_v3/event_argument_linking_audit.csv")
    resolved_idx = {(r.get("articleId"), r.get("eventId"), r.get("mentionText"), r.get("mentionType")): r for r in resolution}
    arg_idx = {(r.get("articleId"), r.get("eventId"), r.get("argumentText"), r.get("argumentRole")): r for r in arg_audit}
    cross = []
    for u in unresolved:
        res = resolved_idx.get((u.get("articleId"), u.get("eventId"), u.get("entityMention"), u.get("mentionType")), {})
        arg = arg_idx.get((u.get("articleId"), u.get("eventId"), u.get("entityMention"), u.get("argumentRole")), {})
        cat = u.get("causeCategory", "")
        if "EMD" in cat or "SPAN" in cat:
            link = "POTENTIAL_EMD_REVIEW"
        elif cat in {"NEAR_KG_CANDIDATE_REVIEW", "AMBIGUOUS_URI_CANDIDATE", "AMBIGUOUS_URI_CANDIDATES"}:
            link = "ENTITY_RESOLUTION_ALIAS_OR_AMBIGUITY"
        elif cat in {"NO_KG_CANDIDATE_ENTITY_OR_ALIAS_REVIEW", "PERSON_NOT_IN_KG_LABELS_OR_NOT_LEADER"}:
            link = "KG_COVERAGE_ALIAS_SCOPE_OR_CONTEXT_UNRESOLVED"
        else:
            link = "MANUAL_CAUSE_REVIEW"
        cross.append({**u, "entityResolutionStatus": res.get("resolutionStatus", ""),
                      "resolvedUri": res.get("resolvedUri", ""), "resolutionMethod": res.get("resolutionMethod", ""),
                      "resolverReason": res.get("reason", ""), "emdCharacterSpanVerified": res.get("spanVerified", ""),
                      "argumentAlignmentMethod": arg.get("alignmentMethod", ""), "triggerLinkStatus": arg.get("linkStatus", ""),
                      "emdCausalAssessment": link, "causalAssessmentStatus": "PROVISIONAL_NOT_GOLD"})
    cross_fields = list(unresolved[0].keys()) + ["entityResolutionStatus", "resolvedUri", "resolutionMethod", "resolverReason", "emdCharacterSpanVerified", "argumentAlignmentMethod", "triggerLinkStatus", "emdCausalAssessment", "causalAssessmentStatus"]
    write_csv(OUT / "unresolved_argument_emd_crosswalk.csv", cross, cross_fields)

    print(json.dumps({"emd": summary, "reviewRows": len(review_rows), "unresolvedRows": len(cross), "out": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
