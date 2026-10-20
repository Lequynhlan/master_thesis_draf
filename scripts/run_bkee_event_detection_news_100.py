"""Run the configured BKEE PhoBERT trigger detector on the fixed 100-article cohort."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from wfkg.config import load_config
from wfkg.event_processing import extractor_from_project_config

RAW_ARTICLES = ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl"
ENRICHED_ARTICLES = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
COHORT_MANIFEST = ROOT / "data/output/news_article_selection_manifest.json"
DEFAULT_OUTPUT = ROOT / "runs/phobert_bkee_event_detection_v2/news_100_final"

FINANCIAL_OVERLAP_TYPES = [
    "Transfer-money", "Transfer-ownership", "Declare-bankruptcy", "Fine", "Sue", "Merge-org",
    "Start-org", "End-org", "Start-position", "End-position", "Elect", "Nominate",
]
UNSUPPORTED_FINANCIAL_TYPES = [
    "earnings/profit/revenue announcements", "dividends and shareholder distributions",
    "capital increase, share issuance, and buybacks", "credit quality, bad debt, and liquidity",
    "interest-rate, lending, and monetary-policy decisions", "investment/project announcements",
    "stock-price movements and market reactions", "credit-rating changes", "most regulatory changes",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/vertical_slice.yaml")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = args.output.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty inference output directory: {output_dir}")
    if not RAW_ARTICLES.is_file() or not ENRICHED_ARTICLES.is_file() or not COHORT_MANIFEST.is_file():
        raise SystemExit("Expected 100-article RAW/enrichment/cohort inputs are missing.")

    cohort = json.loads(COHORT_MANIFEST.read_text(encoding="utf-8"))
    cohort_articles = cohort.get("articles", [])
    cohort_ids = [str(row["articleId"]) for row in cohort_articles]
    raw = read_jsonl(RAW_ARTICLES)
    enriched = read_jsonl(ENRICHED_ARTICLES)
    raw_by_id = {str(row.get("articleId", "")): row for row in raw}
    enriched_by_id = {str(row.get("articleId", "")): row for row in enriched}
    if cohort.get("articleCount") != 100 or len(set(cohort_ids)) != 100:
        raise SystemExit("Cohort manifest does not contain exactly 100 unique article IDs.")
    missing_raw = [article_id for article_id in cohort_ids if article_id not in raw_by_id]
    missing_enriched = [article_id for article_id in cohort_ids if article_id not in enriched_by_id]
    if missing_raw or missing_enriched:
        raise SystemExit(f"Cohort join failed: missing RAW={missing_raw[:3]}, enrichment={missing_enriched[:3]}")

    config = load_config(args.config)
    extractor = extractor_from_project_config(config)
    mapping_path = extractor.config.label_mapping_path
    if not mapping_path or not mapping_path.is_file():
        raise SystemExit(f"Configured label mapping is missing: {mapping_path}")
    label_data = json.loads(mapping_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "event_predictions.jsonl"
    status_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    success_count = 0
    failure_count = 0
    failure_rows = []
    with predictions_path.open("w", encoding="utf-8", newline="\n") as stream:
        for index, article_id in enumerate(cohort_ids, start=1):
            article = raw_by_id[article_id]
            try:
                prepared = extractor.prepare_input(article, enriched_by_id[article_id])
                events = extractor.extract(article, enriched_by_id[article_id])
                success_count += 1
                status_counts[prepared.source] += 1
                for event in events:
                    event_counts[event["eventType"]] += 1
                row = {
                    "articleId": article_id,
                    "url": article.get("url"),
                    "title": prepared.title,
                    "inputSource": prepared.source,
                    "inputStatus": prepared.status,
                    "inputSha256": prepared.sha256,
                    "eventCount": len(events),
                    "events": events,
                    "inferenceStatus": "SUCCESS",
                }
            except Exception as exc:  # preserve a per-article audit trail
                failure_count += 1
                failure_rows.append({"articleId": article_id, "error": f"{type(exc).__name__}: {exc}"})
                row = {"articleId": article_id, "inferenceStatus": "FAILED", "events": [],
                       "error": f"{type(exc).__name__}: {exc}"}
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            print(f"[{index}/100] {article_id}: {row['inferenceStatus']} events={row.get('eventCount', 0)}")

    report = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "task": "BKEE BIO Event Detection; triggers and event types only",
        "cohortId": cohort.get("cohortId"),
        "cohortSize": len(cohort_ids),
        "processedSuccessfully": success_count,
        "failed": failure_count,
        "inputSourceCounts": dict(status_counts),
        "predictedEventCount": sum(event_counts.values()),
        "predictedCountsByBkeeType": dict(sorted(event_counts.items())),
        "bkeeEventTypes": label_data["eventTypes"],
        "bkeeTypesOutsideFinanceTaxonomy": sorted(set(label_data["eventTypes"]) - set(FINANCIAL_OVERLAP_TYPES)),
        "financialEventTypesWithPartialSemanticOverlap": FINANCIAL_OVERLAP_TYPES,
        "financialEventTypesUnsupportedByBkee": UNSUPPORTED_FINANCIAL_TYPES,
        "checkpoint": str(extractor.config.checkpoint_path),
        "modelId": extractor.config.model_id,
        "modelVersion": extractor.config.model_version,
        "testSetUsedForTrainingOrSelection": False,
        "failures": failure_rows,
        "limitations": [
            "BKEE is a general-domain event dataset and its triggers/types do not define the thesis financial event ontology.",
            "Predicted types are trigger-level model outputs; they are not canonical KG Events until reviewed and mapped.",
            "No event arguments, entity linking, duplicate-event canonicalization, or Event-Stock candidates are produced here.",
            "A confidence score is the mean token-class probability over the predicted trigger, not a calibrated event probability.",
            "The fixed 100-article cohort was not used to train or select the model; model quality on finance remains unmeasured.",
        ],
        "nextIntegration": [
            "Convert each prediction and evidence span into an Evidence candidate with article provenance.",
            "Review/map BKEE types to ontology eventType values; add finance-specific labels and annotated data where absent.",
            "Resolve article entities against Company/Bank/Stock/Industry aliases before generating EventStockCandidate routes.",
            "Keep EventStockCandidate confidence separate from post-event AR/CAR reaction weights.",
        ],
    }
    write_json(output_dir / "inference_report.json", report)
    (output_dir / "inference_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"Processed {success_count}/100 articles; predictions={report['predictedEventCount']}; failed={failure_count}")
    print(f"Output: {output_dir}")
    return 0 if failure_count == 0 else 2


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# PhoBERT BKEE Event Detection on the 100 Article Cohort", "",
        f"- Processed successfully: {report['processedSuccessfully']}/{report['cohortSize']}",
        f"- Failures: {report['failed']}",
        f"- Predicted triggers: {report['predictedEventCount']}",
        f"- Checkpoint: `{report['checkpoint']}`",
        "- Training/selection used test set: No", "",
        "## Counts by BKEE event type", "",
    ]
    lines += [f"- `{event_type}`: {count}" for event_type, count in report["predictedCountsByBkeeType"].items()]
    if not report["predictedCountsByBkeeType"]:
        lines.append("- No triggers predicted.")
    lines += ["", "## BKEE label inventory", "", ", ".join(f"`{item}`" for item in report["bkeeEventTypes"]),
              "", "## Partial overlap with finance", "",
              "These BKEE labels can overlap semantically with finance news, but do not constitute a finance event taxonomy:", ""]
    lines += [f"- `{event_type}`" for event_type in report["financialEventTypesWithPartialSemanticOverlap"]]
    lines += ["", "These remaining BKEE labels are outside the finance taxonomy:", ""]
    lines += [f"- `{event_type}`" for event_type in report["bkeeTypesOutsideFinanceTaxonomy"]]
    lines += ["", "## Unsupported finance event types", ""]
    lines += [f"- {event_type}" for event_type in report["financialEventTypesUnsupportedByBkee"]]
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    lines += ["", "## Candidate integration", ""]
    lines += [f"- {item}" for item in report["nextIntegration"]]
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
