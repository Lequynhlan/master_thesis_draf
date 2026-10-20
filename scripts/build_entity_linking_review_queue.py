"""Build a review queue from saved event staging and KG path audits."""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.text_input import prepare_extraction_input

RUN = ROOT / "runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1"
AUDIT = RUN / "entity_linking_v3"
OUT = RUN / "entity_linking_review_queue.csv"


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    staged = json.loads((RUN / "staging_review_eae.json").read_text(encoding="utf-8"))
    events = {str(row["eventId"]): row for row in staged}
    articles = {str(row["articleId"]): row for row in jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(row["articleId"]): row for row in jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    prepared = {aid: prepare_extraction_input(article, enriched.get(aid)).text for aid, article in articles.items()}
    paths = read_csv(AUDIT / "event_path_coverage.csv")
    args = read_csv(AUDIT / "event_argument_linking_audit.csv")
    matched = [row for row in paths if row["pathStatus"] == "MATCHED"]
    matched_event_ids = {row["eventId"] for row in matched}
    argument_by_event_uri = defaultdict(list)
    for row in args:
        if row["linkStatus"] == "LINKED_TO_TRIGGER":
            argument_by_event_uri[(row["eventId"], row["resolvedUri"])].append(row)

    output = []

    def article_info(aid):
        article = articles.get(str(aid), {})
        return article.get("title", ""), article.get("url", ""), article

    def add_event(event_id, sample_kind, path_row=None, review_prompt=""):
        event = events[event_id]
        aid = str(event["articleId"])
        title, url, article = article_info(aid)
        trigger = event.get("trigger", {})
        evd = event.get("evidence", {})
        argument = {}
        if path_row:
            candidates = argument_by_event_uri.get((event_id, path_row.get("entityUri", "")), [])
            argument = next((candidate for candidate in candidates
                             if candidate.get("resolvedUri") == path_row.get("entityUri")), {})
            if not argument:
                # Preserve the candidate path for reviewer attention even when argument audit details are unavailable.
                argument = {}
        else:
            candidate_args = [row for row in args if row["eventId"] == event_id]
            argument = next((row for row in candidate_args if row.get("linkStatus") == "UNRESOLVED_ENTITY"),
                            candidate_args[0] if candidate_args else {})
        reason = (path_row or {}).get("reason", "No complete path found for this staged event.")
        output.append({
            "sampleKind": sample_kind,
            "articleId": aid,
            "articleTitle": title,
            "sourceUrl": url,
            "eventId": event_id,
            "eventType": event.get("eventType", ""),
            "trigger": trigger.get("text", ""),
            "triggerStart": trigger.get("startChar", ""),
            "triggerEnd": trigger.get("endChar", ""),
            "evidenceId": evd.get("evidenceId", ""),
            "evidenceText": evd.get("evidenceText", ""),
            "entityMention": argument.get("argumentText", ""),
            "mentionType": argument.get("mentionType", ""),
            "argumentRole": argument.get("argumentRole", ""),
            "argumentConfidence": argument.get("argumentConfidence", ""),
            "entityUri": (path_row or {}).get("entityUri", "") or argument.get("resolvedUri", ""),
            "path": (path_row or {}).get("path", ""),
            "pathStatus": (path_row or {}).get("pathStatus", "NO_COMPLETE_PATH"),
            "intermediateNodeUris": (path_row or {}).get("intermediateNodeUris", ""),
            "candidateStockUris": (path_row or {}).get("candidateStockUris", ""),
            "eventEntityEvidence": (path_row or {}).get("eventToEntityEvidence", ""),
            "temporalCondition": (path_row or {}).get("temporalCondition", ""),
            "reasoningPath": reason,
            "reviewPrompt": review_prompt,
            "reviewDecision": "",
            "reviewerComment": "",
            "reviewOptions": "CORRECT|INCORRECT|UNCERTAIN",
            "articleExcerpt": "",
        })

    # All Events with a complete path in the updated resolver audit (includes the original 24).
    for path_row in matched:
        add_event(path_row["eventId"], "EVENT_WITH_KG_PATH", path_row,
                  "Check whether event, participant, argument role, URI and every KG edge are supported by the source evidence.")

    # Include every distinct event blocked by one of the few concrete KG-relation/time blockers.
    blocked_ids = []
    by_event = defaultdict(list)
    for row in paths:
        by_event[row["eventId"]].append(row)
    for event_id, rows in by_event.items():
        if event_id not in matched_event_ids and any(row["pathStatus"] in {"MISSING_RELATION", "INSUFFICIENT_EVIDENCE"} for row in rows):
            blocked_ids.append(event_id)
    for event_id in blocked_ids:
        rows = by_event[event_id]
        row = next((r for r in rows if r["pathStatus"] in {"MISSING_RELATION", "INSUFFICIENT_EVIDENCE"}), rows[0])
        add_event(event_id, "NO_PATH_RELATION_OR_TIME_BLOCKER", row,
                  "Check whether the extracted participant is correct and whether the stated KG relation/time blocker is real.")

    # Select eight no-path/no-participant Events, spread deterministically across the saved event list.
    no_path_ids = [str(row["eventId"]) for row in staged
                   if row["eventId"] not in matched_event_ids and str(row["eventId"]) not in blocked_ids]
    take = min(8, len(no_path_ids))
    selected_no_path = [no_path_ids[round(i * (len(no_path_ids)-1) / max(1, take-1))] for i in range(take)] if take else []
    no_path_sample_count = len(selected_no_path)
    for event_id in selected_no_path:
        add_event(event_id, "NO_PATH_NO_LINKED_PARTICIPANT", None,
                  "Check for false positive Event/argument, missed entity resolution, or an actually absent participant.")

    # Ten systematic, spread-out examples from articles for which saved ED produced no Event.
    event_article_ids = {str(event["articleId"]) for event in staged}
    no_event_articles = [article for article in articles.values() if str(article["articleId"]) not in event_article_ids]
    no_event_articles.sort(key=lambda row: (str(row.get("publishedAt", "")), str(row.get("articleId", ""))))
    take = min(10, len(no_event_articles))
    selected_articles = [no_event_articles[round(i * (len(no_event_articles)-1) / max(1, take-1))] for i in range(take)] if take else []
    for article in selected_articles:
        aid = str(article["articleId"])
        text = prepared.get(aid, "")
        excerpt = " ".join(text.split())[:900]
        output.append({
            "sampleKind": "ARTICLE_WITH_NO_PREDICTED_EVENT",
            "articleId": aid,
            "articleTitle": article.get("title", ""),
            "sourceUrl": article.get("url", ""),
            "eventId": "", "eventType": "", "trigger": "", "triggerStart": "", "triggerEnd": "",
            "evidenceId": "", "evidenceText": "", "entityMention": "", "mentionType": "", "argumentRole": "",
            "argumentConfidence": "", "entityUri": "", "path": "", "pathStatus": "NO_PREDICTED_EVENT",
            "intermediateNodeUris": "", "candidateStockUris": "", "eventEntityEvidence": "", "temporalCondition": "",
            "reasoningPath": "No ED Event was stored for this article; inspect for a missed event in the title/text.",
            "reviewPrompt": "Is there a BKEE-scope event with an identifiable trigger in this article?",
            "reviewDecision": "", "reviewerComment": "", "reviewOptions": "CORRECT|INCORRECT|UNCERTAIN",
            "articleExcerpt": excerpt,
        })

    fields = list(output[0]) if output else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(output)
    guide = OUT.with_suffix(".README.md")
    guide.write_text(
        "# Entity Linking and false-negative review queue\n\n"
        f"Rows: {len(output)}. Includes every {len(matched_event_ids)} Event with a complete path in the updated audit, "
        f"{len(blocked_ids)} additional relation/time-blocked Events, {no_path_sample_count} spread-out Events without a complete path/linked participant, "
        f"and {len(selected_articles)} articles with no saved ED Event. This is a review set, not a representative sample of all predictions.\n\n"
        "For each row, choose `CORRECT`, `INCORRECT`, or `UNCERTAIN` in `reviewDecision`; add reasons in `reviewerComment`. "
        "The review queue does not approve or write any prediction. `EVENT_WITH_KG_PATH` rows contain the complete audited path nodes, "
        "evidence and temporal condition. No-event rows include a text excerpt for false-negative review.\n",
        encoding="utf-8")
    print(json.dumps({"reviewRows": len(output), "pathEvents": len(matched_event_ids), "relationOrTimeBlockers": len(blocked_ids),
                      "noPathSamples": no_path_sample_count, "noPredictedEventArticles": len(selected_articles), "path": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
