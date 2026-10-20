"""Chuyển các snapshot đã crawl thành một KG RDF hợp nhất."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rdflib import Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

from wfkg.config import ProjectConfig
from wfkg.graph.store import GraphStore


WFkg = Namespace("https://example.org/wfkg/v1#")


def _records(snapshot_dir: Path, folder: str) -> list[dict[str, Any]]:
    """Đọc snapshot theo tên file ổn định; bỏ qua file lỗi để báo rõ ở bước tổng hợp."""
    result: list[dict[str, Any]] = []
    path = snapshot_dir / folder
    if not path.exists():
        return result
    for file_path in sorted(path.glob("*.json")):
        try:
            # Một số snapshot do công cụ Windows tạo có BOM UTF-8 ở đầu file.
            value = json.loads(file_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Snapshot JSON không đọc được: {file_path}: {exc}") from exc
        if isinstance(value, dict):
            result.append(value)
    return result


def _node(identifier: Any) -> URIRef:
    return WFkg[str(identifier)]


def _literal(graph, subject, predicate: str, value: Any, datatype=None) -> None:
    if value is not None and value != "":
        graph.add((subject, WFkg[predicate], Literal(value, datatype=datatype)))


def _iri(graph, subject, predicate: str, value: Any) -> None:
    if value:
        graph.add((subject, WFkg[predicate], URIRef(str(value))))


def _typed(graph, record: dict[str, Any], class_name: str, id_key: str, fields: dict[str, str]) -> URIRef:
    node = _node(record[id_key])
    graph.add((node, RDF.type, WFkg[class_name]))
    for field, datatype in fields.items():
        value = record.get(field)
        if value is None:
            continue
        if datatype == "iri":
            _iri(graph, node, field, value)
        else:
            _literal(graph, node, field, value, getattr(XSD, datatype) if datatype else None)
    return node


def _add_source_references(graph, node: URIRef, record: dict[str, Any]) -> None:
    """Ontology hiện lưu nguồn bằng sourceReference; giữ từng URL làm provenance trực tiếp."""
    refs = record.get("sourceReferences", [])
    if isinstance(refs, dict):
        refs = [refs]
    for ref in refs if isinstance(refs, list) else []:
        url = ref.get("url") if isinstance(ref, dict) else ref
        _iri(graph, node, "sourceReference", url)


def export_snapshots(config: ProjectConfig) -> tuple[Path, Counter[str]]:
    """Nạp entity snapshots, nối graph giá đã SHACL, rồi xác thực graph toàn cục."""
    root = config.path.parent.parent
    snapshots = root / config.paths["snapshots"]
    store = GraphStore(root / config.paths["schema_ontology"], root / config.paths["schema_shapes"])
    graph = store.graph
    counts: Counter[str] = Counter()

    # Thêm graph giá đã được kiểm tra riêng bởi job crawl thị trường.
    market_graph = root / config.paths["gold"] / "market_observations.ttl"
    if market_graph.is_file():
        store.load(market_graph)

    companies = _records(snapshots, "companies")
    stocks = {str(r["stockId"]): r for r in _records(snapshots, "stocks") if r.get("stockId")}
    # Company snapshots for the seven subsidiaries also carry their exchange-qualified stock ID.
    # Create the minimal Stock identity from that crawled identifier so Company.hasStock resolves.
    for company in companies:
        stock_id = company.get("hasStock")
        if stock_id and str(stock_id) not in stocks:
            exchange, _, ticker = str(stock_id).partition(":")
            stocks[str(stock_id)] = {
                "stockId": str(stock_id), "tickerSymbol": ticker, "exchange": exchange,
                "sourceReferences": company.get("sourceReferences", []),
            }
    aliases = _records(snapshots, "company_aliases")
    for record in stocks.values():
        node = _typed(graph, record, "Stock", "stockId", {
            "stockId": "string", "tickerSymbol": "string", "exchange": "string",
        })
        counts["Stock"] += 1
    company_nodes: dict[str, URIRef] = {}
    for record in companies:
        node = _typed(graph, record, "Company", "companyId", {
            "companyId": "string", "companyType": "string", "fullName": "string", "shortName": "string",
        })
        if str(record.get("companyType", "")).upper() == "BANK":
            graph.add((node, RDF.type, WFkg.Bank))
            counts["Bank"] += 1
        company_nodes[str(record["companyId"])] = node
        if record.get("hasStock"):
            graph.add((node, WFkg.hasStock, _node(record["hasStock"])))
        if record.get("belongsToIndustry"):
            graph.add((node, WFkg.belongsToIndustry, _node(record["belongsToIndustry"])))
        industry_reference = record.get("industrySourceReference", {})
        if isinstance(industry_reference, dict):
            _iri(graph, node, "sourceReference", industry_reference.get("url"))
        counts["Company"] += 1

    for record in aliases:
        node = _typed(graph, record, "CompanyAlias", "aliasId", {
            "aliasId": "string", "aliasName": "string", "aliasType": "string",
        })
        company = company_nodes.get(str(record.get("companyId")))
        if company:
            graph.add((company, WFkg.hasAlias, node))
        counts["CompanyAlias"] += 1

    for record in _records(snapshots, "industries"):
        if record.get("industryGroupId"):
            group = _typed(graph, record, "IndustryGroup", "industryGroupId", {
                "industryGroupId": "string", "industryGroupName": "string", "taxonomyName": "string",
            })
            _add_source_references(graph, group, record)
            counts["IndustryGroup"] += 1
        else:
            node = _typed(graph, record, "Industry", "industryId", {
                "industryId": "string", "industryName": "string", "industryCode": "string", "taxonomyName": "string",
            })
            if record.get("belongsToGroup"):
                graph.add((node, WFkg.belongsToGroup, _node(record["belongsToGroup"])))
            _add_source_references(graph, node, record)
            counts["Industry"] += 1

    for record in _records(snapshots, "government_organizations"):
        node = _typed(graph, record, "GovernmentOrganization", "organizationId", {
            "organizationId": "string", "organizationName": "string",
        })
        _add_source_references(graph, node, record)
        counts["GovernmentOrganization"] += 1

    for record in _records(snapshots, "news_sources"):
        node = _typed(graph, record, "NewsSource", "sourceId", {
            "sourceId": "string", "sourceName": "string", "sourceType": "string",
            "reliabilityScore": "decimal",
        })
        _iri(graph, node, "sourceReference", record.get("homepageUrl"))
        counts["NewsSource"] += 1

    for record in _records(snapshots, "financial_metrics"):
        node = _typed(graph, record, "FinancialMetric", "metricId", {
            "metricId": "string", "metricType": "string", "metricValue": "decimal", "unit": "string",
            "periodType": "string", "periodStart": "date", "periodEnd": "date", "availableAt": "dateTime",
            "sourceReference": "iri",
        })
        company = company_nodes.get(str(record.get("companyId")))
        if company:
            graph.add((company, WFkg.hasFinancialMetric, node))
        for url in record.get("additionalSourceReferences", []):
            _iri(graph, node, "sourceReference", url)
        counts["FinancialMetric"] += 1

    # IndustryExposure là snapshot tín dụng theo ngành, lấy từ bảng phân bổ trong BCTC.
    # exposureStrength dùng cùng tỷ lệ dư nợ để đường liên kết gián tiếp có trọng số dữ liệu.
    for record in _records(snapshots, "industry_exposures"):
        node = _typed(graph, record, "IndustryExposure", "exposureId", {
            "exposureRatio": "decimal", "exposureStrength": "decimal",
            "reportedCategory": "string", "periodType": "string", "periodEnd": "date",
            "availableAt": "dateTime", "relationConfidence": "decimal",
            "dataQualityFlag": "string", "sourceReference": "iri",
        })
        graph.add((node, WFkg.exposureBank, _node(record["exposureBank"])))
        graph.add((node, WFkg.exposureIndustry, _node(record["exposureIndustry"])))
        graph.add((_node(record["exposureBank"]), WFkg.hasIndustryExposure, node))
        counts["IndustryExposure"] += 1

    indexes = _records(snapshots, "market_indexes")
    for record in indexes:
        _typed(graph, record, "MarketIndex", "indexId", {
            "indexId": "string", "indexCode": "string", "indexName": "string",
        })
        counts["MarketIndex"] += 1

    for record in _records(snapshots, "index_memberships"):
        node = _typed(graph, record, "IndexMembership", "membershipId", {
            "validFrom": "date", "availableAt": "dateTime", "relationConfidence": "decimal",
            "dataQualityFlag": "string", "sourceReference": "iri",
        })
        stock = _node(record["memberStock"])
        graph.add((node, WFkg.memberStock, stock))
        graph.add((node, WFkg.memberIndex, _node(record["memberIndex"])))
        graph.add((stock, WFkg.hasIndexMembership, node))
        counts["IndexMembership"] += 1

    for record in _records(snapshots, "corporate_leaders"):
        _typed(graph, record, "CorporateLeader", "personId", {
            "personId": "string", "fullName": "string",
        })
        counts["CorporateLeader"] += 1

    for record in _records(snapshots, "leadership_positions"):
        node = _typed(graph, record, "LeadershipPosition", "positionId", {
            "positionTitle": "string", "validFrom": "date", "availableAt": "dateTime",
            "relationConfidence": "decimal", "dataQualityFlag": "string", "sourceReference": "iri",
        })
        graph.add((node, WFkg.positionHolder, _node(record["positionHolder"])))
        graph.add((node, WFkg.positionAtCompany, _node(record["positionAtCompany"])))
        graph.add((_node(record["positionHolder"]), WFkg.hasLeadershipPosition, node))
        counts["LeadershipPosition"] += 1

    for record in _records(snapshots, "subsidiary_relations"):
        node = _typed(graph, record, "SubsidiaryRelation", "relationId", {
            "observedAsOf": "date", "validFrom": "date", "validTo": "date", "availableAt": "dateTime",
            "relationConfidence": "decimal", "dataQualityFlag": "string", "sourceReference": "iri",
        })
        graph.add((node, WFkg.parentCompany, _node(record["parentCompany"])))
        graph.add((node, WFkg.subsidiaryCompany, _node(record["subsidiaryCompany"])))
        graph.add((_node(record["parentCompany"]), WFkg.hasSubsidiaryRelation, node))
        counts["SubsidiaryRelation"] += 1

    # Đọc mọi snapshot bài báo trước, sau đó chọn cohort theo manifest nếu đã khóa.
    # Cách này giúp các lần build KG dùng cùng một tập 100 bài, dù sau đó ta crawl thêm tin.
    all_article_records = _records(snapshots, "news_articles")
    article_limit = int(config.values.get("vertical_slice", {}).get("article_limit", 100))
    selection_manifest_relative = config.paths.get("news_selection_manifest")
    selection_manifest_path = root / selection_manifest_relative if selection_manifest_relative else None
    selection_manifest: dict[str, Any] | None = None
    if selection_manifest_path and selection_manifest_path.is_file():
        # Manifest chứa ID cố định và nhãn coverage; metadata bài vẫn lấy từ snapshot có provenance.
        selection_manifest = json.loads(selection_manifest_path.read_text(encoding="utf-8-sig"))
        selected_items = selection_manifest.get("articles", [])
        wanted_list = [str(item.get("articleId", "")) for item in selected_items if item.get("articleId")]
        wanted = set(wanted_list)
        if len(wanted_list) != article_limit or len(wanted) != article_limit:
            raise ValueError(
                f"Manifest cohort cần đúng {article_limit} articleId duy nhất; "
                f"hiện có {len(wanted_list)} mục và {len(wanted)} ID duy nhất."
            )
        by_id = {str(record.get("articleId")): record for record in all_article_records}
        missing = sorted(wanted - set(by_id))
        if missing:
            raise ValueError(f"Thiếu {len(missing)} snapshot theo manifest: {', '.join(missing[:5])}")
        # Giữ đúng thứ tự manifest để kết quả build có thứ tự ổn định, dễ so sánh.
        articles = [by_id[article_id] for article_id in wanted_list]
    else:
        # Tương thích với dự án trước khi có cohort manifest: ưu tiên batch crawl gần nhất.
        latest_batch_dir = root / config.paths["raw_daily"] / "news"
        batch_files = sorted(latest_batch_dir.glob("*.json")) if latest_batch_dir.exists() else []
        if batch_files:
            batch = json.loads(batch_files[-1].read_text(encoding="utf-8-sig"))
            wanted = {str(item.get("articleId")) for item in batch.get("articles", []) if item.get("articleId")}
            articles = [record for record in all_article_records if str(record.get("articleId")) in wanted]
            if len(articles) != len(wanted):
                raise ValueError(
                    f"Batch tin mới nhất có {len(wanted)} mã nhưng chỉ tìm thấy {len(articles)} snapshot tương ứng."
                )
        else:
            articles = sorted(
                all_article_records,
                key=lambda item: (str(item.get("availableAt", "")), str(item.get("articleId", ""))),
                reverse=True,
            )[:article_limit]
    for record in articles:
        node = _typed(graph, record, "NewsArticle", "articleId", {
            "articleId": "string", "title": "string", "url": "iri", "publishedAt": "dateTime",
            "availableAt": "dateTime",
        })
        # Ontology chưa có thuộc tính tóm tắt riêng cho NewsArticle; không gán
        # wfkg:description vì property này có domain Event và sẽ suy diễn sai kiểu.
        if record.get("sourceId"):
            graph.add((node, WFkg.publishedBy, _node(record["sourceId"])))
        counts["NewsArticle"] += 1

    # Thêm source URL cho những entity ontology không có trường provenance riêng dạng danh sách.
    # Các snapshot gốc vẫn được giữ nguyên dưới data/snapshots để trace trường xác minh.
    for folder, class_name, id_key in (
        ("companies", "Company", "companyId"), ("stocks", "Stock", "stockId"),
        ("company_aliases", "CompanyAlias", "aliasId"), ("industries", None, None),
        ("corporate_leaders", "CorporateLeader", "personId"), ("market_indexes", "MarketIndex", "indexId"),
    ):
        if class_name is None:
            continue
        for record in _records(snapshots, folder):
            if record.get(id_key):
                _add_source_references(graph, _node(record[id_key]), record)

    # Báo cáo cả hai kiểu quan sát vốn được xuất bởi market job riêng.
    counts["MarketObservation"] = sum(1 for _ in graph.subjects(RDF.type, WFkg.MarketObservation))
    counts["MarketIndexObservation"] = sum(1 for _ in graph.subjects(RDF.type, WFkg.MarketIndexObservation))

    conforms, report = store.validate()
    if not conforms:
        raise RuntimeError(f"KG tổng hợp chưa qua SHACL; chưa lưu file mới.\n{report}")

    output = root / config.paths["gold"] / "knowledge_graph.ttl"
    store.save(output)
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "graphFile": str(output.relative_to(root)),
        "validation": "SHACL_CONFORMS",
        "counts": dict(counts),
        "marketGraphMerged": market_graph.is_file(),
        "newsArticleSelection": (
            str(selection_manifest_path.relative_to(root))
            if selection_manifest is not None and selection_manifest_path is not None
            else "latest raw daily crawl batch, capped by vertical_slice.article_limit"
        ),
        "newsArticleCohortId": selection_manifest.get("cohortId") if selection_manifest else None,
        "newsRelationPathCoverage": selection_manifest.get("relationPathCoverage") if selection_manifest else None,
        "excludedSnapshotFolders": ["leadership_unresolved", "leadership_exclusions", "subsidiary_relation_candidates", "market_observations_vietstock"],
        "note": "Các bản snapshot nguồn được giữ nguyên trong data/snapshots; các bản candidate/chưa đủ điều kiện không thành fact KG.",
    }
    manifest_path = output.with_name("knowledge_graph_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, counts
