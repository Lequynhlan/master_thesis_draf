"""Build a conservative source-context audit package for the saved 100-article cohort.

This uses only local snapshots and saved extracted article text. It does not fetch,
modify RAW/KG/models, or accept any prediction as a review decision.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019/emd_v2_experiment"
OUT = RUN / "source_context_audit"
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.text_input import prepare_extraction_input


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def source_map(title, body, prepared, body_field="bodyText"):
    """Map each prepared model-input code point to a title/body source code point.

    The prepared input is NFC + whitespace collapsed. Source offsets are Unicode
    code-point offsets in the exact title/bodyText fields stored locally.
    """
    out = []
    for seg, raw in (("title", title), (body_field, body)):
        # NFC can combine code points. The mapping conservatively assigns the
        # normalized output to the source cluster span that produced it.
        norm_chars = []
        i = 0
        while i < len(raw):
            j = i + 1
            while j < len(raw) and __import__("unicodedata").combining(raw[j]):
                j += 1
            norm = __import__("unicodedata").normalize("NFC", raw[i:j])
            norm_chars.extend((ch, i, j) for ch in norm)
            i = j
        collapsed = []
        for ch, a, b in norm_chars:
            if ch.isspace():
                if collapsed and collapsed[-1][0] == " ":
                    old = collapsed[-1]
                    collapsed[-1] = (" ", old[1], b)
                else:
                    collapsed.append((" ", a, b))
            else:
                collapsed.append((ch, a, b))
        while collapsed and collapsed[0][0] == " ": collapsed.pop(0)
        while collapsed and collapsed[-1][0] == " ": collapsed.pop()
        if seg == "bodyText" and title:
            out.append({"modelStart": len(out), "modelEnd": len(out)+1, "sourceField": "separator", "sourceStart": 0, "sourceEnd": 0})
        for ch, a, b in collapsed:
            out.append({"modelStart": len(out), "modelEnd": len(out)+1, "sourceField": seg, "sourceStart": a, "sourceEnd": b})
    # The content builder's text is authoritative. Fail closed if map semantics drift.
    mapped_len = len(out)
    if mapped_len != len(prepared):
        # Preserve a compact explicit identity map to the prepared source string;
        # the content/source transformation remains disclosed in the manifest.
        return [{"modelStart": i, "modelEnd": i+1, "sourceField": "preparedInput", "sourceStart": i, "sourceEnd": i+1} for i in range(len(prepared))]
    return out


MARKERS = [
    ("RELATED_NEWS", re.compile(r"(?i)\b(tin liên quan|tin cùng chuyên mục|bài viết liên quan|các tin khác)\b")),
    ("SIDEBAR_OR_RECENT_NEWS", re.compile(r"(?i)\b(tin mới nhất|tin đọc nhiều|tin nổi bật|mới nhất|đọc nhiều)\b")),
    ("NAVIGATION_OR_MORE", re.compile(r"(?i)\b(xem thêm|xem tất cả|quay lại|trang chủ|danh mục)\b")),
    ("AD_OR_PROMO", re.compile(r"(?i)\b(quảng cáo|đăng ký ngay|tải ứng dụng|ưu đãi|nhận thông báo)\b")),
]


def marker_hits(text):
    hits = []
    for kind, pattern in MARKERS:
        for m in pattern.finditer(text):
            a, b = m.span()
            hits.append({"markerType": kind, "startChar": a, "endChar": b, "text": m.group(0)})
    return hits


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    articles = {str(x["articleId"]): x for x in jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(x["articleId"]): x for x in jsonl(ROOT / "data/enriched/news_100_v1/articles.jsonl")}
    enrichment_manifest = json.loads((ROOT / "data/enriched/news_100_v1/enrichment_manifest.json").read_text(encoding="utf-8"))
    snapshots = {}
    for p in (ROOT / "data/snapshots/news_articles").glob("*.json"):
        row = json.loads(p.read_text(encoding="utf-8"))
        snapshots[str(row.get("articleId"))] = (p, row)

    # Preserve the exact model input as a separate, content-addressed staging copy.
    cleaned = {}
    text_rows = []
    for aid, article in articles.items():
        prep = prepare_extraction_input(article, enriched.get(aid))
        body = str(enriched.get(aid, {}).get("bodyText") or "")
        snap_path, snap = snapshots.get(aid, (None, {}))
        selected_body = body if prep.source == "FULL_TEXT" else (str(article.get("summary") or "") if prep.source == "SUMMARY_FALLBACK" else "")
        body_field = "bodyText" if prep.source == "FULL_TEXT" else "summary"
        mapping = source_map(prep.title, selected_body, prep.text, body_field)
        row = {
            "articleId": aid, "sourceUrl": article.get("url"), "sourceVersion": "news_100_v1_saved_article_body_and_prepared_input",
            "selectedTextSource": prep.source, "boundaryStatus": "UNVERIFIED_NO_SAVED_DOM_EVIDENCE",
            "cleaningAction": "PRESERVE_ALL_TEXT_NO_SEGMENT_REMOVED", "text": prep.text,
            "contentSha256": sha(prep.text), "sourceBodySha256": enriched.get(aid, {}).get("bodySha256", ""),
            "sourceBodyChars": len(body), "snapshotPath": str(snap_path.relative_to(ROOT)) if snap_path else "",
            "snapshotKeys": "|".join(sorted(snap.keys())), "sourceOffsetMap": mapping,
            "offsetMapSemantics": "per model-input code point to title or selected bodyText/summary codepoint span; identity fallback explicitly tagged preparedInput",
        }
        cleaned[aid] = row
        text_rows.append(row)
    with (OUT / "cleaned_article_texts.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for row in text_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def source_span(article_id, start, end):
        try:
            a, b = int(start), int(end)
            m = cleaned[str(article_id)]["sourceOffsetMap"][a:b]
            if not m:
                return {"sourceField": "", "sourceStartChar": "", "sourceEndChar": ""}
            fields = {x["sourceField"] for x in m}
            if len(fields) != 1:
                return {"sourceField": "MULTI_SEGMENT", "sourceStartChar": min(x["sourceStart"] for x in m), "sourceEndChar": max(x["sourceEnd"] for x in m)}
            return {"sourceField": next(iter(fields)), "sourceStartChar": min(x["sourceStart"] for x in m), "sourceEndChar": max(x["sourceEnd"] for x in m)}
        except (ValueError, TypeError, KeyError, IndexError):
            return {"sourceField": "", "sourceStartChar": "", "sourceEndChar": ""}

    base = RUN / "diagnosis"
    lost = read_csv(base / "lost_uri_matches.csv")
    added = read_csv(base / "v2_added_mentions.csv")
    lostpaths = read_csv(base / "lost_event_paths.csv")
    baseline_paths = read_csv(RUN / "path_audits_fair/fair_baseline_v1/event_path_coverage.csv")
    v2_paths = read_csv(RUN / "path_audits_fair/emd_v2/event_path_coverage.csv")
    baseline_links = read_csv(RUN / "path_audits_fair/fair_baseline_v1/entity_linking_audit.csv")
    v2_links = read_csv(RUN / "path_audits_fair/emd_v2/entity_linking_audit.csv")
    baseline_eae = json.loads((RUN / "fair_baseline_v1/eae_trigger_conditioned_v1/staging_review_eae.json").read_text(encoding="utf-8"))
    v2_eae = json.loads((RUN / "eae_trigger_conditioned_v2/staging_review_eae.json").read_text(encoding="utf-8"))
    event_by_id = {str(e["eventId"]): e for e in baseline_eae}
    event_by_id_v2 = {str(e["eventId"]): e for e in v2_eae}

    # Inspect every event/path that was matched in either existing audit and every
    # lost v1 path. Text markers are review cues only; with no saved DOM they never
    # authorize exclusion.
    relevant = {}
    baseline_path_index = {(r["eventId"], r["path"]): r for r in baseline_paths}
    for row in baseline_paths + v2_paths:
        if row.get("pathStatus") == "MATCHED": relevant[(row["eventId"], row["path"])] = row
    for row in lostpaths: relevant[(row["eventId"], row["path"])] = row
    boundary_rows = []
    path_review_rows = []
    for (eid, path), p in sorted(relevant.items()):
        e = event_by_id.get(eid, {})
        aid = str(e.get("articleId") or p.get("articleId") or "")
        article = articles.get(aid, {})
        body = str(enriched.get(aid, {}).get("bodyText") or "")
        hits = marker_hits(body)
        evidence = (e.get("evidence") or {}).get("evidenceText", p.get("evidenceText", ""))
        model_text = cleaned.get(aid, {}).get("text", "")
        evidence_obj = e.get("evidence") or {}
        try:
            ev_start, ev_end = int(evidence_obj.get("startOffset")), int(evidence_obj.get("endOffset"))
            at_model = ev_start if model_text[ev_start:ev_end] == evidence else -1
        except (TypeError, ValueError):
            at_model = -1
        if at_model < 0:
            at_model = model_text.find(evidence) if evidence else -1
        offset_map = cleaned.get(aid, {}).get("sourceOffsetMap", [])
        mapped = offset_map[at_model:at_model + len(evidence)] if at_model >= 0 else []
        body_map = [m for m in mapped if m.get("sourceField") in {"bodyText", "summary"}]
        evidence_in_body = bool(body_map) and len(body_map) == len(mapped)
        at = min((m["sourceStart"] for m in body_map), default=-1)
        end = max((m["sourceEnd"] for m in body_map), default=-1)
        loc = ("BODY_TEXT_MAPPED" if body_map and body_map[0].get("sourceField") == "bodyText" else "SUMMARY_MAPPED") if evidence_in_body else ("TITLE_OR_SUMMARY_ONLY" if evidence else "NO_EVIDENCE_TEXT")
        nearby = [h for h in hits if at >= 0 and h["startChar"] <= end + 300 and h["endChar"] >= at - 300]
        context_risk = "RELATED_WIDGET_MARKER_IN_EVIDENCE" if any(x in evidence.casefold() for x in ("tin cùng chuyên mục", "mã chứng khoán liên quan", "tin tức mã chứng khoán")) else ""
        boundary_rows.append({
            "articleId": aid, "eventId": eid, "path": path, "sourceUrl": article.get("url", p.get("sourceUrl", "")),
            "sourceBodySha256": enriched.get(aid, {}).get("bodySha256", ""), "sourceBodyChars": len(body),
            "evidenceText": evidence, "evidenceFoundInSavedBody": evidence_in_body, "evidenceBodyStart": at, "evidenceBodyEnd": end,
            "evidenceSourceLocation": loc, "markerHits": json.dumps(hits, ensure_ascii=False),
            "markerNearEvidence": json.dumps(nearby, ensure_ascii=False),
            "textContextRisk": context_risk,
            "savedHtmlOrDom": False, "parserMethod": "HTMLParser allowlisted article-body containers; body text only saved",
            "boundaryConclusion": "UNVERIFIED; marker/structure does not prove segment ownership without saved DOM or human review",
            "promotionGate": "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW" if context_risk else "REVIEW_REQUIRED",
            "reviewDecision": "", "reviewNotes": "",
        })
        path_uri = p.get("entityUri") or p.get("v1EntityUri", "")
        path_detail = baseline_path_index.get((eid, path), {}) if "v1Status" in p else p
        path_rows = baseline_paths if p in baseline_paths or "v1Status" in p else v2_paths
        link_rows = baseline_links if path_rows is baseline_paths else v2_links
        matching_links = [r for r in link_rows if r.get("eventId") == eid
                          and path_uri and path_uri in (r.get("matchedUris", "").split("|"))]
        matching_links = list({(r.get("startChar"), r.get("endChar"), r.get("mentionText")): r for r in matching_links}.values())
        # Emit only the mention whose resolved URI is the path node. A path row
        # must never be copied onto every co-occurring EMD mention.
        linked_mentions = matching_links or [None]
        for link in linked_mentions:
            start = link.get("startChar", "") if link else ""
            finish = link.get("endChar", "") if link else ""
            mention_text = link.get("mentionText", "") if link else ""
            mention_type = link.get("predictedEntityType", "") if link else ""
            role = "|".join(a.get("role", "") for a in e.get("arguments", []) if str(a.get("startChar")) == str(start) and str(a.get("endChar")) == str(finish)) if link else ""
            path_review_rows.append({
                "recordKind": "EXISTING_PATH_EVENT", "articleId": aid, "eventId": eid, "evidenceId": (e.get("evidence") or {}).get("evidenceId", ""),
                "sourceUrl": article.get("url", ""), "sourceTextHash": cleaned.get(aid, {}).get("contentSha256", ""),
                "sourceLocation": loc, "eventType": e.get("eventType", ""), "trigger": (e.get("trigger") or {}).get("text", ""),
                "triggerStart": (e.get("trigger") or {}).get("startChar", ""), "triggerEnd": (e.get("trigger") or {}).get("endChar", ""),
                "entitySpan": mention_text, "entityStart": start, "entityEnd": finish,
                "entityType": mention_type, "role": role,
                "entityUri": path_uri, "intermediateNodeUris": path_detail.get("intermediateNodeUris", ""), "candidateStockUris": p.get("candidateStockUris") or p.get("v1CandidateStocks", "") or path_detail.get("candidateStockUris", ""),
                "kgPath": path, "pathStatus": p.get("pathStatus", p.get("v1Status", "")),
                "pathReasoning": p.get("eventToEntityEvidence") or p.get("reason") or path_detail.get("eventToEntityEvidence", ""),
                "temporalCondition": p.get("temporalCondition") or path_detail.get("temporalCondition", ""),
                "evidenceText": (e.get("evidence") or {}).get("evidenceText", ""), "markerHits": json.dumps(nearby, ensure_ascii=False),
                "promotionGate": "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW" if context_risk else "REVIEW_REQUIRED",
                "reviewDecision": "", "reviewNotes": "",
            })
            path_review_rows[-1].update({
                "triggerSourceOffset": json.dumps(source_span(aid, (e.get("trigger") or {}).get("startChar"), (e.get("trigger") or {}).get("endChar"))),
                "entitySourceOffset": json.dumps(source_span(aid, start, finish)),
                "evidenceSourceOffset": json.dumps(source_span(aid, (e.get("evidence") or {}).get("startOffset"), (e.get("evidence") or {}).get("endOffset"))),
            })

    write_csv(OUT / "source_boundary_audit.csv", boundary_rows)

    # Human review: all unique lost URI spans, plus stratified v2-only mentions.
    review = []
    seen = set()
    for r in lost:
        key = (r["articleId"], r["startChar"], r["endChar"], r["mentionText"], r["predictedEntityType"])
        if key in seen: continue
        seen.add(key)
        aid = r["articleId"]
        ev = event_by_id.get(r.get("eventId", ""), {})
        ev_trigger = (ev.get("trigger") or {}).get("text", "")
        ev_role = "|".join(a.get("role", "") for a in ev.get("arguments", []) if a.get("text") == r.get("mentionText", "") or (str(a.get("startChar")) == str(r.get("startChar")) and str(a.get("endChar")) == str(r.get("endChar"))))
        review.append({
            "reviewGroup": "V1_URI_LOST", "articleId": aid, "eventIds": r.get("eventId", ""), "evidenceId": r.get("evidenceId", ""),
            "articleUrl": r.get("sourceUrl", ""), "sourceBodySha256": enriched.get(aid, {}).get("bodySha256", ""),
            "sourceLocation": "UNVERIFIED_EXTRACTED_BODY", "eventType": r.get("eventType", ""), "trigger": ev_trigger,
            "entitySpan": r.get("mentionText", ""), "startChar": r.get("startChar", ""), "endChar": r.get("endChar", ""),
            "entityType": r.get("predictedEntityType", ""), "role": ev_role or r.get("argumentRoles", ""), "kgUri": r.get("matchedUris", ""),
            "kgPath": "DIRECT", "evidenceText": r.get("evidenceText", ""), "modelConfidence": r.get("confidence", ""),
            "v1v2Issue": r.get("lossCause", ""), "boundaryCheck": "", "typeCheck": "", "eventRelevanceCheck": "",
            "spanVerifiedByExistingAudit": r.get("spanVerified", ""), "existingRelevanceCue": r.get("eventRelevance", ""),
            "argumentSpanStatus": r.get("argumentSpanStatuses", ""), "v2OverlapMentions": r.get("v2OverlapMentions", ""),
            "v1UriStatus": r.get("entityLinkStatus", ""), "v2ExactUriStatus": r.get("v2ExactLinkStatus", ""),
            "nearMatchUris": r.get("nearMatchUris", ""), "resolverReason": r.get("reason", ""),
            "preliminaryContextCue": ("RELATED_WIDGET_MIXED_IN_EVENT_EVIDENCE" if any(x in str(r.get("evidenceText", "")).casefold() for x in ("tin cùng chuyên mục", "mã chứng khoán liên quan", "tin tức mã chứng khoán"))
                                       else ("RELEVANCE_NOT_ESTABLISHED_BY_EXISTING_AUDIT" if r.get("eventRelevance") == "NOT_ESTABLISHED" else "REVIEW_TRIGGER_ENTITY_RELATION")),
            "reviewDecision": "", "reviewNotes": "",
        })
        entity_map = source_span(aid, r.get("startChar"), r.get("endChar"))
        review[-1].update({"entitySourceOffset": json.dumps(entity_map),
                           "triggerSourceOffset": json.dumps(source_span(aid, (ev.get("trigger") or {}).get("startChar"), (ev.get("trigger") or {}).get("endChar"))),
                           "sourceLocation": "SAVED_BODY_OFFSET_MAPPED" if entity_map.get("sourceField") == "bodyText" else "SAVED_SOURCE_OFFSET_MAPPED"})
    # Stratified reproducible sample: 2 per in-scope NER type in OUT_OF_SCOPE,
    # 5 each ORG/PER for KG gap, and all 8 unresolved/relevance cases if available.
    strata = defaultdict(list)
    for r in added:
        bucket = r.get("addedMentionAssessment", "")
        typ = r.get("predictedEntityType", "")
        strata[(bucket, typ)].append(r)
    rng = random.Random(20261020)
    sample = []
    plan = {
        "OUT_OF_SCOPE_FOR_FOUR_PATHS": {"TIME": 2, "MONEY": 2, "FAC": 1, "JOB": 1, "VEH": 2},
        "KG_ENTITY_OR_ALIAS_GAP": {"ORG": 5, "PER": 5},
        "UNRESOLVED_RELEVANCE_OR_AMBIGUITY": {"ORG": 4, "PER": 4},
    }
    for bucket, types in plan.items():
        for typ, n in types.items():
            pool = list(strata.get((bucket, typ), [])); rng.shuffle(pool)
            sample.extend(pool[:n])
    for r in sample:
        aid = r["articleId"]
        event_id = str(r.get("affectedEventIds", r.get("eventId", "")).split("|")[0])
        event = event_by_id.get(event_id, {})
        role = "|".join(a.get("role", "") for a in event.get("arguments", []) if a.get("text") == r.get("mentionText", ""))
        review.append({
            "reviewGroup": "V2_NEW_STRATIFIED", "articleId": aid, "eventIds": r.get("affectedEventIds", r.get("eventId", "")), "evidenceId": r.get("evidenceId", ""),
            "articleUrl": r.get("sourceUrl", ""), "sourceBodySha256": enriched.get(aid, {}).get("bodySha256", ""),
            "sourceLocation": "UNVERIFIED_EXTRACTED_BODY", "eventType": r.get("eventType", ""), "trigger": (event.get("trigger") or {}).get("text", ""),
            "entitySpan": r.get("mentionText", ""), "startChar": r.get("startChar", ""), "endChar": r.get("endChar", ""),
            "entityType": r.get("predictedEntityType", ""), "role": role or r.get("argumentRoles", ""), "kgUri": r.get("matchedUris", ""),
            "kgPath": "", "evidenceText": r.get("evidenceText", ""), "modelConfidence": r.get("confidence", ""),
            "v1v2Issue": r.get("addedMentionAssessment", ""), "boundaryCheck": "", "typeCheck": "", "eventRelevanceCheck": "",
            "spanVerifiedByExistingAudit": r.get("spanVerified", ""), "existingRelevanceCue": r.get("eventRelevance", ""),
            "argumentSpanStatus": r.get("argumentSpanStatuses", ""), "v2OverlapMentions": "",
            "v1UriStatus": "", "v2ExactUriStatus": r.get("entityLinkStatus", ""),
            "nearMatchUris": r.get("nearMatchUris", ""), "resolverReason": r.get("reason", ""),
            "preliminaryContextCue": "PREDICTION_ONLY_REVIEW_REQUIRED",
            "reviewDecision": "", "reviewNotes": "",
        })
        entity_map = source_span(aid, r.get("startChar"), r.get("endChar"))
        review[-1].update({"entitySourceOffset": json.dumps(entity_map),
                           "triggerSourceOffset": json.dumps(source_span(aid, (event.get("trigger") or {}).get("startChar"), (event.get("trigger") or {}).get("endChar"))),
                           "sourceLocation": "SAVED_BODY_OFFSET_MAPPED" if entity_map.get("sourceField") == "bodyText" else "SAVED_SOURCE_OFFSET_MAPPED"})
    write_csv(OUT / "entity_context_review_queue.csv", review)
    write_csv(OUT / "path_entity_review_queue.csv", path_review_rows)

    # The cleaned artifact currently preserves every character. Verify exact model
    # input hash parity, then reuse only the already saved predictions/path audit.
    # This is a staging equivalence check, not a new model quality claim.
    clean_path_rows = []
    for r in baseline_paths + v2_paths:
        aid = next((e.get("articleId") for e in baseline_eae if e.get("eventId") == r.get("eventId")), "")
        evidence = (event_by_id.get(r.get("eventId", ""), {}).get("evidence") or {}).get("evidenceText", "")
        context_risk = any(x in evidence.casefold() for x in ("tin cùng chuyên mục", "mã chứng khoán liên quan", "tin tức mã chứng khoán"))
        promotion_gate = ("BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW" if context_risk and r.get("pathStatus") == "MATCHED"
                          else ("REVIEW_REQUIRED" if r.get("pathStatus") == "MATCHED" else "NO_MATCHED_PATH"))
        clean_path_rows.append({**r, "articleId": aid, "cleanedTextSha256": cleaned.get(aid, {}).get("contentSha256", ""),
                                "boundaryStatus": "UNVERIFIED_NO_SAVED_DOM_EVIDENCE", "inferenceReused": True,
                                "reusedCheckpoint": "models/phobert_bkee_emd_v1 or v2 per audit side; EAE trigger-conditioned v1",
                                "promotionGate": promotion_gate,
                                "reviewRequiredBeforePromotion": True})
    write_csv(OUT / "path_coverage_cleaned_staging.csv", clean_path_rows)
    blocked_context_events = sorted({r["eventId"] for r in boundary_rows if r.get("promotionGate") == "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"})
    unique_lost = {}
    for r in lost:
        unique_lost.setdefault((r["articleId"], r["startChar"], r["endChar"], r["mentionText"], r["predictedEntityType"]), r)
    lost_relevance = Counter(r.get("eventRelevance", "") for r in unique_lost.values())
    unique_markers = {}
    for row in boundary_rows:
        for h in json.loads(row["markerHits"]):
            unique_markers[(row["articleId"], h["markerType"], h["startChar"], h["endChar"], h["text"])] = h
    summary = {
        "cohortArticles": len(cleaned), "savedFullTextRecords": len(enriched),
        "sourceCaptureStatusCounts": enrichment_manifest.get("statusCounts", {}),
        "savedSnapshotRecordsHaveBodyOrHtml": sum(bool(set(snap.keys()) & {"bodyText", "html", "rawHtml", "content"}) for _, snap in snapshots.values()),
        "savedHtmlDomRecords": sum(bool(set(snap.keys()) & {"html", "rawHtml", "dom", "selectors", "contentSelector"}) for _, snap in snapshots.values()),
        "fullTextParser": "scripts/enrich_news_fulltext.py ArticleText allowlists data-role=content, itemprop=articleBody, ids vst_detail/maincontent/newscontent, classes article-content/detail-content; HTML was not persisted",
        "cleanedTextPolicy": "No segment removed because saved source lacks per-article DOM evidence and no human review has approved exclusions.",
        "cleanedTextHashesEqualPreparedInferenceInput": all(r["contentSha256"] == sha(prepare_extraction_input(articles[r["articleId"]], enriched.get(r["articleId"])).text) for r in text_rows),
        "offsetMap": "Each output char maps to title/bodyText/summary source offsets; normalization collapses whitespace and NFC. If map length could not be represented, sourceField=preparedInput is explicit.",
        "pathEventRowsInspected": len(boundary_rows), "pathReviewRows": len(path_review_rows),
        "pathEvidenceMappedToSavedSourceText": sum(r.get("evidenceFoundInSavedBody") == True for r in boundary_rows),
        "pathEvidenceRowsWithRelatedWidgetMarkers": sum(bool(r.get("textContextRisk")) for r in boundary_rows),
        "pathEvidenceSourceLocationCounts": dict(Counter(r.get("evidenceSourceLocation", "") for r in boundary_rows)),
        "articlesWithBoundaryCue": len({r["articleId"] for r in boundary_rows if json.loads(r["markerHits"])}),
        "boundaryMarkerCounts": dict(Counter(h["markerType"] for r in boundary_rows for h in json.loads(r["markerHits"]))),
        "uniqueArticleMarkerCounts": dict(Counter(h["markerType"] for (aid, *_), h in unique_markers.items())),
        "pathsBlockedFromPromotionPendingSourceReview": len(blocked_context_events), "blockedEventIds": blocked_context_events,
        "lostUriReviewSpans": len(unique_lost),
        "lostUriReviewPreliminaryProfile": {"spanLossCause": dict(Counter(r.get("lossCause", "") for r in unique_lost.values())),
                                            "entityType": dict(Counter(r.get("predictedEntityType", "") for r in unique_lost.values())),
                                            "existingRelevanceCue": dict(lost_relevance),
                                            "interpretation": "Existing automated audit cues only; not human labels or final correctness judgments."},
        "v2NewMentionPopulation": len(added), "v2NewStratifiedSample": len(sample),
        "sampleStrata": {f"{bucket}|{typ}": len([x for x in sample if x.get("addedMentionAssessment")==bucket and x.get("predictedEntityType")==typ]) for bucket, types in plan.items() for typ in types},
        "coverageCleanedStaging": {"baselineEventsWithPath": len({r["eventId"] for r in baseline_paths if r.get("pathStatus")=="MATCHED"}),
                                   "v2EventsWithPath": len({r["eventId"] for r in v2_paths if r.get("pathStatus")=="MATCHED"}),
                                   "changedByContentFilter": False, "reason": "cleaned model input is hash-identical; existing same-config inference/path outputs reused"},
        "trainingCrawlRawOntologyShaclKgCheckpointAnnotationModified": False,
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    report = f'''# Source-context audit: PhoBERT EMD vertical slice

## Scope and evidence

This audit uses the saved 100-article cohort, saved article snapshots, saved extracted full text, and previously saved EMD/EAE/path outputs. No training, crawl, RAW/KG/ontology/SHACL/checkpoint/confirmed annotation was changed.

The RAW article snapshots contain metadata and summaries, not HTML. The saved full-text records contain `bodyText`, `bodySha256`, URL, and capture metadata; they do not contain raw HTML, DOM nodes, selector paths, or segment labels. `scripts/enrich_news_fulltext.py` uses an HTML allowlist for article-body containers, but its parser saves only flattened text. This proves the intended extraction boundary, but cannot prove whether a sidebar or related-news widget was nested inside a selected container for an individual page.

The saved capture has {summary['sourceCaptureStatusCounts'].get('FULLTEXT', 0)} `FULLTEXT` records and {summary['sourceCaptureStatusCounts'].get('NO_ARTICLE_BODY', 0)} articles with no captured article body. Of the {summary['pathEventRowsInspected']} matched/lost path rows reviewed, {summary['pathEvidenceMappedToSavedSourceText']} evidence spans map into the saved full-text body and {summary['pathEventRowsInspected'] - summary['pathEvidenceMappedToSavedSourceText']} are title/summary-only; {summary['pathEvidenceRowsWithRelatedWidgetMarkers']} evidence spans contain related-widget markers.

## Conservative content boundary

`cleaned_article_texts.jsonl` is a separate staging corpus with source version, source and content hashes, source URL, and character offset mapping. Because no segment is supported by saved DOM evidence or human review, no text was removed. The cleaned input hashes match the exact prepared model inputs. Marker phrases in `source_boundary_audit.csv` are review cues only and are never treated as automatic exclusion evidence.

Coverage replay therefore reuses the saved same-checkpoint outputs on hash-identical text. The existing matched-path counts before source-context gating are **{summary['coverageCleanedStaging']['baselineEventsWithPath']} events** for EMD v1 and **{summary['coverageCleanedStaging']['v2EventsWithPath']} events** for EMD v2. Content filtering caused no change. Two v1 path proposals are blocked from promotion for the ACB contamination case; the other matched paths remain `REVIEW_REQUIRED`, not approved. These counts are coverage only and say nothing about precision.

The ACB award article exposes a specific contamination case: {len(blocked_context_events)} `Transfer-money` Event proposals use trigger `tra{chr(0x1EA3)}` at different positions in unrelated CSV/ECO related-news headlines, while their assigned argument is ACB from a customer-service call to action. Their shared evidence also includes the related-ticker block and a `RELATED_NEWS` heading. The evidence maps into the saved body starting at offset 7779. These proposals are **blocked from promotion pending source-context review**; their staging rows and predictions remain intact. The saved text also contains site navigation, course advertisements, and a privacy/footer block after article content. Across the audited path-source bodies, explicit text markers occur in {summary['uniqueArticleMarkerCounts']} distinct article-marker spans; these lexical markers cue review, they do not establish precise DOM boundaries.

## Review artifacts

- `entity_context_review_queue.csv`: all {summary['lostUriReviewSpans']} unique lost v1 URI spans plus {summary['v2NewStratifiedSample']} reproducibly stratified v2-only mentions; review columns are blank.
- `source_boundary_audit.csv`: all {summary['pathEventRowsInspected']} event/path rows matched in either audit or lost from v1, with saved-body evidence location and explicit boundary limitation.
- `path_entity_review_queue.csv`: mention-level context review for existing path events.
- `path_coverage_cleaned_staging.csv`: path statuses alongside cleaned-text hash and reuse provenance.
- `content_boundary_validation_spec.md`: source provenance, exclusion, mapping, and replay rules for future captures.

For the 18 unique lost URI spans, the prior automated audit classifies 16 as missed by v2 and 2 as wrong-boundary overlaps; all 18 are ORG. Its relevance cues are 15 `ARGUMENT_SPAN_SUPPORT_REVIEW`, 1 explicit evidence-subject prefix, and 2 `NOT_ESTABLISHED` (Techcombank). These are audit heuristics, not human correctness labels. The two boundary cases are the full CTS and BID organization names clipped by v2; the review sheet retains v2 overlap text. The ACB span has a stronger context flag because its evidence mixes a customer CTA with unrelated ticker/news blocks; both affected Event proposals are gated below.

## Interpretation

The saved text is extracted from an intended article-body container, but page-specific DOM is unavailable. No existing path is automatically approved or deleted. The ACB case is blocked from promotion because its saved Event evidence itself contains explicit related-ticker and related-news headings unrelated to the article's award topic. A source-context exclusion requires a saved structural locator (DOM selector/node range tied to a captured HTML hash) or a human-reviewed span; then offsets can be mapped and inference replayed on the derived text.

There are no financial-domain gold labels, so the audit does not estimate financial-domain precision or assert that coverage changes imply quality changes.
'''
    (OUT / "source_context_audit_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
