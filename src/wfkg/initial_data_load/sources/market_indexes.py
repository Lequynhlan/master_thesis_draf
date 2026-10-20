"""Thu thập hồ sơ định danh chỉ số thị trường từ trang công khai CafeF."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Browser


@dataclass(frozen=True)
class MarketIndexRecord:
    """Thông tin định danh tối thiểu cần cho MarketIndexShape."""

    indexId: str
    indexCode: str
    indexName: str
    sourceReferences: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_one(browser: Browser, index_code: str, url: str) -> MarketIndexRecord:
    """Xác nhận mã chỉ số có hiển thị trên trang CafeF rồi lưu provenance."""
    code = index_code.strip().upper()
    page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or response.status != 200:
            status = response.status if response else "không nhận được phản hồi HTTP"
            raise RuntimeError(f"CafeF trả về trạng thái {status}: {url}")

        # Trang lịch sử giao dịch hiển thị mã trong bộ lọc "Mã CK/Index".
        page.get_by_text(code, exact=True).first.wait_for(state="visible", timeout=10_000)
        retrieved_at = datetime.now(timezone.utc).isoformat()
    finally:
        page.close()

    return MarketIndexRecord(
        indexId=f"INDEX:{code}",
        indexCode=code,
        indexName=code,
        sourceReferences=[
            {
                "sourceName": "CafeF",
                "url": url,
                "retrievedAt": retrieved_at,
                "verifiedFields": "indexCode",
            }
        ],
    )


def from_official_constituent_list(
    index_code: str,
    index_name: str,
    source_url: str,
    retrieved_at: str,
) -> MarketIndexRecord:
    """Tạo metadata chỉ số từ danh sách thành phần do đơn vị quản lý công bố."""
    code = index_code.strip().upper()
    return MarketIndexRecord(
        indexId=f"INDEX:{code}",
        indexCode=code,
        indexName=index_name.strip(),
        sourceReferences=[
            {
                "sourceName": "HOSE",
                "url": source_url,
                "retrievedAt": retrieved_at,
                "verifiedFields": "indexCode,indexName",
            }
        ],
    )
