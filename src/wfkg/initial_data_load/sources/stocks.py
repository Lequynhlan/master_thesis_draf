"""Thu thập thông tin định danh cổ phiếu từ trang hồ sơ công khai."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Browser, Page, TimeoutError as PlaywrightTimeoutError


@dataclass(frozen=True)
class StockRecord:
    """Các trường tối thiểu khớp với StockShape trong SHACL."""

    stockId: str
    tickerSymbol: str
    exchange: str
    sourceReferences: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _open_public_page(browser: Browser, url: str) -> tuple[Page, str]:
    """Mở trang trong context mới, không dùng cookie hay hồ sơ Edge của người dùng."""
    page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status != 200:
        page.close()
        status = response.status if response else "không nhận được phản hồi HTTP"
        raise RuntimeError(f"Trang nguồn trả về trạng thái {status}: {url}")
    return page, datetime.now(timezone.utc).isoformat()


def _read_visible_text(page: Page, selector: str, label: str) -> str:
    """Đọc một trường đang hiển thị; báo rõ nếu website đổi cấu trúc hoặc chặn dữ liệu."""
    try:
        node = page.locator(selector).first
        node.wait_for(state="visible", timeout=10_000)
        value = " ".join(node.inner_text().split())
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"Không thấy trường '{label}' trên trang. Có thể trang đổi giao diện hoặc yêu cầu quyền xem."
        ) from exc
    if not value or "***" in value:
        raise RuntimeError(f"Trường '{label}' đang trống hoặc bị giới hạn quyền xem trên nguồn.")
    return value


def _read_cafef_ticker(page: Page) -> str:
    """Đọc mã CafeF từ nhãn mã trên trang; một số hồ sơ chỉ ghi mã trong tiêu đề trang."""
    node = page.locator(".symbol").first
    if node.count() and node.is_visible():
        value = " ".join(node.inner_text().split()).upper()
        if value and "***" not in value:
            return value

    # CafeF chuyển một số mã sang đường dẫn /hose/ và bỏ phần tử .symbol.
    # Tiêu đề tab do CafeF đặt vẫn bắt đầu bằng mã, ví dụ "HDB: ... (HOSE)".
    title_prefix = page.title().split(":", maxsplit=1)[0].strip().upper()
    if title_prefix and title_prefix.isalnum():
        return title_prefix
    raise RuntimeError("Không thấy mã cổ phiếu trong nội dung hoặc tiêu đề trang CafeF.")


def collect_one(
    browser: Browser,
    ticker: str,
    vietstock_url: str,
    cafef_url: str,
) -> StockRecord:
    """Lấy mã/sàn từ Vietstock và đối chiếu mã trên hồ sơ CafeF.

    Chỉ đọc nội dung hiển thị trên trang. HTML/response body không được ghi ra đĩa.
    """
    symbol = ticker.strip().upper()
    vietstock_page, vietstock_fetched_at = _open_public_page(browser, vietstock_url)
    try:
        vietstock_ticker = _read_visible_text(
            vietstock_page, ".company-general-stock-code", "mã cổ phiếu Vietstock"
        ).upper()
        exchange = _read_visible_text(
            vietstock_page, ".company-general-stock-exchange", "sàn giao dịch Vietstock"
        ).upper()
    finally:
        vietstock_page.close()

    if vietstock_ticker != symbol:
        raise RuntimeError(
            f"Mã trên Vietstock là {vietstock_ticker}, không khớp mã cấu hình {symbol}."
        )

    cafef_page, cafef_fetched_at = _open_public_page(browser, cafef_url)
    try:
        cafef_ticker = _read_cafef_ticker(cafef_page)
    finally:
        cafef_page.close()

    if cafef_ticker != symbol:
        raise RuntimeError(f"Mã trên CafeF là {cafef_ticker}, không khớp mã cấu hình {symbol}.")

    # StockShape cần một ID duy nhất; sàn + mã tạo khóa ổn định, dễ đọc và dễ đối chiếu.
    return StockRecord(
        stockId=f"{exchange}:{symbol}",
        tickerSymbol=symbol,
        exchange=exchange,
        sourceReferences=[
            {
                "sourceName": "VietstockFinance",
                "url": vietstock_url,
                "retrievedAt": vietstock_fetched_at,
                "verifiedFields": "tickerSymbol,exchange",
            },
            {
                "sourceName": "CafeF",
                "url": cafef_url,
                "retrievedAt": cafef_fetched_at,
                "verifiedFields": "tickerSymbol",
            },
        ],
    )
