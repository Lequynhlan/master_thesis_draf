"""Thu thập tin mới từ nhiều nguồn qua RSS và trang chủ công khai."""

from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


USER_AGENT = "WFKGVerticalSlice/0.1 (academic research; contact: project owner)"
TIMEOUT_SECONDS = 12
RSS_DISCOVERY_PAGES = {
    "cafef.vn": ("https://cafef.vn/index.rss",),
    "vietstock.vn": ("https://vietstock.vn/rss",),
    "www.tinnhanhchungkhoan.vn": ("https://www.tinnhanhchungkhoan.vn/rss",),
    "tinnhanhchungkhoan.vn": ("https://tinnhanhchungkhoan.vn/rss",),
    "nguoiquansat.vn": ("https://nguoiquansat.vn/rss/trang-chu",),
    "vneconomy.vn": ("https://vneconomy.vn/tin-moi.rss", "https://vneconomy.vn/tai-chinh.rss"),
    "vnexpress.net": ("https://vnexpress.net/rss",),
    "baodautu.vn": ("https://baodautu.vn/trang-chu.rss", "https://baodautu.vn/ngan-hang--bao-hiem.rss"),
}


@dataclass
class _Link:
    url: str
    title: str = ""
    published_at: str = ""
    summary: str = ""


class _PageLinks(HTMLParser):
    """Lấy link bài và các RSS được công bố trên trang HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.articles: list[_Link] = []
        self.feeds: list[str] = []
        self._current: _Link | None = None
        self._title_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and "rss" in (values.get("type") or "").lower():
            href = values.get("href")
            if href:
                self.feeds.append(href)
        if tag == "a" and values.get("href"):
            self._current = _Link(values["href"] or "")
            self.articles.append(self._current)
            if ".rss" in (values["href"] or "").lower() or "/rss/" in (values["href"] or "").lower():
                self.feeds.append(values["href"] or "")
            self._title_depth = 0
        elif self._current and tag in {"h1", "h2", "h3"}:
            self._title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._current = None
            self._title_depth = 0
        elif self._current and tag in {"h1", "h2", "h3"}:
            self._title_depth = max(0, self._title_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._current and data.strip():
            self._current.title = " ".join((self._current.title + " " + data.strip()).split())


class _ArticleMetadata(HTMLParser):
    """Đọc metadata phổ biến (Open Graph, JSON-LD-style meta, canonical)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}
        self._jsonld = False
        self._jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta":
            key = values.get("property") or values.get("name") or values.get("itemprop") or ""
            content = values.get("content")
            if key and content:
                self.values[key.lower()] = content.strip()
        elif tag == "link" and "canonical" in (values.get("rel") or "").lower():
            if values.get("href"):
                self.values["canonical"] = values["href"] or ""
        elif tag == "time" and values.get("datetime"):
            self.values.setdefault("date", values["datetime"] or "")
        elif tag == "script" and "ld+json" in (values.get("type") or "").lower():
            self._jsonld = True
            self._jsonld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._jsonld:
            self._jsonld = False
            try:
                decoded = json.loads("".join(self._jsonld_parts))
            except (json.JSONDecodeError, TypeError):
                return
            self._read_jsonld(decoded)

    def handle_data(self, data: str) -> None:
        if self._jsonld:
            self._jsonld_parts.append(data)

    def _read_jsonld(self, value: object) -> None:
        """Đọc ngày đăng và tiêu đề trong JSON-LD mà nhiều báo nhúng vào trang."""
        if isinstance(value, list):
            for item in value:
                self._read_jsonld(item)
        elif isinstance(value, dict):
            for key, target in (("headline", "jsonld:title"), ("datePublished", "jsonld:date"), ("description", "jsonld:summary")):
                item = value.get(key)
                if isinstance(item, str):
                    self.values.setdefault(target, item.strip())
            for key in ("@graph", "mainEntity", "article"):
                if key in value:
                    self._read_jsonld(value[key])


