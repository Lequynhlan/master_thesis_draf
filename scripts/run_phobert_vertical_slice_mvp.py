"""Run a small, fresh PhoBERT -> Entity/Stock -> market-reaction MVP.

This is intentionally a staging experiment. It reads existing project inputs and
checkpoints and writes only to a new run directory; it never updates the main KG.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rdflib import Graph, Namespace, URIRef  # noqa: E402

from wfkg.config import load_config  # noqa: E402
from wfkg.event_processing import PhoBERTEventExtractor  # noqa: E402
from wfkg.event_processing.candidates import generate_candidates  # noqa: E402
from wfkg.event_processing.extraction import ExtractorConfig  # noqa: E402
from wfkg.event_processing.effective_trading_date import (  # noqa: E402
    HoseTradingCalendar,
    resolve_effective_trading_date,
)
from wfkg.event_processing.kg_entity_resolution import build_index, resolve_mention  # noqa: E402
from wfkg.market_reaction.job import calculate_car  # noqa: E402

WF = Namespace("https://example.org/wfkg/v1#")
SELECTION_REASON = (
    "Selected from the fixed 100-article cohort using bank/company names in title/body; "
    "selection is for execution coverage, not a gold label or relevance judgment."
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference-input", default="runs/phobert_vertical_slice_mvp_20261020_v1/fresh_phobert_inference.json")
    parser.add_argument("--output", default="runs/phobert_vertical_slice_mvp_20261020_v1")
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if ROOT not in out.parents:
        raise ValueError("Output directory must stay inside the project.")
    inference_path = (ROOT / args.inference_input).resolve()
    if not inference_path.is_file():
        raise FileNotFoundError(f"Fresh inference artifact not found: {inference_path}")
    if out.exists() and (out / "run_manifest.json").exists():
        raise FileExistsError(f"Refusing to overwrite completed run directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    cohort_manifest_path = ROOT / "data/output/news_article_selection_manifest.json"
    raw_path = ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl"
    enriched_path = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
    kg_path = ROOT / "data/gold/knowledge_graph.ttl"
    alias_path = ROOT / "data/external/verified_entity_aliases.json"
    timestamp_path = ROOT / "data/derived/news_timestamp_trust_audit.json"
    calendar_path = ROOT / "config/hose_trading_calendar_2026.json"
    market_dir = ROOT / "runs/wfkg_vertical_slice_news_100_release_v1/snapshot/data/raw/daily/market_observations/20261017T023853Z"
    config_path = ROOT / "config/vertical_slice.yaml"

    inference_artifact = json.loads(inference_path.read_text(encoding="utf-8-sig"))
    if inference_artifact.get("schemaVersion") != "phobert_mvp_fresh_inference_v1":
        raise ValueError("Wrong inference artifact schema; saved cohort outputs are not accepted here.")
    fresh_rows = {str(row["articleId"]): row for row in inference_artifact.get("articles", [])}
    selected_manifest = json.loads(cohort_manifest_path.read_text(encoding="utf-8-sig"))
    cohort_rows = {str(row["articleId"]): row for row in selected_manifest["articles"]}
    raw = {str(row["articleId"]): row for row in read_jsonl(raw_path)}
    enriched = {str(row["articleId"]): row for row in read_jsonl(enriched_path)}
    selected_ids = [aid for aid in fresh_rows if aid in cohort_rows and aid in raw and aid in enriched]
    if not selected_ids:
        raise RuntimeError("No fresh inference rows could be joined to the selected cohort and source text.")

    graph = Graph().parse(kg_path, format="turtle")
    entity_index, alias_index = build_index(graph, alias_path)
    calendar = HoseTradingCalendar.load(calendar_path)
    timestamp_audit = json.loads(timestamp_path.read_text(encoding="utf-8-sig"))
    timestamp_by_article = timestamp_audit.get("sources", {})
    market_manifest = json.loads((market_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    ticker_series: dict[str, dict[date, Decimal]] = {}
    for ticker in ("ACB", "BID", "CTG", "HDB", "LPB", "MBB", "SHB", "SSB", "STB", "TCB", "VCB", "VIB", "VPB", "VNINDEX"):
        market_doc = json.loads((market_dir / f"{ticker}.json").read_text(encoding="utf-8-sig"))
        ticker_series[ticker] = {
            date.fromisoformat(row["time"][:10]): Decimal(str(row["close"]))
            for row in market_doc.get("rawRows", [])
        }
    sessions = sorted(set.intersection(*(set(values) for values in ticker_series.values())))

    project_config = load_config(config_path)
    base = project_config.values.get("extractor", {})
    extractor_config = ExtractorConfig(
        model_id=str(base.get("model_id", "vinai/phobert-base-v2")),
        checkpoint_path=ROOT / str(base.get("checkpoint_path", "models/phobert_bkee_event_detection_v2")),
        label_mapping_path=ROOT / str(base.get("label_mapping_path", "models/phobert_bkee_event_detection_v2/label_mapping.json")),
        model_version=str(base.get("model_version", "bkee-bio-dev-selected-v2")),
        short_body_review_chars=int(base.get("short_body_review_chars", 500)),
        device="cpu",
        entity_checkpoint_path=ROOT / "models/phobert_bkee_emd_v2",
        trigger_conditioned_argument_checkpoint_path=ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1",
    )
    extractor = PhoBERTEventExtractor(extractor_config)  # prepare offsets only; model inference is in the CUDA run.

    article_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []
    argument_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    t0_rows: dict[str, dict[str, Any]] = {}
    for index, article_id in enumerate(selected_ids, 1):
        article = raw[article_id]
        prepared = extractor.prepare_input(article, enriched[article_id])
        base_article = cohort_rows[article_id]
        source_url = str(article.get("url") or base_article.get("url") or "")
        article_out: dict[str, Any] = {
            "articleId": article_id,
            "title": article.get("title", ""),
            "sourceUrl": source_url,
            "publishedAtRaw": article.get("publishedAt"),
            "inputSource": prepared.source,
            "inputStatus": prepared.status,
            "inputSha256": prepared.sha256,
            "inputCharCount": prepared.char_count,
            "selectionReason": inference_artifact.get("selectionReason", SELECTION_REASON),
            "events": fresh_rows[article_id].get("events", []),
            "status": fresh_rows[article_id].get("status", "FAILED"),
        }
        predictions = article_out["events"] if article_out["status"] == "SUCCESS" else []
        if article_out["status"] == "FAILED":
            article_out["error"] = fresh_rows[article_id].get("error", "Inference failed; see fresh_phobert_inference.json")
        article_rows.append(article_out)
        print(f"[{index}/{len(selected_ids)}] {article_id}: {article_out['status']}, events={len(predictions)}", flush=True)

        audited_time = timestamp_by_article.get(article_id, {})
        reliable = str(audited_time.get("reliability", "")).startswith("VERIFIED_SOURCE_PAGE_TIME")
        timestamp_used = audited_time.get("timestampLocal") if reliable else article.get("publishedAt")
        t0 = resolve_effective_trading_date(
            timestamp_used,
            timestamp_reliable=reliable,
            calendar=calendar,
            assume_wall_clock_timezone=False,
        )
        t0_rows[article_id] = {
            **t0,
            "articleId": article_id,
            "timestampClass": audited_time.get("reliability", "UNVERIFIED_RAW_PUBLISHED_AT"),
            "timestampSourceUrl": audited_time.get("sourceUrl", ""),
            "timestampSnapshotPath": audited_time.get("snapshotPath", ""),
            "rawPublishedAt": article.get("publishedAt", ""),
        }

        for prediction in predictions:
            event_id = str(prediction["eventId"])
            evidence_span = prediction["evidenceSpan"]
            evidence_id = "EVIDENCE:" + hashlib.sha256(
                f"{article_id}|{evidence_span['startChar']}|{evidence_span['endChar']}".encode("utf-8")
            ).hexdigest()[:20]
            event_record: dict[str, Any] = {
                **prediction,
                "articleId": article_id,
                "sourceUrl": source_url,
                "title": article.get("title", ""),
                "evidenceId": evidence_id,
                "evidence": {
                    "evidenceId": evidence_id,
                    "evidenceText": evidence_span["text"],
                    "startOffset": evidence_span["startChar"],
                    "endOffset": evidence_span["endChar"],
                    "offsetBasis": "PhoBERT prepared title+selected body input",
                    "sourceTextSha256": prepared.sha256,
                    "extractedFrom": article_id,
                    "sourceUrl": source_url,
                },
                "relationPaths": [],
                "effectiveTradingDate": t0.get("effectiveTradingDate"),
                "t0Status": t0.get("status"),
                "reviewStatus": "REVIEW_REQUIRED",
            }
            mention_resolution: dict[str, dict[str, Any]] = {}
            for mention in prediction.get("entityMentions", []):
                resolved = resolve_mention(mention, entity_index, alias_index, context=prepared.text)
                mention_id = str(mention.get("mentionId", ""))
                mention_resolution[mention_id] = resolved
                mention_rows.append({
                    "articleId": article_id, "eventId": event_id, "evidenceId": evidence_id,
                    "sourceUrl": source_url, "mentionId": mention_id,
                    "text": mention.get("text", ""), "entityType": mention.get("entityType", ""),
                    "startChar": mention.get("startChar"), "endChar": mention.get("endChar"),
                    "spanVerified": bool(prepared.text[int(mention["startChar"]):int(mention["endChar"])] == mention.get("text")) if isinstance(mention.get("startChar"), int) and isinstance(mention.get("endChar"), int) else False,
                    "resolverStatus": resolved.get("status"), "entityUri": resolved.get("uri"),
                    "resolutionMethod": resolved.get("method"), "reason": resolved.get("reason"),
                    "nearCandidates": json.dumps(resolved.get("candidates", []), ensure_ascii=False),
                    "reviewStatus": "REVIEW_REQUIRED",
                })
            for argument in prediction.get("argumentMentions", []):
                mention = argument.get("entityMention") or {}
                mention_id = str(argument.get("entityMentionId") or mention.get("mentionId") or "")
                resolution = mention_resolution.get(mention_id, {"status": "UNRESOLVED", "uri": None, "reason": "NO_EXACT_EMD_MENTION_ID"})
                compatible_participant = (
                    argument.get("triggerLinkStatus") == "LINKED_TO_TRIGGER"
                    and argument.get("eventRoleCompatible") is True
                    and argument.get("entityRoleCompatible") is True
                    and mention_id
                    and resolution.get("status") == "MATCHED"
                )
                argument_row = {
                    "articleId": article_id, "eventId": event_id, "evidenceId": evidence_id,
                    "sourceUrl": source_url, "trigger": prediction["trigger"]["text"],
                    "eventType": prediction["eventType"], "argumentText": argument.get("text", ""),
                    "role": argument.get("role", ""), "entityMentionId": mention_id,
                    "entityUri": resolution.get("uri"), "resolverStatus": resolution.get("status"),
                    "startChar": argument.get("startChar"), "endChar": argument.get("endChar"),
                    "triggerLinkStatus": argument.get("triggerLinkStatus"),
                    "participantEligible": bool(compatible_participant),
                    "reviewStatus": "REVIEW_REQUIRED",
                }
                argument_rows.append(argument_row)
                if not compatible_participant:
                    continue
                company_uri = str(resolution["uri"])
                company_types = set(entity_index.get(company_uri, {}).get("types", []))
                if not company_types.intersection({"Company", "Bank"}):
                    continue
                for stock_uri in graph.objects(URIRef(company_uri), WF.hasStock):
                    ticker = str(stock_uri).rsplit(":", 1)[-1]
                    if ticker not in ticker_series:
                        continue
                    path_evidence = {
                        "articleId": article_id,
                        "evidenceId": evidence_id,
                        "sourceUrl": source_url,
                        "sentenceEvidence": evidence_span["text"],
                        "eventTrigger": prediction["trigger"],
                        "argumentText": argument.get("text", ""),
                        "argumentRole": argument.get("role", ""),
                        "entityMentionId": mention_id,
                        "companyUri": company_uri,
                        "stockUri": str(stock_uri),
                    }
                    event_record["relationPaths"].append({
                        "impactType": "DIRECT", "ticker": ticker,
                        "relationStrength": 1.0,
                        "confidenceScore": float(prediction.get("confidenceScore", 0.0)),
                        "evidence": path_evidence,
                        "companyUri": company_uri,
                        "stockUri": str(stock_uri),
                        "argumentRole": argument.get("role", ""),
                        "entityMentionId": mention_id,
                    })
                    link_rows.append({
                        **argument_row,
                        "companyUri": company_uri,
                        "stockUri": str(stock_uri),
                        "ticker": ticker,
                        "path": "DIRECT",
                        "pathEvidence": json.dumps(path_evidence, ensure_ascii=False),
                    })
            event_rows.append(event_record)

    candidate_events = [
        {**event, "effectiveTradingDate": t0_rows[event["articleId"]].get("effectiveTradingDate")}
        for event in event_rows
    ]
    candidate_records = generate_candidates(candidate_events, (
        "ACB", "BID", "CTG", "HDB", "LPB", "MBB", "SHB", "SSB", "STB", "TCB", "VCB", "VIB", "VPB"
    ))
    event_by_id = {event["eventId"]: event for event in candidate_events}
    candidate_rows: list[dict[str, Any]] = []
    reaction_rows: list[dict[str, Any]] = []
    for candidate in candidate_records:
        event = event_by_id[str(candidate["eventId"])]
        path = next((path for path in event["relationPaths"] if path["ticker"] == candidate["ticker"]), {})
        t0 = t0_rows[event["articleId"]]
        reason = (
            f"PhoBERT predicted {event['eventType']} with trigger '{event['trigger']['text']}'; "
            f"trigger-conditioned argument role {path.get('argumentRole')} linked mention "
            f"{path.get('entityMentionId')} to {path.get('companyUri')}; KG hasStock reaches "
            f"{path.get('stockUri')}. Model relation remains unreviewed."
        )
        candidate_rows.append({
            "candidateId": candidate["candidateId"], "articleId": event["articleId"],
            "sourceUrl": event["sourceUrl"], "eventId": event["eventId"],
            "eventType": event["eventType"], "trigger": event["trigger"]["text"],
            "evidenceId": event["evidenceId"], "evidenceText": event["evidence"]["evidenceText"],
            "argumentText": path.get("evidence", {}).get("argumentText", ""),
            "argumentRole": path.get("argumentRole", ""),
            "entityMentionId": path.get("entityMentionId", ""),
            "companyUri": path.get("companyUri", ""), "stockUri": path.get("stockUri", ""),
            "ticker": candidate["ticker"], "relationPath": "Event → Company → Stock",
            "relationPathType": candidate["impactType"], "relationStrength": candidate["relationStrength"],
            "eventConfidence": candidate["confidenceScore"], "candidateScore": candidate["candidateScore"],
            "candidateReason": reason, "effectiveTradingDate": t0.get("effectiveTradingDate"),
            "t0Status": t0.get("status"), "candidateStatus": "STAGING_REVIEW_REQUIRED",
            "reviewStatus": "REVIEW_REQUIRED",
        })
        if t0.get("status") != "RESOLVED" or not t0.get("effectiveTradingDate"):
            reaction_rows.append({
                "candidateId": candidate["candidateId"], "articleId": event["articleId"],
                "ticker": candidate["ticker"], "effectiveTradingDate": "",
                "status": "NOT_EVALUATED", "reason": "T0_UNRESOLVED_UNVERIFIED_PUBLICATION_TIMESTAMP",
                "CAR_0_3": "", "CAR_1_3": "", "dailyAR": "[]",
            })
            continue
        stock = ticker_series[candidate["ticker"]]
        benchmark = ticker_series["VNINDEX"]
        reaction = calculate_car(stock, benchmark, date.fromisoformat(str(t0["effectiveTradingDate"])), (0, 3), sessions)
        reaction_1_3 = calculate_car(stock, benchmark, date.fromisoformat(str(t0["effectiveTradingDate"])), (1, 3), sessions)
        reaction_rows.append({
            "candidateId": candidate["candidateId"], "articleId": event["articleId"],
            "ticker": candidate["ticker"], "effectiveTradingDate": t0["effectiveTradingDate"],
            "status": reaction["status"], "reason": reaction["reason"],
            "CAR_0_3": str(reaction["car"]) if reaction.get("car") is not None else "",
            "CAR_1_3": str(reaction_1_3["car"]) if reaction_1_3.get("car") is not None else "",
            "dailyAR": json.dumps([str(value) for value in reaction.get("dailyAR", [])]),
        })

    status_counts = Counter(row["status"] for row in article_rows)
    event_type_counts = Counter(row["eventType"] for row in event_rows)
    reaction_counts = Counter(row["status"] for row in reaction_rows)
    checkpoint_dirs = {
        "ED": ROOT / "models/phobert_bkee_event_detection_v2",
        "EMD": ROOT / "models/phobert_bkee_emd_v2",
        "EAE": ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1",
    }
    checkpoint_hashes = {
        name: {
            filename: sha256(folder / filename)
            for filename in ("config.json", "model.safetensors", "label_mapping.json")
            if (folder / filename).is_file()
        }
        for name, folder in checkpoint_dirs.items()
    }
    file_hashes = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in (cohort_manifest_path, raw_path, enriched_path, kg_path, alias_path, timestamp_path, calendar_path, market_dir / "manifest.json", config_path, inference_path)
        if path.is_file()
    }
    file_hashes.update({
        str((market_dir / f"{ticker}.json").relative_to(ROOT)): sha256(market_dir / f"{ticker}.json")
        for ticker in ("ACB", "BID", "CTG", "HDB", "LPB", "MBB", "SHB", "SSB", "STB", "TCB", "VCB", "VIB", "VPB", "VNINDEX")
    })
    (out / "inference_output.json").write_text(json.dumps({"articles": article_rows, "events": event_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "entity_links.json").write_text(json.dumps({"mentions": mention_rows, "arguments": argument_rows, "directPaths": link_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "candidates.json").write_text(json.dumps(candidate_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "market_reactions.json").write_text(json.dumps(reaction_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "timestamp_alignment.json").write_text(json.dumps(t0_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(out / "articles.csv", article_rows, ["articleId", "title", "sourceUrl", "publishedAtRaw", "inputSource", "inputStatus", "inputSha256", "inputCharCount", "status", "error"])
    write_csv(out / "events.csv", [{
        "articleId": row["articleId"], "sourceUrl": row["sourceUrl"], "eventId": row["eventId"],
        "eventType": row["eventType"], "trigger": row["trigger"]["text"],
        "confidence": row["confidenceScore"], "evidenceId": row["evidenceId"],
        "evidenceText": row["evidence"]["evidenceText"], "evidenceStart": row["evidence"]["startOffset"],
        "evidenceEnd": row["evidence"]["endOffset"], "argumentCount": len(row["argumentMentions"]),
    } for row in event_rows], ["articleId", "sourceUrl", "eventId", "eventType", "trigger", "confidence", "evidenceId", "evidenceText", "evidenceStart", "evidenceEnd", "argumentCount"])
    write_csv(out / "entity_links.csv", link_rows, ["articleId", "eventId", "evidenceId", "sourceUrl", "trigger", "eventType", "argumentText", "role", "entityMentionId", "entityUri", "resolverStatus", "ticker", "companyUri", "stockUri", "path", "participantEligible", "triggerLinkStatus", "pathEvidence"])
    write_csv(out / "event_stock_candidates.csv", candidate_rows, list(candidate_rows[0]) if candidate_rows else ["candidateId", "articleId", "eventId", "ticker", "candidateScore", "candidateReason"])
    write_csv(out / "market_reactions.csv", reaction_rows, ["candidateId", "articleId", "ticker", "effectiveTradingDate", "status", "reason", "CAR_0_3", "CAR_1_3", "dailyAR"])
    write_csv(out / "timestamp_alignment.csv", list(t0_rows.values()), ["articleId", "status", "effectiveTradingDate", "reason", "publicationTimestampLocal", "timestampClass", "timestampSourceUrl", "timestampSnapshotPath", "ruleId", "cutoffLocal", "timezone", "rawPublishedAt"])

    report = {
        "runId": out.name,
        "status": "COMPLETED_STAGING_ONLY",
        "articleCount": len(article_rows),
        "processedSuccessfully": status_counts["SUCCESS"],
        "failed": status_counts["FAILED"],
        "eventCount": len(event_rows),
        "articlesWithEvents": len({row["articleId"] for row in event_rows}),
        "articlesWithoutEvents": status_counts["SUCCESS"] - len({row["articleId"] for row in event_rows}),
        "eventTypeCounts": dict(event_type_counts),
        "entityMentionCount": len(mention_rows),
        "argumentCount": len(argument_rows),
        "argumentLinkedToTriggerCount": sum(row["triggerLinkStatus"] == "LINKED_TO_TRIGGER" for row in argument_rows),
        "matchedEntityMentionCount": sum(row["resolverStatus"] == "MATCHED" for row in mention_rows),
        "directEventCompanyStockPathCount": len(link_rows),
        "candidateCount": len(candidate_rows),
        "reactionCounts": dict(reaction_counts),
        "timestampStatusCounts": dict(Counter(row.get("status", "UNKNOWN") for row in t0_rows.values())),
        "timestampClassCounts": dict(Counter(row.get("timestampClass", "UNKNOWN") for row in t0_rows.values())),
        "candidateTickerCounts": dict(Counter(row["ticker"] for row in candidate_rows)),
        "reactionReasonCounts": dict(Counter(row["reason"] for row in reaction_rows)),
        "marketDataBatch": market_dir.name,
        "marketLatestTradingDate": max(day.isoformat() for day in sessions),
        "marketDataBatchManifestSha256": sha256(market_dir / "manifest.json"),
        "marketSource": market_manifest.get("sourceCode", ""),
        "marketPriceSemantics": market_manifest.get("priceSemantics", ""),
        "modelCheckpoints": {name: str(folder.relative_to(ROOT)) for name, folder in checkpoint_dirs.items()},
        "checkpointHashes": checkpoint_hashes,
        "inputHashes": file_hashes,
        "freshPhoBERTInference": True,
        "trainingOrCrawlRerun": False,
        "productionKgModified": False,
        "candidateScoreFormula": "candidate_score(event confidence, direct hasStock relation strength); market reaction excluded",
        "argumentRoleCompatibilitySource": "Official BKEE train event_mentions[].arguments; role inventory corrected for BKEE labels; checkpoint unchanged.",
        "deviceRequested": inference_artifact.get("deviceRequested", "unknown"),
        "deviceActual": inference_artifact.get("deviceActual", "unknown"),
        "freshInferenceArtifact": str(inference_path.relative_to(ROOT)),
        "freshInferenceArtifactSha256": sha256(inference_path),
        "selectionReason": SELECTION_REASON,
        "elapsedSeconds": round(time.perf_counter() - started, 2),
        "limitations": [
            "Predictions are BKEE model outputs and require human review; they are not financial-domain gold.",
            "EMD v2 and trigger-conditioned EAE v1 were reused unchanged; no training or crawl occurred.",
            "Only article timestamps independently present in the timestamp-trust audit resolve T0; other RAW publishedAt values are not treated as verified.",
            "Candidate paths are limited to Event → Company/Bank → Stock and remain staging review proposals.",
            "Market reaction uses the frozen KBS market snapshot and will remain unevaluated if T0 is unresolved or the full T0..T+3 window is missing.",
            "A detected Event/argument/path is not evidence that the model prediction is semantically correct.",
        ],
    }
    (out / "run_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_lines = [
        "# PhoBERT Vertical Slice MVP — Run Report", "",
        f"- Articles: {report['processedSuccessfully']}/{report['articleCount']} processed; {report['failed']} failed.",
        f"- Fresh PhoBERT ED/EMD/EAE inference: {report['eventCount']} events in {report['articlesWithEvents']} articles; {report['articlesWithoutEvents']} successful articles had no predicted Event.",
        f"- Mentions: {report['entityMentionCount']}; arguments: {report['argumentCount']} ({report['argumentLinkedToTriggerCount']} linked to a trigger).",
        f"- Entity resolution: {report['matchedEntityMentionCount']} matched mentions; direct Event→Company→Stock paths: {report['directEventCompanyStockPathCount']}.",
        f"- EventStockCandidate proposals: {report['candidateCount']}; reactions: {dict(reaction_counts)}.",
        f"- Device: requested `{report['deviceRequested']}`, actual `{report['deviceActual']}`.",
        "- All candidates and predictions remain staging/review-only; production KG was not modified.", "",
        "## Output files", "",
        "- `inference_output.json`: article, Event, trigger, Evidence, EMD mentions, EAE arguments.",
        "- `entity_links.json` / `entity_links.csv`: URI resolutions and direct paths.",
        "- `event_stock_candidates.csv` / `candidates.json`: scored Candidate proposals and reasons.",
        "- `market_reactions.csv` / `market_reactions.json`: T0 status and AR/CAR result or explicit blocker.",
        "- `timestamp_alignment.json` / `timestamp_alignment.csv`: trusted timestamp source and cutoff result.",
        "- `run_manifest.json`: model/input hashes and run counts.", "",
        "## Limitations", "", *[f"- {item}" for item in report["limitations"]], "",
    ]
    (out / "report.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(json.dumps({
        "runDirectory": str(out), "processed": report["processedSuccessfully"],
        "failed": report["failed"], "events": report["eventCount"],
        "arguments": report["argumentCount"], "matchedMentions": report["matchedEntityMentionCount"],
        "directPaths": report["directEventCompanyStockPathCount"], "candidates": report["candidateCount"],
        "reactionCounts": report["reactionCounts"], "device": report["deviceActual"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
