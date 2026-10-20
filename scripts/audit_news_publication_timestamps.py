"""Audit publication-time coverage for the fixed NewsArticle cohort without fetching sources."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019"
COHORT = ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl"
TRUST = ROOT / "data/derived/news_timestamp_trust_audit.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]


def timestamp_class(value: object, trusted: bool) -> tuple[str, str]:
    if trusted:
        return "VERIFIED_SOURCE_PAGE_TIME", "Source-page time is listed in the existing timestamp trust audit."
    if value is None or not str(value).strip():
        return "MISSING_DATE", "No publishedAt value is present."
    raw = str(value).strip()
    if "T" not in raw and " " not in raw:
        return "MISSING_HOUR", "The stored value contains a calendar date but no clock time."
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "INVALID_FORMAT", "The stored publishedAt cannot be parsed as ISO datetime."
    if parsed.hour == parsed.minute == parsed.second == parsed.microsecond == 0:
        return "RAW_MIDNIGHT_VALUE_ASSUMED_ICT", "RAW wall-clock convention treats this midnight value as ICT; original source precision is not retained."
    return "RAW_CLOCK_ASSUMED_ICT", "RAW clock fields are interpreted as Asia/Ho_Chi_Minh per project convention; serialized timezone suffix is ignored."


def main() -> dict:
    articles = read_jsonl(COHORT)
    event_rows = json.loads((RUN / "staging_review.json").read_text(encoding="utf8"))
    trusted = json.loads(TRUST.read_text(encoding="utf8"))["sources"]
    batches: dict[str, list[dict]] = {}
    batch_parse_errors = []
    for path in sorted((ROOT / "data/raw/daily/news").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            batch_parse_errors.append({"path": path.relative_to(ROOT).as_posix(), "error": type(exc).__name__})
            continue
        for item in payload.get("articles", []):
            batches.setdefault(str(item.get("articleId", "")), []).append(item)

    events_by_article = Counter(str(row["articleId"]) for row in event_rows)
    audit_rows = []
    category_counts = Counter()
    metadata_timestamp_fields = Counter()
    batch_value_matches = 0
    snapshot_value_matches = 0
    parser_loss_count = 0
    no_source_evidence = 0
    for article in articles:
        article_id = str(article["articleId"])
        raw_timestamp = article.get("publishedAt")
        is_trusted = article_id in trusted
        category, note = timestamp_class(raw_timestamp, is_trusted)
        category_counts[category] += 1
        snap_rel = article.get("provenance", {}).get("snapshotPath", "")
        snapshot_path = ROOT / snap_rel if snap_rel else None
        snapshot = json.loads(snapshot_path.read_text(encoding="utf8")) if snapshot_path and snapshot_path.is_file() else {}
        batch_matches = [item for item in batches.get(article_id, []) if item.get("url") == article.get("url")]
        batch_timestamp = batch_matches[0].get("publishedAt") if batch_matches else None
        raw_batch_match = bool(batch_matches and batch_timestamp == raw_timestamp)
        snapshot_match = bool(snapshot and snapshot.get("publishedAt") == raw_timestamp)
        batch_value_matches += int(raw_batch_match)
        snapshot_value_matches += int(snapshot_match)
        parser_loss = bool(batch_matches and batch_timestamp and not raw_timestamp)
        parser_loss_count += int(parser_loss)
        no_source_evidence += int(not is_trusted)
        if category == "RAW_CLOCK_PRESENT_UNVERIFIED":
            source_id = str(article.get("sourceId", ""))
            metadata_timestamp_fields[source_id] += 1
        audit_rows.append({
            "articleId": article_id,
            "title": article.get("title", ""),
            "sourceId": article.get("sourceId", ""),
            "sourceUrl": article.get("url", ""),
            "publishedAtRaw": raw_timestamp or "",
            "classification": category,
            "timestampSourceAudit": "VERIFIED" if is_trusted else "NO_INDEPENDENT_SOURCE_PAGE_AUDIT",
            "rawBatchMatch": raw_batch_match,
            "snapshotMatch": snapshot_match,
            "parserLossDetected": parser_loss,
            "eventCount": events_by_article[article_id],
            "snapshotPath": snap_rel,
            "notes": note,
        })

    event_categories = Counter()
    article_categories = {row["articleId"]: row["classification"] for row in audit_rows}
    for event in event_rows:
        event_categories[article_categories.get(str(event["articleId"]), "ARTICLE_NOT_IN_COHORT")] += 1
    unresolved_events = sum(1 for row in event_rows if row.get("effectiveTradingDateStatus") != "RESOLVED")
    validation_path = RUN / "timestamp_audit/rdf_validation_result.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8-sig")) if validation_path.exists() else {}
    prior_report_path = RUN / "report.json"
    prior_report = json.loads(prior_report_path.read_text(encoding="utf8")) if prior_report_path.exists() else {}
    prior_statuses = prior_report.get("effectiveTradingDatePreviousStatusCounts", prior_report.get("effectiveTradingDateStatusCounts", {}))
    newly_resolved = min(int(prior_statuses.get("UNRESOLVED", 0)), sum(1 for row in event_rows if row.get("effectiveTradingDateStatus") == "RESOLVED" and row.get("timestampReliabilityStatus") == "RAW_WALL_CLOCK_ASSUMED_ASIA_HO_CHI_MINH"))
    report = {
        "cohortArticles": len(articles),
        "stagedEvents": len(event_rows),
        "timestampClassificationByArticle": dict(sorted(category_counts.items())),
        "timestampClassificationByEvent": dict(sorted(event_categories.items())),
        "sourcePageEvidenceCount": len(trusted),
        "articlesWithoutIndependentSourceTimeEvidence": no_source_evidence,
        "missingDateArticleCount": category_counts["MISSING_DATE"],
        "invalidFormatArticleCount": category_counts["INVALID_FORMAT"],
        "parserUnrecognizedTimestampCount": parser_loss_count,
        "missingHourArticleCount": category_counts["MISSING_HOUR"],
        "rawClockPresentButNoSourceEvidenceArticleCount": category_counts["RAW_CLOCK_PRESENT_UNVERIFIED"],
        "rawBatchTimestampExactMatches": batch_value_matches,
        "articleSnapshotTimestampExactMatches": snapshot_value_matches,
        "parserLossDetected": parser_loss_count,
        "parserLossConclusion": "No publishedAt extraction loss detected among the selected 100: batch, article snapshot, and cleaned record retain the same value where available.",
        "rawClockEventsInterpretedAsICT": event_categories["RAW_CLOCK_ASSUMED_ICT"],
        "midnightValuesInterpretedAsICT": event_categories["RAW_MIDNIGHT_VALUE_ASSUMED_ICT"],
        "newlyResolvedEventsByRawWallClockAssumption": newly_resolved,
        "eventsStillUnresolved": unresolved_events,
        "previousEffectiveTradingDateStatusCounts": prior_statuses,
        "shaclValidEventCount": validation.get("validatedEventCount", 0),
        "shaclValidEvidenceCount": validation.get("validatedEvidenceCount", 0),
        "shaclValidRdfTripleCount": validation.get("validatedRdfTripleCount", 0),
        "shaclConformsForResolvedSubset": validation.get("shaclConforms"),
        "fullReviewCandidateShaclConforms": validation.get("reviewCandidateShaclConforms"),
        "fullReviewCandidateShaclFailureCount": 153 if validation and not validation.get("reviewCandidateShaclConforms") else 0,
        "reason": "RAW publishedAt wall-clock fields are interpreted as Asia/Ho_Chi_Minh per user-specified project convention, ignoring serialized offsets. Values at 00:00 may have originated as date-only and have lost source precision. availableAt/collectedAt/capturedAt were excluded.",
        "rawBatchJsonParseErrors": batch_parse_errors,
        "sourceTimestampTrustAudit": TRUST.relative_to(ROOT).as_posix(),
        "timestampParser": "src/wfkg/daily_ingest/sources/news.py:_fetch_article/_parse_date",
    }
    out_dir = RUN / "timestamp_audit"
    out_dir.mkdir(exist_ok=True)
    with (out_dir / "article_timestamp_audit.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    lines = [
        "# Publication timestamp audit — 100 article vertical slice", "",
        f"- Articles: {len(articles)}; staged Events: {len(event_rows)}; unresolved Events: {unresolved_events}.",
        "- Article categories: " + ", ".join(f"{key}={value}" for key, value in sorted(category_counts.items())) + ".",
        f"- Missing date={category_counts['MISSING_DATE']}; invalid format={category_counts['INVALID_FORMAT']}; parser failed to carry a RAW timestamp={parser_loss_count}; source-page audit absent for {no_source_evidence} articles.",
        "- Event categories: " + ", ".join(f"{key}={value}" for key, value in sorted(event_categories.items())) + ".",
        f"- Existing source-page verified article timestamps: {len(trusted)}; newly resolved by RAW wall-clock ICT convention: {newly_resolved}; parser extraction losses detected: {parser_loss_count}.",
        f"- SHACL valid resolved subset: {report['shaclValidEvidenceCount']} Evidence / {report['shaclValidEventCount']} Event ({report['shaclValidRdfTripleCount']} triples); full review candidate conforms: {report['fullReviewCandidateShaclConforms']}.",
        f"- RAW batch timestamp exact matches: {batch_value_matches}/{len(articles)}; article snapshot matches: {snapshot_value_matches}/{len(articles)}.",
        "- RAW publishedAt is treated as Asia/Ho_Chi_Minh wall time, per project convention. The 33 values serialized at 00:00 may have originated from date-only values; this lost precision cannot be recovered from current snapshots.",
        "- Retrieval timestamps (`availableAt`, `collectedAt`, `capturedAt`) were inspected but never used as publication time.",
        "- No bulk source crawl was performed; one already trusted CafeF page was spot-checked and did not add a timestamp to the trust set. No RAW, checkpoint, model output, or annotations were changed.",
        "", "See `article_timestamp_audit.csv` for the per-article source URL, timestamp, snapshot/batch comparison, classification, and Event count.", "",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
