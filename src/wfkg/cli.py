"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from wfkg.config import load_config, validate_vertical_slice
from wfkg.daily_ingest.job import run as run_daily_ingest, run_news as run_daily_news
from wfkg.graph.snapshot_loader import export_snapshots
from wfkg.initial_data_load.job import (
    build_ticker_aliases,
    run_company_profile,
    run_corporate_leaders,
    run_industry_classification,
    run_market_index_profile,
    run_market_observations,
    run_news_sources,
    run_government_organizations,
    run_subsidiaries,
    run_stock_profile,
    run_vn30_memberships,
)
from wfkg.vertical_slice.job import run_vertical_slice
from wfkg.vertical_slice.end_to_end import run_staged_event_stock_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfkg", description="Vietnamese financial KG pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate-config", help="validate slice config and schema paths")
    validate_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    build_kg_parser = subparsers.add_parser(
        "build-kg", help="hợp nhất snapshot đã crawl thành KG Turtle và kiểm tra SHACL"
    )
    build_kg_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    daily_news_parser = subparsers.add_parser(
        "crawl-news-daily", help="tự tìm RSS/link và crawl bài mới từ các nguồn tin đã nạp"
    )
    daily_news_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    daily_parser = subparsers.add_parser(
        "crawl-daily", help="cập nhật giá thị trường và crawl tin từ nhiều nguồn"
    )
    daily_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    stock_parser = subparsers.add_parser("crawl-stock", help="crawl one stock profile from configured sources")
    stock_parser.add_argument("--ticker", required=True, help="ticker to crawl, for example ACB")
    stock_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    company_parser = subparsers.add_parser(
        "crawl-company", help="crawl one bank profile from CafeF and link it to a Stock snapshot"
    )
    company_parser.add_argument("--ticker", required=True, help="ticker to crawl, for example ACB")
    company_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    subparsers.add_parser(
        "build-ticker-aliases", help="derive CompanyAlias snapshots from crawled Company profiles"
    ).add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    index_parser = subparsers.add_parser(
        "crawl-index", help="crawl one configured MarketIndex profile"
    )
    index_parser.add_argument("--index", required=True, help="index code, for example VNINDEX")
    index_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    market_parser = subparsers.add_parser(
        "crawl-market-observations",
        help="crawl adjusted close cho 13 mã ngân hàng và benchmark VNINDEX qua Vnstock",
    )
    market_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    industry_parser = subparsers.add_parser(
        "crawl-industries", help="crawl the configured stocks' visible Vietstock industry taxonomy"
    )
    industry_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    membership_parser = subparsers.add_parser(
        "crawl-vn30-memberships", help="crawl official HOSE VN30 component list for configured stocks"
    )
    membership_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    leader_parser = subparsers.add_parser(
        "crawl-corporate-leaders", help="crawl visible CafeF leader profiles and dated positions"
    )
    leader_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    for command, help_text in (
        ("crawl-news-sources", "crawl danh bạ 7 nguồn báo đã chốt"),
        ("crawl-government-organizations", "lưu 5 cơ quan nhà nước đã chốt"),
        ("crawl-subsidiaries", "lưu 7 quan hệ công ty con cho vertical slice"),
    ):
        subparsers.add_parser(command, help=help_text).add_argument(
            "--config", type=Path, default=Path("config/vertical_slice.yaml")
        )
    replay_parser = subparsers.add_parser(
        "run-vertical-slice", help="replay the checksum-pinned reviewed WFKG PoC snapshot"
    )
    replay_parser.add_argument(
        "--manifest", type=Path,
        default=Path("runs/wfkg_vertical_slice_news_100_release_v1/release_manifest.json"),
    )
    replay_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice_poc_v1.yaml"))
    replay_parser.add_argument("--output", type=Path, required=True)
    e2e_parser = subparsers.add_parser(
        "run-event-stock-slice",
        help="build staged Event-Stock Candidates and T0..T+3 reactions from saved inference",
    )
    e2e_parser.add_argument("--config", type=Path, default=Path("config/vertical_slice.yaml"))
    e2e_parser.add_argument("--event-run-dir", type=Path, default=Path("runs/news_event_vertical_slice_20261019/emd_v2_experiment"))
    e2e_parser.add_argument("--cohort-run-dir", type=Path, default=Path("runs/news_event_vertical_slice_20261019"))
    e2e_parser.add_argument("--market-batch-dir", type=Path, default=Path("runs/wfkg_vertical_slice_news_100_release_v1/snapshot/data/raw/daily/market_observations/20261017T023853Z"))
    e2e_parser.add_argument("--release-graph", type=Path, default=Path("runs/wfkg_vertical_slice_news_100_release_v1/release_kg.ttl"))
    e2e_parser.add_argument(
        "--output", type=Path,
        default=Path("runs") / f"event_stock_vertical_slice_{datetime.now():%Y%m%dT%H%M%S%f}",
    )
    return parser


