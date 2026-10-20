"""Điều phối các job nạp dữ liệu nền."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright
from rdflib import Literal, Namespace, RDF, URIRef, XSD

from wfkg.config import ProjectConfig
from wfkg.graph.store import GraphStore
from wfkg.initial_data_load.sources.aliases import from_company_snapshot
from wfkg.initial_data_load.sources.companies import collect_one as collect_company
from wfkg.initial_data_load.sources.market_indexes import (
    collect_one as collect_market_index,
    from_official_constituent_list,
)
from wfkg.initial_data_load.sources.market_data import collect as collect_market_observations
from wfkg.initial_data_load.sources.news_sources import collect as collect_news_sources
from wfkg.initial_data_load.sources.relationships import (
    collect_government_organizations,
    collect_subsidiaries,
)
from wfkg.initial_data_load.sources.industries import collect_classification
from wfkg.initial_data_load.sources.index_memberships import collect_vn30_memberships
from wfkg.initial_data_load.sources.leaders import collect_company_leaders
from wfkg.initial_data_load.sources.stocks import collect_one


def run_stock_profile(config: ProjectConfig, ticker: str) -> Path:
    """Crawl thử hồ sơ của một mã rồi lưu JSON chuẩn hóa vào snapshot."""
    symbol = ticker.strip().upper()
    if symbol not in config.stock_symbols:
        raise ValueError(f"{symbol} không nằm trong universe 13 mã ở vertical_slice.yaml.")

    pages = config.values.get("stock_profile_pages", {}).get(symbol, {})
    vietstock_url = pages.get("vietstock")
    cafef_url = pages.get("cafef")
    if not vietstock_url or not cafef_url:
        raise ValueError(
            f"Chưa khai báo URL Vietstock và CafeF đã xác minh cho {symbol} "
            "trong stock_profile_pages."
        )

    # Mỗi lần chạy dùng browser profile tạm, tách biệt hoàn toàn với phiên đăng nhập Edge.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            record = collect_one(browser, symbol, vietstock_url, cafef_url)
        finally:
            browser.close()

    project_root = config.path.parent.parent
    output_path = project_root / config.paths["snapshots"] / "stocks" / f"{symbol}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def run_company_profile(config: ProjectConfig, ticker: str) -> Path:
    """Crawl hồ sơ Company/Bank cho một ticker rồi lưu snapshot có provenance."""
    symbol = ticker.strip().upper()
    if symbol not in config.stock_symbols:
        raise ValueError(f"{symbol} không nằm trong universe 13 mã ở vertical_slice.yaml.")

    pages = config.values.get("stock_profile_pages", {}).get(symbol, {})
    cafef_url = pages.get("cafef")
    if not cafef_url:
        raise ValueError(f"Chưa khai báo URL CafeF đã xác minh cho {symbol}.")

    project_root = config.path.parent.parent
    stock_path = project_root / config.paths["snapshots"] / "stocks" / f"{symbol}.json"
    if not stock_path.is_file():
        raise ValueError(f"Chưa có Stock snapshot đã crawl cho {symbol}: {stock_path}")
    stock_record = json.loads(stock_path.read_text(encoding="utf-8"))
    stock_id = stock_record.get("stockId")
    if not stock_id:
        raise ValueError(f"Stock snapshot của {symbol} chưa có stockId.")

    # Mỗi lần chạy dùng browser profile mới và không tái sử dụng phiên Edge.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            record = collect_company(browser, symbol, cafef_url, stock_id)
        finally:
            browser.close()

    output_path = project_root / config.paths["snapshots"] / "companies" / f"{symbol}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_ticker_aliases(config: ProjectConfig) -> list[Path]:
    """Tạo alias ticker từ Company snapshots đã crawl và lưu từng alias riêng."""
    project_root = config.path.parent.parent
    company_dir = project_root / config.paths["snapshots"] / "companies"
    output_dir = project_root / config.paths["snapshots"] / "company_aliases"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for symbol in config.stock_symbols:
        company_path = company_dir / f"{symbol}.json"
        if not company_path.is_file():
            raise ValueError(f"Chưa có Company/Bank snapshot đã crawl cho {symbol}: {company_path}")
        company = json.loads(company_path.read_text(encoding="utf-8"))
        alias = from_company_snapshot(company)
        output_path = output_dir / f"{symbol}.json"
        output_path.write_text(
            json.dumps(alias.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs.append(output_path)
    return outputs


def run_market_index_profile(config: ProjectConfig, index_code: str) -> Path:
    """Crawl hồ sơ một chỉ số benchmark rồi lưu snapshot có provenance."""
    code = index_code.strip().upper()
    if code != str(config.values.get("vertical_slice", {}).get("benchmark_index", "")).upper():
        raise ValueError(f"{code} không phải benchmark_index được cấu hình cho vertical slice.")

    pages = config.values.get("market_index_pages", {})
    url = pages.get(code)
    if not url:
        raise ValueError(f"Chưa khai báo URL hồ sơ đã xác minh cho MarketIndex {code}.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            record = collect_market_index(browser, code, url)
        finally:
            browser.close()

    project_root = config.path.parent.parent
    output_path = project_root / config.paths["snapshots"] / "market_indexes" / f"{code}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def run_market_observations(
    config: ProjectConfig,
    date_to_override: str | None = None,
    daily: bool = False,
) -> list[Path]:
    """Crawl adjusted close cho universe, lưu raw và snapshot dùng cho KG."""
    project_root = config.path.parent.parent
    slice_config = config.values.get("vertical_slice", {})
    date_from = slice_config.get("market_observation_date_from")
    date_to = date_to_override or slice_config.get("market_observation_date_to")
    if daily and date_to_override is None:
        timezone_name = str(config.values.get("project", {}).get("timezone", "Asia/Ho_Chi_Minh"))
        date_to = datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    if not date_from or not date_to:
        raise ValueError("Cần khai báo khoảng ngày market_observation_date_from/date_to.")
    source = str(config.values.get("market_data", {}).get("source", "kbs"))

    # Chỉ ghi file sau khi đã lấy đủ cả 13 cổ phiếu và benchmark để tránh snapshot nửa chừng.
    records = collect_market_observations(
        config.stock_symbols,
        str(slice_config["benchmark_index"]),
        str(date_from),
        str(date_to),
        source=source,
    )
    expected_codes = set(config.stock_symbols) | {str(slice_config["benchmark_index"]).upper()}
    actual_codes = {str(record["instrumentCode"]).upper() for record in records}
    if actual_codes != expected_codes:
        raise RuntimeError(f"Universe crawl không khớp; thiếu={sorted(expected_codes - actual_codes)}.")

    # Tạo graph thật từ snapshot và chỉ xuất bản sau khi dữ liệu qua SHACL.
    graph_store = GraphStore(
        project_root / config.paths["schema_ontology"],
        project_root / config.paths["schema_shapes"],
    )
    graph = graph_store.graph
    wfkg = Namespace("https://example.org/wfkg/v1#")
    by_code = {str(record["instrumentCode"]).upper(): record for record in records}
    for symbol in config.stock_symbols:
        stock_path = project_root / config.paths["snapshots"] / "stocks" / f"{symbol}.json"
        if not stock_path.is_file():
            raise ValueError(f"Chưa có Stock snapshot để nối observation: {stock_path}")
        stock = json.loads(stock_path.read_text(encoding="utf-8"))
        stock_node = wfkg[str(stock["stockId"])]
        graph.add((stock_node, RDF.type, wfkg.Stock))
        graph.add((stock_node, wfkg.stockId, Literal(str(stock["stockId"]), datatype=XSD.string)))
        graph.add((stock_node, wfkg.tickerSymbol, Literal(str(stock["tickerSymbol"]), datatype=XSD.string)))
        graph.add((stock_node, wfkg.exchange, Literal(str(stock["exchange"]), datatype=XSD.string)))
        for observation in by_code[symbol.upper()]["observations"]:
            graph.add((stock_node, wfkg.hasMarketObservation, wfkg[str(observation["observationId"])]))

    index_code = str(slice_config["benchmark_index"]).upper()
    index_path = project_root / config.paths["snapshots"] / "market_indexes" / f"{index_code}.json"
    if not index_path.is_file():
        raise ValueError(f"Chưa có MarketIndex snapshot để nối observation: {index_path}")
    index_record = json.loads(index_path.read_text(encoding="utf-8"))
    index_node = wfkg[str(index_record["indexId"])]
    graph.add((index_node, RDF.type, wfkg.MarketIndex))
    graph.add((index_node, wfkg.indexId, Literal(str(index_record["indexId"]), datatype=XSD.string)))
    graph.add((index_node, wfkg.indexCode, Literal(str(index_record["indexCode"]), datatype=XSD.string)))
    graph.add((index_node, wfkg.indexName, Literal(str(index_record["indexName"]), datatype=XSD.string)))
    for observation in by_code[index_code]["observations"]:
        graph.add((index_node, wfkg.hasIndexObservation, wfkg[str(observation["observationId"])]))

    for record in records:
        is_index = record["instrumentType"] == "index"
        observation_class = wfkg.MarketIndexObservation if is_index else wfkg.MarketObservation
        for observation in record["observations"]:
            node = wfkg[str(observation["observationId"])]
            graph.add((node, RDF.type, observation_class))
            graph.add((node, wfkg.observationId, Literal(str(observation["observationId"]), datatype=XSD.string)))
            graph.add((node, wfkg.tradingDate, Literal(str(observation["tradingDate"]), datatype=XSD.date)))
            graph.add((node, wfkg.adjustedClose, Literal(Decimal(str(observation["adjustedClose"])), datatype=XSD.decimal)))
            graph.add((node, wfkg.returnValue, Literal(Decimal(str(observation["returnValue"])), datatype=XSD.decimal)))
            graph.add((node, wfkg.availableAt, Literal(str(observation["availableAt"]), datatype=XSD.dateTime)))
            graph.add((node, wfkg.sourceReference, URIRef(str(observation["sourceReference"]))))
            if not is_index:
                graph.add((node, wfkg.volume, Literal(Decimal(str(observation["volume"])), datatype=XSD.decimal)))
    conforms, validation_report = graph_store.validate()
    if not conforms:
        raise RuntimeError(f"Market data không qua SHACL; chưa ghi snapshot mới.\n{validation_report}")

    if daily:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_dir = project_root / config.paths["raw_daily"] / "market_observations" / run_id
    else:
        raw_dir = project_root / config.paths["raw_initial_data"] / "market_observations_vnstock_kbs"
    snapshot_dir = project_root / config.paths["snapshots"] / "market_observations"
    archive_dir = project_root / config.paths["snapshots"] / "market_observations_vietstock"
    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    manifest_records: dict[str, object] = {}

    for record in records:
        symbol = str(record["instrumentCode"])
        snapshot_path = snapshot_dir / f"{symbol}.json"
        # Giữ nguyên snapshot Vietstock ban đầu để có thể đối chiếu lại nguồn và giá chưa điều chỉnh.
        if snapshot_path.is_file() and not (archive_dir / snapshot_path.name).exists():
            shutil.copy2(snapshot_path, archive_dir / snapshot_path.name)

        raw_path = raw_dir / f"{symbol}.json"
        raw_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        snapshot = {
            key: value for key, value in record.items() if key not in {"rawRows", "sourceMetadata"}
        }
        snapshot["dataQualityFlag"] = "ADJUSTED_CLOSE_READY"
        snapshot["priceSemantics"] = (
            "Adjusted close in VND; Vnstock close is adjusted for corporate actions."
            if record["instrumentType"] == "equity"
            else "Index close in index points; no corporate-action adjustment is applied."
        )
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        outputs.append(snapshot_path)
        manifest_records[symbol] = {
            "count": record["count"],
            "firstTradingDate": record["firstTradingDate"],
            "lastTradingDate": record["lastTradingDate"],
            "rawFile": str(raw_path.relative_to(project_root)),
            "snapshotFile": str(snapshot_path.relative_to(project_root)),
        }
        print(
            f"Đã crawl {symbol}: {record['count']} phiên "
            f"({record['firstTradingDate']} → {record['lastTradingDate']})",
            flush=True,
        )

    manifest = {
        "source": "Vnstock",
        "sourceCode": source,
        "providerName": records[0]["providerName"],
        "dateFrom": str(date_from),
        "dateTo": str(date_to),
        "requestedStartWithBuffer": records[0]["requestStartWithBuffer"],
        "documentationUrl": records[0]["documentationUrl"],
        "priceSemantics": "Equity close is adjusted for corporate actions; returned in thousand VND.",
        "returnFormula": "adjustedClose_t / adjustedClose_previous_trading_session - 1",
        "records": manifest_records,
    }
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    graph_path = project_root / config.paths["gold"] / "market_observations.ttl"
    graph_store.save(graph_path)
    print(f"SHACL hợp lệ; đã xuất graph thị trường: {graph_path}", flush=True)
    return outputs


def run_industry_classification(config: ProjectConfig) -> list[Path]:
    """Crawl phân cấp ngành của 13 mã, lưu hai entity và nối Company với Industry."""
    symbols = config.stock_symbols
    profile_pages = config.values.get("stock_profile_pages", {})
    results: list[tuple[str, list[str], dict[str, str]]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for symbol in symbols:
                url = profile_pages.get(symbol, {}).get("vietstock")
                if not url:
                    raise ValueError(f"Chưa khai báo URL Vietstock cho {symbol}.")
                levels, reference = collect_classification(browser, symbol, url)
                results.append((symbol, levels, reference))
                print(f"Đã đọc ngành {symbol}: {' > '.join(levels)}", flush=True)
        finally:
            browser.close()

    paths = {tuple(levels[-2:]) for _, levels, _ in results}
    if len(paths) != 1:
        raise RuntimeError(f"Các mã có phân loại ngành không đồng nhất; cần xử lý riêng: {sorted(paths)}")

    project_root = config.path.parent.parent
    output_dir = project_root / config.paths["snapshots"] / "industries"
    output_dir.mkdir(parents=True, exist_ok=True)
    group_name, industry_name = next(iter(paths))
    group_id = "INDUSTRY_GROUP:VIETSTOCK:TCTD"
    industry_id = "INDUSTRY:VIETSTOCK:NGAN-HANG"
    references = [reference for _, _, reference in results]

    group_record = {
        "industryGroupId": group_id,
        "industryGroupName": group_name,
        "taxonomyName": "VietstockFinance",
        "taxonomyPath": " > ".join(results[0][1]),
        "sourceReferences": references,
    }
    industry_record = {
        "industryId": industry_id,
        "industryName": industry_name,
        "belongsToGroup": group_id,
        "taxonomyName": "VietstockFinance",
        "taxonomyPath": " > ".join(results[0][1]),
        "sourceReferences": references,
    }
    output_paths = [output_dir / "industry_group_tctd.json", output_dir / "industry_ngan_hang.json"]
    for path, record in zip(output_paths, (group_record, industry_record), strict=True):
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Ghi liên kết Company -> Industry cùng provenance ngành đã crawl.
    company_dir = project_root / config.paths["snapshots"] / "companies"
    for symbol, _, reference in results:
        company_path = company_dir / f"{symbol}.json"
        company = json.loads(company_path.read_text(encoding="utf-8"))
        company["belongsToIndustry"] = industry_id
        company["industrySourceReference"] = reference
        company_path.write_text(json.dumps(company, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_paths


def run_vn30_memberships(config: ProjectConfig) -> list[Path]:
    """Crawl danh mục VN30 chính thức và lưu membership cho các mã vertical slice."""
    project_root = config.path.parent.parent
    snapshots_dir = project_root / config.paths["snapshots"]
    stock_ids: dict[str, str] = {}
    for symbol in config.stock_symbols:
        stock_path = snapshots_dir / "stocks" / f"{symbol}.json"
        if not stock_path.is_file():
            raise ValueError(f"Chưa có Stock snapshot đã crawl cho {symbol}: {stock_path}")
        stock_ids[symbol] = json.loads(stock_path.read_text(encoding="utf-8"))["stockId"]

    membership_config = config.values.get("vn30_membership", {})
    source_url = membership_config.get("source_url")
    effective_from = membership_config.get("effective_from")
    if not source_url or not effective_from:
        raise ValueError("Cần khai báo source_url và effective_from trong vn30_membership.")

    index_id = "INDEX:VN30"
    records = collect_vn30_memberships(source_url, effective_from, stock_ids, index_id)
    index_record = from_official_constituent_list(
        "VN30",
        "VN30",
        source_url,
        records[0].availableAt,
    )
    index_dir = snapshots_dir / "market_indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "VN30.json").write_text(
        json.dumps(index_record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    output_dir = snapshots_dir / "index_memberships"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for record in records:
        ticker = record.membershipId.split(":")[2]
        output_path = output_dir / f"{ticker}.json"
        output_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs.append(output_path)
    return outputs


def run_corporate_leaders(config: ProjectConfig) -> dict[str, int]:
    """Crawl leaders/positions hiện tại cho từng bank và lưu kết quả có provenance."""
    profile_pages = config.values.get("stock_profile_pages", {})
    project_root = config.path.parent.parent
    snapshots_dir = project_root / config.paths["snapshots"]
    leaders_dir = snapshots_dir / "corporate_leaders"
    positions_dir = snapshots_dir / "leadership_positions"
    unresolved_dir = snapshots_dir / "leadership_unresolved"
    for directory in (leaders_dir, positions_dir, unresolved_dir):
        directory.mkdir(parents=True, exist_ok=True)

    all_leaders: dict[str, dict[str, object]] = {}
    total_unresolved = 0
    total_unresolved_profiles = 0
    position_records: dict[str, dict[str, object]] = {}
    unresolved_records: dict[str, dict[str, object]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for symbol in config.stock_symbols:
                url = profile_pages.get(symbol, {}).get("cafef")
                if not url:
                    raise ValueError(f"Chưa khai báo URL CafeF cho {symbol}.")
                collected = collect_company_leaders(browser, symbol, url)
                for leader in collected["leaders"]:
                    person_id = str(leader["personId"])
                    existing = all_leaders.setdefault(person_id, leader)
                    existing.setdefault("hasLeadershipPosition", [])
                for position in collected["positions"]:
                    person_id = str(position["positionHolder"])
                    all_leaders[person_id]["hasLeadershipPosition"].append(position["positionId"])
                    filename = str(position["positionId"]).replace(":", "_") + ".json"
                    position_records[filename] = position
                missing_dates = collected["unresolvedPositions"]
                unresolved_profiles = collected["unresolvedProfiles"]
                total_unresolved += len(missing_dates)
                total_unresolved_profiles += len(unresolved_profiles)
                if missing_dates or unresolved_profiles:
                    unresolved_records[f"{symbol}.json"] = {
                        "missingAppointmentDates": missing_dates,
                        "unresolvedProfiles": unresolved_profiles,
                    }
                print(
                    f"{symbol}: {len(collected['leaders'])} leaders, "
                    f"{len(collected['positions'])} dated positions, "
                    f"{len(missing_dates)} missing appointment dates, "
                    f"{len(unresolved_profiles)} unresolved profiles",
                    flush=True,
                )
        finally:
            browser.close()

    # Chỉ cập nhật sau khi crawl đủ các mã; xóa file JSON cũ không còn trong lượt chạy mới.
    snapshots_to_write = {
        leaders_dir: {f"{person_id}.json": leader for person_id, leader in all_leaders.items()},
        positions_dir: position_records,
        unresolved_dir: unresolved_records,
    }
    for directory, records_by_name in snapshots_to_write.items():
        for filename, record in records_by_name.items():
            (directory / filename).write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        for old_path in directory.glob("*.json"):
            if old_path.name not in records_by_name:
                old_path.unlink()
    return {
        "leaders": len(all_leaders),
        "positions": len(position_records),
        "unresolved_positions": total_unresolved,
        "unresolved_profiles": total_unresolved_profiles,
    }


def run(config: ProjectConfig) -> None:
    """Run initial data collection for the configured stock universe."""
    raise NotImplementedError(
        "Initial data collectors are scaffolds. Implement source adapters before running this job."
    )


def run_news_sources(config: ProjectConfig) -> list[Path]:
    """Crawl trang chủ của 7 báo và lưu từng NewsSource snapshot."""
    project_root = config.path.parent.parent
    output_dir = project_root / config.paths["snapshots"] / "news_sources"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for record in collect_news_sources():
        source_id = str(record["sourceId"]).split(":", maxsplit=1)[1].lower()
        path = output_dir / f"{source_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
        print(f"Đã crawl nguồn {record['sourceName']}: {record['homepageUrl']}", flush=True)
    return outputs


def run_government_organizations(config: ProjectConfig) -> list[Path]:
    """Lưu danh sách GovernmentOrganization cùng trang cổng chính thức để kiểm tra."""
    project_root = config.path.parent.parent
    output_dir = project_root / config.paths["snapshots"] / "government_organizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for record in collect_government_organizations():
        org_id = str(record["organizationId"]).split(":", maxsplit=1)[1].lower()
        path = output_dir / f"{org_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
    return outputs


def run_subsidiaries(config: ProjectConfig) -> list[Path]:
    """Cập nhật trang pháp nhân mà vẫn giữ bằng chứng ownership đã xác minh."""
    project_root = config.path.parent.parent
    snapshots_dir = project_root / config.paths["snapshots"]
    candidates_dir = snapshots_dir / "subsidiary_relation_candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    preserved_fields = (
        "ownershipEvidence", "recentRelationEvidence", "historicalEvidence", "observedAsOf", "effectiveStartDate"
    )

    for relation in collect_subsidiaries():
        parent = str(relation["parentTicker"])
        child = str(relation["subsidiaryTicker"])
        out = candidates_dir / f"{parent}_{child}.json"
        previous = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        candidate_snapshot = {
            "candidateId": relation["relationId"],
            "candidateParentCompany": f"COMPANY:{parent}",
            "candidateSubsidiaryTicker": child,
            "candidateSubsidiaryName": previous.get("candidateSubsidiaryName", relation["subsidiaryName"]),
            "availableAt": relation["availableAt"],
            "dataQualityFlag": relation["dataQualityFlag"],
            "companyHomepage": relation["sourceReference"],
            "companyHomepageStatus": relation["officialHomepageStatus"],
            "companyHomepageTitle": relation["officialHomepageTitle"],
            "evidenceNote": previous.get(
                "evidenceNote",
                "Ticker mẹ/con do người dùng cung cấp; trang chủ xác nhận pháp nhân, "
                "còn trạng thái sở hữu phải có nguồn riêng.",
            ),
        }
        # Crawl lại trang chủ không được làm mất nguồn sở hữu và ngày quan sát đã ghi nhận.
        for field in preserved_fields:
            if field in previous:
                candidate_snapshot[field] = previous[field]
        if previous.get("dataQualityFlag", "").startswith(("OWNERSHIP_SUPPORTED_", "RELATION_CONFIRMED_")):
            candidate_snapshot["dataQualityFlag"] = previous["dataQualityFlag"]
        out.write_text(json.dumps(candidate_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(out)

        # Chỉ tạo relation khi có ngày nguồn xác nhận; không dùng ngày crawl hoặc suy ra validFrom.
        observed_as_of = candidate_snapshot.get("observedAsOf")
        ownership_evidence = candidate_snapshot.get("ownershipEvidence", {})
        if observed_as_of and ownership_evidence.get("supportsCurrentOrRecentSubsidiaryStatus"):
            relation_id = f"SUBSIDIARY:{parent}:{child}"
            relation_source = candidate_snapshot.get("recentRelationEvidence", {}).get("url") or ownership_evidence.get("url")
            relation_snapshot = {
                "relationId": relation_id,
                "parentCompany": f"COMPANY:{parent}",
                "subsidiaryCompany": f"COMPANY:{child}",
                "observedAsOf": observed_as_of,
                "relationConfidence": "1.0",
                "availableAt": relation["availableAt"],
                "sourceReference": relation_source,
                "dataQualityFlag": "OBSERVED_AS_OF_ONLY",
            }
            relation_dir = snapshots_dir / "subsidiary_relations"
            relation_dir.mkdir(parents=True, exist_ok=True)
            relation_path = relation_dir / f"{parent}_{child}.json"
            relation_path.write_text(
                json.dumps(relation_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            parent_path = companies_dir / f"{parent}.json"
            if parent_path.is_file():
                parent_company = json.loads(parent_path.read_text(encoding="utf-8"))
                links = parent_company.setdefault("hasSubsidiaryRelation", [])
                if relation_id not in links:
                    links.append(relation_id)
                parent_path.write_text(
                    json.dumps(parent_company, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
    return outputs
