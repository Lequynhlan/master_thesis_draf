"""Thu thập hồ sơ Company/Bank từ trang dữ liệu công khai của CafeF."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Browser


@dataclass(frozen=True)
class CompanyRecord:
    """Thông tin Company tối thiểu cùng liên kết tới Stock đã crawl."""

    companyId: str
    companyType: str
    fullName: str
    shortName: str
    hasStock: str
    sourceReferences: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_company_name(page: Any, ticker: str) -> str:
    """Đọc tên ngân hàng từ tiêu đề hồ sơ CafeF, hỗ trợ hai kiểu giao diện."""
    heading = page.locator("h1").first
    if heading.count() and heading.is_visible():
        name = " ".join(heading.inner_text().split())
        if name:
            return name

    # Một số hồ sơ CafeF không có H1; tiêu đề tab hiện tên công ty kèm mã.
    title = " ".join(page.title().split())
    prefix = f"{ticker}:"
    if title.upper().startswith(prefix.upper()):
        name = title[len(prefix):].strip()
        for suffix in (" (HOSE)", " (HNX)", " (UPCOM)"):
            if name.upper().endswith(suffix):
                name = name[:-len(suffix)].strip()
        if name:
            return name
    raise RuntimeError(f"Không đọc được tên Company/Bank hiển thị trên hồ sơ CafeF của {ticker}.")


def collect_one(
    browser: Browser,
    ticker: str,
    cafef_url: str,
    stock_id: str,
) -> CompanyRecord:
    """Lấy tên ngân hàng từ hồ sơ CafeF và gắn với Stock đã được xác minh."""
    page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
    try:
        response = page.goto(cafef_url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or response.status != 200:
            status = response.status if response else "không nhận được phản hồi HTTP"
            raise RuntimeError(f"CafeF trả về trạng thái {status}: {cafef_url}")

        # CafeF có nhiều mẫu trang; đọc mã từ phần tử hồ sơ hoặc tiêu đề do nguồn cung cấp.
        ticker_node = page.locator(".symbol").first
        if ticker_node.count() and ticker_node.is_visible():
            source_ticker = " ".join(ticker_node.inner_text().split()).upper()
        else:
            source_ticker = page.title().split(":", maxsplit=1)[0].strip().upper()
        if source_ticker != ticker:
            raise RuntimeError(
                f"Mã trên hồ sơ CafeF là '{source_ticker}', không khớp cấu hình {ticker}."
            )

        full_name = _read_company_name(page, ticker)
        retrieved_at = datetime.now(timezone.utc).isoformat()
    finally:
        page.close()

    return CompanyRecord(
        companyId=f"COMPANY:{ticker}",
        companyType="BANK",
        fullName=full_name,
        shortName=ticker,
        hasStock=stock_id,
        sourceReferences=[
            {
                "sourceName": "CafeF",
                "url": cafef_url,
                "retrievedAt": retrieved_at,
                "verifiedFields": "fullName,tickerSymbol",
            }
        ],
    )