def main() -> int:
    # PowerShell mặc định có thể dùng encoding không hỗ trợ tiếng Việt; ép stdout UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    if args.command == "run-event-stock-slice":
        try:
            config = load_config(args.config)
            result = run_staged_event_stock_pipeline(
                config, args.output, event_run_dir=args.event_run_dir,
                cohort_run_dir=args.cohort_run_dir, market_batch_dir=args.market_batch_dir,
                release_snapshot_graph=args.release_graph,
            )
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Event-Stock staged run failed: {exc}")
            return 2
        print(f"Staged Event-Stock run: {args.output.resolve()}")
        print(f"Events={result['eventCount']}; Candidates={result['candidateCount']}; CAR[0,3]={result['computedCAR03Count']}; focused SHACL={result['shacl']['focusedCandidateReactionConforms']}")
        return 0
    if args.command == "run-vertical-slice":
        try:
            result = run_vertical_slice(args.manifest, args.output, args.config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Integrated vertical slice failed: {exc}")
            return 2
        print(result["stdout"])
        print(f"Integrated run manifest: {args.output.resolve() / 'integrated_run_manifest.json'}")
        return 0
    if args.command == "validate-config":
        try:
            config = load_config(args.config)
            errors = validate_vertical_slice(config, config.path.parent.parent)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Configuration error: {exc}")
            return 2
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 2
        print(f"Configuration is valid: {config.path}")
        print(f"Scope: 100 articles, {len(config.stock_symbols)} stock tickers")
        return 0
    if args.command == "build-kg":
        try:
            config = load_config(args.config)
            output_path, entity_counts = export_snapshots(config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Không xuất được KG: {exc}")
            return 2
        print(f"KG đã qua SHACL và được lưu tại: {output_path}")
        for entity, count in sorted(entity_counts.items()):
            print(f"- {entity}: {count}")
        print(f"Manifest: {output_path.with_name('knowledge_graph_manifest.json')}")
        return 0
    if args.command == "crawl-news-daily":
        try:
            config = load_config(args.config)
            raw_path, article_count, source_status = run_daily_news(config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Không chạy được daily news crawl: {exc}")
            return 2
        print(f"Đã lưu {article_count} bài báo vào {raw_path}")
        for source in source_status:
            feed_count = len(source["feedUrls"])
            print(
                f"- {source['sourceId']}: tìm thấy {source['discovered']}, "
                f"chọn {source['selected']}, {feed_count} RSS, "
                f"lỗi={source['error'] or 'không'}"
            )
        return 0
    if args.command == "crawl-daily":
        try:
            config = load_config(args.config)
            result = run_daily_ingest(config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Không chạy được daily ingest: {exc}")
            return 2
        market_paths = result["marketSnapshots"]
        print(f"Đã cập nhật {len(market_paths)} snapshot giá và graph market qua SHACL.")
        if result["newsBatch"]:
            print(f"Đã crawl {result['articleCount']} bài; batch: {result['newsBatch']}")
            for source in result.get("sourceStatus", []):
                print(
                    f"- {source['sourceId']}: tìm thấy {source['discovered']}, "
                    f"chọn {source['selected']}, lỗi={source['error'] or 'không'}"
                )
        for error in result["errors"]:
            print(f"LỖI: {error}")
        return 2 if result["errors"] else 0
    if args.command == "crawl-stock":
        try:
            config = load_config(args.config)
            output_path = run_stock_profile(config, args.ticker)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được {args.ticker.upper()}: {exc}")
            return 2
        print(f"Đã lưu Stock snapshot: {output_path}")
        return 0
    if args.command == "crawl-company":
        try:
            config = load_config(args.config)
            output_path = run_company_profile(config, args.ticker)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được Company/Bank {args.ticker.upper()}: {exc}")
            return 2
        print(f"Đã lưu Company/Bank snapshot: {output_path}")
        return 0
    if args.command == "build-ticker-aliases":
        try:
            config = load_config(args.config)
            outputs = build_ticker_aliases(config)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Không tạo được CompanyAlias: {exc}")
            return 2
        print(f"Đã lưu {len(outputs)} CompanyAlias snapshot tại {outputs[0].parent}")
        return 0
    if args.command == "crawl-index":
        try:
            config = load_config(args.config)
            output_path = run_market_index_profile(config, args.index)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được MarketIndex {args.index.upper()}: {exc}")
            return 2
        print(f"Đã lưu MarketIndex snapshot: {output_path}")
        return 0
    if args.command == "crawl-market-observations":
        try:
            config = load_config(args.config)
            outputs = run_market_observations(config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Không crawl được MarketObservation: {exc}")
            return 2
        print(f"Đã lưu {len(outputs)} snapshot thị trường tại {outputs[0].parent}")
        return 0
    if args.command == "crawl-industries":
        try:
            config = load_config(args.config)
            outputs = run_industry_classification(config)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được Industry: {exc}")
            return 2
        print(f"Đã lưu IndustryGroup/Industry snapshot: {', '.join(str(path) for path in outputs)}")
        return 0
    if args.command == "crawl-vn30-memberships":
        try:
            config = load_config(args.config)
            outputs = run_vn30_memberships(config)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được IndexMembership: {exc}")
            return 2
        print(f"Đã lưu {len(outputs)} IndexMembership snapshot tại {outputs[0].parent}")
        return 0
    if args.command == "crawl-corporate-leaders":
        try:
            config = load_config(args.config)
            counts = run_corporate_leaders(config)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"Không crawl được CorporateLeader/LeadershipPosition: {exc}")
            return 2
        print(
            "Đã lưu CorporateLeader/LeadershipPosition: "
            f"{counts['leaders']} leaders, {counts['positions']} positions, "
            f"{counts['unresolved_positions']} thiếu ngày bổ nhiệm, "
            f"{counts['unresolved_profiles']} hồ sơ chưa xác minh được"
        )
        return 0
    if args.command in {"crawl-news-sources", "crawl-government-organizations", "crawl-subsidiaries"}:
        try:
            config = load_config(args.config)
            if args.command == "crawl-news-sources":
                outputs = run_news_sources(config)
            elif args.command == "crawl-government-organizations":
                outputs = run_government_organizations(config)
            else:
                outputs = run_subsidiaries(config)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Không thu thập được dữ liệu entity: {exc}")
            return 2
        print(f"Đã lưu {len(outputs)} snapshot tại {outputs[0].parent}")
        return 0
    return 2
