"""Create a small, human-labeled financial-domain gold-review package.

Reads only the saved 100-article cohort and existing inference/path audits. It
does not run any model or mutate RAW, KG, ontology, checkpoints, or prior output.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019/emd_v2_experiment"
SRC_AUDIT = RUN / "source_context_audit"
OUT = RUN / "financial_gold_eval_v1"
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.phobert_detector import _sentence_spans


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_key(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def source_span(offset_map, start, end):
    try:
        a, b = int(start), int(end)
        pieces = offset_map[a:b]
        if not pieces:
            return None
        fields = {p.get("sourceField") for p in pieces}
        field = next(iter(fields)) if len(fields) == 1 else "MULTI_SEGMENT"
        return {"sourceField": field, "start": min(p["sourceStart"] for p in pieces), "end": max(p["sourceEnd"] for p in pieces)}
    except (ValueError, TypeError, IndexError, KeyError):
        return None


def sentence_for(article_sentences, span):
    if not span:
        return None
    for row in article_sentences:
        if row["sourceField"] == span["sourceField"] and row["sentenceStart"] <= span["start"] and span["end"] <= row["sentenceEnd"]:
            return row
    # Some model spans include a token that crosses a punctuation boundary after
    # whitespace normalization. Preserve it for review when there is clear overlap.
    candidates = [r for r in article_sentences if r["sourceField"] == span["sourceField"] and max(r["sentenceStart"], span["start"]) < min(r["sentenceEnd"], span["end"])]
    return candidates[0] if len(candidates) == 1 else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    articles = {str(x["articleId"]): x for x in read_jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    snapshots = {str(x["articleId"]): x for x in (read_json(p) for p in (ROOT / "data/snapshots/news_articles").glob("*.json"))}
    enriched = {str(x["articleId"]): x for x in read_jsonl(ROOT / "data/enriched/news_100_v1/articles.jsonl")}
    prepared = {str(x["articleId"]): x for x in read_jsonl(SRC_AUDIT / "cleaned_article_texts.jsonl")}
    base_events = read_json(RUN / "fair_baseline_v1/eae_trigger_conditioned_v1/staging_review_eae.json")
    v2_events = read_json(RUN / "eae_trigger_conditioned_v2/staging_review_eae.json")
    events_v1 = defaultdict(list); events_v2 = defaultdict(list)
    for e in base_events: events_v1[str(e["articleId"])].append(e)
    for e in v2_events: events_v2[str(e["articleId"])].append(e)

    path_rows = read_csv(RUN / "path_audits_fair/fair_baseline_v1/event_path_coverage.csv")
    matched_path_rows = [r for r in path_rows if r.get("pathStatus") == "MATCHED"]
    path_articles = {r["articleId"] for r in matched_path_rows}
    path_by_article = defaultdict(list)
    for r in matched_path_rows: path_by_article[r["articleId"]].append(r)
    entity_links_v1 = read_csv(RUN / "path_audits_fair/fair_baseline_v1/entity_linking_audit.csv")
    entity_links_v2 = read_csv(RUN / "path_audits_fair/emd_v2/entity_linking_audit.csv")
    linked_no_path = {r["articleId"] for r in entity_links_v1 if r.get("entityLinkStatus") == "MATCHED" and r["articleId"] not in path_articles}
    lost_rows = read_csv(RUN / "diagnosis/lost_uri_matches.csv")
    lost_article_ids = {r["articleId"] for r in lost_rows}
    boundary_rows = read_csv(SRC_AUDIT / "source_boundary_audit.csv")
    marker_articles = {r["articleId"] for r in boundary_rows if r.get("markerHits") not in ("", "[]")}
    reviewed_sidebar = {r["articleId"] for r in boundary_rows if r.get("textContextRisk")}
    no_event = {aid for aid in articles if not events_v1.get(aid)}

    # Select unique articles with reproducible category quotas. ACB is forced into
    # the sample, all three saved marker-positive articles are represented, and
    # overlapping issue categories are preserved as tags rather than forced labels.
    chosen = []
    def add_group(ids, quota, required=()):
        for aid in required:
            if aid in articles and aid not in chosen: chosen.append(aid)
        ordered = sorted((x for x in ids if x not in chosen), key=lambda x: stable_key("financial-gold-v1:" + x))
        for aid in ordered[:max(0, quota - sum(x in ids for x in chosen))]:
            if aid not in chosen: chosen.append(aid)

    add_group(marker_articles, len(marker_articles), required=("NEWS_ARTICLE:a7e1249d10ef144d9298",))
    add_group(linked_no_path, 4)
    # Prefer known v1-v2 boundary cases, then missed URI spans from distinct articles.
    boundary_ids = []
    for r in lost_rows:
        if r.get("lossCause") == "WRONG_BOUNDARY" and r["articleId"] not in boundary_ids: boundary_ids.append(r["articleId"])
    missed_ids = []
    for r in lost_rows:
        if r.get("lossCause") == "MISSED_ENTITY" and r["articleId"] not in missed_ids: missed_ids.append(r["articleId"])
    add_group(boundary_ids + missed_ids, 4)
    add_group(no_event, 4)
    add_group(path_articles, 6, required=("NEWS_ARTICLE:a7e1249d10ef144d9298",))
    if len(chosen) < 20:
        fill_candidates = (set(boundary_ids + missed_ids) | path_articles | linked_no_path) - set(chosen)
        for aid in sorted(fill_candidates, key=lambda x: stable_key("gold-fill:" + x)):
            if len(chosen) >= 20: break
            chosen.append(aid)
    if len(chosen) < 20:
        fill_candidates = set(articles) - set(chosen)
        for aid in sorted(fill_candidates, key=lambda x: stable_key("gold-fill:" + x)):
            if len(chosen) >= 20: break
            chosen.append(aid)
    if len(chosen) != 20:
        raise RuntimeError(f"Expected 20 unique sampled articles, got {len(chosen)}")

    article_meta = {}
    sentence_rows = []
    article_sentences = defaultdict(list)
    raw_fields = {}
    for aid in chosen:
        a = articles[aid]; snap = snapshots.get(aid, {}); full = enriched.get(aid, {})
        source = prepared[aid].get("selectedTextSource", "")
        fields = [("title", str(snap.get("title") or a.get("title") or ""))]
        if source == "FULL_TEXT" and full.get("bodyText"):
            fields.append(("bodyText", str(full["bodyText"])))
        elif source == "SUMMARY_FALLBACK":
            fields.append(("summary", str(a.get("summary") or "")))
        raw_fields[aid] = {field: text for field, text in fields if text}
        capture_status = full.get("status", "NO_ARTICLE_BODY")
        tags = []
        if aid in path_articles: tags.append("EVENT_WITH_KG_PATH")
        if aid in linked_no_path: tags.append("ENTITY_URI_MATCH_WITHOUT_PATH")
        if aid in lost_article_ids: tags.append("BOUNDARY_OR_MISSED_ENTITY")
        if aid in no_event: tags.append("NO_PREDICTED_EVENT")
        if aid in marker_articles: tags.append("RELATED_NEWS_OR_SIDEBAR_CUE")
        if aid in reviewed_sidebar: tags.append("RELATED_WIDGET_IN_EVENT_EVIDENCE")
        article_meta[aid] = {
            "articleId": aid, "sourceUrl": a.get("url", ""), "title": snap.get("title", a.get("title", "")),
            "sourceName": a.get("sourceName", ""), "selectedTextSource": source, "fullTextStatus": capture_status,
            "sourceBodySha256": full.get("bodySha256", ""), "preparedTextSha256": prepared[aid].get("contentSha256", ""),
            "stratumTags": "|".join(tags), "sampleRank": len(article_meta) + 1,
        }
        sentence_idx = 0
        for field, text in raw_fields[aid].items():
            for s, e in _sentence_spans(text):
                sentence_idx += 1
                row = {
                    "articleId": aid, "sourceUrl": a.get("url", ""), "title": snap.get("title", a.get("title", "")),
                    "sourceVersion": f"saved_news_100_v1:{field}", "sourceContentHash": full.get("bodySha256", "") if field == "bodyText" else hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "sentenceId": f"{aid}:S{sentence_idx:04d}", "sourceField": field, "sentenceStart": s, "sentenceEnd": e,
                    "originalText": text[s:e], "sentenceReviewStatus": "", "sourceContextDecision": "", "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
                }
                sentence_rows.append(row); article_sentences[aid].append(row)
    write_csv(OUT / "article_sample.csv", list(article_meta.values()))

    # Prediction rows are carried into separate annotation sheets. Gold decisions
    # and gold span/type/role/URI fields deliberately begin empty.
    event_rows = []
    entity_rows = []
    argument_rows = []
    event_id_to_sentence = {}
    entity_candidate_by_event = defaultdict(dict)
    seen_entity_rows = {}
    def pred_source_span(aid, start, end):
        m = source_span(prepared[aid].get("sourceOffsetMap", []), start, end)
        if not m or m["sourceField"] == "MULTI_SEGMENT": return None
        return m

    for aid in chosen:
        meta = article_meta[aid]
        ev_by_id = {e["eventId"]: e for e in events_v1.get(aid, [])}
        for e in events_v1.get(aid, []):
            trig = pred_source_span(aid, (e.get("trigger") or {}).get("startChar"), (e.get("trigger") or {}).get("endChar"))
            sent = sentence_for(article_sentences[aid], trig)
            if not sent: continue
            evid = e.get("evidence") or {}
            evid_span = pred_source_span(aid, evid.get("startOffset"), evid.get("endOffset"))
            eid = str(e["eventId"]); event_id_to_sentence[eid] = sent
            event_rows.append({
                **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                "rowId": "ED:" + eid, "candidateOrigin": "MODEL_PREDICTION", "modelVersion": "ED_SHARED",
                "eventId": eid, "sentenceId": sent["sentenceId"], "sourceField": trig["sourceField"], "sentenceStart": sent["sentenceStart"], "sentenceEnd": sent["sentenceEnd"], "originalText": sent["originalText"],
                "predictedTriggerText": (e.get("trigger") or {}).get("text", ""), "predictedTriggerStart": trig["start"], "predictedTriggerEnd": trig["end"],
                "predictedEventType": e.get("eventType", ""), "predictedEvidenceText": evid.get("evidenceText", ""),
                "predictedEvidenceSourceField": evid_span["sourceField"] if evid_span else "", "predictedEvidenceStart": evid_span["start"] if evid_span else "", "predictedEvidenceEnd": evid_span["end"] if evid_span else "",
                "triggerDecision": "", "eventTypeDecision": "", "goldTriggerText": "", "goldTriggerStart": "", "goldTriggerEnd": "", "goldEventType": "",
                "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "", "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
            })
        # Include one editable missed-event slot per sentence. Researchers may add
        # further rows when a sentence contains multiple missed events.
        for sent in article_sentences[aid]:
            event_rows.append({
                **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                "rowId": f"ADD_EVENT:{sent['sentenceId']}", "candidateOrigin": "REVIEW_ADDED_SLOT", "modelVersion": "REVIEWER", "eventId": "", "sentenceId": sent["sentenceId"],
                "sourceField": sent["sourceField"], "sentenceStart": sent["sentenceStart"], "sentenceEnd": sent["sentenceEnd"], "originalText": sent["originalText"],
                "predictedTriggerText": "", "predictedTriggerStart": "", "predictedTriggerEnd": "", "predictedEventType": "", "predictedEvidenceText": "",
                "predictedEvidenceSourceField": "", "predictedEvidenceStart": "", "predictedEvidenceEnd": "", "triggerDecision": "", "eventTypeDecision": "",
                "goldTriggerText": "", "goldTriggerStart": "", "goldTriggerEnd": "", "goldEventType": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "",
                "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
            })

        for version, audit_rows in (("EMD_V1", entity_links_v1), ("EMD_V2", entity_links_v2)):
            per_mention = {}
            for r in audit_rows:
                if r.get("articleId") != aid or r.get("recordKind") == "ARGUMENT": continue
                mapped = pred_source_span(aid, r.get("startChar"), r.get("endChar"))
                sent = sentence_for(article_sentences[aid], mapped)
                if not mapped or not sent: continue
                key = (mapped["sourceField"], mapped["start"], mapped["end"], r.get("predictedEntityType", ""))
                row = per_mention.setdefault(key, {"mapped": mapped, "sentence": sent, "text": r.get("mentionText", ""), "type": r.get("predictedEntityType", ""), "events": set(), "uris": set(), "statuses": set(), "confidence": r.get("confidence", "")})
                row["events"].add(r.get("eventId", "")); row["statuses"].add(r.get("entityLinkStatus", ""))
                row["uris"].update(u for u in r.get("matchedUris", "").split("|") if u)
            for (field, start, end, typ), m in per_mention.items():
                uri = next(iter(m["uris"])) if len(m["uris"]) == 1 else ""
                rid = f"{version}:{aid}:{field}:{start}:{end}:{typ}"
                row = {
                    **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                    "rowId": rid, "candidateOrigin": "MODEL_PREDICTION", "modelVersion": version, "eventIds": "|".join(sorted(x for x in m["events"] if x)),
                    "sentenceId": m["sentence"]["sentenceId"], "sourceField": field, "sentenceStart": m["sentence"]["sentenceStart"], "sentenceEnd": m["sentence"]["sentenceEnd"],
                    "originalText": m["sentence"]["originalText"], "predictedEntityText": m["text"], "predictedEntityStart": start, "predictedEntityEnd": end,
                    "predictedEvidenceText": m["text"], "predictedEvidenceStart": start, "predictedEvidenceEnd": end,
                    "predictedEntityType": typ, "predictedEntityURI": uri, "resolverStatus": "|".join(sorted(m["statuses"])), "modelConfidence": m["confidence"],
                    "spanDecision": "", "typeDecision": "", "uriDecision": "", "goldEntityText": "", "goldEntityStart": "", "goldEntityEnd": "", "goldEntityType": "", "goldEntityURI": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "",
                    "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
                }
                entity_rows.append(row); seen_entity_rows[(aid, version, field, start, end, typ)] = row
                for event_id in m["events"]:
                    entity_candidate_by_event[(aid, version, event_id)][(field, start, end, typ)] = (m["text"], uri, m["sentence"])
            for sent in article_sentences[aid] if version == "EMD_V1" else []:
                entity_rows.append({
                    **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                    "rowId": f"ADD_ENTITY:{sent['sentenceId']}", "candidateOrigin": "REVIEW_ADDED_SLOT", "modelVersion": "REVIEWER", "eventIds": "",
                    "sentenceId": sent["sentenceId"], "sourceField": sent["sourceField"], "sentenceStart": sent["sentenceStart"], "sentenceEnd": sent["sentenceEnd"], "originalText": sent["originalText"],
                    "predictedEntityText": "", "predictedEntityStart": "", "predictedEntityEnd": "", "predictedEvidenceText": "", "predictedEvidenceStart": "", "predictedEvidenceEnd": "", "predictedEntityType": "", "predictedEntityURI": "", "resolverStatus": "", "modelConfidence": "",
                    "spanDecision": "", "typeDecision": "", "uriDecision": "", "goldEntityText": "", "goldEntityStart": "", "goldEntityEnd": "", "goldEntityType": "", "goldEntityURI": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "",
                    "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
                })

        # Positive and NONE role proposals, conditioned on each event and EMD
        # version. The empty reviewer-added row supports missed arguments/events.
        for version, version_events in (("EMD_V1", events_v1.get(aid, [])), ("EMD_V2", events_v2.get(aid, []))):
            matching_audit = entity_links_v1 if version == "EMD_V1" else entity_links_v2
            for e in version_events:
                eid = str(e["eventId"]); event_sent = event_id_to_sentence.get(eid)
                if not event_sent: continue
                arg_roles = defaultdict(list)
                for arg in e.get("arguments", []):
                    key = (str(arg.get("startChar", "")), str(arg.get("endChar", "")))
                    arg_roles[key].append(str(arg.get("role", "NONE")))
                candidates = []
                for m in e.get("entities", []):
                    mapped = pred_source_span(aid, m.get("startChar"), m.get("endChar"))
                    sent = sentence_for(article_sentences[aid], mapped)
                    if not mapped or not sent or sent["sentenceId"] != event_sent["sentenceId"]: continue
                    candidates.append((m, mapped, sent))
                for m, mapped, sent in candidates:
                    roles = arg_roles.get((str(m.get("startChar", "")), str(m.get("endChar", ""))), []) or ["NONE"]
                    uri_rows = [r for r in matching_audit if r.get("eventId") == eid and r.get("recordKind") != "ARGUMENT"
                                and str(r.get("startChar")) == str(m.get("startChar")) and str(r.get("endChar")) == str(m.get("endChar"))]
                    uris = {u for r in uri_rows for u in r.get("matchedUris", "").split("|") if u}
                    uri = next(iter(uris)) if len(uris) == 1 else ""
                    for role in roles:
                        argument_rows.append({
                            **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                            "rowId": f"PAIR:{version}:{eid}:{mapped['sourceField']}:{mapped['start']}:{mapped['end']}:{role}", "candidateOrigin": "MODEL_PAIR",
                            "modelVersion": version, "eventId": eid, "sentenceId": sent["sentenceId"], "sourceField": sent["sourceField"],
                            "sentenceStart": sent["sentenceStart"], "sentenceEnd": sent["sentenceEnd"], "originalText": sent["originalText"],
                            "predictedTriggerText": (e.get("trigger") or {}).get("text", ""),
                            "predictedTriggerSpan": json.dumps(pred_source_span(aid, (e.get("trigger") or {}).get("startChar"), (e.get("trigger") or {}).get("endChar")), ensure_ascii=False),
                            "predictedEventType": e.get("eventType", ""), "predictedEntityText": m.get("text", ""), "predictedEntityStart": mapped["start"], "predictedEntityEnd": mapped["end"],
                            "predictedEvidenceText": sent["originalText"], "predictedEvidenceStart": sent["sentenceStart"], "predictedEvidenceEnd": sent["sentenceEnd"],
                            "predictedEntityType": m.get("entityType", ""), "predictedEntityURI": uri, "predictedArgumentRole": role,
                            "argumentDecision": "", "roleDecision": "", "goldEntityText": "", "goldEntityStart": "", "goldEntityEnd": "", "goldEntityType": "", "goldEntityURI": "", "goldArgumentRole": "",
                            "goldTriggerText": "", "goldTriggerStart": "", "goldTriggerEnd": "", "goldEventType": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "",
                            "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
                        })
                if version == "EMD_V1":
                    argument_rows.append({
                    **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                    "rowId": f"ADD_ARGUMENT:{eid}", "candidateOrigin": "REVIEW_ADDED_SLOT", "modelVersion": "REVIEWER", "eventId": eid,
                    "sentenceId": event_sent["sentenceId"], "sourceField": event_sent["sourceField"], "sentenceStart": event_sent["sentenceStart"], "sentenceEnd": event_sent["sentenceEnd"],
                    "originalText": event_sent["originalText"], "predictedTriggerText": "", "predictedTriggerSpan": "", "predictedEventType": "", "predictedEntityText": "",
                    "predictedEntityStart": "", "predictedEntityEnd": "", "predictedEntityType": "", "predictedEntityURI": "", "predictedArgumentRole": "",
                    "predictedEvidenceText": "", "predictedEvidenceStart": "", "predictedEvidenceEnd": "",
                    "argumentDecision": "", "roleDecision": "", "goldEntityText": "", "goldEntityStart": "", "goldEntityEnd": "", "goldEntityType": "", "goldEntityURI": "", "goldArgumentRole": "",
                    "goldTriggerText": "", "goldTriggerStart": "", "goldTriggerEnd": "", "goldEventType": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "",
                    "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
                })

    for sent in sentence_rows:
        # One generic slot per sentence; duplicate a row for additional links.
        meta = article_meta[sent["articleId"]]
        argument_rows.append({
                **{k: meta[k] for k in ("articleId", "sourceUrl", "title", "sourceBodySha256", "preparedTextSha256")},
                "rowId": f"ADD_ARGUMENT_SENTENCE:{sent['sentenceId']}", "candidateOrigin": "REVIEW_ADDED_SLOT", "modelVersion": "REVIEWER",
                "eventId": "", "sentenceId": sent["sentenceId"], "sourceField": sent["sourceField"], "sentenceStart": sent["sentenceStart"], "sentenceEnd": sent["sentenceEnd"], "originalText": sent["originalText"],
                "predictedTriggerText": "", "predictedTriggerSpan": "", "predictedEventType": "", "predictedEntityText": "", "predictedEntityStart": "", "predictedEntityEnd": "", "predictedEntityType": "", "predictedEntityURI": "", "predictedArgumentRole": "",
                "predictedEvidenceText": "", "predictedEvidenceStart": "", "predictedEvidenceEnd": "", "argumentDecision": "", "roleDecision": "", "goldEntityText": "", "goldEntityStart": "", "goldEntityEnd": "", "goldEntityType": "", "goldEntityURI": "", "goldArgumentRole": "", "goldTriggerText": "", "goldTriggerStart": "", "goldTriggerEnd": "", "goldEventType": "", "goldEvidenceText": "", "goldEvidenceStart": "", "goldEvidenceEnd": "", "reviewerId": "", "reviewedAt": "", "reviewNotes": "",
            })

    write_csv(OUT / "sentence_annotation_template.csv", sentence_rows)
    write_csv(OUT / "event_annotation_template.csv", event_rows)
    write_csv(OUT / "entity_annotation_template.csv", entity_rows)
    write_csv(OUT / "argument_link_annotation_template.csv", argument_rows)

    sample_counts = defaultdict(int)
    for row in article_meta.values():
        for tag in row["stratumTags"].split("|"):
            if tag: sample_counts[tag] += 1
    dump_json(OUT / "sample_manifest.json", {
        "cohort": "NEWS_COHORT_2026Q3_100_CONTROLLED_V1", "sampleSize": len(article_meta),
        "selectionMethod": "Deterministic stratified purposive sample; quotas are non-exclusive; all saved boundary-cue articles included; ACB event-context case forced in; remaining slots filled reproducibly.",
        "stratumCountsNonExclusive": dict(sample_counts), "reviewDecisionValues": ["CORRECT", "INCORRECT", "UNCERTAIN", "NOT_IN_MAIN_ARTICLE"],
        "allReviewFieldsInitiallyBlank": True, "articleIds": list(article_meta), "acbPromotionBlocked": True,
        "blockedAcbEventIds": ["PREDICTED_EVENT:15e41d2933fe972e935d", "PREDICTED_EVENT:5665abf1d39db4a7a00b"],
        "limitations": ["This is a small review set, not a random sample for population prevalence.", "No financial-domain gold labels or financial-domain metrics are produced until review is complete."],
    })
    (OUT / "ANNOTATION_GUIDE.md").write_text(make_guide(sample_counts, article_meta), encoding="utf-8")
    (OUT / "README.md").write_text(make_readme(), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "articles": len(article_meta), "strata": dict(sample_counts),
                      "sentences": len(sentence_rows), "events": len(event_rows), "entities": len(entity_rows), "argumentPairs": len(argument_rows)}, ensure_ascii=False, indent=2))


def make_readme():
    return """# Financial-domain gold evaluation v1

