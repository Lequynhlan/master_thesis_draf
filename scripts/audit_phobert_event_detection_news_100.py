"""Audit saved PhoBERT predictions against the fixed news cohort and current KG."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Namespace, RDF

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "runs/phobert_bkee_event_detection_v2/news_100_final/event_predictions.jsonl"
REPORT = ROOT / "runs/phobert_bkee_event_detection_v2/news_100_final/inference_report.json"
MANIFEST = ROOT / "data/output/news_article_selection_manifest.json"
KG = ROOT / "data/gold/knowledge_graph.ttl"
ANALYST_EVENTS = ROOT / "runs/wfkg_vertical_slice_news_100_v1/event_extractions.jsonl"
ENRICHED = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
OUTPUT = ROOT / "runs/phobert_bkee_event_detection_v2/inference_audit_100_20261019"

PARTIAL_FINANCE_TYPES = {
    "Transfer-money", "Transfer-ownership", "Declare-bankruptcy", "Fine", "Sue", "Merge-org",
    "Start-org", "End-org", "Start-position", "End-position", "Elect", "Nominate",
}
NO_FINANCE_MAPPING_TYPES = {
    "Appeal", "Arquit", "Arrest-jail", "Attack", "Be-born", "Charge-indict", "Convict",
    "Demonstrate", "Die", "Divorce", "Execute", "Extradite", "Injure", "Marry", "Meet",
    "Pardon", "Phone-write", "Release-parole", "Sentence", "Transport", "Trial-hearing",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fold(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def clean_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split()).strip()


def has_alias(text: str, alias: str) -> bool:
    alias_folded = fold(alias)
    if len(alias_folded) <= 4 and alias_folded.isascii() and alias_folded.isalnum():
        return re.search(rf"(?<![a-z0-9]){re.escape(alias_folded)}(?![a-z0-9])", fold(text)) is not None
    return alias_folded in fold(text)


def render_markdown(summary: dict, event_counts: Counter, confidence: dict, entity_summary: dict,
                    ontology_rows: list[dict], annotation: dict) -> str:
    lines = [
        "# PhoBERT Event Detection: audit 100 bài báo",
        "",
        f"- Cohort: `{summary['cohortId']}` ({summary['cohortSize']} bài).",
        f"- Checkpoint: `{summary['checkpoint']}`; đọc inference đã lưu, không chạy lại model.",
        f"- Bài có ≥1 event: **{summary['articlesWithEvents']}**; không có event: **{summary['articlesWithoutEvents']}**.",
        f"- Tổng prediction: **{summary['predictedEventCount']}**; successful inference: {summary['processedSuccessfully']}/100.",
        f"- Confidence: mean {confidence['mean']:.3f}, median {confidence['median']:.3f}, min {confidence['min']:.3f}, max {confidence['max']:.3f}.",
        "",
        "## Phân bố prediction",
        "",
        "| BKEE type | Số event | Ontology/finance audit |",
        "|---|---:|---|",
    ]
    ontology_by_type = {row["eventType"]: row["auditStatus"] for row in ontology_rows}
    lines += [f"| `{kind}` | {count} | {ontology_by_type.get(kind, 'Không xuất hiện')} |" for kind, count in event_counts.most_common()]
    lines += [
        "",
        "Ontology hiện khai báo `wfkg:eventType` là `xsd:string`, không có danh mục giá trị đóng hay mapping BKEE. Vì vậy nhãn có thể ghi về mặt kiểu dữ liệu, nhưng chưa có ánh xạ ontology đã xác nhận. Nhóm semantic overlap chỉ là gợi ý rà soát; không tự tạo hoặc ghi nhãn ontology mới.",
        "",
        "## Entity linking",
        "",
        f"- Prediction có ticker/name VN30 ngân hàng khớp literal trong title/evidence: {entity_summary['eventsWithVn30BankMention']}/{summary['predictedEventCount']} event.",
        f"- Prediction có ít nhất một entity Company/Bank trong KG khớp literal: {entity_summary['eventsWithKgCompanyMention']}/{summary['predictedEventCount']} event.",
        f"- Không khớp entity Company/Bank KG theo literal: {entity_summary['eventsWithoutKgCompanyMention']} event.",
        "- Đây là kiểm tra khả năng sinh ứng viên bằng exact alias, không phải NER/entity linking đã xác nhận. KG hiện có 13 Bank, 20 Company, 13 CompanyAlias; article có thể gắn với ticker con/đơn vị khác trong KG.",
        "",
        "## Đối chiếu annotation và phân loại lỗi",
        "",
        f"- Có {annotation['analystReviewedRecordCount']} event records `ANALYST_REVIEWED_RULE_BASED_NOT_PHOBERT` trên {annotation['analystReviewedUniqueCanonicalEvents']} canonical event trong cùng cohort. Đây là annotation tham khảo có chọn lọc, không exhaustive gold; đánh giá release cũng ghi NLP P/R/F1 NOT_EVALUATED. KG chính có {annotation['kgEventCount']} Event, {annotation['kgEvidenceCount']} Evidence, {annotation['kgCandidateCount']} EventStockCandidate. Hai manual gold files khác là entity templates còn `PENDING`.",
        f"- Đối chiếu tham khảo: {annotation['directBkeeTypeMatches']}/{annotation['analystReviewedRecordCount']} record có type khớp trực tiếp; trigger của {annotation['predictedTriggersWithinHashVerifiedEvidence']}/{annotation['hashVerifiedEvidenceRecordCount']} record rơi trong evidence span reviewed khi body hash khớp. Không quy đổi thành precision/recall vì labels financial chưa thuộc BKEE và reference không exhaustive.",
        f"- Hash body reviewed khớp corpus hiện tại ở {annotation['hashVerifiedEvidenceRecordCount']}/{annotation['analystReviewedRecordCount']} record; offsets của record còn lại không dùng để so span.",
        "- Sai loại sự kiện và không nhận diện event: không thể chấm tổng thể khi thiếu gold span/type exhaustive. Trên các reference: xem `analyst_review_comparison.csv`; hai canonical labels (`EARNINGS_*`, `CAPITAL_INCREASE_*`) không có BKEE label tương ứng, nên không nhận diện đúng loại chuyên biệt là giới hạn taxonomy.",
        f"- Thiếu entity: extractor không xuất argument/entity. Literal scan cho thấy {entity_summary['eventsWithoutKgCompanyMention']} prediction không có Company/Bank KG alias trong title/evidence; số này không đồng nghĩa chắc chắn là lỗi vì entity có thể nằm ngoài cửa sổ evidence hoặc chưa có alias.",
        "- Không hỗ trợ ontology: mọi type xuất hiện đều chưa có mapping BKEE→ontology được định nghĩa; các type nằm ngoài nhóm overlap cần được abstain/duyệt thủ công.",
        f"- Thiếu bằng chứng: {summary['eventsMissingEvidence']} prediction thiếu evidence text hoặc trigger không nằm trong evidence text; prediction còn lại có evidence span cục bộ, nhưng chưa được analyst xác nhận là đủ hỗ trợ ngữ nghĩa.",
        "",
        "## Kết luận end-to-end",
        "",
        "Checkpoint phù hợp làm bước đề xuất trigger có provenance để analyst review. Chưa nên đưa thẳng prediction thành Event/EventStockCandidate: hiện không có event arguments, canonical entity link, mapping type đã duyệt, hoặc đánh giá gold trên miền tài chính. Cần annotation event/argument/entity cho cohort, mapping type được duyệt, rồi mới sinh candidate theo các route KG/SHACL.",
        "",
        "## Artefacts",
        "",
        "- `event_predictions_audit.csv`: bảng chi tiết theo yêu cầu, một hàng mỗi prediction.",
        "- `article_entity_link_audit.csv`: heuristic entity alias match theo bài.",
        "- `ontology_type_audit.csv`: mapping status cho đủ 33 BKEE labels.",
        "- `analyst_review_comparison.csv`: so sánh tham khảo theo 5 record reviewed event.",
        "- `audit_summary.json`: thống kê máy đọc được.",
        "",
        "Confidence bins: " + ", ".join(f"{key}={value}" for key, value in confidence["bins"].items()) + ".",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if any(OUTPUT.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty audit directory: {OUTPUT}")
    inference = json.loads(REPORT.read_text(encoding="utf-8"))
    predictions = load_jsonl(PREDICTIONS)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    articles = {article["articleId"]: article for article in manifest["articles"]}

    graph = Graph().parse(KG, format="turtle")
    wfkg = Namespace("https://example.org/wfkg/v1#")
    companies: dict[str, dict] = {}
    for subject in set(graph.subjects(RDF.type, wfkg.Company)):
        entity_id = str(next(iter(graph.objects(subject, wfkg.companyId)), subject).split("#")[-1])
        names = set()
        for predicate in (wfkg.fullName, wfkg.shortName, wfkg.tickerSymbol):
            names.update(str(obj) for obj in graph.objects(subject, predicate))
        for alias_node in graph.objects(subject, wfkg.hasAlias):
            names.update(str(obj) for obj in graph.objects(alias_node, wfkg.aliasName))
        for stock in graph.objects(subject, wfkg.hasStock):
            names.update(str(obj) for obj in graph.objects(stock, wfkg.tickerSymbol))
        names.add(entity_id.split(":")[-1])
        companies[entity_id] = {
            "id": entity_id,
            "isBank": (subject, RDF.type, wfkg.Bank) in graph,
            "names": sorted(names),
        }

    event_rows: list[dict] = []
    article_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    confidences: list[float] = []
    events_missing_evidence = 0
    entity_articles: list[dict] = []
    events_with_bank_mention = 0
    events_with_kg_company_mention = 0
    ambiguous_company_event_count = 0

    per_article_events: dict[str, list[dict]] = defaultdict(list)
    for article in predictions:
        article_id = article["articleId"]
        article_manifest = articles[article_id]
        title = article.get("title") or article_manifest.get("title", "")
        for event in article.get("events", []):
            event_type = event["eventType"]
            trigger = event.get("trigger", {}).get("text", "")
            evidence = event.get("evidenceSpan", {}).get("text", "")
            confidence = float(event.get("confidenceScore", 0.0))
            full_match_text = f"{title} {evidence}"
            matched = []
            for entity in companies.values():
                aliases = [name for name in entity["names"] if name]
                if any(has_alias(full_match_text, name) for name in aliases):
                    matched.append(entity)
            bank_matches = [entity for entity in matched if entity["isBank"]]
            events_with_bank_mention += bool(bank_matches)
            events_with_kg_company_mention += bool(matched)
            ambiguous_company_event_count += len(matched) > 1
            evidence_ok = bool(evidence and trigger and trigger in evidence)
            events_missing_evidence += not evidence_ok
            row = {
                "articleId": article_id,
                "title": title,
                "predictedEventType": event_type,
                "trigger": trigger,
                "confidence": confidence,
                "evidenceText": evidence,
                "sourceMethod": event.get("extractionMethod", ""),
            }
            event_rows.append(row)
            per_article_events[article_id].append(row)
            type_counts[event_type] += 1
            confidences.append(confidence)
            article_counts[article_id] += 1

    with (OUTPUT / "event_predictions_audit.csv").open("w", encoding="utf-8-sig", newline="") as dest:
        fields = ["articleId", "title", "predictedEventType", "trigger", "confidence", "evidenceText", "sourceMethod"]
        writer = csv.DictWriter(dest, fieldnames=fields)
        writer.writeheader()
        for row in event_rows:
            writer.writerow(row)

    for article in predictions:
        article_id = article["articleId"]
        article_manifest = articles[article_id]
        full_text = article_manifest.get("title") or ""
        for event in per_article_events.get(article_id, []):
            full_text += " " + event["evidenceText"]
        matched = []
        for entity in companies.values():
            if any(has_alias(full_text, name) for name in entity["names"] if name):
                matched.append(entity)
        entity_articles.append({
            "articleId": article_id,
            "title": article_manifest.get("title", ""),
            "listingTicker": article_manifest.get("listingTicker", ""),
            "predictedEventCount": len(per_article_events.get(article_id, [])),
            "matchedVn30BankEntityIds": ";".join(sorted(e["id"] for e in matched if e["isBank"])),
            "matchedKgCompanyEntityIds": ";".join(sorted(e["id"] for e in matched)),
            "matchMethod": "literal alias match in title and predicted evidence only; listingTicker is metadata, not counted",
        })
    with (OUTPUT / "article_entity_link_audit.csv").open("w", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=list(entity_articles[0]))
        writer.writeheader()
        writer.writerows(entity_articles)

    bkee_types = inference["bkeeEventTypes"]
    ontology_rows = []
    for event_type in bkee_types:
        if event_type in PARTIAL_FINANCE_TYPES:
            status = "PARTIAL_FINANCE_SEMANTIC_OVERLAP; no approved mapping"
        elif event_type in NO_FINANCE_MAPPING_TYPES:
            status = "NO_CLEAR_FINANCE_MAPPING; no approved mapping"
        else:
            status = "No approved mapping"
        ontology_rows.append({"eventType": event_type, "eventTypeDatatype": "xsd:string", "closedOntologyValue": False,
                             "auditStatus": status, "appearsInCohort": event_type in type_counts,
                             "predictedCount": type_counts.get(event_type, 0)})
    with (OUTPUT / "ontology_type_audit.csv").open("w", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=list(ontology_rows[0]))
        writer.writeheader()
        writer.writerows(ontology_rows)

    enriched_by_id = {row["articleId"]: row for row in load_jsonl(ENRICHED)}
    predictions_by_id = {row["articleId"]: row for row in predictions}
    analyst_events = [row for row in load_jsonl(ANALYST_EVENTS) if row.get("articleId") in articles]
    analyst_comparisons = []
    direct_type_matches = 0
    triggers_within_reviewed_evidence = 0
    for reviewed in analyst_events:
        article_id = reviewed["articleId"]
        prediction_row = predictions_by_id.get(article_id, {})
        predicted_events = prediction_row.get("events", [])
        enriched_row = enriched_by_id.get(article_id, {})
        model_title = clean_text(prediction_row.get("title", ""))
        body = clean_text(enriched_row.get("bodyText", ""))
        model_text = "\n".join(part for part in (model_title, body) if part)
        reconstructed_input_hash = hashlib.sha256(model_text.encode("utf-8")).hexdigest()
        input_hash_matches = reconstructed_input_hash == prediction_row.get("inputSha256")
        body_hash_matches = hashlib.sha256(body.encode("utf-8")).hexdigest() == reviewed.get("bodyTextSha256")
        title_offset = len(model_title) + (1 if model_title and body else 0)
        reviewed_start = title_offset + int(reviewed.get("startOffset", 0))
        reviewed_end = title_offset + int(reviewed.get("endOffset", 0))
        bkee_type_match = any(event.get("eventType") == reviewed.get("eventType") for event in predicted_events)
        trigger_inside = body_hash_matches and input_hash_matches and any(
            int(event.get("trigger", {}).get("startChar", -1)) >= reviewed_start
            and int(event.get("trigger", {}).get("endChar", -1)) <= reviewed_end
            for event in predicted_events
        )
        direct_type_matches += bkee_type_match
        triggers_within_reviewed_evidence += trigger_inside
        prediction_text = " | ".join(
            f"{event.get('eventType')}:{event.get('trigger', {}).get('text', '')}"
            f" ({event.get('confidenceScore', 0):.3f})"
            for event in predicted_events
        )
        analyst_comparisons.append({
            "articleId": article_id,
            "title": prediction_row.get("title", reviewed.get("articleTitle", "")),
            "analystArticleTitle": reviewed.get("articleTitle", ""),
            "analystEventId": reviewed.get("eventId", ""),
            "canonicalEventType": reviewed.get("eventType", ""),
            "analystEvidenceText": reviewed.get("evidenceText", ""),
            "predictedEventCount": len(predicted_events),
            "predictedTypeTriggerConfidence": prediction_text,
            "modelInputHashReconstructed": input_hash_matches,
            "analystBodyHashMatchesEnrichment": body_hash_matches,
            "predictedTriggerInsideReviewedEvidence": trigger_inside,
            "reviewedEvidenceOffsetComparable": body_hash_matches and input_hash_matches,
            "directBkeeTypeMatch": bkee_type_match,
            "referenceComparisonStatus": (
                "NO_BKEE_PREDICTION_FOR_REVIEWED_EVENT" if not predicted_events
                else "PREDICTIONS_PRESENT_BUT_NO_DIRECT_TYPE_MATCH; not scored as false positive"
            ),
            "comparisonNote": "Curated analyst reference; not exhaustive gold. No approved BKEE mapping for this financial type.",
        })
    with (OUTPUT / "analyst_review_comparison.csv").open("w", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=list(analyst_comparisons[0]))
        writer.writeheader()
        writer.writerows(analyst_comparisons)

    confidence_bins = {
        "<0.50": sum(score < 0.5 for score in confidences),
        "0.50-0.69": sum(0.5 <= score < 0.7 for score in confidences),
        "0.70-0.89": sum(0.7 <= score < 0.9 for score in confidences),
        ">=0.90": sum(score >= 0.9 for score in confidences),
    }
    confidence_stats = {
        "mean": statistics.mean(confidences) if confidences else 0.0,
        "median": statistics.median(confidences) if confidences else 0.0,
        "min": min(confidences, default=0.0),
        "max": max(confidences, default=0.0),
        "bins": confidence_bins,
    }
    annotation_files = [
        ROOT / "runs/phobert_ner_pilot_news_100_v1/manual_gold_annotation_template.csv",
        ROOT / "runs/phobert_ner_checkpoint_probe_quocanh944_news_100_v1/manual_gold_annotation_template.csv",
    ]
    annotation_templates = []
    for path in annotation_files:
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        annotation_templates.append({
            "path": str(path.relative_to(ROOT)),
            "rows": len(rows),
            "adjudicationStatuses": dict(Counter(row.get("adjudicationStatus", "") for row in rows)),
            "nonemptyGoldEntitySpans": sum(bool(row.get("goldEntitySpansJson", "").strip()) for row in rows),
        })
    k7_path = ROOT / "data/cleaned/news_100_v1/k7_sample_review.csv"
    with k7_path.open(encoding="utf-8-sig", newline="") as source:
        k7_rows = list(csv.DictReader(source))
    annotation = {
        "eventAnalystReviewedRecordsFound": len(analyst_events),
        "analystReviewedRecordCount": len(analyst_events),
        "analystReviewedUniqueCanonicalEvents": len({row.get("eventId") for row in analyst_events}),
        "directBkeeTypeMatches": direct_type_matches,
        "predictedTriggersWithinReviewedEvidence": triggers_within_reviewed_evidence,
        "predictedTriggersWithinHashVerifiedEvidence": triggers_within_reviewed_evidence,
        "hashVerifiedEvidenceRecordCount": sum(row["analystBodyHashMatchesEnrichment"] and row["modelInputHashReconstructed"] for row in analyst_comparisons),
        "curatedReferenceNotExhaustive": True,
        "eventRecordsPath": str(ANALYST_EVENTS.relative_to(ROOT)),
        "searchedFor": "analyst-reviewed extraction records and event annotation files",
        "manualEntityAnnotationTemplates": annotation_templates,
        "textNormalizationReviewRows": len(k7_rows),
        "textNormalizationReviewStatuses": dict(Counter(row.get("sampleReviewStatus", "") for row in k7_rows)),
        "kgEventCount": len(set(graph.subjects(RDF.type, wfkg.Event))),
        "kgEvidenceCount": len(set(graph.subjects(RDF.type, wfkg.Evidence))),
        "kgCandidateCount": len(set(graph.subjects(RDF.type, wfkg.EventStockCandidate))),
    }
    summary = {
        "cohortId": inference["cohortId"],
        "cohortSize": inference["cohortSize"],
        "checkpoint": inference["checkpoint"],
        "processedSuccessfully": inference["processedSuccessfully"],
        "failed": inference["failed"],
        "articlesWithEvents": len(article_counts),
        "articlesWithoutEvents": inference["cohortSize"] - len(article_counts),
        "predictedEventCount": len(event_rows),
        "predictedCountsByType": dict(type_counts.most_common()),
        "confidence": confidence_stats,
        "eventsMissingEvidence": events_missing_evidence,
        "sourceMethods": dict(Counter(row["sourceMethod"] for row in event_rows)),
        "entityMatch": {
            "companyEntityCountInKg": len(companies),
            "bankEntityCountInKg": sum(entity["isBank"] for entity in companies.values()),
            "eventsWithVn30BankMention": events_with_bank_mention,
            "eventsWithKgCompanyMention": events_with_kg_company_mention,
            "eventsWithoutKgCompanyMention": len(event_rows) - events_with_kg_company_mention,
            "eventsWithMultipleKgCompanyMentions": ambiguous_company_event_count,
            "articlesWithAnyVn30BankMention": sum(bool(row["matchedVn30BankEntityIds"]) for row in entity_articles),
            "articlesWithAnyKgCompanyMention": sum(bool(row["matchedKgCompanyEntityIds"]) for row in entity_articles),
            "note": "Literal alias audit only; not an entity recognition/linking system and not gold-validated.",
        },
        "ontology": {
            "eventTypeRange": "xsd:string",
            "closedAllowedValueList": False,
            "approvedBkeeMappings": 0,
            "partialFinanceOverlapTypes": sorted(PARTIAL_FINANCE_TYPES),
            "noClearFinanceMappingTypes": sorted(NO_FINANCE_MAPPING_TYPES),
            "typeAuditFile": "ontology_type_audit.csv",
        },
        "annotation": annotation,
        "errorAssessability": {
            "wrongEventType": "not measurable: no gold event type annotations",
            "missedEvent": "not measurable: no gold event spans",
            "missingEntity": "no event arguments are emitted; see literal-match heuristic table, not a scored error",
            "ontologyUnsupported": "no BKEE mappings approved; partial overlaps require analyst mapping",
            "missingEvidence": events_missing_evidence,
        },
        "devEventMetrics": {"precision": 0.45193008011653313, "recall": 0.7148617511520737, "f1": 0.5537706381079875,
                            "domain": "BKEE dev, not the financial 100-article cohort"},
        "trainingOrInferenceRepeated": False,
        "sourceReport": str(REPORT.relative_to(ROOT)),
    }
    (OUTPUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUTPUT / "audit_report.md").write_text(
        render_markdown(summary, type_counts, confidence_stats, summary["entityMatch"], ontology_rows, annotation),
        encoding="utf-8",
    )
    print(OUTPUT)
    print(json.dumps({
        "articlesWithEvents": summary["articlesWithEvents"],
        "articlesWithoutEvents": summary["articlesWithoutEvents"],
        "events": summary["predictedEventCount"],
        "confidence": confidence_stats,
        "entityMatch": summary["entityMatch"],
        "annotation": annotation,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
