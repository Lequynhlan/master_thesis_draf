"""Create an auditable Event-to-Candidate WFKG vertical-slice staging run.

The script reads the fixed news cohort, current KG and saved market snapshots.
It writes only under runs/wfkg_vertical_slice_news_100_v1 and never updates
RAW, CLEAN, DQS, the source graph, ontology or SHACL shapes.

Event annotations are analyst-reviewed rule-based annotations, not PhoBERT NER
or model predictions. Reactions are emitted only when all required observations
and the requested benchmark window exist. Missing windows stay NOT_EVALUATED.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

from wfkg.event_processing.scoring import candidate_score, confidence_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs" / "wfkg_vertical_slice_news_100_v1"
W = Namespace("https://example.org/wfkg/v1#")
WINDOWS = ((0, 0), (0, 1), (-1, 1), (0, 3))
RUN_TIME = datetime.now(timezone.utc).replace(microsecond=0)
RUN_ISO = RUN_TIME.isoformat().replace("+00:00", "Z")
MANIFEST = ROOT / "data/output/news_article_selection_manifest.json"
ENRICHED = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
KG_PATH = ROOT / "data/gold/knowledge_graph.ttl"
MARKET_PATH = ROOT / "data/gold/market_observations.ttl"

# Four distinct Events supported by five full-text articles. Two TCB reports
# describe the same approval and therefore share one canonicalKey/Event.
ANNOTATIONS = [
    {
        "eventId": "EVENT:TCB:EARNINGS:2026Q2",
        "canonicalKey": "EARNINGS:TCB:2026Q2",
        "eventType": "EARNINGS_ANNOUNCEMENT",
        "companyId": "COMPANY:TCB",
        "ticker": "TCB",
        "articles": ["NEWS_ARTICLE:d87a5dfa9094c5f7491f"],
        "cue": "Techcombank reported record earnings in the second quarter of 2026",
        "description": "Techcombank reported record Q2 2026 earnings.",
        "review": "Body states record Q2 earnings and gives related financial evidence.",
    },
    {
        "eventId": "EVENT:MBB:CAPITAL_INCREASE:2026",
        "canonicalKey": "CAPITAL_INCREASE_COMPLETION:MBB:2026-09-25",
        "eventType": "CAPITAL_INCREASE_COMPLETION",
        "companyId": "COMPANY:MBB",
        "ticker": "MBB",
        "articles": ["NEWS_ARTICLE:057920a32d3d68452b4a"],
        "cue": "đã chính thức hoàn tất tăng vốn điều lệ lên 100.687,5 tỷ đồng",
        "description": "MB completed its charter-capital increase to VND 100.6875 trillion.",
        "review": "Body attributes the completed increase to MB and states the resulting amount.",
    },
    {
        "eventId": "EVENT:TCB:CAPITAL_INCREASE_APPROVAL:2026",
        "canonicalKey": "CAPITAL_INCREASE_APPROVAL:TCB:2026-10-13",
        "eventType": "CAPITAL_INCREASE_APPROVAL",
        "companyId": "COMPANY:TCB",
        "ticker": "TCB",
        "articles": [
            "NEWS_ARTICLE:64427a6e8c606384dd4f",
            "NEWS_ARTICLE:959096d14783f1fcfc54",
        ],
        "cueByArticle": {
            "NEWS_ARTICLE:64427a6e8c606384dd4f": "Ngân hàng Nhà nước Việt Nam đã chấp thuận đề nghị tăng mức vốn điều lệ",
            "NEWS_ARTICLE:959096d14783f1fcfc54": "NHNN chính thức chấp thuận cho Techcombank tăng vốn điều lệ",
        },
        "description": "The State Bank of Vietnam approved Techcombank's 2026 charter-capital increase.",
        "review": "Both reports refer to the same 2026-10-13 approval and identify Techcombank.",
    },
    {
        "eventId": "EVENT:SHB:EARNINGS_ESTIMATE:2026Q3",
        "canonicalKey": "EARNINGS_ESTIMATE:SHB:2026Q3",
        "eventType": "EARNINGS_ESTIMATE",
        "companyId": "COMPANY:SHB",
        "ticker": "SHB",
        "articles": ["NEWS_ARTICLE:fa98bc3a32c14b237f00"],
        "cue": "lợi nhuận trước thuế của SHB 9 tháng đầu năm ước đạt 14.300 tỷ đồng",
        "description": "SHB reported a preliminary nine-month 2026 pre-tax profit estimate.",
        "review": "The article attributes the nine-month estimate to SHB management.",
    },
]


def read_jsonl(path: Path) -> dict[str, dict[str, object]]:
    return {
        item["articleId"]: item
        for item in (json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines())
        if item.get("articleId")
    }


def add(g: Graph, s: URIRef, p: URIRef, value: object, datatype: URIRef | None = None) -> None:
    if isinstance(value, URIRef):
        o = value
    elif datatype:
        if datatype == XSD.decimal:
            o = Literal(Decimal(str(value)), datatype=datatype)
        else:
            o = Literal(value, datatype=datatype)
    else:
        o = Literal(value)
    g.add((s, p, o))


def one(g: Graph, subject: URIRef, predicate: URIRef) -> object:
    values = list(g.objects(subject, predicate))
    if len(values) != 1:
        raise ValueError(f"Expected one {predicate} for {subject}, found {len(values)}")
    return values[0]


def literal_text(g: Graph, subject: URIRef, predicate: URIRef) -> str:
    return str(one(g, subject, predicate))


def next_session_day(available_at: datetime) -> date:
    """Find first ordinary Mon-Fri HOSE session opening strictly after time.

    Trading-calendar exception days are not present in the local artifacts;
    this is a tentative calendar mapping and is disclosed in the report.
    """
    local = available_at.astimezone(timezone(timedelta(hours=7)))
    day = local.date()
    opening = time(9, 0)
    if day.weekday() < 5 and local.time().replace(tzinfo=None) < opening:
        return day
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def extract_span(text: str, cue: str) -> tuple[int, int, str]:
    start = text.find(cue)
    if start < 0:
        raise ValueError(f"Evidence cue not found in body: {cue!r}")
    end = start + len(cue)
    # Extend the exact cue through a sentence boundary when it remains nearby.
    match = re.search(r"[.!?](?:\s|$)", text[end : min(len(text), end + 500)])
    if match:
        end += match.end() - 1
    return start, end, text[start:end]


def market_coverage(market: Graph) -> dict[str, object]:
    by_ticker: dict[str, list[date]] = {}
    for obs in market.subjects(RDF.type, W.MarketObservation):
        tickers = list(market.objects(obs, W.instrumentCode)) or []
        # Current graph may instead identify the stock through hasMarketObservation.
        if tickers:
            ticker = str(tickers[0])
        else:
            stocks = list(market.subjects(W.hasMarketObservation, obs))
            ticker = str(next(iter(market.objects(stocks[0], W.tickerSymbol)), "")) if stocks else ""
        dates = list(market.objects(obs, W.tradingDate))
        if ticker and dates:
            by_ticker.setdefault(ticker, []).append(date.fromisoformat(str(dates[0])))
    index_dates: dict[str, list[date]] = {}
    for obs in market.subjects(RDF.type, W.MarketIndexObservation):
        indexes = list(market.subjects(W.hasIndexObservation, obs))
        code = str(next(iter(market.objects(indexes[0], W.indexCode)), "")) if indexes else ""
        dates = list(market.objects(obs, W.tradingDate))
        if code and dates:
            index_dates.setdefault(code, []).append(date.fromisoformat(str(dates[0])))
    return {
        "stock": {k: sorted(set(v)) for k, v in by_ticker.items()},
        "index": {k: sorted(set(v)) for k, v in index_dates.items()},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cohort = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    enriched = read_jsonl(ENRICHED)
    base = Graph().parse(KG_PATH, format="turtle")
    market = Graph().parse(MARKET_PATH, format="turtle")
    market_cov = market_coverage(market)
    event_ids: list[URIRef] = []
    candidate_ids: list[URIRef] = []
    extraction_rows: list[dict[str, object]] = []
    issue_rows: list[dict[str, object]] = []
    stage = Graph()
    stage.bind("wfkg", W)
    stage.bind("xsd", XSD)

    cohort_ids = {item["articleId"] for item in cohort["articles"]}
    if len(cohort_ids) != 100:
        raise ValueError(f"Expected exactly 100 cohort IDs, found {len(cohort_ids)}")

    for annotation in ANNOTATIONS:
        event = W[annotation["eventId"]]
        event_ids.append(event)
        company = W[annotation["companyId"]]
        support_data: list[tuple[str, URIRef, URIRef, str, int, int]] = []
        for article_id in annotation["articles"]:
            if article_id not in cohort_ids:
                raise ValueError(f"Article outside fixed cohort: {article_id}")
            article_data = enriched.get(article_id)
            if not article_data or article_data.get("status") != "FULLTEXT" or not article_data.get("bodyText"):
                raise ValueError(f"Full text missing for selected article: {article_id}")
            article = W[article_id]
            if (article, RDF.type, W.NewsArticle) not in base:
                raise ValueError(f"Article is not in current KG: {article_id}")
            body = str(article_data["bodyText"])
            cue = annotation.get("cueByArticle", {}).get(article_id, annotation.get("cue"))
            start, end, evidence_text = extract_span(body, str(cue))
            evidence = W[f"EVIDENCE:VS100:{article_id.split(':', 1)[1]}"]
            pub_at = datetime.fromisoformat(literal_text(base, article, W.publishedAt))
            article_at = datetime.fromisoformat(literal_text(base, article, W.availableAt))
            body_retrieved_at = datetime.fromisoformat(str(article_data["capturedAt"]))
            evidence_at = max(pub_at, article_at, body_retrieved_at)
            add(stage, evidence, RDF.type, W.Evidence)
            add(stage, evidence, W.evidenceId, f"EVIDENCE:VS100:{article_id.split(':', 1)[1]}", XSD.string)
            add(stage, evidence, W.extractedFrom, article)
            add(stage, evidence, W.supports, event)
            add(stage, evidence, W.evidenceText, evidence_text, XSD.string)
            add(stage, evidence, W.startOffset, start, XSD.integer)
            add(stage, evidence, W.endOffset, end, XSD.integer)
            add(stage, evidence, W.availableAt, evidence_at.isoformat(), XSD.dateTime)
            support_data.append((article_id, article, evidence, evidence_text, start, end, evidence_at))

        available_at = min(item[6] for item in support_data)
        effective_day = next_session_day(available_at)
        add(stage, event, RDF.type, W.Event)
        add(stage, event, W.eventId, annotation["eventId"], XSD.string)
        add(stage, event, W.canonicalKey, annotation["canonicalKey"], XSD.string)
        add(stage, event, W.eventType, annotation["eventType"], XSD.string)
        add(stage, event, W.description, annotation["description"], XSD.string)
        add(stage, event, W.availableAt, available_at.isoformat(), XSD.dateTime)
        add(stage, event, W.effectiveTradingDate, effective_day.isoformat(), XSD.date)
        add(stage, event, W.involvesCompany, company)
        for _, article, _, _, _, _, _ in support_data:
            add(stage, article, W.reports, event)

        # Verify the direct path against KG edges before creating a Candidate.
        stock = W[f"HOSE:{annotation['ticker']}"]
        if (company, W.hasStock, stock) not in base:
            raise ValueError(f"Direct path missing in KG: {company} --hasStock--> {stock}")
        candidate_id = W[f"CANDIDATE:VS100:{annotation['ticker']}:{annotation['eventId'].split(':', 2)[-1]}"]
        candidate_ids.append(candidate_id)
        source_conf = 0.5  # Fixed Phase-1 baseline constraint in shapes.ttl.
        extraction_conf = 0.9  # Analyst-reviewed rule annotation; pilot, uncalibrated.
        linking_conf = 1.0  # Exact company mention/identity match, no ambiguity.
        relation_conf = 1.0  # Existing direct company->stock edge was verified.
        conf = confidence_score(source_conf, extraction_conf, linking_conf, relation_conf)
        strength = 1.0  # DIRECT baseline relation strength.
        score = candidate_score(conf, strength)
        add(stage, event, W.hasEventStockCandidate, candidate_id)
        add(stage, candidate_id, RDF.type, W.EventStockCandidate)
        add(stage, candidate_id, W.candidateId, str(candidate_id).rsplit("#", 1)[1], XSD.string)
        add(stage, candidate_id, W.forEvent, event)
        add(stage, candidate_id, W.candidateStock, stock)
        add(stage, candidate_id, W.impactType, "DIRECT", XSD.string)
        add(stage, candidate_id, W.relationPath, "DIRECT", XSD.string)
        add(stage, candidate_id, W.candidateReason, annotation["review"], XSD.string)
        add(stage, candidate_id, W.expectedDirection, "UNKNOWN", XSD.string)
        add(stage, candidate_id, W.relationStrength, strength, XSD.decimal)
        add(stage, candidate_id, W.sourceConfidence, source_conf, XSD.decimal)
        add(stage, candidate_id, W.extractionConfidence, extraction_conf, XSD.decimal)
        add(stage, candidate_id, W.linkingConfidence, linking_conf, XSD.decimal)
        add(stage, candidate_id, W.relationConfidence, relation_conf, XSD.decimal)
        add(stage, candidate_id, W.confidenceScore, conf, XSD.decimal)
        add(stage, candidate_id, W.candidateScore, score, XSD.decimal)
        add(stage, candidate_id, W.candidateStatus, "PENDING_MARKET_WINDOW", XSD.string)
        add(stage, candidate_id, W.inferenceCutoff, available_at.isoformat(), XSD.dateTime)
        add(stage, candidate_id, W.generatedAt, RUN_ISO, XSD.dateTime)
        add(stage, candidate_id, W.availableAt, RUN_ISO, XSD.dateTime)
        add(stage, candidate_id, W.methodVersion, "analyst-reviewed-rule-event-mvp-0.1", XSD.string)

        for article_id, _, evidence, text, start, end, evidence_at in support_data:
            extraction_rows.append({
                "articleId": article_id,
                "articleUrl": str(article_data.get("url", "")),
                "articleTitle": literal_text(base, article, W.title),
                "publishedAt": literal_text(base, article, W.publishedAt),
                "articleAvailableAt": literal_text(base, article, W.availableAt),
                "bodyTextSha256": str(article_data.get("cleanBodySha256") or article_data.get("bodySha256") or ""),
                "evidenceOffsetBasis": "bodyText in data/enriched_cleaned/news_100_v1/articles.jsonl",
                "eventId": annotation["eventId"],
                "canonicalKey": annotation["canonicalKey"],
                "eventType": annotation["eventType"],
                "candidateId": str(candidate_id),
                "ticker": annotation["ticker"],
                "evidenceId": str(evidence),
                "evidenceAvailableAt": evidence_at.isoformat(),
                "startOffset": start,
                "endOffset": end,
                "evidenceText": text,
                "annotationSource": "ANALYST_REVIEWED_RULE_BASED_NOT_PHOBERT",
                "reviewNote": annotation["review"],
                "availableAt": available_at.isoformat(),
                "effectiveTradingDate": effective_day.isoformat(),
                "confidenceScore": conf,
                "relationStrength": strength,
                "candidateScore": score,
            })

        for start_off, end_off in WINDOWS:
            dates_needed = end_off - start_off + 2  # event-window sessions + predecessor
            local_vn30 = market_cov["index"].get("VN30", [])
            local_stock = market_cov["stock"].get(annotation["ticker"], [])
            local_vnindex = market_cov["index"].get("VNINDEX", [])
            reason_parts = []
            if effective_day not in local_stock:
                reason_parts.append(f"stock {annotation['ticker']} has no Day 0/future observations from {effective_day}")
            if not local_vn30:
                reason_parts.append("no saved VN30 MarketIndexObservation/adjusted-close series in current market graph")
            if local_vn30 and len([d for d in local_vn30 if d >= effective_day]) < end_off + 1:
                reason_parts.append(f"VN30 lacks complete {dates_needed}-session window plus predecessor")
            if local_vnindex and not local_vn30:
                reason_parts.append("VNINDEX exists, but is not substituted for requested VN30 benchmark")
            issue_rows.append({
                "candidateId": str(candidate_id),
                "eventId": annotation["eventId"],
                "ticker": annotation["ticker"],
                "windowStartOffset": start_off,
                "windowEndOffset": end_off,
                "status": "NOT_EVALUATED" if reason_parts else "READY",
                "requiredSessionsIncludingPredecessor": dates_needed,
                "eventDay0": effective_day.isoformat(),
                "availableAt": available_at.isoformat(),
                "bankMarketDataLastDate": max(local_stock).isoformat() if local_stock else "MISSING",
                "VN30MarketDataLastDate": max(local_vn30).isoformat() if local_vn30 else "MISSING",
                "reason": "; ".join(reason_parts),
                "formula": "AR_t=(adjustedClose_stock_t/adjustedClose_stock_t-1-1)-(VN30_t/VN30_t-1-1); CAR=sum(AR_t); impact=min(1,abs(CAR)/0.10); reactionWeight=impact*confidenceScore*relationStrength; signedWeight=sign(CAR)*reactionWeight",
            })

    stage.serialize(destination=OUT / "staging_kg.ttl", format="turtle")
    (OUT / "event_extractions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in extraction_rows), encoding="utf-8"
    )
    with (OUT / "reaction_evaluation_status.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(issue_rows[0]))
        writer.writeheader(); writer.writerows(issue_rows)

    # Combine immutable base graphs in memory with this run's staging graph.
    combined = Graph()
    for graph in (base, market, stage):
        for triple in graph:
            combined.add(triple)
    ontology = Graph().parse(ROOT / "schema/ontology.ttl", format="turtle")
    shapes = Graph().parse(ROOT / "schema/shapes.ttl", format="turtle")
    conforms, report_graph, _ = validate(
        combined, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True
    )
    stage_nodes = set(event_ids + candidate_ids)
    violations = []
    for result in report_graph.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#ValidationResult")):
        focus = next(iter(report_graph.objects(result, URIRef("http://www.w3.org/ns/shacl#focusNode"))), None)
        if focus in stage_nodes or (focus and str(focus).startswith(str(W)) and any(str(focus) == str(x) for x in stage.subjects())):
            violations.append({
                "focusNode": str(focus) if focus else "",
                "message": str(next(iter(report_graph.objects(result, URIRef("http://www.w3.org/ns/shacl#resultMessage"))), "")),
                "path": str(next(iter(report_graph.objects(result, URIRef("http://www.w3.org/ns/shacl#resultPath"))), "")),
            })
    shacl_report = {
        "conforms": bool(conforms),
        "combinedGraphViolationCount": sum(1 for _ in report_graph.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#ValidationResult"))),
        "stagingEventCandidateViolationCount": len(violations),
        "stagingViolations": violations,
        "validationScope": "current immutable KG + current market observations + this run staging graph; no source writes",
    }
    (OUT / "shacl_validation.json").write_text(json.dumps(shacl_report, indent=2, ensure_ascii=False), encoding="utf-8")

    query = """PREFIX wfkg: <https://example.org/wfkg/v1#>
