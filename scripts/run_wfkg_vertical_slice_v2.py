"""Build a new, auditable WFKG reaction staging run (v2).

This is deliberately separate from run_wfkg_vertical_slice.py and v1 outputs.
It preserves the original KG, market graph, corpus, ontology and SHACL files.
The staged NewsArticle records are publication-time projections: their
availableAt is the source publication time, while the accompanying audit
records the later time at which the local body/snapshot was collected.
"""
from __future__ import annotations

import csv, hashlib, json, math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, getcontext
from html.parser import HTMLParser
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/wfkg_vertical_slice_news_100_v2"
W = Namespace("https://example.org/wfkg/v1#")
TZ7 = timezone(timedelta(hours=7))
WINDOWS = [(0, 0), (0, 1), (-1, 1), (0, 3)]
RUN_TIME = datetime.now(timezone.utc).replace(microsecond=0)
RUN_ISO = RUN_TIME.isoformat().replace("+00:00", "Z")
MANIFEST = ROOT / "data/output/news_article_selection_manifest.json"
BODY = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
KG_PATH = ROOT / "data/gold/knowledge_graph.ttl"
MARKET_PATH = ROOT / "data/gold/market_observations.ttl"
VN30_PATH = OUT / "market_inputs/VN30_kbs_vnstock.json"
TBTCO_HTML = OUT / "tbtco_response.html"
OLD_EXTRACTIONS = OUT.parent / "wfkg_vertical_slice_news_100_v1/event_extractions.jsonl"
getcontext().prec = 28


def read_jsonl(path):
    return {x["articleId"]: x for x in map(json.loads, path.read_text(encoding="utf-8-sig").splitlines()) if x.get("articleId")}


def add(g, s, p, value, dtype=None):
    if isinstance(value, (URIRef, Literal)):
        obj = value
    elif dtype == XSD.decimal:
        obj = Literal(Decimal(str(value)), datatype=dtype)
    else:
        obj = Literal(value, datatype=dtype) if dtype else Literal(value)
    g.add((s, p, obj))


def one(g, s, p):
    xs = list(g.objects(s, p))
    if len(xs) != 1:
        raise ValueError(f"Expected exactly one {p} for {s}, got {len(xs)}")
    return xs[0]


def dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q(x):
    return Decimal(str(x))


def dstr(x):
    return format(x, ".15g") if isinstance(x, float) else str(x)


def next_hose_open(public_at, session_days):
    """First locally observed HOSE trading day whose 09:00 open is later."""
    local = public_at.astimezone(TZ7)
    for day in session_days:
        opening = datetime.combine(day, time(9, 0), TZ7)
        if opening > local:
            return day
    return None


def find_stock_observations(g):
    out = {}
    for stock in g.subjects(RDF.type, W.Stock):
        ticker = next(iter(g.objects(stock, W.tickerSymbol)), None)
        if not ticker:
            continue
        items = {}
        for obs in g.objects(stock, W.hasMarketObservation):
            d = next(iter(g.objects(obs, W.tradingDate)), None)
            if d:
                items[date.fromisoformat(str(d))] = obs
        out[str(ticker)] = (stock, items)
    return out


