"""Score the manually completed 20-article financial review set.

Refuses to emit metrics unless every selected article and every model proposal
has explicit human review. Unreviewed rows are never treated as gold.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

DECISIONS = {"CORRECT", "INCORRECT", "UNCERTAIN", "NOT_IN_MAIN_ARTICLE"}
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "runs/news_event_vertical_slice_20261019/emd_v2_experiment/financial_gold_eval_v1"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def val(row, field):
    return (row.get(field) or "").strip()


def reviewed_context(sentence_by_id, row):
    sent = sentence_by_id.get(val(row, "sentenceId"), {})
    return val(sent, "sourceContextDecision")


def active_prediction_context(decision):
    # Keep out-of-main-article proposals in the prediction set so they count as
    # false positives; they are excluded only from the gold set.
    return decision not in {"UNCERTAIN", "INCORRECT"}


def key(row, fields):
    values = tuple(val(row, f) for f in fields)
    return values if all(values) else None


def prf(pred, gold):
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = (2 * p * r / (p + r)) if p is not None and r is not None and p + r else (0.0 if tp == 0 and (pred or gold) else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def validate_complete(sample, sentences, events, entities, args):
    problems = []
    required_articles = {val(r, "articleId") for r in sample if val(r, "articleId")}
    sent_by_id = {val(r, "sentenceId"): r for r in sentences}
    covered = {val(r, "articleId") for r in sentences}
    for aid in sorted(required_articles - covered):
        problems.append(f"article has no sentence rows: {aid}")
    for r in sentences:
        if val(r, "articleId") not in required_articles:
            continue
        if val(r, "sentenceReviewStatus") != "REVIEWED":
            problems.append(f"sentence not reviewed: {r.get('sentenceId','')}")
        if val(r, "sourceContextDecision") not in DECISIONS:
            problems.append(f"invalid/missing sourceContextDecision: {r.get('sentenceId','')}")
    checks = [
        (events, "MODEL_PREDICTION", ("triggerDecision", "eventTypeDecision")),
        (entities, "MODEL_PREDICTION", ("spanDecision", "typeDecision")),
        (args, "MODEL_PAIR", ("argumentDecision", "roleDecision")),
    ]
    for rows, origin, fields in checks:
        for r in rows:
            if val(r, "candidateOrigin") == origin and val(r, "articleId") in required_articles:
                for field in fields:
                    if val(r, field) not in DECISIONS:
                        problems.append(f"invalid/missing {field}: {r.get('rowId','')}")
            if val(r, "candidateOrigin") == "REVIEW_ADDED_SLOT" and val(r, "articleId") in required_articles:
                gold_fields = [k for k in r if k.startswith("gold")]
                if any(val(r, k) for k in gold_fields):
                    # A used add-slot must have an explicit human decision.
                    decision_fields = [k for k in fields if k in r]
                    if not decision_fields or any(val(r, f) not in DECISIONS for f in decision_fields):
                        problems.append(f"incomplete reviewer-added row: {r.get('rowId','')}")
    for r in entities:
        if val(r, "candidateOrigin") == "MODEL_PREDICTION" and val(r, "articleId") in required_articles:
            if val(r, "uriDecision") not in DECISIONS:
                problems.append(f"invalid/missing uriDecision: {r.get('rowId','')}")
    return required_articles, sent_by_id, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--output", type=Path, default=None)
    ns = ap.parse_args()
    d = ns.input_dir
    sample = read_csv(d / "article_sample.csv")
    sentences = read_csv(d / "sentence_annotation_template.csv")
    events = read_csv(d / "event_annotation_template.csv")
    entities = read_csv(d / "entity_annotation_template.csv")
    args = read_csv(d / "argument_link_annotation_template.csv")
    required_articles, sent_by_id, problems = validate_complete(sample, sentences, events, entities, args)
    if problems:
        print(json.dumps({"status": "NOT_READY", "articlesRequired": len(required_articles),
                          "blockingIssueCount": len(problems), "examples": problems[:20],
                          "metricsWritten": False}, ensure_ascii=False, indent=2))
        return 2

    metrics = {}
    # ED predictions and gold are trigger + type tuples. Reviewer-added slots
    # supply missed gold items; model rows only supply predictions.
    ed_pred, ed_gold = set(), set()
    for r in events:
        ctx = reviewed_context(sent_by_id, r)
        if val(r, "candidateOrigin") == "MODEL_PREDICTION" and active_prediction_context(ctx):
            k = key(r, ("articleId", "sourceField", "predictedTriggerStart", "predictedTriggerEnd", "predictedEventType"))
            if k: ed_pred.add(k)
        if val(r, "candidateOrigin") == "REVIEW_ADDED_SLOT" and ctx == "CORRECT" and val(r, "triggerDecision") == "CORRECT" and val(r, "eventTypeDecision") == "CORRECT":
            k = key(r, ("articleId", "sourceField", "goldTriggerStart", "goldTriggerEnd", "goldEventType"))
            if k: ed_gold.add(k)
        if val(r, "candidateOrigin") == "MODEL_PREDICTION" and ctx == "CORRECT" and val(r, "triggerDecision") == "CORRECT" and val(r, "eventTypeDecision") == "CORRECT":
            k = key(r, ("articleId", "sourceField", "predictedTriggerStart", "predictedTriggerEnd", "predictedEventType"))
            if k: ed_gold.add(k)
    metrics["ED"] = prf(ed_pred, ed_gold)

    # EMD is compared independently for each saved version against the same
    # human gold spans. Exact span and type are both required.
    for version in ("EMD_V1", "EMD_V2"):
        pred, gold = set(), set()
        for r in entities:
            origin = val(r, "candidateOrigin")
            ctx = reviewed_context(sent_by_id, r)
            if origin == "MODEL_PREDICTION" and val(r, "modelVersion") == version and active_prediction_context(ctx):
                k = key(r, ("articleId", "sourceField", "predictedEntityStart", "predictedEntityEnd", "predictedEntityType"))
                if k: pred.add(k)
            if origin == "MODEL_PREDICTION" and ctx == "CORRECT" and val(r, "spanDecision") == "CORRECT" and val(r, "typeDecision") == "CORRECT":
                k = key(r, ("articleId", "sourceField", "predictedEntityStart", "predictedEntityEnd", "predictedEntityType"))
                if k: gold.add(k)
            if origin == "REVIEW_ADDED_SLOT" and ctx == "CORRECT" and val(r, "spanDecision") == "CORRECT" and val(r, "typeDecision") == "CORRECT":
                k = key(r, ("articleId", "sourceField", "goldEntityStart", "goldEntityEnd", "goldEntityType"))
                if k: gold.add(k)
        metrics[version] = prf(pred, gold)

    # EAE positive role tuples; NONE is excluded from micro P/R/F1. EMD
    # version-specific rows provide different entities but the same ED trigger.
    for version in ("EMD_V1", "EMD_V2"):
        pred, gold = set(), set()
        for r in args:
            origin = val(r, "candidateOrigin")
            ctx = reviewed_context(sent_by_id, r)
            if origin == "MODEL_PAIR" and val(r, "modelVersion") == version and active_prediction_context(ctx) and val(r, "predictedArgumentRole") not in ("", "NONE"):
                try: trig = json.loads(val(r, "predictedTriggerSpan")) or {}
                except json.JSONDecodeError: trig = {}
                k = (val(r, "articleId"), val(r, "sourceField"), str(trig.get("start", "")), str(trig.get("end", "")), val(r, "predictedEventType"), val(r, "predictedEntityStart"), val(r, "predictedEntityEnd"), val(r, "predictedArgumentRole"))
                if all(k): pred.add(k)
            if origin == "MODEL_PAIR" and ctx == "CORRECT" and val(r, "argumentDecision") == "CORRECT" and val(r, "roleDecision") == "CORRECT" and val(r, "predictedArgumentRole") not in ("", "NONE"):
                try: trig = json.loads(val(r, "predictedTriggerSpan")) or {}
                except json.JSONDecodeError: trig = {}
                k = (val(r, "articleId"), val(r, "sourceField"), str(trig.get("start", "")), str(trig.get("end", "")), val(r, "predictedEventType"), val(r, "predictedEntityStart"), val(r, "predictedEntityEnd"), val(r, "predictedArgumentRole"))
                if all(k): gold.add(k)
            if origin == "REVIEW_ADDED_SLOT" and ctx == "CORRECT" and val(r, "argumentDecision") == "CORRECT" and val(r, "roleDecision") == "CORRECT":
                k = key(r, ("articleId", "sourceField", "goldTriggerStart", "goldTriggerEnd", "goldEventType", "goldEntityStart", "goldEntityEnd", "goldArgumentRole"))
                if k: gold.add(k)
        metrics[f"EAE_{version}"] = prf(pred, gold)

    # URI linking uses exact confirmed mention span/type plus URI. Mention
    # correctness and URI correctness are separate decisions.
    for version in ("EMD_V1", "EMD_V2"):
        pred, gold = set(), set()
        for r in entities:
            origin, ctx = val(r, "candidateOrigin"), reviewed_context(sent_by_id, r)
            if origin == "MODEL_PREDICTION" and val(r, "modelVersion") == version and active_prediction_context(ctx) and val(r, "predictedEntityURI") and val(r, "uriDecision") != "UNCERTAIN":
                k = key(r, ("articleId", "sourceField", "predictedEntityStart", "predictedEntityEnd", "predictedEntityType", "predictedEntityURI"))
                if k: pred.add(k)
            if origin == "MODEL_PREDICTION" and ctx == "CORRECT" and val(r, "spanDecision") == "CORRECT" and val(r, "typeDecision") == "CORRECT" and val(r, "goldEntityURI"):
                uri = val(r, "goldEntityURI")
                k = key({**r, "uri": uri}, ("articleId", "sourceField", "predictedEntityStart", "predictedEntityEnd", "predictedEntityType", "uri"))
                if k: gold.add(k)
            if origin == "REVIEW_ADDED_SLOT" and ctx == "CORRECT" and val(r, "spanDecision") == "CORRECT" and val(r, "typeDecision") == "CORRECT" and val(r, "uriDecision") == "CORRECT":
                k = key(r, ("articleId", "sourceField", "goldEntityStart", "goldEntityEnd", "goldEntityType", "goldEntityURI"))
                if k: gold.add(k)
        metrics[f"EntityLinking_{version}"] = prf(pred, gold)

    result = {"status": "READY", "reviewedArticleCount": len(required_articles),
              "sampleSize": len(required_articles), "decisionPolicy": "UNCERTAIN excluded; NOT_IN_MAIN_ARTICLE predictions retained as predictions and never gold; NONE excluded from EAE role PRF.",
              "metrics": metrics, "note": "Diagnostic metrics on this purposive 20-article sample only; not population estimates."}
    output = ns.output or d / "financial_gold_metrics.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "READY", "metricsFile": str(output), "reviewedArticleCount": len(required_articles)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
