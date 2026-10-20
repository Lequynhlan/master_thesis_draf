"""Thu thập danh bạ các trang tin do người dùng đã chọn."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class _TitleReader(HTMLParser):
    """Đọc tiêu đề trang từ HTML mà không lưu nội dung trang thô."""

    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data.strip())


SOURCES = (
    ("CAFEF", "https://cafef.vn/", "CafeF"),
    ("VIETSTOCK", "https://vietstock.vn/", "Vietstock"),
    ("TINNHANHCHUNGKHOAN", "https://www.tinnhanhchungkhoan.vn/", "Đầu tư Chứng khoán"),
    ("NGUOIQUANSAT", "https://nguoiquansat.vn/", "Người Quan Sát"),
    ("VNECONOMY", "https://vneconomy.vn/", "VnEconomy"),
    ("VNEXPRESS", "https://vnexpress.net/", "VnExpress"),
    ("BAODAUTU", "https://baodautu.vn/", "Báo Đầu tư"),
)


def collect() -> list[dict[str, object]]:
    """Mở từng trang nguồn, lưu tên xác minh được và điểm trung tính tạm thời."""
    records: list[dict[str, object]] = []
    for source_id, url, fallback_name in SOURCES:
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        })
        with urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"Nguồn {url} trả HTTP {response.status}")
            html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            final_url = response.geturl()
        reader = _TitleReader()
        reader.feed(html)
        title = " ".join(" ".join(reader.parts).split())
        # Trang có thể chặn bot hoặc không có title; tên do người dùng phê duyệt vẫn được giữ.
        name = title.split("|")[0].strip(" -–") if title else fallback_name
        records.append({
            "sourceId": f"NEWS_SOURCE:{source_id}",
            "sourceName": name or fallback_name,
            "sourceType": "NEWS_MEDIA",
            "reliabilityScore": "0.5",
            "reliabilityScoreStatus": "PROVISIONAL_NEUTRAL_UNRATED",
            "homepageUrl": final_url,
            "retrievedAt": datetime.now(timezone.utc).isoformat(),
            "verification": "HTTP 200; publisher name read from page title or user-approved fallback",
        })
    return records
