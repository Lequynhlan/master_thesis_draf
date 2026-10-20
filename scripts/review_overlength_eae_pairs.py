"""Score the 17 saved overlength candidates with bounded context windows for review."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.text_input import prepare_extraction_input
from wfkg.event_processing.trigger_conditioned_eae import TriggerConditionedEAE
from rerun_trigger_conditioned_eae_news_100 import sentence_bounds

RUN = ROOT / "runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1"
OUT = RUN / "overlength_context_window_review.csv"


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    articles = {str(row["articleId"]): row for row in jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(row["articleId"]): row for row in jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    text_by_article = {aid: prepare_extraction_input(article, enriched.get(aid)).text for aid, article in articles.items()}
    events = json.loads((RUN / "staging_review_eae.json").read_text(encoding="utf-8"))
    events_by_id = {str(row["eventId"]): row for row in events}
    pair_rows = json.loads((RUN / "event_entity_pair_predictions.json").read_text(encoding="utf-8"))
    overlength = [row for row in pair_rows if row.get("predictedLabel") == "OVER_MAX_LENGTH"]
    model = TriggerConditionedEAE(ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1", device="cuda")
    model_inputs, metadata = [], []
    for row in overlength:
        event = events_by_id[row["eventId"]]
        article_id = str(event["articleId"])
        text = text_by_article[article_id]
        trigger = event["trigger"]
        ts, te = trigger["startChar"], trigger["endChar"]
        sentence_start, sentence_end = sentence_bounds(text, ts, te)
        mention = next((item for item in event.get("entities", [])
                        if item.get("startChar") == row.get("entityStartChar")
                        and item.get("endChar") == row.get("entityEndChar")
                        and item.get("text") == row.get("entityText")), None)
        if mention is None:
            continue
        model_inputs.append({
            "sentence": text[sentence_start:sentence_end],
            "triggerSpan": (ts-sentence_start, te-sentence_start),
            "eventType": event["eventType"],
            "entitySpan": (mention["startChar"]-sentence_start, mention["endChar"]-sentence_start),
            "entityType": mention.get("entityType", "UNK"),
        })
        metadata.append((row, event, article_id, sentence_start))
    outputs = model.predict_pairs(model_inputs, crop_overlength=True)
    output_rows = []
    for (old, event, article_id, sentence_start), result in zip(metadata, outputs):
        window = result.get("contextWindowSpan", {})
        article = articles.get(article_id, {})
        output_rows.append({
            "articleId": article_id, "articleTitle": article.get("title", ""), "sourceUrl": article.get("url", ""),
            "eventId": event["eventId"], "eventType": event["eventType"],
            "trigger": event["trigger"].get("text", ""), "triggerStart": event["trigger"]["startChar"],
            "triggerEnd": event["trigger"]["endChar"], "entityMention": old.get("entityText", ""),
            "entityType": old.get("entityType", ""), "entityStart": old.get("entityStartChar", ""),
            "entityEnd": old.get("entityEndChar", ""), "originalSentenceTokenLength": "430-456",
            "contextWindowStart": sentence_start + window.get("startChar", 0),
            "contextWindowEnd": sentence_start + window.get("endChar", 0),
            "triggerSpanPreserved": window.get("triggerSpanPreserved", False),
            "entitySpanPreserved": window.get("entitySpanPreserved", False),
            "predictionStatus": result.get("status"), "suggestedRole": result.get("label", ""),
            "confidenceUncalibrated": result.get("confidence", ""),
            "evidenceText": event.get("evidence", {}).get("evidenceText", ""),
            "reviewStatus": "REVIEW_REQUIRED_CONTEXT_WINDOW_EXPERIMENT",
            "note": "Separate review-only prediction; not merged into EAE staging or KG.",
            "reviewDecision": "", "reviewerComment": "",
        })
    fields = list(output_rows[0]) if output_rows else []
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(output_rows)
    print(json.dumps({"savedOverlength": len(overlength), "evaluated": len(output_rows),
                      "predictionStatuses": {status: sum(row["predictionStatus"] == status for row in output_rows)
                                             for status in sorted({row["predictionStatus"] for row in output_rows})},
                      "spansPreserved": sum(row["triggerSpanPreserved"] and row["entitySpanPreserved"] for row in output_rows),
                      "path": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