def market_index_projection(vn30, stage):
    index = W["INDEX:VN30"]
    add(stage, index, RDF.type, W.MarketIndex)
    add(stage, index, W.indexCode, "VN30", XSD.string)
    # The base KG already has the unique canonical indexName "VN30".
    observations = {}
    for item in vn30["observations"]:
        day = date.fromisoformat(item["tradingDate"])
        obs = W[item["observationId"]]
        observations[day] = obs
        add(stage, obs, RDF.type, W.MarketIndexObservation)
        add(stage, obs, W.observationId, item["observationId"], XSD.string)
        add(stage, obs, W.tradingDate, day.isoformat(), XSD.date)
        add(stage, obs, W.adjustedClose, item["adjustedClose"], XSD.decimal)
        add(stage, obs, W.returnValue, item["returnValue"], XSD.decimal)
        add(stage, obs, W.availableAt, item["availableAt"], XSD.dateTime)
        add(stage, obs, W.sourceReference, URIRef(item["sourceReference"]))
        add(stage, obs, W.instrumentCode, "VN30", XSD.string)
        add(stage, index, W.hasIndexObservation, obs)
    return index, observations


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "market_inputs").mkdir(exist_ok=True)
    cohort = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    body = read_jsonl(BODY)
    base = Graph().parse(KG_PATH, format="turtle")
    market = Graph().parse(MARKET_PATH, format="turtle")
    old = {x["articleId"]: x for x in map(json.loads, OLD_EXTRACTIONS.read_text(encoding="utf-8-sig").splitlines())}
    vn30 = json.loads(VN30_PATH.read_text(encoding="utf-8"))
    if len(cohort["articles"]) != 100 or len(vn30["observations"]) != 64:
        raise ValueError("Cohort or VN30 input count differs from audited expected count")
    cohort_ids = {x["articleId"] for x in cohort["articles"]}
    if not cohort_ids.issubset(body): raise ValueError("Cohort/article body ID mismatch")

    annotations = [
        {"key":"EARNINGS:TCB:2026Q2", "eventId":"EVENT:TCB:EARNINGS:2026Q2:V2", "type":"EARNINGS_ANNOUNCEMENT", "company":"COMPANY:TCB", "ticker":"TCB", "articles":["NEWS_ARTICLE:d87a5dfa9094c5f7491f"], "status":"NEEDS_REVIEW", "note":"Official Techcombank result/call pages identify July 22, but no exact first-publication time was verified; retain Day 0 as provisional and do not calculate reaction."},
        {"key":"CAPITAL_INCREASE_COMPLETION:MBB:2026-09-23", "eventId":"EVENT:MBB:CAPITAL_INCREASE:2026-09-23:V2", "type":"CAPITAL_INCREASE_COMPLETION", "company":"COMPANY:MBB", "ticker":"MBB", "articles":["NEWS_ARTICLE:057920a32d3d68452b4a"], "status":"EARLIEST_SOURCE_CONFLICT", "note":"The completed offer ended 2026-09-23 per the official filing attachment and TBTCO page. However, the official HOSE-linked disclosure listing is dated 2026-09-25 00:00 with no reliable intraday time; TBTCO is timestamped 17:18 that day, so it cannot establish earliest availability. Day 0/reaction are withheld."},
        {"key":"CAPITAL_INCREASE_APPROVAL:TCB:2026-10-13", "eventId":"EVENT:TCB:CAPITAL_INCREASE_APPROVAL:2026:V2", "type":"CAPITAL_INCREASE_APPROVAL", "company":"COMPANY:TCB", "ticker":"TCB", "articles":["NEWS_ARTICLE:64427a6e8c606384dd4f", "NEWS_ARTICLE:959096d14783f1fcfc54"], "status":"VERIFIED_PUBLICATION_TIME", "note":"Vietstock page gives 2026-10-13 17:51 ICT. Later CafeF report has a conflict between cohort manifest timestamp and visible Vietstock duplicate listing; it is not used as first timestamp."},
        {"key":"EARNINGS_ESTIMATE:SHB:2026Q3", "eventId":"EVENT:SHB:EARNINGS_ESTIMATE:2026Q3:V2", "type":"EARNINGS_ESTIMATE", "company":"COMPANY:SHB", "ticker":"SHB", "articles":["NEWS_ARTICLE:fa98bc3a32c14b237f00"], "status":"NEEDS_REVIEW", "note":"CafeF manifest has a timestamp, but SHB official page confirms only the date (Oct 16) without time; earlier official availability cannot be ruled out."},
    ]
    # Exact quote extracted from the saved TBTCO HTML response (not generated).
    parser = VisibleText(); parser.feed(TBTCO_HTML.read_text(encoding="utf-8-sig")); page_text = " ".join(parser.parts)
    tbtco_title = "MB hoàn tất chào bán hơn 805 triệu cổ phiếu, chạm đỉnh vốn điều lệ 100.000 tỷ đồng"
    tbtco_evidence = "Thời gian nhận đăng ký mua và nộp tiền đối với cổ đông hiện hữu từ ngày 18/8 đến ngày 7/9/2026; ngày kết thúc đợt chào bán là 23/9/2026. Kết thúc đợt chào bán, toàn bộ 805,5 triệu cổ phiếu đã được phân phối cho 116.316 nhà đầu tư, tương ứng 100% lượng chào bán."
    if tbtco_evidence not in page_text or "17:18 | 25/09/2026" not in page_text:
        raise ValueError("Saved TBTCO page no longer contains the audited quote/date")
    tbtco_pub = datetime(2026, 9, 25, 10, 18, tzinfo=timezone.utc)  # 17:18 ICT

    stage = Graph(); stage.bind("wfkg", W); stage.bind("xsd", XSD)
    old_by_article = old
    article_rows=[]; timestamp_rows=[]; event_rows=[]; candidate_rows=[]; reaction_rows=[]; window_rows=[]; market_rows=[]; tbtco_rows=[]
    stock_map = find_stock_observations(base)
    vn30_index, index_obs = market_index_projection(vn30, stage)
    sessions = sorted(set(date.fromisoformat(x["tradingDate"]) for x in vn30["observations"]))
    if not (date(2026, 9, 25) in sessions and date(2026, 10, 16) in sessions):
        raise ValueError("Expected market sessions absent from downloaded VN30 session calendar")

    # Source Article projection and Evidence resources; base KG article remains untouched.
    for ann in annotations:
        euri = W[ann["eventId"]]
        supports=[]
        article_ids = list(ann["articles"])
        for aid in article_ids:
            if aid not in cohort_ids: raise ValueError(f"Outside cohort: {aid}")
            oldrow = old_by_article[aid]
            original = W[aid]
            if (original, RDF.type, W.NewsArticle) not in base: raise ValueError(f"Article missing in base KG: {aid}")
            pub = dt(one(base, original, W.publishedAt))
            collected = dt(one(base, original, W.availableAt))
            source = one(base, original, W.publishedBy)
            projection = W["PUBLICATION_VIEW:" + aid.split(":",1)[1]]
            add(stage, projection, RDF.type, W.NewsArticle)
            for pred in (W.articleId, W.title): add(stage, projection, pred, one(base, original, pred), XSD.string)
            add(stage, projection, W.url, one(base, original, W.url))
            add(stage, projection, W.publishedAt, pub.isoformat(), XSD.dateTime)
            add(stage, projection, W.availableAt, pub.isoformat(), XSD.dateTime)
            add(stage, projection, W.publishedBy, source)
            add(stage, projection, W.sourceReference, original)
            bodytext = str(body[aid].get("bodyText", ""))
            saved_evidence = oldrow["evidenceText"]
            if saved_evidence not in bodytext:
                raise ValueError(f"Prior evidence span no longer aligns to cleaned body: {aid}")
            start = bodytext.find(saved_evidence); end = start + len(saved_evidence)
            evid = W["EVIDENCE:V2:" + aid.split(":",1)[1]]
            add(stage, evid, RDF.type, W.Evidence); add(stage, evid, W.evidenceId, str(evid).rsplit("#",1)[1], XSD.string)
            add(stage, evid, W.extractedFrom, projection); add(stage, evid, W.supports, euri)
            add(stage, evid, W.evidenceText, saved_evidence, XSD.string)
            add(stage, evid, W.startOffset, start, XSD.integer); add(stage, evid, W.endOffset, end, XSD.integer)
            add(stage, evid, W.availableAt, pub.isoformat(), XSD.dateTime)
            add(stage, projection, W.reports, euri)
            supports.append((pub, projection, evid, aid))
            article_rows.append({"articleId":aid,"articleUri":str(original),"publicationProjectionUri":str(projection),"title":str(one(base,original,W.title)),"url":str(one(base,original,W.url)),"publishedAtSource":pub.isoformat(),"kgAvailableAt_collection":collected.isoformat(),"enrichmentCapturedAt":str(body[aid].get("capturedAt","")),"evidenceAvailableAt":pub.isoformat(),"evidenceText":saved_evidence,"bodySha256":str(body[aid].get("cleanBodySha256") or body[aid].get("bodySha256") or ""),"temporalCaveat":"Body fetched/captured later than publication; no crawl-time historical HTML snapshot verified."})
            timestamp_rows.append({"recordType":"COHORT_ARTICLE","articleId":aid,"eventId":ann["eventId"],"publishedAt":pub.isoformat(),"collectedAvailableAt":collected.isoformat(),"enrichmentCapturedAt":str(body[aid].get("capturedAt","")),"sourceTimeBasis":"cohort KG publishedAt; source page audit where available","usedForDay0":ann["status"]=="VERIFIED_PUBLICATION_TIME","auditNote":ann["note"]})

        if ann["ticker"] == "MBB":
            source = W["NEWS_SOURCE:TBTCO"]
            add(stage, source, RDF.type, W.NewsSource); add(stage, source, W.sourceId, "NEWS_SOURCE:TBTCO", XSD.string)
            add(stage, source, W.sourceName, "Thời báo Tài chính Việt Nam (TBTCO)", XSD.string)
            add(stage, source, W.sourceType, "GOVERNMENT_FINANCIAL_NEWS", XSD.string)
            add(stage, source, W.reliabilityScore, Decimal("0.5"), XSD.decimal) # neutral registry placeholder; not used by candidate score
            ext = W["EXTERNAL_PUBLICATION:TBTCO:204399"]
            add(stage, ext, RDF.type, W.NewsArticle); add(stage, ext, W.articleId, "EXTERNAL_NEWS_ARTICLE:TBTCO:204399", XSD.string)
            add(stage, ext, W.title, tbtco_title, XSD.string)
            tbtco_url = URIRef("https://thoibaotaichinhvietnam.vn/mb-hoan-tat-chao-ban-hon-805-trieu-co-phieu-cham-dinh-von-dieu-le-100-000-ty-dong-204399.html")
            add(stage, ext, W.url, tbtco_url); add(stage, ext, W.publishedAt, tbtco_pub.isoformat(), XSD.dateTime); add(stage, ext, W.availableAt, tbtco_pub.isoformat(), XSD.dateTime)
            add(stage, ext, W.publishedBy, source); add(stage, ext, W.sourceReference, tbtco_url); add(stage, ext, W.reports, euri)
            evid = W["EVIDENCE:V2:TBTCO:204399"]
            add(stage, evid, RDF.type, W.Evidence); add(stage, evid, W.evidenceId, "EVIDENCE:V2:TBTCO:204399", XSD.string)
            add(stage, evid, W.extractedFrom, ext); add(stage, evid, W.supports, euri); add(stage, evid, W.evidenceText, tbtco_evidence, XSD.string)
            add(stage, evid, W.availableAt, tbtco_pub.isoformat(), XSD.dateTime)
            supports.append((tbtco_pub, ext, evid, "EXTERNAL_NEWS_ARTICLE:TBTCO:204399"))
            tbtco_rows.append({"url":str(tbtco_url),"publishedAt":"2026-09-25T17:18:00+07:00","capturedAt":RUN_ISO,"sha256":sha(TBTCO_HTML),"localSnapshot":str(TBTCO_HTML.relative_to(ROOT)),"quote":tbtco_evidence,"sourceAssessment":"Financial news source citing MB; exact time present in saved page. No direct MB announcement timestamp located."})
            timestamp_rows.append({"recordType":"EXTERNAL_SOURCE_ARTICLE","articleId":"EXTERNAL_NEWS_ARTICLE:TBTCO:204399","eventId":ann["eventId"],"publishedAt":tbtco_pub.isoformat(),"collectedAvailableAt":tbtco_pub.isoformat(),"enrichmentCapturedAt":RUN_ISO,"sourceTimeBasis":"page byline/publication time 17:18 ICT 25 Sep 2026","usedForDay0":True,"auditNote":"Saved current HTML verifies published timestamp and content; capture time is not the publication time."})

        available_at = min(x[0] for x in supports)
        day0 = next_hose_open(available_at, sessions)
        if day0 is None: raise ValueError(f"No later session in saved market calendar for {ann['eventId']}")
        add(stage,euri,RDF.type,W.Event); add(stage,euri,W.eventId,ann["eventId"],XSD.string); add(stage,euri,W.canonicalKey,ann["key"],XSD.string)
        add(stage,euri,W.eventType,ann["type"],XSD.string)
        add(stage,euri,W.description,ann["note"],XSD.string); add(stage,euri,W.availableAt,available_at.isoformat(),XSD.dateTime)
        add(stage,euri,W.effectiveTradingDate,day0.isoformat(),XSD.date); add(stage,euri,W.involvesCompany,W[ann["company"]])
        event_rows.append({"eventId":ann["eventId"],"canonicalKey":ann["key"],"ticker":ann["ticker"],"earliestEvidenceAvailableAt":available_at.isoformat(),"day0":day0.isoformat(),"timestampAuditStatus":ann["status"],"calculationEligibility":"ELIGIBLE" if ann["status"]=="VERIFIED_PUBLICATION_TIME" else "NOT_EVALUATED","earliestEvidenceArticle":str(min(supports,key=lambda x:x[0])[1]),"supportingEvidenceCount":len(supports),"note":ann["note"]})

        stock = W[f"HOSE:{ann['ticker']}"]
        if (W[ann["company"]], W.hasStock, stock) not in base: raise ValueError(f"KG direct path missing for {ann['ticker']}")
        candidate = W["CANDIDATE:V2:"+ann["ticker"]+":"+ann["key"].replace(":","_")]
        conf=Decimal("0.85"); strength=Decimal("1.0"); score=conf*strength
        add(stage,euri,W.hasEventStockCandidate,candidate); add(stage,candidate,RDF.type,W.EventStockCandidate)
        for p,v,dtype in [(W.candidateId,str(candidate).rsplit("#",1)[1],XSD.string),(W.impactType,"DIRECT",XSD.string),(W.relationPath,"DIRECT",XSD.string),(W.candidateReason,ann["note"],XSD.string),(W.expectedDirection,"UNKNOWN",XSD.string),(W.relationStrength,strength,XSD.decimal),(W.sourceConfidence,Decimal("0.5"),XSD.decimal),(W.extractionConfidence,Decimal("0.9"),XSD.decimal),(W.linkingConfidence,Decimal("1.0"),XSD.decimal),(W.relationConfidence,Decimal("1.0"),XSD.decimal),(W.confidenceScore,conf,XSD.decimal),(W.candidateScore,score,XSD.decimal),(W.inferenceCutoff,available_at.isoformat(),XSD.dateTime),(W.generatedAt,RUN_ISO,XSD.dateTime),(W.availableAt,RUN_ISO,XSD.dateTime),(W.methodVersion,"analyst-reviewed-rule-event-mvp-0.2-publication-audit",XSD.string)]: add(stage,candidate,p,v,dtype)
        add(stage,candidate,W.forEvent,euri); add(stage,candidate,W.candidateStock,stock)
        so=stock_map.get(ann["ticker"],(None,{}))[1]
        can_react=ann["status"]=="VERIFIED_PUBLICATION_TIME"
        complete_windows=[]
        for lo,hi in WINDOWS:
            offset_days=list(range(lo-1,hi+1))
            idx0=sessions.index(day0) if day0 in sessions else -1
            needed=[sessions[idx0+offset] for offset in offset_days] if idx0>=0 and idx0+min(offset_days)>=0 and idx0+max(offset_days)<len(sessions) else []
            reasons=[]
            if not can_react: reasons.append("Publication timestamp/earliest-information time is not sufficiently verified for historical Day 0.")
            if not needed: reasons.append("Required HOSE session dates exceed the saved VN30 calendar.")
            elif any(d not in so for d in needed): reasons.append("One or more MBB/TCB adjusted-close observations are absent.")
            elif any(d not in index_obs for d in needed): reasons.append("One or more VN30 observations are absent.")
            if reasons:
                window_rows.append({"eventId":ann["eventId"],"candidateId":str(candidate),"ticker":ann["ticker"],"window":f"[{lo},{hi:+d}]","startOffset":lo,"endOffset":hi,"day0":day0.isoformat(),"status":"NOT_EVALUATED","reason":" ".join(reasons),"requiredTradingDates":";".join(d.isoformat() for d in needed)})
                continue
            # Use each observed session's already-validated simple return. Provenance stores window days plus predecessor.
            ars={}
            for off in range(lo,hi+1):
                d=sessions[idx0+off]
                stock_r=q(one(base,so[d],W.returnValue)); index_r=q(one(stage,index_obs[d],W.returnValue))
                ars[d]=stock_r-index_r
            car=sum(ars.values(),Decimal(0)); day0ar=ars[day0]
            impact=min(Decimal(1),abs(car)/Decimal("0.10")); weight=impact*conf*strength
            signed=weight if car>0 else (-weight if car<0 else Decimal(0))
            direction="POSITIVE" if car>0 else ("NEGATIVE" if car<0 else "NEUTRAL")
            rid=W["REACTION:V2:"+ann["ticker"]+":"+ann["key"].replace(":","_")+f":{lo}_{hi}"]
            add(stage,candidate,W.hasReaction,rid)
            add(stage,rid,RDF.type,W.EventStockReaction); add(stage,rid,W.reactionId,str(rid).rsplit("#",1)[1],XSD.string)
            add(stage,rid,W.onCandidate,candidate); add(stage,rid,W.benchmarkIndex,vn30_index)
            add(stage,rid,W.windowStartOffset,lo,XSD.integer); add(stage,rid,W.windowEndOffset,hi,XSD.integer)
            add(stage,rid,W.abnormalReturn,day0ar,XSD.decimal); add(stage,rid,W.cumulativeAbnormalReturn,car,XSD.decimal)
            add(stage,rid,W.marketReactionDirection,direction,XSD.string); add(stage,rid,W.impactScore,impact,XSD.decimal)
            add(stage,rid,W.reactionWeight,weight,XSD.decimal); add(stage,rid,W.signedWeight,signed,XSD.decimal)
            add(stage,rid,W.availableAt,RUN_ISO,XSD.dateTime); add(stage,rid,W.methodVersion,"daily-adjusted-close-ar-car-vn30-0.1",XSD.string)
            provdates=[sessions[idx0+off] for off in offset_days]
            for d in provdates:
                add(stage,rid,W.derivedFromObservation,so[d]); add(stage,rid,W.derivedFromIndexObservation,index_obs[d])
            complete_windows.append((lo,hi))
            stock_close={d:Decimal(str(one(base,so[d],W.adjustedClose))) for d in provdates}
            index_close={d:Decimal(str(one(stage,index_obs[d],W.adjustedClose))) for d in provdates}
            reaction_rows.append({"reactionId":str(rid),"eventId":ann["eventId"],"candidateId":str(candidate),"ticker":ann["ticker"],"benchmark":"VN30","window":f"[{lo},{hi:+d}]","day0":day0.isoformat(),"abnormalReturnDay0":dstr(day0ar),"CAR":dstr(car),"impactScore":dstr(impact),"confidenceScore":dstr(conf),"relationStrength":dstr(strength),"reactionWeight":dstr(weight),"signedWeight":dstr(signed),"direction":direction,"inputDates":";".join(d.isoformat() for d in provdates),"stockAdjustedClose":";".join(dstr(stock_close[d]) for d in provdates),"vn30Close":";".join(dstr(index_close[d]) for d in provdates),"stockObservationUris":";".join(str(so[d]) for d in provdates),"vn30ObservationUris":";".join(str(index_obs[d]) for d in provdates)})
        add(stage,candidate,W.candidateStatus,"REACTION_READY" if complete_windows else "PENDING_MARKET_WINDOW",XSD.string)
        candidate_rows.append({"candidateId":str(candidate),"eventId":ann["eventId"],"ticker":ann["ticker"],"confidenceScore":dstr(conf),"relationStrength":dstr(strength),"candidateScore":dstr(score),"status":"REACTION_READY" if complete_windows else "PENDING_MARKET_WINDOW","reactionWindowsComputed":len(complete_windows)})

    # Page-level timestamp reconciliation captured during this run. The CafeF
    # HTML reports local ICT time; the cohort manifest serializes the same
    # clock value with a Z suffix, which would shift it +7h if treated as UTC.
    cafe_id = "NEWS_ARTICLE:959096d14783f1fcfc54"
    viet_id = "NEWS_ARTICLE:64427a6e8c606384dd4f"
    cafe_graph_pub = dt(one(base, W[cafe_id], W.publishedAt))
    viet_graph_pub = dt(one(base, W[viet_id], W.publishedAt))
    timestamp_rows.extend([
        {"recordType":"SOURCE_PAGE_TIMESTAMP_CHECK","articleId":cafe_id,"eventId":"EVENT:TCB:CAPITAL_INCREASE_APPROVAL:2026:V2","publishedAt":cafe_graph_pub.isoformat(),"collectedAvailableAt":dt(one(base,W[cafe_id],W.availableAt)).isoformat(),"enrichmentCapturedAt":str(body[cafe_id].get("capturedAt","")),"sourceTimeBasis":"CafeF page byline shows 14-10-2026 16:05 PM ICT; source HTML saved in v2","usedForDay0":False,"auditNote":"Cohort graph timestamp is 2026-10-14T16:05:00Z; interpreting Z literally gives 23:05 ICT, a +7h timezone serialization mismatch. CafeF page capture is current, not a historical snapshot."},
        {"recordType":"SOURCE_PAGE_TIMESTAMP_CHECK","articleId":viet_id,"eventId":"EVENT:TCB:CAPITAL_INCREASE_APPROVAL:2026:V2","publishedAt":viet_graph_pub.isoformat(),"collectedAvailableAt":dt(one(base,W[viet_id],W.availableAt)).isoformat(),"enrichmentCapturedAt":str(body[viet_id].get("capturedAt","")),"sourceTimeBasis":"Vietstock page shows 13/10/2026 17:51 ICT; source HTML saved in v2","usedForDay0":True,"auditNote":"Page-local timestamp matches the cohort UTC timestamp after +07 conversion. Earliest verified source for this canonical Event among cohort reports."},
        {"recordType":"OFFICIAL_FILING_DATE_ONLY","articleId":"EXTERNAL_HOSE_DISCLOSURE:MBB:20260924","eventId":"EVENT:MBB:CAPITAL_INCREASE:2026-09-23:V2","publishedAt":"DATE_ONLY_2026-09-25","collectedAvailableAt":"","enrichmentCapturedAt":RUN_ISO,"sourceTimeBasis":"CafeF corporate-disclosure listing links a report attributed to HOSE; display time 25/09/2026 00:00 is a date-only placeholder. Attached PDF filename is 20260924.","usedForDay0":False,"auditNote":"Official source confirms event/results but does not provide a verifiable time of public release. Because TBTCO at 17:18 ICT is later on the same date, it cannot establish earliest availability; Day 0 remains unresolved."},
    ])
    source_capture_manifest={"capturedAt":RUN_ISO,"note":"Current page captures used to audit displayed publication timestamps; they are not historical HTML snapshots.","sources":[
      {"articleId":cafe_id,"url":"https://cafef.vn/techcombank-tang-von-khung-mo-rong-du-dia-tang-truong-188261014160544014.chn","pageDisplayedPublishedAt":"2026-10-14 16:05 ICT","cohortGraphPublishedAt":cafe_graph_pub.isoformat(),"localSnapshot":"cafef_tcb_capital_article.html","sha256":sha(OUT/"cafef_tcb_capital_article.html")},
      {"articleId":viet_id,"url":"https://vietstock.vn/2026/10/techcombank-duoc-phe-duyet-tang-von-dieu-le-len-tren-106-ngan-ty-dan-dau-nganh-ngan-hang-757-1502000.htm","pageDisplayedPublishedAt":"2026-10-13 17:51 ICT","cohortGraphPublishedAt":viet_graph_pub.isoformat(),"localSnapshot":"vietstock_tcb_approval_article.html","sha256":sha(OUT/"vietstock_tcb_approval_article.html")},
      {"articleId":"EXTERNAL_NEWS_ARTICLE:TBTCO:204399","url":"https://thoibaotaichinhvietnam.vn/mb-hoan-tat-chao-ban-hon-805-trieu-co-phieu-cham-dinh-von-dieu-le-100-000-ty-dong-204399.html","pageDisplayedPublishedAt":"2026-09-25 17:18 ICT","localSnapshot":"tbtco_response.html","sha256":sha(TBTCO_HTML)},
      {"articleId":"EXTERNAL_HOSE_DISCLOSURE:MBB:20260924","url":"https://cafef.vn/du-lieu/mbb-2984342/mbb-da-chao-ban-805499990-co-phieu-ra-cong-chung.chn","pageDisplayedPublishedAt":"2026-09-25 (00:00 displayed; exact time unverified)","officialAttachment":"20260924 - MBB - Bao cao ket qua dot chao ban co phieu ra cong chung.pdf","attachmentLocalSnapshot":"mbb_hose_share_offer_report.pdf","attachmentSha256":sha(OUT/"mbb_hose_share_offer_report.pdf"),"listingLocalSnapshot":"mbb_hose_disclosure_listing.html","listingSha256":sha(OUT/"mbb_hose_disclosure_listing.html")} ]}

    # Market source audit: VN30 close levels from KBS/Vnstock, not corporate-action-adjusted equity prices.
    for item in vn30["observations"]:
        market_rows.append({"ticker":"VN30","tradingDate":item["tradingDate"],"adjustedCloseSchemaValue":item["adjustedClose"],"returnValue":item["returnValue"],"source":vn30["providerName"],"method":"Published VN30 index close level; stored in adjustedClose field because the schema uses that field for both stock/index observations. No corporate-action adjustment applies to index level.","availableAt":item["availableAt"],"sourceReference":item["sourceReference"],"rawFileSha256":sha(VN30_PATH)})
    for ticker in ("MBB","TCB"):
        obsmap=stock_map[ticker][1]
        for d,obs in sorted(obsmap.items()):
            market_rows.append({"ticker":ticker,"tradingDate":d.isoformat(),"adjustedCloseSchemaValue":str(one(base,obs,W.adjustedClose)),"returnValue":str(one(base,obs,W.returnValue)),"source":"Existing immutable KG market observations (KBS source provenance)","method":"Adjusted close supplied by existing market observation; not modified in v2.","availableAt":str(one(base,obs,W.availableAt)),"sourceReference":str(one(base,obs,W.sourceReference)),"rawFileSha256":sha(MARKET_PATH)})

    stage.serialize(destination=OUT/"staging_kg.ttl",format="turtle")
    def write_csv(name, rows):
        if not rows: return
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
            wr=csv.DictWriter(f,fieldnames=fields); wr.writeheader(); wr.writerows(rows)
    write_csv("article_timestamp_audit.csv",timestamp_rows)
    write_csv("event_timestamp_day0_audit.csv",event_rows)
    write_csv("article_publication_evidence.csv",article_rows)
    write_csv("market_input_audit.csv",market_rows)
    write_csv("reaction_evaluation_status.csv",window_rows)
    write_csv("reaction_results.csv",reaction_rows)
    write_csv("candidate_results.csv",candidate_rows)
    write_csv("external_source_evidence.csv",tbtco_rows)
    (OUT/"source_timestamp_evidence_manifest.json").write_text(json.dumps(source_capture_manifest,indent=2,ensure_ascii=False),encoding="utf-8")

    combined=Graph()
    for g in (base,market,stage):
        for t in g: combined.add(t)
    ontology=Graph().parse(ROOT/"schema/ontology.ttl",format="turtle")
    shapes=Graph().parse(ROOT/"schema/shapes.ttl",format="turtle")
    conforms, report_graph, report_text=validate(combined,shacl_graph=shapes,ont_graph=ontology,inference="rdfs",advanced=True)
    sh=Namespace("http://www.w3.org/ns/shacl#")
    violations=[]
    for r in report_graph.subjects(RDF.type,sh.ValidationResult):
        violations.append({"focusNode":str(next(iter(report_graph.objects(r,sh.focusNode)),"")),"path":str(next(iter(report_graph.objects(r,sh.resultPath)),"")),"message":str(next(iter(report_graph.objects(r,sh.resultMessage)),""))})
    (OUT/"shacl_validation.json").write_text(json.dumps({"conforms":bool(conforms),"violationCount":len(violations),"violations":violations,"scope":"immutable base KG + immutable saved stock observations + v2 VN30 index observations + v2 staging; no source graph writes"},indent=2,ensure_ascii=False),encoding="utf-8")

    query="""PREFIX wfkg: <https://example.org/wfkg/v1#>
SELECT ?articleId ?title ?evidenceId ?eventId ?ticker ?candidateId ?reactionId ?start ?end ?car WHERE {
 ?article a wfkg:NewsArticle ; wfkg:articleId ?articleId ; wfkg:title ?title ; wfkg:reports ?event .
 ?evidence a wfkg:Evidence ; wfkg:extractedFrom ?article ; wfkg:supports ?event ; wfkg:evidenceId ?evidenceId .
 ?event wfkg:eventId ?eventId ; wfkg:hasEventStockCandidate ?candidate .
 ?candidate wfkg:candidateId ?candidateId ; wfkg:candidateStock ?stock . ?stock wfkg:tickerSymbol ?ticker .
 ?candidate wfkg:hasReaction ?reaction .
 ?reaction wfkg:reactionId ?reactionId ; wfkg:windowStartOffset ?start ; wfkg:windowEndOffset ?end ; wfkg:cumulativeAbnormalReturn ?car .
 FILTER(?event IN ("""+", ".join(f"<{W[x['eventId']]}>" for x in annotations)+"))\n}\nORDER BY ?eventId ?articleId ?start ?end"
    (OUT/"news_event_candidate_reaction.rq").write_text(query+"\n",encoding="utf-8")
    query_rows=[]
    for row in combined.query(query): query_rows.append({k:(str(v) if v is not None else "") for k,v in zip(["articleId","title","evidenceId","eventId","ticker","candidateId","reactionId","windowStartOffset","windowEndOffset","CAR"],row)})
    write_csv("sparql_results.csv",query_rows)
    (OUT/"shacl_report.txt").write_text(str(report_text),encoding="utf-8")

    # Hash all inputs and outputs, including explicit source capture and run code.
    inputs=[MANIFEST,BODY,KG_PATH,MARKET_PATH,ROOT/"schema/ontology.ttl",ROOT/"schema/shapes.ttl",ROOT/"scripts/run_wfkg_vertical_slice.py",ROOT/"scripts/run_wfkg_vertical_slice_v2.py",ROOT/"doc/gop_y_phase1_truoc_code_phase2.txt",VN30_PATH,TBTCO_HTML,OUT/"cafef_tcb_capital_article.html",OUT/"vietstock_tcb_approval_article.html",OUT/"mbb_hose_disclosure_listing.html",OUT/"mbb_hose_share_offer_report.pdf"]
    input_hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    outputs={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="run_manifest.json"}
    manifest={"runAt":RUN_ISO,"cohortId":cohort.get("cohortId"),"cohortArticleCount":len(cohort_ids),"events":len(annotations),"candidates":len(candidate_rows),"computedReactions":len(reaction_rows),"notEvaluatedWindows":sum(x["status"]=="NOT_EVALUATED" for x in window_rows),"vn30ObservationCount":len(vn30["observations"]),"vn30Range":[vn30["firstTradingDate"],vn30["lastTradingDate"]],"vn30Source":vn30["providerName"],"vn30Method":"KBS/Vnstock reported index close; index value copied to schema adjustedClose, not an equity-style corporate-action adjustment","shaclConforms":bool(conforms),"shaclViolations":len(violations),"sparqlRows":len(query_rows),"inputSha256":input_hashes,"outputSha256":outputs,"temporalPolicy":"Day 0 = first evidenced HOSE session whose 09:00 ICT open is strictly later than earliest verified public Evidence.availableAt. Crawl/capture timestamps are audited separately and never substituted for publication time.","caveats":["Staging publication-view articles keep source publication time separate from later KG collection and enrichment capture times.","Bodies were collected after publication and no crawl-time historical HTML snapshots for cohort articles were verified; the extracted text is a retrospective evidence reconstruction.","TBTCO page is captured during this run and its displayed publication time/content are not a byte-for-byte historical archive from 25 Sep.","KBS/Vnstock exposes VN30 index close, not a separately adjusted index close. The field is mapped to adjustedClose because that is the ontology's market-level value field; no VNINDEX substitution was made.","Three TCB-capital reactions are computed. MBB is withheld because an official HOSE-linked filing is date-only and predates the timestamped TBTCO report; TCB earnings and SHB windows are withheld due to unresolved earliest-publication-time evidence; TCB capital [0,+3] extends beyond saved data."]}
    (OUT/"run_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    report=["# WFKG vertical slice v2: publication-time audit and market reaction","",f"Run: `{RUN_ISO}`; fixed cohort `{cohort.get('cohortId')}` (100 IDs).","", "## Results", "",f"- Canonical Events: {len(annotations)}; Candidates: {len(candidate_rows)}; computed Reactions: {len(reaction_rows)}; NOT_EVALUATED windows: {manifest['notEvaluatedWindows']}",f"- New VN30 observations: {len(vn30['observations'])}, 2026-07-16 through 2026-10-16; source {vn30['providerName']} via Vnstock/KBS.",f"- SHACL conforms: {bool(conforms)} ({len(violations)} validation results). SPARQL returned {len(query_rows)} Article -> Evidence -> Event -> Candidate -> Reaction rows.","- TCB capital-approval event has a fully linked path and three calculated windows. MBB is retained for audit, but its reactions are withheld because the official filing has no reliable publication time.","", "## Temporal audit and Day 0", "", "Day 0 uses the earliest timestamped source-publication Evidence.availableAt, not KG collection or enrichment capturedAt. Staging Article projections separate source publication from later collection. Day 0 is the first observed HOSE session whose 09:00 ICT open is strictly later than that timestamp. The VN30 session sequence is cross-checked against the stock observations; HOSE's published schedule states trading starts at 09:00.","", "TBTCO says the MBB offer ended on 23 Sep 2026. CafeF lists a HOSE-attributed disclosure dated 25 Sep 2026 and displays 00:00; the attachment filename is dated 24 Sep. No reliable intraday publication time was found. TBTCO is timestamped 17:18 ICT on 25 Sep, so it cannot prove first public availability. The event's candidate Day 0 (28 Sep) is provisional and all MBB reactions are NOT_EVALUATED.","", "For TCB capital approval, Vietstock displays 13 Oct 2026 17:51 ICT; Day 0 is 14 Oct. No earlier official issuer/regulator publication time was verified in the searched materials. CafeF's later duplicate shows 14 Oct 16:05 ICT, while the cohort graph stores `2026-10-14T16:05:00Z`; interpreting the Z literally would shift this to 23:05 ICT, a +07 timezone serialization mismatch. It does not change first-source selection. TCB Q2 earnings and SHB 9M estimate remain NOT_EVALUATED due to uncertain earliest public time.","", "KG `availableAt` (collection), enrichment `capturedAt`, source `publishedAt`, and Evidence time are reported separately. Page captures made during this run do not prove byte-for-byte historical content. See `article_timestamp_audit.csv` and `source_timestamp_evidence_manifest.json`.","", "## Market inputs and formulas", "", "MBB/TCB adjusted-close values are read from the immutable market graph; each Reaction row stores observation URIs and closes. VN30 daily index close levels were retrieved through Vnstock's KBS market route and saved with raw OHLCV, retrieval metadata, source URL and SHA-256. Vnstock documents `Market().index(symbol).ohlcv()` and KBS as an available domestic source. VN30 close is stored in ontology `adjustedClose` as the equivalent index closing level; no corporate-action adjustment applies to an index, and VNINDEX was not substituted.","", "For each session t: stockReturn = close(t)/close(t-1)-1; VN30Return likewise; AR_t = stockReturn - VN30Return. CAR is the sum of daily AR over the requested window. impactScore=min(1,abs(CAR)/0.10); reactionWeight=impactScore x Candidate.confidenceScore x relationStrength; signedWeight=sign(CAR) x reactionWeight. Candidate score remains independent of post-event returns.","", "TCB capital approval: [0,0], [0,+1], and [-1,+1] evaluated; [0,+3] NOT_EVALUATED because the next session lies beyond saved data ending 16 Oct. MBB: all four windows withheld due to source-time conflict. Q2 earnings and SHB: all windows withheld due to publication-time uncertainty. See `reaction_results.csv` and `reaction_evaluation_status.csv`.","", "## KG validation and query", "", "The v2 graph adds publication-time Article projections, Evidence, Events, Candidates, VN30 observations and valid Reaction nodes. SHACL runs against immutable base KG + existing stock market graph + v2 staging. `news_event_candidate_reaction.rq` joins Article -> Evidence -> Event -> Candidate -> Reaction and outputs ticker, window and CAR in `sparql_results.csv`.","", "## Reproducibility and limitations", "", "Input/output SHA-256 values are in `run_manifest.json`. The v1 run remains untouched. No RAW/CLEAN, ontology, SHACL, source graph or main KG files were modified. Current-source HTML captures and later full-text bodies cannot prove byte-level historical content; better archived publisher/issuer records could change eligibility. The in-repository protocol is represented by ontology, SHACL and `doc/gop_y_phase1_truoc_code_phase2.txt`; there is no separate formal protocol artifact.",""]
    report += ["", "## Day 0 audit table", "", "| Event | Earliest timestamped evidence | Day 0 from strict 09:00 rule | Eligibility |", "|---|---|---:|---|"]
    for x in event_rows:
        report.append(f"| {x['eventId']} | {x['earliestEvidenceAvailableAt']} | {x['day0']} | {x['calculationEligibility']} ({x['timestampAuditStatus']}) |")
    report += ["", "## Evaluated reactions", "", "| Ticker | Window | Day 0 | AR at Day 0 | CAR | impactScore | reactionWeight | signedWeight |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for x in reaction_rows:
        report.append(f"| {x['ticker']} | {x['window']} | {x['day0']} | {x['abnormalReturnDay0']} | {x['CAR']} | {x['impactScore']} | {x['reactionWeight']} | {x['signedWeight']} |")
    (OUT/"report.md").write_text("\n".join(report),encoding="utf-8")
    # Refresh output hashes to include report.
    manifest["outputSha256"]={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="run_manifest.json"}
    (OUT/"run_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"out":str(OUT),"events":len(annotations),"candidates":len(candidate_rows),"reactions":len(reaction_rows),"notEvaluated":manifest["notEvaluatedWindows"],"shaclConforms":bool(conforms),"shaclViolations":len(violations),"sparqlRows":len(query_rows)},ensure_ascii=False))

if __name__=="__main__": main()
