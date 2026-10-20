"""Điều phối job crawl tin hằng ngày từ danh bạ nguồn đã nạp."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from wfkg.config import ProjectConfig
from wfkg.daily_ingest.sources.news import collect
from wfkg.initial_data_load.job import run_market_observations


def run(config: ProjectConfig) -> dict[str, object]:
    """Cập nhật giá đến ngày hiện tại và crawl tin; lỗi một nhánh không chặn nhánh kia."""
    result: dict[str, object] = {"marketSnapshots": [], "newsBatch": None, "articleCount": 0, "errors": []}
    errors = result["errors"]
    assert isinstance(errors, list)

    try:
        # Dùng lại collector đã chuẩn hóa adjusted close và kiểm tra SHACL.
        result["marketSnapshots"] = run_market_observations(config, daily=True)
    # Vnstock raises its NetworkError from a library-specific Exception type
    # that does not inherit OSError/RuntimeError. Isolate the market adapter
    # boundary so one upstream failure cannot prevent the independent news run.
    except Exception as exc:
        errors.append(f"MarketObservation: {exc}")

    try:
        raw_path, article_count, source_status = run_news(config)
        result["newsBatch"] = raw_path
        result["articleCount"] = article_count
        result["sourceStatus"] = source_status
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        errors.append(f"NewsArticle: {exc}")

    return result


def run_news(config: ProjectConfig) -> tuple[Path, int, list[dict[str, object]]]:
    """Crawl tối đa 100 bài mới, lưu bản crawl thô và snapshot từng bài."""
    project_root = config.path.parent.parent
    source_dir = project_root / config.paths["snapshots"] / "news_sources"
    source_records: list[dict[str, str]] = []
    for path in sorted(source_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("sourceId") and record.get("sourceName") and record.get("homepageUrl"):
            source_records.append({
                "sourceId": str(record["sourceId"]),
                "sourceName": str(record["sourceName"]),
                "homepageUrl": str(record["homepageUrl"]),
            })
    if not source_records:
        raise ValueError("Chưa có danh bạ nguồn. Hãy chạy `wfkg crawl-news-sources` trước.")

    article_limit = int(config.values.get("vertical_slice", {}).get("article_limit", 100))
    if article_limit < 1:
        raise ValueError("vertical_slice.article_limit phải lớn hơn 0.")
    snapshot_dir = project_root / config.paths["snapshots"] / "news_articles"
    # Đọc các URL đã lưu để hai lượt trong ngày không ghi lại cùng một bài.
    known_urls: set[str] = set()
    for path in snapshot_dir.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("url"):
            known_urls.add(str(record["url"]))
    articles, source_status = collect(source_records, article_limit, known_urls)
    if not articles and not any(bool(item.get("homeFetched")) for item in source_status):
        details = "; ".join(
            f"{item['sourceId']}: {item['error'] or 'không truy cập được trang nguồn'}"
            for item in source_status
        )
        raise RuntimeError(f"Không truy cập được trang nguồn nào. {details}")

    run_time = datetime.now(timezone.utc)
    run_id = run_time.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = project_root / config.paths["raw_daily"] / "news"
    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    # Bản batch ghi trạng thái từng nguồn để biết nguồn nào lỗi hoặc không có RSS.
    raw_path = raw_dir / f"{run_id}.json"
    raw_path.write_text(json.dumps({
        "runId": run_id,
        "collectedAt": run_time.isoformat(),
        "articleLimit": article_limit,
        "sourceStatus": source_status,
        "articles": articles,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for article in articles:
        article_id = str(article["articleId"]).split(":", 1)[-1]
        (snapshot_dir / f"{article_id}.json").write_text(
            json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return raw_path, len(articles), source_status
