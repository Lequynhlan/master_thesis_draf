"""Run EMD v2 on the frozen 100-article cohort, leaving ED and KG untouched."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector
from wfkg.event_processing.text_input import prepare_extraction_input

RUN = ROOT / "runs/news_event_vertical_slice_20261019"
OUT = RUN / "emd_v2_experiment"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {OUT}")
    articles = read_jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")
    enriched = {str(row["articleId"]): row for row in read_jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    prepared = {str(row["articleId"]): prepare_extraction_input(row, enriched.get(str(row["articleId"]))).text for row in articles}
    detector = PhoBERTEventDetector(ROOT / "models/phobert_bkee_emd_v2", device="cuda")
    predictions: dict[str, list[dict]] = {}
    for idx, (aid, text) in enumerate(prepared.items(), 1):
        rows = detector.predict(text)
        predictions[aid] = rows
        if idx % 10 == 0:
            print(f"EMD v2 cohort inference {idx}/{len(prepared)}", flush=True)
    stage = json.loads((RUN / "staging_review.json").read_text(encoding="utf-8"))
    new_stage = copy.deepcopy(stage)
    attached = Counter()
    for event in new_stage:
        aid = str(event["articleId"])
        ev = event.get("evidence") or {}
        es, ee = ev.get("startOffset"), ev.get("endOffset")
        # Attach mentions only when the full-document span lies inside this Event's evidence.
        selected = []
        for item in predictions.get(aid, []):
            span = item.get("triggerSpan") or {}
            start, end = span.get("startChar"), span.get("endChar")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if isinstance(es, int) and isinstance(ee, int) and not (es <= start < end <= ee):
                continue
            entity_type = item.get("eventType")
            key = f"{aid}|{start}|{end}|{entity_type}"
            selected.append({"mentionId": "EMD_V2_MENTION:" + hashlib.sha256(key.encode()).hexdigest()[:20],
                             "text": item.get("trigger"), "entityType": entity_type,
                             "startChar": start, "endChar": end, "confidence": item.get("confidence"),
                             "sourceMethod": "PHOBERT_BKEE_EMD_V2", "entityMatchStatus": "UNRESOLVED"})
        event["entities"] = selected
        event["arguments"] = []
        event["entityLinkSuggestions"] = []
        event["emdModel"] = "phobert_bkee_emd_v2"
        attached["eventRows"] += 1
        attached["mentionsAttached"] += len(selected)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cohort_emd_predictions.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (OUT / "staging_review.json").write_text(json.dumps(new_stage, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    summary = {"articleCount": len(articles), "articlesWithAnyEmdMention": sum(bool(v) for v in predictions.values()),
               "emdMentionCount": sum(map(len, predictions.values())), "stagedEventCount": len(stage),
               "eventRowsWithReplacedEntities": attached["eventRows"], "mentionsContainedInEventEvidence": attached["mentionsAttached"],
               "edRerun": False, "eaeRerun": False, "crawlRun": False, "trainingRun": False,
               "mainKgModified": False, "rawOntologyShaclAnnotationModified": False,
               "checkpoint": "models/phobert_bkee_emd_v2", "outputIsReviewStaging": True}
    (OUT / "emd_cohort_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