This package prepares a 20-article review sample from saved local inputs and inference only. It does not label predictions, train models, crawl, or modify project source data.

## Files

- `article_sample.csv`: selected article IDs, URLs, text hashes, and overlapping sampling strata.
- `sentence_annotation_template.csv`: original saved text by sentence and source-context review.
- `event_annotation_template.csv`: shared ED proposals plus one missed-event slot per sentence.
- `entity_annotation_template.csv`: EMD v1/v2 proposals plus missed-entity slots.
- `argument_link_annotation_template.csv`: EAE v1/v2 role proposals, NONE pairs, and missed-link slots.
- `ANNOTATION_GUIDE.md`: decision definitions and examples.
- `sample_manifest.json`: reproducibility and sample limits.
- `scripts/evaluate_financial_gold.py` (run from the project root): evaluator. It emits no PRF metrics until all selected articles and model proposals have complete review.

The annotation CSVs are the working copies. Keep a backup before editing; do not rename columns or turn blank decisions into defaults.
"""


def make_guide(sample_counts, article_meta):
    template = (Path(__file__).resolve().parent / "financial_gold_eval_guide.md").read_text(encoding="utf-8-sig")
    return template.replace("{{SAMPLE_COUNTS}}", repr(dict(sample_counts)))
    # Kept below for compatibility with older checked-in copies; active guide is
    # the maintained UTF-8 template above.
    acb = "https://vietstock.vn/2026/10/tu-gan-200-ho-so-du-giai-acb-chinh-phuc-hang-muc-kep-tai-thuong-hieu-vang-tphcm-2026-757-1502321.htm"
    return f'''# Annotation guide — Financial-domain gold evaluation v1

## Goal and scope

Review the selected 20 articles as a small financial-domain gold set. Annotate what the saved source supports, including events/entities missed by the models. Do not accept a model prediction just because it exists. Keep candidate predictions and gold judgments separate.

All review fields begin blank. Only a researcher can enter a decision. The four allowed decisions are exactly `CORRECT`, `INCORRECT`, `UNCERTAIN`, and `NOT_IN_MAIN_ARTICLE`.

## Sample design

The selection is deterministic, stratified, purposive, and overlapping. Current tags and counts: `{dict(sample_counts)}`. Categories ensure coverage of Event+KG path, URI match without path, v1/v2 boundary or missed-entity cases, articles with no predicted Event, and all saved articles with source-boundary marker cues. This sample is for model diagnosis, not estimating prevalence over all 100 articles.

## Unit and coordinates

- `sentence_annotation_template.csv` has one row per sentence from the saved article title and selected body/summary. `originalText` is copied from local saved source text. `sentenceStart`/`sentenceEnd` are zero-based, half-open character offsets within the `sourceField` named in the row.
- Candidate trigger/entity/evidence offsets in the other sheets are mapped from the saved model input back to the original saved source field. They use the same zero-based, half-open convention. `sourceContentHash` pins text version; do not edit `originalText`.
- Evidence spans should be the shortest text that supports the event and participant relation. A sentence can contain multiple Events or Entities. Add rows as needed.

## Decision meanings

- `CORRECT`: the exact candidate value is supported by the source and matches the annotation task.
- `INCORRECT`: the candidate is wrong in span, type, role, URI, or event relation, according to its specific decision column.
- `UNCERTAIN`: source/context does not support a confident judgment. Exclude it from gold scoring.
- `NOT_IN_MAIN_ARTICLE`: the text is sidebar, related news, navigation, ad, footer, or other material outside the main story. Do not count it as a gold event/entity. Keep the model proposal in the sheet so it can be measured as a source-boundary false positive.

`sourceContextDecision` concerns whether the evidence text belongs to the main article and supports the reading being reviewed. `CORRECT` means valid main-article context, `INCORRECT` means it is in the main article but does not support the proposed fact, `NOT_IN_MAIN_ARTICLE` means non-article content, and `UNCERTAIN` means the boundary cannot be decided from the saved source.

## Review workflow

1. Open the article URL and compare with the saved sentence. For this prepared gold set, use the saved text and hash as the reproducible input; do not silently replace it with newer page text.
2. Mark each sentence `sentenceReviewStatus=REVIEWED` only after checking the entire sentence for missed Events and Entities. Set its `sourceContextDecision` separately.
3. For each ED proposal, judge trigger and event type separately. Keep predicted fields unchanged. If incorrect or missing, add an `REVIEW_ADDED_SLOT` row, enter the gold trigger/type/evidence and set both relevant decisions to `CORRECT`.
4. For EMD, judge span and type separately. Correct one does not imply the other. When the models missed an entity, fill a reviewer-added slot with its exact source span/type. Do not normalize away punctuation or legal names in the span.
5. In argument rows, judge whether this entity participates in this specific Event (`argumentDecision`) and whether its role is correct (`roleDecision`). `NONE` is a negative pair. Do not link all entities in a sentence to every Event. Add rows for missed arguments and for entities the models did not propose.
6. Resolve URI only when the source and KG identity are clear. Enter `goldEntityURI` for confirmed URI; leave it blank if the entity is outside the KG or unresolved and explain in notes. URI matching is independent from Event participation.
7. Enter reviewer ID and date. Keep all uncertain and non-main-article decisions explicit. Do not delete candidate rows.

## Concrete examples

### ACB related-news contamination — review, do not pre-label

Article: {acb}

The article is about ACB receiving awards. Two saved ED/EAE proposals predict `Transfer-money` with trigger “trả” and assign ACB the role `Giver`. Their evidence starts around saved `bodyText` offset 7779, begins with an ACB customer-service call to action, and then contains related-ticker / related-news headings and CSV/ECO headlines. The trigger “trả” occurs in the unrelated CSV/ECO headlines. The ACB direct path is `BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW`; do not change that gate based on model output. If the reviewer verifies the segment is outside the main story, mark `NOT_IN_MAIN_ARTICLE`; if page structure is unavailable, use `UNCERTAIN`. Do not mark the relation gold from co-occurrence alone.

### Boundary cases

- CTS: v1 span is “Công ty Cổ phần Chứng khoán VietinBank”; v2 overlap is only “Chứng khoán”. Review the exact complete organization name in source. A v2 boundary miss is not repaired by assigning the URI from v1; annotate the true source span, then evaluate the URI independently.
- BID: v1 span is “Ngân hàng Thương mại Cổ phần Đầu tư và Phát triển Việt Nam”; v2 overlap begins “Thương mại Cổ phần Đầu tư và Phát triển Việt Nam”. Decide the boundary against the source rather than treating the near-match URI as proof.

### Type review

For every ORG/PER/FAC/other span, use the type definitions in the BKEE label guide and the entity referent in this sentence. Do not infer `ORG` just because a string resembles a ticker, or `PER` because a phrase refers to a job-holder. If boundary is correct but type is wrong, mark `spanDecision=CORRECT`, `typeDecision=INCORRECT`, then add/complete the corrected annotation row with the gold type. Never infer a type from KG path availability.

## Evaluator contract

The evaluator requires every sentence in an article to be marked `REVIEWED`, a source-context decision for every sentence, and explicit decisions for all model prediction rows. It will not score an incomplete article. Confirmed gold items are constructed only from reviewer decisions `CORRECT` plus reviewer-entered spans/types/roles; unreviewed rows are never gold. `UNCERTAIN` is excluded; `NOT_IN_MAIN_ARTICLE` stays a model prediction (so it can count as an out-of-main-content false positive) but is never gold. Reported scores are small-sample diagnostics, not a 100-article population estimate.
'''


if __name__ == "__main__":
    main()