SELECT ?articleId ?title ?eventId ?eventType ?candidateId ?ticker ?reactionId WHERE {
  ?article a wfkg:NewsArticle ; wfkg:articleId ?articleId ; wfkg:title ?title ; wfkg:reports ?event .
  ?event wfkg:eventId ?eventId ; wfkg:eventType ?eventType ; wfkg:hasEventStockCandidate ?candidate .
  ?candidate wfkg:candidateId ?candidateId ; wfkg:candidateStock ?stock .
  ?stock wfkg:tickerSymbol ?ticker .
  OPTIONAL { ?candidate wfkg:hasReaction ?reaction . ?reaction wfkg:reactionId ?reactionId . }
  FILTER (?event IN (""" + ", ".join(f"<{e}>" for e in event_ids) + "))\n}\nORDER BY ?eventId ?articleId"
    (OUT / "news_event_candidate_reaction.rq").write_text(query + "\n", encoding="utf-8")
    query_rows = []
    for row in combined.query(query):
        query_rows.append({key: str(val) if val is not None else "" for key, val in zip(
            ["articleId", "title", "eventId", "eventType", "candidateId", "ticker", "reactionId"], row
        )})
    fields = ["articleId", "title", "eventId", "eventType", "candidateId", "ticker", "reactionId"]
    with (OUT / "sparql_results.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(query_rows)

    # Reproducibility manifest with immutable input and output digests.
    files = [MANIFEST, ENRICHED, KG_PATH, MARKET_PATH, ROOT / "schema/ontology.ttl", ROOT / "schema/shapes.ttl", ROOT / "scripts/run_wfkg_vertical_slice.py"]
    input_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    run_manifest = {
        "runAt": RUN_ISO,
        "cohortId": cohort.get("cohortId"),
        "cohortArticleCount": len(cohort_ids),
        "selectedArticleCount": len({r["articleId"] for r in extraction_rows}),
        "canonicalEventCount": len(event_ids),
        "candidateCount": len(candidate_ids),
        "reactionCount": 0,
        "reactionStatusCounts": {"NOT_EVALUATED": sum(r["status"] == "NOT_EVALUATED" for r in issue_rows)},
        "benchmarkRequested": "VN30",
        "benchmarkSavedObservationCounts": {k: len(v) for k, v in market_cov["index"].items()},
        "marketCoverage": {
            "stockTickers": {k: {"count": len(v), "from": min(v).isoformat(), "to": max(v).isoformat()} for k, v in market_cov["stock"].items()},
            "indices": {k: {"count": len(v), "from": min(v).isoformat(), "to": max(v).isoformat()} for k, v in market_cov["index"].items()},
        },
        "shacl": shacl_report,
        "sparqlResultRows": len(query_rows),
        "inputSha256": input_hashes,
        "outputSha256": {},
        "status": "CANDIDATE_SLICE_COMPLETE_REACTION_NOT_EVALUATED",
        "limitations": [
            "Current graph has VNINDEX observations but no VN30 observations; no benchmark substitution was made.",
            "Current saved bank observations end 2026-10-16. Evidence availableAt is after the HOSE 09:00 opening on that date; Day 0 is the next weekday session 2026-10-19, so the reaction windows are incomplete.",
            "The local repository has no separate formal evaluation-protocol document; scoring and market-reaction equations were taken from ontology/shapes and the fixed windows requested in this task.",
        ],
    }
    report = [
        "# WFKG vertical slice: NewsArticle → Evidence → Event → Candidate → staging KG → SPARQL",
        "",
        f"- Run: `{RUN_ISO}`; cohort `{cohort.get('cohortId')}` (100 fixed article IDs).",
        f"- Reviewed full-text articles: {run_manifest['selectedArticleCount']}; canonical Events: {len(event_ids)}; EventStockCandidates: {len(candidate_ids)}.",
        "- Event labels are analyst-reviewed rule-based annotations. They are not PhoBERT outputs or gold labels.",
        "- All candidates use the verified direct path Event → Bank/Company → Stock; direction remains UNKNOWN.",
        "- Candidate confidence uses the SHACL frozen mean: source 0.5, extraction 0.9 (uncalibrated pilot review), linking 1.0 (exact), relation 1.0 (KG edge verified). Candidate score = confidence × relationStrength.",
        f"- Requested benchmark VN30: saved observation count = {run_manifest['benchmarkSavedObservationCounts'].get('VN30', 0)}. Saved benchmark in KG is VNINDEX with {run_manifest['benchmarkSavedObservationCounts'].get('VNINDEX', 0)} rows; it was not substituted.",
        "- Bank adjusted-close observations end at 2026-10-16. Article/evidence availability times are on 2026-10-16 after HOSE opened at 09:00 local time, so the first session opening strictly later is Monday 2026-10-19. That Day 0 and all requested windows are not in the saved market dataset.",
        "- Reactions materialized: 0. Each candidate × window is `NOT_EVALUATED` due to missing post-event stock observations and missing VN30 benchmark observations; see `reaction_evaluation_status.csv`.",
        f"- SHACL combined graph conforms: {conforms}; combined violations: {shacl_report['combinedGraphViolationCount']}; staging Event/Candidate violations: {len(violations)}.",
        f"- SPARQL query returned {len(query_rows)} NewsArticle→Event→Candidate rows; `reactionId` is unbound because no valid Reaction can be created from available data.",
        "",
        "## Event evidence",
        "",
        "`event_extractions.jsonl` contains verbatim evidence spans, offsets into the cleaned full-text body, article IDs, canonical event IDs, source method and review notes. One Techcombank capital-approval Event is supported by two reports and shares one canonicalKey.",
        "",
        "## Baseline formulas and evaluation status",
        "",
        "The candidate calculation follows project code and SHACL: confidenceScore = mean(sourceConfidence, extractionConfidence, linkingConfidence, relationConfidence); candidateScore = confidenceScore × relationStrength. `relationStrength` is independent of reaction data.",
        "",
        "Requested reaction formulas are recorded in the per-window status CSV: stock/benchmark simple returns from consecutive adjusted closes, AR = stock return − VN30 return, CAR = sum of window AR, impactScore = min(1, abs(CAR)/0.10), reactionWeight = impactScore × confidenceScore × relationStrength, signedWeight = sign(CAR) × reactionWeight. No value was computed without the complete price/benchmark window.",
        "",
        "## Staging and reproducibility",
        "",
        "`staging_kg.ttl` contains only this run's Evidence, Event, article reports links and Candidate triples. It is kept under `runs/`; the main KG, RAW/CLEAN/DQS, enrichment, ontology and shapes were read-only. `run_manifest.json` stores input/output SHA-256 values. The SHACL run used the immutable current KG + saved market observations + staging graph in memory.",
        "",
        "## Remaining data needed to finish the Reaction chain",
        "",
        "1. A saved, provenance-bearing VN30 daily index series aligned to the bank observations.",
        "2. Bank and VN30 observations from Day 0 (2026-10-19) through at least Day 0 + 3, plus the preceding session for each return. Re-run only after those closes are available and verified.",
        "3. An explicit future trading-session calendar if an exchange holiday falls in the event window; this pilot's 2026-10-19 mapping uses the documented HOSE 09:00 open and ordinary weekday calendar.",
    ]
    (OUT / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    outputs = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "run_manifest.json")
    run_manifest["outputSha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}
    (OUT / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "output": str(OUT), "articles": run_manifest["selectedArticleCount"],
        "events": len(event_ids), "candidates": len(candidate_ids),
        "reactions": 0, "notEvaluatedWindows": run_manifest["reactionStatusCounts"]["NOT_EVALUATED"],
        "shaclConforms": bool(conforms), "stagingViolations": len(violations),
        "sparqlRows": len(query_rows), "vn30Observations": run_manifest["benchmarkSavedObservationCounts"].get("VN30", 0),
    }, indent=2))


if __name__ == "__main__":
    main()
