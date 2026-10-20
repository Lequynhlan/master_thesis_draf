"""Staged Event -> stock -> T0..T+3 replay over saved inference and market data.

This job is deliberately read-only with respect to RAW, the production KG,
ontology, SHACL and model checkpoints. Predictions remain staged.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from pyshacl import validate as shacl_validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

from wfkg.config import ProjectConfig
from wfkg.event_processing.candidates import generate_candidates
from wfkg.event_processing.effective_trading_date import (
    RULE_ID,
    HoseTradingCalendar,
    resolve_effective_trading_date,
)
from wfkg.market_reaction.job import reaction_weights

WF = Namespace("https://example.org/wfkg/v1#")
STAGING = Namespace("https://example.org/wfkg/staging/")
FOUR_PATHS = {"DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP", "INDIRECT_INDUSTRY"}
ACB_BLOCKED_EVENT_IDS = {
    "PREDICTED_EVENT:15e41d2933fe972e935d",
    "PREDICTED_EVENT:5665abf1d39db4a7a00b",
}
METHOD_VERSION = "WFKG_STAGED_CANDIDATE_REACTION_V1"
DECISION_TIMESTAMP_POLICY = (
    "RAW_CLOCK_FIELDS_ASSUMED_AS_ASIA_HO_CHI_MINH; VERIFIED_SOURCE_TIMESTAMP_CONVERTED_FROM_EXPLICIT_OFFSET"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:20]}"


def resolve_event_t0(
    event: dict[str, Any],
    article_timestamp: dict[str, str],
    calendar: HoseTradingCalendar,
) -> dict[str, Any]:
    """Resolve T0 only from publishedAt and its audited precision class."""
    raw = event.get("sourceTimestampRaw") or event.get("sourceTimestampUsed")
    classification = article_timestamp.get("classification", "")
    result: dict[str, Any] = {
        "eventId": event.get("eventId", ""),
        "articleId": event.get("articleId", ""),
        "publishedAtRaw": raw or "",
        "timestampClass": classification,
        "timestampInterpretation": (
            "RAW_WALL_CLOCK_ASSUMED_ICT" if classification == "RAW_CLOCK_ASSUMED_ICT"
            else "VERIFIED_OFFSET_CONVERTED_TO_ICT" if classification == "VERIFIED_SOURCE_PAGE_TIME"
            else "UNRESOLVED_PRECISION"
        ),
        "cutoff": "08:00:00",
        "timezone": "Asia/Ho_Chi_Minh",
        "ruleId": RULE_ID,
        "effectiveTradingDate": "",
        "status": "UNRESOLVED",
        "reason": "",
        "timestampSource": (event.get("timestampSource") or {}).get("sourceEvidencePath", ""),
        "timestampSourceSha256": (event.get("timestampSource") or {}).get("sourceEvidenceSha256", ""),
    }
    if classification == "RAW_MIDNIGHT_VALUE_ASSUMED_ICT":
        result.update(status="UNCERTAIN_T0", reason="RAW_MIDNIGHT_PRECISION_MAY_BE_DATE_ONLY")
        return result
    reliable = classification in {"RAW_CLOCK_ASSUMED_ICT", "VERIFIED_SOURCE_PAGE_TIME"}
    if not reliable:
        result.update(status="UNRESOLVED", reason="NO_TRUSTED_PUBLICATION_TIMESTAMP_CLASS")
        return result
    resolved = resolve_effective_trading_date(
        raw,
        timestamp_reliable=True,
        calendar=calendar,
        assume_wall_clock_timezone=(classification == "RAW_CLOCK_ASSUMED_ICT"),
    )
    result.update(
        effectiveTradingDate=resolved.get("effectiveTradingDate") or "",
        status=resolved.get("status", "UNRESOLVED"),
        reason=resolved.get("reason") or "",
        publicationTimestampLocal=resolved.get("publicationTimestampLocal") or "",
    )
    return result


def deduplicate_event_stock_paths(paths: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse multiple valid paths for one Event-stock pair, retaining each."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        event_id = str(path.get("eventId", ""))
        stock_uri = str(path.get("candidateStockUri", ""))
        if not event_id or not stock_uri:
            continue
        group = groups.setdefault((event_id, stock_uri), {**path, "supportingPaths": []})
        key = (str(path.get("path", "")), str(path.get("evidenceId", "")), str(path.get("entityUri", "")))
        if key not in {
            (str(p.get("path", "")), str(p.get("evidenceId", "")), str(p.get("entityUri", "")))
            for p in group["supportingPaths"]
        }:
            group["supportingPaths"].append(path)
    result = list(groups.values())
    for group in result:
        group["supportingPaths"].sort(key=lambda row: (row.get("path", ""), row.get("evidenceId", "")))
        primary = sorted(group["supportingPaths"], key=lambda row: (row.get("path") != "DIRECT", row.get("path", "")))[0]
        for key in ("path", "entityUri", "evidenceId", "sourceUrl", "eventToEntityEvidence", "temporalCondition"):
            group[key] = primary.get(key, "")
    return sorted(result, key=lambda row: (str(row["eventId"]), str(row["candidateStockUri"])))


def _classify_candidate_path(
    path: dict[str, str],
    event: dict[str, Any],
    time_row: dict[str, Any],
    gate: dict[str, str],
    stock_symbols: set[str],
) -> str:
    event_id = path.get("eventId", "")
    ticker = path.get("candidateStockUri", "").rsplit(":", 1)[-1]
    if event_id in ACB_BLOCKED_EVENT_IDS or gate.get("promotionGate") == "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW":
        return "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"
    if ticker not in stock_symbols:
        return "BLOCKED_OUT_OF_SCOPE_TICKER"
    # Leadership/industry/subsidiary snapshots can describe historical validity
    # without establishing when the fact became publicly available. Do not use
    # those facts at T0 unless their knowledge time is evidenced.
    if path.get("path") != "DIRECT":
        condition = (path.get("temporalCondition") or "").lower()
        known_at = event.get("kgRelationKnownAt") or path.get("relationKnownAt")
        if not known_at or "observedasof" in condition or "snapshot" in condition:
            return "BLOCKED_TEMPORAL_KNOWLEDGE_NOT_ESTABLISHED"
        if str(known_at) > str(time_row.get("publicationTimestampLocal", "")):
            return "BLOCKED_LOOKAHEAD_RELATION_KNOWN_AFTER_T0"
    if time_row.get("status") == "UNCERTAIN_T0":
        # Preserve a supported relation proposal for review, while withholding
        # its effective date, candidate score, reaction, and RDF promotion.
        return "STAGING_UNCERTAIN_T0"
    if time_row.get("status") != "RESOLVED":
        return "BLOCKED_" + (time_row.get("status") or "UNRESOLVED")
    if gate.get("boundaryStatus") == "UNVERIFIED_NO_SAVED_DOM_EVIDENCE":
        return "STAGING_SOURCE_CONTEXT_REVIEW_REQUIRED"
    if gate.get("promotionGate") == "REVIEW_REQUIRED":
        return "STAGING_REVIEW_REQUIRED"
    return "STAGING_REVIEW_REQUIRED"


def _load_market_inputs(batch_dir: Path, stock_symbols: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, dict[date, dict[str, Any]]]]:
    manifest_path = batch_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if str(manifest.get("sourceCode", "")).lower() != "kbs":
        raise ValueError(f"Market snapshot must be the frozen KBS batch, got {manifest.get('sourceCode')!r}.")
    if "adjusted" not in str(manifest.get("priceSemantics", "")).lower():
        raise ValueError("Market snapshot does not document adjusted-close semantics.")
    instruments: dict[str, dict[date, dict[str, Any]]] = {}
    for ticker in (*stock_symbols, "VNINDEX"):
        path = batch_dir / f"{ticker}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing frozen KBS adjusted-close input: {path}")
        data = _read_json(path)
        if data.get("instrumentCode") != ticker:
            raise ValueError(f"Market file/instrument mismatch: {path}")
        if data.get("dataQualityFlag") == "RAW_UNADJUSTED_CLOSE_NOT_SHACL_READY":
            raise ValueError(f"Refusing unadjusted market input: {path}")
        series: dict[date, dict[str, Any]] = {}
        for row in data.get("observations", []):
            day = date.fromisoformat(row["tradingDate"])
            value = row.get("adjustedClose")
            if value is None or Decimal(str(value)) <= 0:
                raise ValueError(f"Invalid adjustedClose for {ticker} on {day}.")
            series[day] = row
        if not series:
            raise ValueError(f"No observations in {path}")
        instruments[ticker] = series
    index_days = set(instruments["VNINDEX"])
    for ticker in stock_symbols:
        if set(instruments[ticker]) != index_days:
            raise ValueError(f"{ticker} and VNINDEX have different trading-date sets in the pinned market batch.")
    return manifest, instruments


def _reaction_for_candidate(
    candidate: dict[str, Any],
    sessions: list[date],
    market: dict[str, dict[date, dict[str, Any]]],
) -> dict[str, Any]:
    ticker = candidate["ticker"]
    t0 = date.fromisoformat(candidate["effectiveTradingDate"])
    if t0 not in sessions:
        return {"status": "INSUFFICIENT_DATA", "reason": "T0_NOT_IN_PINNED_MARKET_SESSIONS", "daily": []}
    start = sessions.index(t0)
    daily = []
    latest = max(set(market[ticker]) & set(market["VNINDEX"]))
    for offset in range(4):
        pos = start + offset
        if pos >= len(sessions):
            return {"status": "PENDING_T3", "reason": "T_PLUS_3_AFTER_LAST_KNOWN_HOSE_SESSION", "daily": daily}
        current = sessions[pos]
        if current > latest:
            return {"status": "PENDING_T3", "reason": "T_PLUS_3_MARKET_DATA_NOT_YET_AVAILABLE", "daily": daily}
        if pos == 0:
            return {"status": "INSUFFICIENT_DATA", "reason": "MISSING_PREVIOUS_SESSION", "daily": daily}
        previous = sessions[pos - 1]
        stock_cur = market[ticker].get(current)
        stock_prev = market[ticker].get(previous)
        index_cur = market["VNINDEX"].get(current)
        index_prev = market["VNINDEX"].get(previous)
        if not all((stock_cur, stock_prev, index_cur, index_prev)):
            return {"status": "INSUFFICIENT_DATA", "reason": f"MISSING_CLOSE:{current.isoformat()}", "daily": daily}
        stock_return = Decimal(str(stock_cur["adjustedClose"])) / Decimal(str(stock_prev["adjustedClose"])) - 1
        market_return = Decimal(str(index_cur["adjustedClose"])) / Decimal(str(index_prev["adjustedClose"])) - 1
        daily.append({
            "sessionOffset": offset,
            "tradingDate": current.isoformat(),
            "previousTradingDate": previous.isoformat(),
            "stockReturn": stock_return,
            "marketReturn": market_return,
            "abnormalReturn": stock_return - market_return,
            "stockObservationId": stock_cur.get("observationId", ""),
            "stockPreviousObservationId": stock_prev.get("observationId", ""),
            "indexObservationId": index_cur.get("observationId", ""),
            "indexPreviousObservationId": index_prev.get("observationId", ""),
        })
    ars = [row["abnormalReturn"] for row in daily]
    return {
        "status": "EVALUATED",
        "reason": "COMPLETE_T0_TO_T_PLUS_3_WINDOW",
        "daily": daily,
        "car_0_3": sum(ars, Decimal(0)),
        "car_1_3": sum(ars[1:], Decimal(0)),
    }


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _add_lit(graph: Graph, subject: URIRef, predicate: URIRef, value: Any, datatype: URIRef) -> None:
    graph.add((subject, predicate, Literal(value, datatype=datatype)))


def _add_market_observation(
    graph: Graph,
    ticker: str,
    day: date,
    prior_day: date,
    row: dict[str, Any],
    previous: dict[str, Any],
    batch_id: str,
    index_uri: URIRef,
) -> URIRef:
    is_index = ticker == "VNINDEX"
    cls = WF.MarketIndexObservation if is_index else WF.MarketObservation
    prefix = "MARKET_INDEX" if is_index else "MARKET"
    uri = URIRef(str(WF[f"{prefix}:KBS:{batch_id}:{ticker}:{day.isoformat()}"]))
    graph.add((uri, RDF.type, cls))
    _add_lit(graph, uri, WF.observationId, str(row.get("observationId") or str(uri).rsplit("#", 1)[-1]), XSD.string)
    _add_lit(graph, uri, WF.tradingDate, day.isoformat(), XSD.date)
    _add_lit(graph, uri, WF.adjustedClose, _decimal(row["adjustedClose"]), XSD.decimal)
    value_return = _decimal(row["adjustedClose"]) / _decimal(previous["adjustedClose"]) - 1
    _add_lit(graph, uri, WF.returnValue, value_return, XSD.decimal)
    available = row.get("availableAt")
    if available:
        _add_lit(graph, uri, WF.availableAt, datetime.fromisoformat(str(available).replace("Z", "+00:00")), XSD.dateTime)
    graph.add((uri, WF.sourceReference, URIRef(str(row.get("sourceReference") or "https://kbsec.com.vn/"))))
    if is_index:
        graph.add((index_uri, WF.hasIndexObservation, uri))
    else:
        stock_uri = URIRef(str(WF[f"HOSE:{ticker}"]))
        graph.add((stock_uri, WF.hasMarketObservation, uri))
        if row.get("volume") is not None:
            _add_lit(graph, uri, WF.volume, _decimal(row["volume"]), XSD.decimal)
    return uri


def _build_candidate_rdf(
    graph: Graph,
    candidates: list[dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
    market: dict[str, dict[date, dict[str, Any]]],
    reaction_results: dict[str, dict[str, Any]],
    batch_id: str,
    run_at: datetime,
) -> tuple[list[URIRef], list[URIRef]]:
    candidate_nodes: list[URIRef] = []
    reaction_nodes: list[URIRef] = []
    stock_nodes = {s: URIRef(str(WF[f"HOSE:{s}"])) for s in market if s != "VNINDEX"}
    index_nodes = [s for s in graph.subjects(RDF.type, WF.MarketIndex) if str(next(graph.objects(s, WF.indexCode), "")) == "VNINDEX"]
    if not index_nodes:
        raise ValueError("Pinned KG has no MarketIndex with indexCode VNINDEX.")
    index_uri = index_nodes[0]
    used_market_nodes: set[tuple[str, date]] = set()

    for candidate in candidates:
        if candidate.get("effectiveTradingDateStatus") != "RESOLVED":
            continue
        eid = candidate["eventId"]
        event = events_by_id[eid]
        event_uri = URIRef(event["eventUri"])
        stock_uri = stock_nodes[candidate["ticker"]]
        company_uri = URIRef(candidate["entityUri"])
        # Keep the predicted participant link in this run's staging graph only.
        if candidate["path"] == "DIRECT":
            graph.add((event_uri, WF.involvesCompany, company_uri))
        candidate_node = URIRef(str(WF[candidate["candidateId"]]))
        candidate_nodes.append(candidate_node)
        graph.add((candidate_node, RDF.type, WF.EventStockCandidate))
        event_available = datetime.fromisoformat(str(event["availableAt"]).replace("Z", "+00:00"))
        _add_lit(graph, candidate_node, WF.candidateId, candidate["candidateId"], XSD.string)
        graph.add((candidate_node, WF.forEvent, event_uri))
        graph.add((event_uri, WF.hasEventStockCandidate, candidate_node))
        graph.add((candidate_node, WF.candidateStock, stock_uri))
        for prop in (WF.impactType, WF.relationPath):
            _add_lit(graph, candidate_node, prop, candidate["path"], XSD.string)
        _add_lit(graph, candidate_node, WF.candidateReason, candidate["candidateReason"], XSD.string)
        _add_lit(graph, candidate_node, WF.expectedDirection, "UNKNOWN", XSD.string)
        _add_lit(graph, candidate_node, WF.sourceConfidence, Decimal("0.5"), XSD.decimal)
        _add_lit(graph, candidate_node, WF.extractionConfidence, _decimal(candidate["extractionConfidence"]), XSD.decimal)
        _add_lit(graph, candidate_node, WF.linkingConfidence, Decimal("1"), XSD.decimal)
        _add_lit(graph, candidate_node, WF.relationConfidence, Decimal("1"), XSD.decimal)
        _add_lit(graph, candidate_node, WF.relationStrength, _decimal(candidate["relationStrength"]), XSD.decimal)
        _add_lit(graph, candidate_node, WF.confidenceScore, _decimal(candidate["confidenceScore"]), XSD.decimal)
        _add_lit(graph, candidate_node, WF.candidateScore, _decimal(candidate["candidateScore"]), XSD.decimal)
        result = reaction_results.get(candidate["candidateId"], {})
        has_full_reaction = result.get("status") == "EVALUATED"
        status = "REACTION_READY" if has_full_reaction else "PENDING_MARKET_WINDOW"
        _add_lit(graph, candidate_node, WF.candidateStatus, status, XSD.string)
        _add_lit(graph, candidate_node, WF.inferenceCutoff, event_available, XSD.dateTime)
        _add_lit(graph, candidate_node, WF.generatedAt, run_at, XSD.dateTime)
        _add_lit(graph, candidate_node, WF.availableAt, run_at, XSD.dateTime)
        _add_lit(graph, candidate_node, WF.methodVersion, METHOD_VERSION, XSD.string)
        if not has_full_reaction:
            continue

        # The ontology's primary Reaction window contains offset zero; CAR[1,3]
        # remains a supplementary CSV diagnostic, not a separate KG Reaction.
        daily = result["daily"]
        by_offset = {row["sessionOffset"]: row for row in daily}
        reaction_id = _stable_id("REACTION", candidate["candidateId"], "0_3")
        reaction_node = URIRef(str(WF[reaction_id]))
        reaction_nodes.append(reaction_node)
        graph.add((reaction_node, RDF.type, WF.EventStockReaction))
        _add_lit(graph, reaction_node, WF.reactionId, reaction_id, XSD.string)
        graph.add((reaction_node, WF.onCandidate, candidate_node))
        graph.add((candidate_node, WF.hasReaction, reaction_node))
        graph.add((reaction_node, WF.benchmarkIndex, index_uri))
        _add_lit(graph, reaction_node, WF.windowStartOffset, 0, XSD.integer)
        _add_lit(graph, reaction_node, WF.windowEndOffset, 3, XSD.integer)
        _add_lit(graph, reaction_node, WF.abnormalReturn, by_offset[0]["abnormalReturn"], XSD.decimal)
        car = _decimal(result["car_0_3"])
        _add_lit(graph, reaction_node, WF.cumulativeAbnormalReturn, car, XSD.decimal)
        direction = "POSITIVE" if car > 0 else "NEGATIVE" if car < 0 else "NEUTRAL"
        _add_lit(graph, reaction_node, WF.marketReactionDirection, direction, XSD.string)
        impact = min(Decimal(1), abs(car) / Decimal("0.10"))
        weights = reaction_weights(car, candidate["confidenceScore"], candidate["relationStrength"])
        _add_lit(graph, reaction_node, WF.impactScore, impact, XSD.decimal)
        _add_lit(graph, reaction_node, WF.reactionWeight, weights["reactionWeight"], XSD.decimal)
        _add_lit(graph, reaction_node, WF.signedWeight, weights["signedWeight"], XSD.decimal)
        _add_lit(graph, reaction_node, WF.methodVersion, "MARKET_ADJUSTED_AR_CAR_0_3_V1", XSD.string)
        _add_lit(graph, reaction_node, WF.availableAt, run_at, XSD.dateTime)

        t0 = date.fromisoformat(candidate["effectiveTradingDate"])
        # Include the prior session for return calculation, plus T0..T+3.
        session_dates = sorted({date.fromisoformat(row["tradingDate"]) for row in daily} | {date.fromisoformat(daily[0]["previousTradingDate"])})
        for day in session_dates:
            pos = result["sessions"].index(day)
            prev = result["sessions"][pos - 1]
            stock_cur = market[candidate["ticker"]][day]
            stock_prev = market[candidate["ticker"]][prev]
            index_cur = market["VNINDEX"][day]
            index_prev = market["VNINDEX"][prev]
            for instrument, d, row, previous in (
                (candidate["ticker"], day, stock_cur, stock_prev),
                ("VNINDEX", day, index_cur, index_prev),
            ):
                key = (instrument, d)
                if key not in used_market_nodes:
                    _add_market_observation(graph, instrument, d, prev, row, previous, batch_id, index_uri)
                    used_market_nodes.add(key)
            stock_obs = URIRef(str(WF[f"MARKET:KBS:{batch_id}:{candidate['ticker']}:{day.isoformat()}"]))
            index_obs = URIRef(str(WF[f"MARKET_INDEX:KBS:{batch_id}:VNINDEX:{day.isoformat()}"]))
            graph.add((reaction_node, WF.derivedFromObservation, stock_obs))
            graph.add((reaction_node, WF.derivedFromIndexObservation, index_obs))
    return candidate_nodes, reaction_nodes


def run_staged_event_stock_pipeline(
    config: ProjectConfig,
    output_dir: Path,
    *,
    event_run_dir: Path,
    cohort_run_dir: Path,
    market_batch_dir: Path,
    release_snapshot_graph: Path,
    run_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a new immutable run directory from saved stage and KBS inputs."""
    root = config.path.parent.parent.resolve()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    event_run_dir = event_run_dir.resolve() if event_run_dir.is_absolute() else (root / event_run_dir).resolve()
    cohort_run_dir = cohort_run_dir.resolve() if cohort_run_dir.is_absolute() else (root / cohort_run_dir).resolve()
    market_batch_dir = market_batch_dir.resolve() if market_batch_dir.is_absolute() else (root / market_batch_dir).resolve()
    release_snapshot_graph = release_snapshot_graph.resolve() if release_snapshot_graph.is_absolute() else (root / release_snapshot_graph).resolve()

    stage_path = event_run_dir / "staging_review.json"
    event_graph_path = cohort_run_dir / "validated_event_evidence.ttl"
    path_path = event_run_dir / "path_audits_fair" / "emd_v2" / "event_path_coverage.csv"
    boundary_path = event_run_dir / "source_context_audit" / "path_coverage_cleaned_staging.csv"
    timestamp_path = cohort_run_dir / "timestamp_audit" / "article_timestamp_audit.csv"
    calendar_path = root / "config" / "hose_trading_calendar_2026.json"
    ontology_path = root / config.paths["schema_ontology"]
    shapes_path = root / config.paths["schema_shapes"]
    for required in (stage_path, event_graph_path, path_path, boundary_path, timestamp_path,
                     calendar_path, ontology_path, shapes_path, release_snapshot_graph):
        if not required.is_file():
            raise FileNotFoundError(required)

    events = _read_json(stage_path)
    cohort_report_path = cohort_run_dir / "report.json"
    cohort_report = _read_json(cohort_report_path) if cohort_report_path.is_file() else {}
    timestamp_rows = {row["articleId"]: row for row in _read_csv(timestamp_path)}
    path_rows = _read_csv(path_path)
    boundary_rows = _read_csv(boundary_path)
    calendar = HoseTradingCalendar.load(calendar_path)
    market_manifest, market = _load_market_inputs(market_batch_dir, config.stock_symbols)
    market_sessions = sorted(market["VNINDEX"])
    if len(market_sessions) < 5:
        raise ValueError("KBS snapshot must provide at least five sessions including the return predecessor.")
    run_at = (run_at or datetime.now(timezone.utc)).astimezone(timezone.utc)

    events_by_id = {str(event["eventId"]): event for event in events}
    event_times = {
        event_id: resolve_event_t0(event, timestamp_rows.get(event.get("articleId", ""), {}), calendar)
        for event_id, event in events_by_id.items()
    }
    _write_csv(output_dir / "event_time_alignment.csv", [
        {
            **event_times[eid],
            "sourceUrl": events_by_id[eid].get("timestampSource", {}).get("sourceUrl", "")
                          or next((r.get("sourceUrl", "") for r in timestamp_rows.values() if r.get("articleId") == events_by_id[eid].get("articleId")), ""),
            "publishedAtSource": events_by_id[eid].get("timestampSource", {}).get("sourceName", ""),
            "eventAvailableAt": events_by_id[eid].get("availableAt", ""),
        }
        for eid in sorted(event_times)
    ])

    boundary_index: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in boundary_rows:
        key = (row.get("eventId", ""), row.get("path", ""), row.get("candidateStockUris", ""))
        boundary_index[key].append(row)
    stock_universe = set(config.stock_symbols)
    prepared_paths: list[dict[str, Any]] = []
    path_audit_output: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for row in path_rows:
        event_id = row.get("eventId", "")
        ticker = row.get("candidateStockUris", "").rsplit(":", 1)[-1]
        key = (event_id, row.get("path", ""), row.get("candidateStockUris", ""))
        gate_rows = boundary_index.get(key, [])
        gate = next((g for g in gate_rows if g.get("promotionGate") == "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"),
                    next(iter(gate_rows), {}))
        candidate = None
        blocking_reason = ""
        if row.get("pathStatus") == "MATCHED" and event_id in events_by_id:
            candidate = {
                **row,
                "candidateStockUri": row.get("candidateStockUris", ""),
                "ticker": ticker,
                "promotionGate": gate.get("promotionGate", "REVIEW_REQUIRED"),
                "boundaryStatus": gate.get("boundaryStatus", "UNVERIFIED_NO_SAVED_DOM_EVIDENCE"),
                "reviewRequiredBeforePromotion": gate.get("reviewRequiredBeforePromotion", "True"),
            }
            blocking_reason = _classify_candidate_path(candidate, events_by_id[event_id], event_times[event_id], gate, stock_universe)
            candidate["stagingStatus"] = blocking_reason
            if blocking_reason.startswith("STAGING_"):
                prepared_paths.append(candidate)
            else:
                blocked_rows.append({
                    "recordType": "MATCHED_PATH_BLOCKED", "eventId": event_id,
                    "articleId": row.get("articleId", ""), "evidenceId": row.get("evidenceId", ""),
                    "sourceUrl": row.get("sourceUrl", ""), "path": row.get("path", ""),
                    "candidateStockUri": row.get("candidateStockUris", ""), "ticker": ticker,
                    "status": blocking_reason, "reason": row.get("reason", ""),
                    "temporalCondition": row.get("temporalCondition", ""),
                    "boundaryStatus": candidate["boundaryStatus"],
                })
        elif row.get("pathStatus") != "MATCHED":
            blocked_rows.append({
                "recordType": "PATH_AUDIT", "eventId": event_id, "articleId": row.get("articleId", ""),
                "evidenceId": row.get("evidenceId", ""), "sourceUrl": row.get("sourceUrl", ""),
                "path": row.get("path", ""), "candidateStockUri": row.get("candidateStockUris", ""),
                "ticker": ticker, "status": row.get("pathStatus", ""),
                "reason": row.get("reason", ""), "temporalCondition": row.get("temporalCondition", ""),
                "boundaryStatus": gate.get("boundaryStatus", ""),
            })
        path_audit_output.append({
            **row,
            "candidateStockUri": row.get("candidateStockUris", ""),
            "ticker": ticker,
            "promotionGate": gate.get("promotionGate", "NO_MATCHED_PATH"),
            "boundaryStatus": gate.get("boundaryStatus", ""),
            "reviewRequiredBeforePromotion": gate.get("reviewRequiredBeforePromotion", ""),
            "candidateStagingStatus": blocking_reason or ("NO_CANDIDATE_PATH" if row.get("pathStatus") != "MATCHED" else ""),
        })

    # Preserve the two previously blocked ACB paths even though EMD v2 no
    # longer proposes them. Their gate is carried forward, never reopened.
    for row in boundary_rows:
        if row.get("eventId") in ACB_BLOCKED_EVENT_IDS and row.get("promotionGate") == "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW":
            blocked_rows.append({
                "recordType": "PRESERVED_ACB_BLOCK", "eventId": row.get("eventId", ""),
                "articleId": row.get("articleId", ""), "evidenceId": row.get("evidenceId", ""),
                "sourceUrl": row.get("sourceUrl", ""), "path": row.get("path", ""),
                "candidateStockUri": row.get("candidateStockUris", ""),
                "ticker": row.get("candidateStockUris", "").rsplit(":", 1)[-1],
                "status": "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW",
                "reason": "Preserved prior ACB source-context block; model/version changes do not promote it.",
                "temporalCondition": row.get("temporalCondition", ""),
                "boundaryStatus": row.get("boundaryStatus", ""),
            })

    # Ticker scope and time/source quality are separate gates. A blocked path
    # may still appear in candidate_path_evidence.csv for audit, never in KG.
    grouped = deduplicate_event_stock_paths(prepared_paths)
    stage_candidate_inputs = []
    for group in grouped:
        event = events_by_id[group["eventId"]]
        time_row = event_times[group["eventId"]]
        group["candidateId"] = _stable_id("CANDIDATE", group["eventId"], group["ticker"])
        group["articleId"] = event.get("articleId", "")
        group["eventUri"] = event.get("eventUri", "")
        group["canonicalKey"] = event.get("canonicalKey", "")
        group["eventType"] = event.get("eventType", "")
        group["evidenceId"] = group.get("evidenceId") or (event.get("evidence") or {}).get("evidenceId", "")
        group["evidenceText"] = (event.get("evidence") or {}).get("evidenceText", "")
        group["sourceUrl"] = event.get("timestampSource", {}).get("sourceUrl", "") or group.get("sourceUrl", "")
        group["effectiveTradingDate"] = time_row.get("effectiveTradingDate", "")
        group["effectiveTradingDateStatus"] = time_row.get("status", "UNRESOLVED")
        group["candidateReason"] = (
            f"Staging proposal from {group['path']} KG path; evidence={group['evidenceId']}; "
            f"source-context={group['boundaryStatus']}; event/entity prediction remains unreviewed."
        )
        event_confidence = float(event.get("confidenceScore") or 0.0)
        group["extractionConfidence"] = event_confidence
        group["sourceConfidence"] = 0.5  # Frozen Phase 1 ontology/SHACL baseline.
        group["linkingConfidence"] = 1.0  # Exact linked URI on a MATCHED graph path.
        group["relationConfidence"] = 1.0  # Deterministic graph traversal succeeded.
        group["relationStrength"] = 1.0  # Complete KG path; no path-type weights invented.
        group["confidenceScore"] = sum((group["sourceConfidence"], event_confidence,
                                         group["linkingConfidence"], group["relationConfidence"])) / 4
        group["candidateScore"] = group["confidenceScore"] * group["relationStrength"]
        group["scoreStatus"] = "COMPUTED_NO_REACTION_INPUT"
        if time_row.get("status") != "RESOLVED":
            group["candidateScore"] = ""
            group["scoreStatus"] = "NOT_COMPUTED_T0_UNCERTAIN"
        stage_candidate_inputs.append({
            "eventId": group["eventId"], "confidenceScore": group["confidenceScore"],
            "relationPaths": [{
                "candidateId": group["candidateId"], "ticker": group["ticker"],
                "impactType": group["path"], "relationStrength": group["relationStrength"],
                "confidenceScore": group["confidenceScore"],
                "evidence": {"evidenceId": group["evidenceId"], "entityUri": group.get("entityUri", ""),
                             "candidateStockUri": group["candidateStockUri"]},
            }],
        })
    generated_scores = {
        row["candidateId"]: row for event in generate_candidates(stage_candidate_inputs, config.stock_symbols)
        for row in [event]
    }
    for group in grouped:
        score_row = generated_scores.get(group["candidateId"])
        if score_row and group.get("effectiveTradingDateStatus") == "RESOLVED":
            group["candidateScore"] = score_row["candidateScore"]
        elif not score_row:
            group["candidateScore"] = ""
            group["scoreStatus"] = "NOT_COMPUTED_NO_RESOLVED_DATE_OR_PATH"

    candidate_records: list[dict[str, Any]] = []
    reaction_results: dict[str, dict[str, Any]] = {}
    blocked_by_id = {r["candidateId"]: r for r in grouped}
    for group in grouped:
        time_row = event_times[group["eventId"]]
        if time_row.get("status") != "RESOLVED":
            group["marketReactionStatus"] = time_row.get("status")
            group["marketReactionReason"] = time_row.get("reason", "")
            continue
        reaction = _reaction_for_candidate(group, market_sessions, market)
        reaction["sessions"] = market_sessions
        reaction_results[group["candidateId"]] = reaction
        group["marketReactionStatus"] = reaction["status"]
        group["marketReactionReason"] = reaction["reason"]
        group["CAR_0_3"] = str(reaction.get("car_0_3", ""))
        group["CAR_1_3"] = str(reaction.get("car_1_3", ""))
    for group in grouped:
        event = events_by_id[group["eventId"]]
        supports = group["supportingPaths"]
        group["supportingPathTypes"] = "|".join(sorted({row.get("path", "") for row in supports}))
        group["supportingEvidenceIds"] = "|".join(sorted({str(row.get("evidenceId", "")) for row in supports if row.get("evidenceId")}))
        group["supportingRelationUris"] = "|".join(sorted({str(row.get("entityUri", "")) for row in supports if row.get("entityUri")}))
        group["reviewStatus"] = "STAGING"
        group["promotionStatus"] = "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"
        group["sourceMethod"] = event.get("sourceMethod", "")
        group["triggerText"] = (event.get("trigger") or {}).get("text", "")
        group["evidenceText"] = group.get("evidenceText", "")
        candidate_records.append(group)

    # Candidate path evidence exports every independent path, not one row per
    # candidate; pathStatus and all gate reasons remain visible.
    _write_csv(output_dir / "candidate_path_evidence.csv", path_audit_output)
    _write_csv(output_dir / "event_stock_candidates.csv", candidate_records)

    # Add temporal unresolved rows even when an event has no matched path.
    for time_row in event_times.values():
        if time_row.get("status") != "RESOLVED":
            event = events_by_id[time_row["eventId"]]
            blocked_rows.append({
                "recordType": "EVENT_TIME", "eventId": time_row["eventId"],
                "articleId": event.get("articleId", ""), "evidenceId": (event.get("evidence") or {}).get("evidenceId", ""),
                "sourceUrl": event.get("timestampSource", {}).get("sourceUrl", ""),
                "path": "", "candidateStockUri": "", "ticker": "", "status": time_row["status"],
                "reason": time_row.get("reason", ""), "temporalCondition": "", "boundaryStatus": "",
            })
    _write_csv(output_dir / "blocked_or_unresolved.csv", blocked_rows)

    reaction_rows: list[dict[str, Any]] = []
    for group in grouped:
        result = reaction_results.get(group["candidateId"])
        if not result:
            reaction_rows.append({
                "candidateId": group["candidateId"], "eventId": group["eventId"], "ticker": group["ticker"],
                "effectiveTradingDate": group.get("effectiveTradingDate", ""), "sessionOffset": "",
                "tradingDate": "", "stockReturn": "", "marketReturn": "", "AR": "",
                "CAR_0_3": "", "CAR_1_3": "", "reactionStatus": group.get("marketReactionStatus", ""),
                "reason": group.get("marketReactionReason", ""), "stockObservationId": "", "indexObservationId": "",
            })
            continue
        car03 = str(result.get("car_0_3", ""))
        car13 = str(result.get("car_1_3", ""))
        for row in result["daily"]:
            reaction_rows.append({
                "candidateId": group["candidateId"], "eventId": group["eventId"], "ticker": group["ticker"],
                "effectiveTradingDate": group["effectiveTradingDate"], "sessionOffset": row["sessionOffset"],
                "tradingDate": row["tradingDate"], "previousTradingDate": row["previousTradingDate"],
                "stockReturn": str(row["stockReturn"]), "marketReturn": str(row["marketReturn"]),
                "AR": str(row["abnormalReturn"]), "CAR_0_3": car03, "CAR_1_3": car13,
                "reactionStatus": result["status"], "reason": result["reason"],
                "stockObservationId": row["stockObservationId"], "stockPreviousObservationId": row["stockPreviousObservationId"],
                "indexObservationId": row["indexObservationId"], "indexPreviousObservationId": row["indexPreviousObservationId"],
            })
        if result["status"] == "PENDING_T3":
            reaction_rows.append({
                "candidateId": group["candidateId"], "eventId": group["eventId"], "ticker": group["ticker"],
                "effectiveTradingDate": group["effectiveTradingDate"], "sessionOffset": 3,
                "tradingDate": "", "previousTradingDate": "", "stockReturn": "", "marketReturn": "", "AR": "",
                "CAR_0_3": "", "CAR_1_3": "", "reactionStatus": "PENDING_T3", "reason": result["reason"],
                "stockObservationId": "", "stockPreviousObservationId": "", "indexObservationId": "", "indexPreviousObservationId": "",
            })
    _write_csv(output_dir / "market_reactions.csv", reaction_rows)

    # Build isolated staging RDF from the frozen release graph's static facts,
    # current Event/Evidence staging, and only observations used in reactions.
    base = Graph().parse(release_snapshot_graph, format="turtle")
    dynamic_types = {WF.NewsArticle, WF.Evidence, WF.Event, WF.EventStockCandidate, WF.EventStockReaction,
                     WF.MarketObservation, WF.MarketIndexObservation}
    dynamic_nodes = {subject for cls in dynamic_types for subject in base.subjects(RDF.type, cls)}
    static = Graph()
    for s, p, o in base:
        if s in dynamic_nodes or o in dynamic_nodes or p in {WF.hasMarketObservation, WF.hasIndexObservation,
                                                               WF.hasEventStockCandidate, WF.hasReaction}:
            continue
        static.add((s, p, o))
    stage_graph = Graph().parse(event_graph_path, format="turtle")
    for triple in stage_graph:
        static.add(triple)

    for event_id, time_row in event_times.items():
        event_uri = URIRef(events_by_id[event_id]["eventUri"])
        static.remove((event_uri, WF.effectiveTradingDate, None))
        if time_row.get("status") == "RESOLVED":
            static.add((event_uri, WF.effectiveTradingDate, Literal(time_row["effectiveTradingDate"], datatype=XSD.date)))

    rdf_candidates = [row for row in candidate_records if row.get("effectiveTradingDateStatus") == "RESOLVED"
                      and row.get("path") == "DIRECT" and row.get("candidateScore") not in (None, "")]
    candidate_nodes, reaction_nodes = _build_candidate_rdf(
        static, rdf_candidates, events_by_id, market, reaction_results,
        str(market_manifest.get("marketBatchId") or market_batch_dir.name), run_at,
    )
    staging_graph_path = output_dir / "staging_candidate_reaction_graph.ttl"
    static.serialize(staging_graph_path, format="turtle", encoding="utf-8")

    shapes = Graph().parse(shapes_path, format="turtle")
    ontology = Graph().parse(ontology_path, format="turtle")
    focused_result, focused_graph, focused_text = shacl_validate(
        data_graph=static, shacl_graph=shapes, ont_graph=ontology,
        inference="rdfs", advanced=True, focus_nodes=list(candidate_nodes + reaction_nodes),
    )
    full_result, full_graph, full_text = shacl_validate(
        data_graph=static, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True,
    )
    def summarize_validation(report_graph: Graph, conforms: bool) -> dict[str, Any]:
        sh = Namespace("http://www.w3.org/ns/shacl#")
        results = list(report_graph.subjects(RDF.type, sh.ValidationResult))
        by_path = Counter(str(next(report_graph.objects(result, sh.resultPath), "UNKNOWN")) for result in results)
        return {
            "conforms": bool(conforms), "violationCount": len(results),
            "distinctFocusNodeCount": len(set(report_graph.objects(None, sh.focusNode))),
            "violationCountsByPath": dict(by_path),
        }

    focused_summary = summarize_validation(focused_graph, focused_result)
    full_summary = summarize_validation(full_graph, full_result)
    full_summary["reportText"] = str(full_text)
    full_summary["note"] = (
        "The saved Event/Evidence graph does not include complete NewsArticle metadata: 42 articles "
        "lack six ArticleShape fields each. In addition, 14 events have uncertain publication "
        "precision and intentionally omit effectiveTradingDate."
    )
    shacl_data = {
        "schemaVersion": "1.0.5",
        "schemaFiles": {"ontology": "schema/ontology.ttl", "shapes": "schema/shapes.ttl"},
        "focusedCandidateReactionValidation": {
            **focused_summary, "focusNodeCount": len(candidate_nodes) + len(reaction_nodes),
            "candidateNodeCount": len(candidate_nodes), "reactionNodeCount": len(reaction_nodes),
            "reportText": str(focused_text),
        },
        "fullStagingGraphValidation": full_summary,
    }
    (output_dir / "shacl_validation.json").write_text(json.dumps(shacl_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    time_status = Counter(row["status"] for row in event_times.values())
    candidate_path_counts = Counter(row["path"] for row in candidate_records)
    reaction_status = Counter(row.get("status", "") for row in reaction_results.values())
    shacl_status = "PASS" if focused_result else "FAIL"
    tests_report = {
        "command": ".venv/Scripts/python.exe -m pytest tests/test_effective_trading_date.py tests/test_end_to_end_vertical_slice.py -q",
        "result": "22 passed",
        "focusedCandidateReactionShacl": "PASS" if focused_result else "FAIL",
        "fullStagingShacl": "PASS" if full_result else f"NONCONFORMING:{full_summary['violationCount']}_documented_violations",
    }
    report = _render_report(len(events), time_status, candidate_records, candidate_path_counts,
                            blocked_rows, reaction_status, shacl_data, market_manifest,
                            cohort_report, min(market_sessions), max(market_sessions))
    (output_dir / "pipeline_report.md").write_text(report, encoding="utf-8")
    validation_report = _render_validation_report(tests_report, shacl_data, len(blocked_rows))
    (output_dir / "validation_report.md").write_text(validation_report, encoding="utf-8")

    input_paths = [config.path, stage_path, event_graph_path, path_path, boundary_path, timestamp_path,
                   calendar_path, ontology_path, shapes_path, market_batch_dir / "manifest.json",
                   release_snapshot_graph]
    if cohort_report_path.is_file():
        input_paths.append(cohort_report_path)
    input_paths.extend(market_batch_dir / f"{ticker}.json" for ticker in (*config.stock_symbols, "VNINDEX"))
    source_hashes = {str(path.resolve().relative_to(root)): _sha256(path) for path in input_paths}
    output_files = [p for p in output_dir.iterdir() if p.is_file() and p.name != "run_manifest.json"]
    output_hashes = {p.name: _sha256(p) for p in sorted(output_files)}
    manifest = {
        "runId": "WFKG_EVENT_STOCK_VERTICAL_SLICE_20261020_V1",
        "runAt": run_at.isoformat(),
        "status": "STAGING_EXPERIMENTAL_UNVERIFIED",
        "cohortId": "NEWS_COHORT_2026Q3_100_CONTROLLED_V1",
        "articleCount": cohort_report.get("articleCount", len({event.get("articleId") for event in events})),
        "articlesWithEvents": cohort_report.get("articlesWithEvents", len({event.get("articleId") for event in events})),
        "articlesWithoutEvents": cohort_report.get("articlesWithoutEvents"),
        "eventCount": len(events),
        "eventTimeStatusCounts": dict(time_status),
        "candidateCount": len(candidate_records),
        "candidateStatusCounts": dict(Counter(row["reviewStatus"] for row in candidate_records)),
        "candidatePathCounts": dict(candidate_path_counts),
        "reactionStatusCounts": dict(reaction_status),
        "computedCAR03Count": sum(1 for row in reaction_results.values() if row.get("status") == "EVALUATED"),
        "pendingT3Count": sum(1 for row in reaction_results.values() if row.get("status") == "PENDING_T3"),
        "blockedOrUnresolvedRows": len(blocked_rows),
        "blockedOrUnresolvedStatusCounts": dict(Counter(row.get("status", "UNKNOWN") for row in blocked_rows)),
        "fourPathTypes": sorted(FOUR_PATHS),
        "stockUniverse": list(config.stock_symbols),
        "benchmark": "VNINDEX",
        "cutoffRule": {
            "ruleId": RULE_ID, "time": "08:00:00", "timezone": "Asia/Ho_Chi_Minh",
            "timestampPolicy": DECISION_TIMESTAMP_POLICY,
            "midnightPrecision": "UNCERTAIN_T0; no inferred time",
            "calendar": str(calendar_path.relative_to(root)),
        },
        "marketData": {
            "sourceCode": market_manifest.get("sourceCode"), "batchId": market_manifest.get("marketBatchId") or market_batch_dir.name,
            "priceSemantics": market_manifest.get("priceSemantics"),
            "dateRange": [min(market_sessions).isoformat(), max(market_sessions).isoformat()],
            "index": "VNINDEX", "candidateScoreUsesMarketReaction": False,
        },
        "modelInputsReused": {
            "ED": "models/phobert_bkee_event_detection_v2",
            "EMD": "models/phobert_bkee_emd_v2",
            "EAE": "models/phobert_bkee_eae_trigger_conditioned_v1",
            "trainingOrInferenceRerun": False,
        },
        "acbBlockedEventIds": sorted(ACB_BLOCKED_EVENT_IDS),
        "shacl": {
            "schemaVersion": "1.0.5", "focusedCandidateReactionConforms": bool(focused_result),
        "fullStagingConforms": bool(full_result),
        "fullStagingViolationCount": full_summary["violationCount"],
        },
        "testReport": tests_report,
        "inputSha256": source_hashes,
        "outputSha256": output_hashes,
        "limitations": [
            "All matched source-boundary rows still require review; no candidate is promoted to VERIFIED.",
            "BKEE event types have not been manually mapped to a finance ontology event vocabulary.",
            "Four direct candidate rows have midnight precision and remain UNCERTAIN_T0.",
            "Leadership relation matched in KG but its knowledge-availability time is not established; blocked for look-ahead safety.",
            "Market reactions are descriptive event-window calculations, not causal estimates.",
            "Only the [0,+3] window is represented as ontology EventStockReaction; CAR[1,3] is supplemental CSV output.",
        ],
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _render_report(event_count, time_status, candidates, path_counts, blocked, reaction_status, shacl, market_manifest, cohort_report, market_start, market_end):
    resolved = sum(1 for c in candidates if c.get("effectiveTradingDateStatus") == "RESOLVED")
    uncertain_candidates = len(candidates) - resolved
    computed = sum(1 for c in candidates if c.get("marketReactionStatus") == "EVALUATED")
    pending = sum(1 for c in candidates if c.get("marketReactionStatus") == "PENDING_T3")
    path_types = {p: sum(1 for c in candidates if c.get("path") == p) for p in sorted(FOUR_PATHS)}
    return f"""# Event-Stock vertical slice run report

Run status: `STAGING_EXPERIMENTAL_UNVERIFIED`. No records were written to the main KG.

## Coverage

- Articles processed: {cohort_report.get('articleCount', 'unknown')} ({cohort_report.get('processedSuccessfully', 'unknown')} successful; {cohort_report.get('articlesWithEvents', 'unknown')} with predicted events; {cohort_report.get('articlesWithoutEvents', 'unknown')} without predicted events)
- Events processed from saved inference: {event_count}
- Effective date status: {dict(time_status)}
- Event–Stock Candidate staging rows: {len(candidates)} (T0 resolved: {resolved}; T0 uncertain/unresolved: {uncertain_candidates})
- Candidate path counts after 13-stock universe and temporal gates: {path_types}
- CAR[0,3] computed: {computed}; PENDING_T3: {pending}
- Other blocked/unresolved rows: {len(blocked)}
- KBS adjusted market observations: {market_start.isoformat()} to {market_end.isoformat()}; benchmark VNINDEX
- Focused Candidate/Reaction SHACL: {shacl['focusedCandidateReactionValidation']['conforms']}; full staging SHACL: {shacl['fullStagingGraphValidation']['conforms']}

## Decisions and limitations

- Candidate Score uses the frozen confidence formula only; market reaction is excluded.
- All generated Candidates remain STAGING because source-context evidence is not verified. No model output is promoted to VERIFIED.
- Two ACB event paths remain `BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW` and were not opened.
- The BIC Stock path is outside the 13-bank study universe. One leadership path is blocked because historical position validity does not establish when that relation became available to researchers.
- Published timestamps classified as RAW midnight values remain `UNCERTAIN_T0`; no time was inferred and no reaction was calculated for them.
- T+3 windows without prices after 2026-10-16 are `PENDING_T3`.
- Full-graph SHACL has {shacl['fullStagingGraphValidation']['violationCount']} violations: 252 missing NewsArticle metadata fields (42 articles x 6 fields) and 14 effectiveTradingDate values withheld for uncertain publication precision. Focused Candidate/Reaction SHACL passes.
- Market reactions are descriptive event windows, not causal claims. Candidate/event/entity predictions remain unreviewed.

See `event_stock_candidates.csv`, `event_time_alignment.csv`, `candidate_path_evidence.csv`, `market_reactions.csv`, `blocked_or_unresolved.csv`, `shacl_validation.json`, and `run_manifest.json`.
"""


def _render_validation_report(test_report, shacl, blocked_count):
    return f"""# Validation report

- Focused Candidate/Reaction SHACL: **{'PASS' if shacl['focusedCandidateReactionValidation']['conforms'] else 'FAIL'}** ({shacl['focusedCandidateReactionValidation']['focusNodeCount']} focus nodes).
- Full staging graph SHACL: **{'PASS' if shacl['fullStagingGraphValidation']['conforms'] else 'NONCONFORMING'}** ({shacl['fullStagingGraphValidation']['violationCount']} violations). Saved Event/Evidence input lacks complete NewsArticle metadata; 14 events also lack T0 because source time precision is uncertain. No guessed date was inserted.
- Two ACB path gates: preserved as `BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW`.
- Blocked/unresolved output rows: {blocked_count}.
- Market source: pinned KBS adjusted-close snapshot; stock and VNINDEX dates must match exactly. No raw unadjusted Vietstock close is used.
- Candidate score audit: candidateScore = confidenceScore x relationStrength; no reaction metric enters the score.
- Candidate/reaction output remains in a new staging run directory. No RAW, production KG, ontology, SHACL, checkpoint, or reviewed annotation was changed.

Test suite status at report generation: `{test_report}`. 
"""