def _get(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.7"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read(), response.headers.get_content_charset() or "utf-8", response.geturl()


def _clean_url(url: str) -> str:
    """Chuẩn hóa URL để cùng một bài không bị lưu lặp do tracking parameters."""
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "ref"}]
    path = re.sub(r"/{2,}", "/", parts.path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _parse_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _read_feed(xml_bytes: bytes, base_url: str) -> list[_Link]:
    # Bỏ BOM/khoảng trắng đầu file vì một số RSS đặt chúng trước khai báo XML.
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf \t\r\n"))
    results: list[_Link] = []
    for item in root.findall(".//item"):
        fields = {element.tag.rsplit("}", 1)[-1].lower(): element for element in item}
        def value(*names: str) -> str:
            element = next((fields[name.lower()] for name in names if name.lower() in fields), None)
            return " ".join("".join(element.itertext()).split()) if element is not None else ""
        url = value("link")
        if url:
            results.append(_Link(urljoin(base_url, url), value("title"), _parse_date(value("pubDate", "published", "updated", "date")), value("description", "summary")))
    # Atom dùng namespace nên đọc theo local-name để không phụ thuộc namespace cụ thể.
    if not results:
        for item in (element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "entry"):
            fields = {child.tag.rsplit("}", 1)[-1]: child for child in item}
            link = fields.get("link")
            href = link.attrib.get("href", "") if link is not None else ""
            title = "".join(fields["title"].itertext()).strip() if fields.get("title") is not None else ""
            date_node = fields.get("published") or fields.get("updated")
            date = _parse_date("".join(date_node.itertext())) if date_node is not None else ""
            summary_node = fields.get("summary")
            summary = "".join(summary_node.itertext()).strip() if summary_node is not None else ""
            if href:
                results.append(_Link(urljoin(base_url, href), title, date, summary))
    return results


def _discover_feed_urls(homepage: str, html: str) -> tuple[list[str], list[_Link]]:
    parser = _PageLinks()
    parser.feed(html)
    base = urlsplit(homepage)
    # Nếu trang không khai báo RSS trực tiếp, thử một số đường dẫn RSS phổ biến.
    feeds = [urljoin(homepage, link) for link in parser.feeds]
    feeds.extend(RSS_DISCOVERY_PAGES.get(base.netloc.lower().removeprefix("www."), ()))
    return list(dict.fromkeys(feeds)), parser.articles


def _fetch_article(link: _Link, source_host: str) -> dict[str, str] | None:
    url = _clean_url(link.url)
    if urlsplit(url).netloc != source_host:
        return None
    try:
        raw, charset, final_url = _get(url)
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError):
        return None
    metadata = _ArticleMetadata()
    metadata.feed(raw.decode(charset, errors="replace"))
    canonical = _clean_url(urljoin(final_url, metadata.values.get("canonical", final_url)))
    if urlsplit(canonical).netloc != source_host:
        canonical = _clean_url(final_url)
    title = metadata.values.get("og:title") or metadata.values.get("twitter:title") or metadata.values.get("title") or metadata.values.get("jsonld:title") or link.title
    date_candidates = (
        metadata.values.get("article:published_time", ""),
        metadata.values.get("datepublished", ""),
        metadata.values.get("date", ""),
        metadata.values.get("jsonld:date", ""),
        link.published_at,
    )
    published = next((parsed for value in date_candidates if (parsed := _parse_date(value))), "")
    summary = metadata.values.get("og:description") or metadata.values.get("description") or metadata.values.get("jsonld:summary") or link.summary
    if not title or not published:
        return None
    return {"url": canonical, "title": " ".join(title.split()), "publishedAt": published, "summary": " ".join(summary.split())}


def collect(
    sources: list[dict[str, str]], article_limit: int, known_urls: set[str] | None = None
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Duyệt nguồn, tự tìm RSS/link bài, loại URL trùng và giới hạn tổng bài."""
    discovered: list[dict[str, object]] = []
    source_status: list[dict[str, object]] = []
    now = datetime.now(timezone.utc).isoformat()
    for source in sources:
        source_id = source["sourceId"]
        homepage = source["homepageUrl"]
        host = urlsplit(homepage).netloc.lower()
        status: dict[str, object] = {
            "sourceId": source_id,
            "homepageUrl": homepage,
            "homeFetched": False,
            "feedUrls": [],
            "discovered": 0,
            "error": None,
        }
        links: list[_Link] = []
        try:
            home_bytes, charset, final_home = _get(homepage)
            status["homeFetched"] = True
            # Một số website chuyển www/non-www; dùng host sau redirect làm host chuẩn.
            host = urlsplit(final_home).netloc.lower()
            feeds, home_links = _discover_feed_urls(final_home, home_bytes.decode(charset, errors="replace"))
            seen_feeds: set[str] = set()
            feed_pages_to_scan = list(dict.fromkeys(feeds))
            scanned_pages: set[str] = set()
            for feed_url in feeds:
                if feed_url in seen_feeds:
                    continue
                seen_feeds.add(feed_url)
                try:
                    feed_bytes, _, final_feed = _get(feed_url)
                    scanned_pages.add(feed_url)
                    try:
                        feed_entries = _read_feed(feed_bytes, final_feed)
                    except ET.ParseError:
                        feed_entries = []
                    if feed_entries:
                        status["feedUrls"].append(final_feed)
                        links.extend(feed_entries)
                    else:
                        # Một số báo có trang danh mục RSS thay vì một feed; tự lần theo link RSS con.
                        page = _PageLinks()
                        page.feed(feed_bytes.decode("utf-8", errors="replace"))
                        feed_pages_to_scan.extend(urljoin(final_feed, link) for link in page.feeds)
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ET.ParseError):
                    continue
                time.sleep(0.2)
            for feed_url in list(dict.fromkeys(feed_pages_to_scan))[:8]:
                if feed_url in scanned_pages or len(links) >= article_limit * 2:
                    continue
                try:
                    feed_bytes, _, final_feed = _get(feed_url)
                    feed_entries = _read_feed(feed_bytes, final_feed)
                    if feed_entries:
                        links.extend(feed_entries)
                        status["feedUrls"].append(final_feed)
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ET.ParseError):
                    continue
                time.sleep(0.2)
            if not links:
                # Không có RSS thì đi theo link bài tìm thấy trên trang nguồn.
                links = home_links
            unique: dict[str, _Link] = {}
            for link in links:
                cleaned = _clean_url(urljoin(final_home, link.url))
                parts = urlsplit(cleaned)
                if parts.netloc.lower() == host and len(parts.path.strip("/").split("/")) >= 1 and len(parts.path) > 12:
                    unique.setdefault(cleaned, link)
            article_candidates = list(unique.values())[: max(8, (article_limit + len(sources) - 1) // len(sources) * 2)]
            # Tải song song có giới hạn để crawl nhiều bài mà không chờ tuần tự từng trang.
            with ThreadPoolExecutor(max_workers=4) as pool:
                fetched = pool.map(lambda link: _fetch_article(link, host), article_candidates)
            for item in fetched:
                if item:
                    item.update({"sourceId": source_id, "sourceName": source["sourceName"], "collectedAt": now})
                    discovered.append(item)
                    status["discovered"] = int(status["discovered"]) + 1
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            status["error"] = str(exc)
        source_status.append(status)

    # URL chuẩn duy nhất giúp hợp nhất bài được đăng lại cùng link.
    by_url: dict[str, dict[str, object]] = {}
    for item in discovered:
        url = str(item["url"])
        if known_urls and url in known_urls:
            continue
        by_url.setdefault(url, item)
    # Chọn luân phiên giữa các nguồn để một báo không chiếm gần hết 100 bài.
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in by_url.values():
        grouped.setdefault(str(item["sourceId"]), []).append(item)
    for items in grouped.values():
        items.sort(key=lambda item: str(item["publishedAt"]), reverse=True)
    selected: list[dict[str, object]] = []
    source_ids = sorted(grouped)
    while len(selected) < article_limit and any(grouped.values()):
        for source_id in source_ids:
            if grouped[source_id] and len(selected) < article_limit:
                selected.append(grouped[source_id].pop(0))
    for item in selected:
        digest = hashlib.sha256(str(item["url"]).encode("utf-8")).hexdigest()[:20]
        item["articleId"] = f"NEWS_ARTICLE:{digest}"
        item["availableAt"] = item["collectedAt"]
    selected_counts = {source_id: sum(1 for item in selected if item["sourceId"] == source_id) for source_id in source_ids}
    for status in source_status:
        status["selected"] = selected_counts.get(str(status["sourceId"]), 0)
    return selected, source_status
