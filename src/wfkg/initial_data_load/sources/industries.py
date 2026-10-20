"""Thu thập phân loại ngành hiển thị trên hồ sơ cổ phiếu VietstockFinance."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from playwright.sync_api import Browser


def collect_classification(
    browser: Browser,
    ticker: str,
    vietstock_url: str,
) -> tuple[list[str], dict[str, str]]:
    """Đọc đường dẫn ngành và provenance từ trang hồ sơ của một mã."""
    page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
    try:
        response = page.goto(vietstock_url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or response.status != 200:
            status = response.status if response else "không nhận được phản hồi HTTP"
            raise RuntimeError(f"VietstockFinance trả về trạng thái {status}: {vietstock_url}")

        # Trang hiển thị phân cấp sau nhãn "Ngành:"; giữ thứ tự và không tự phân loại.
        label = "\u004e\u0067\u00e0\u006e\u0068:"
        line = next(
            (item.strip() for item in page.locator("body").inner_text().splitlines()
             if item.strip().startswith(label)),
            "",
        )
        if not line:
            raise RuntimeError(f"Không tìm thấy phân loại ngành hiển thị trên trang {ticker}.")

        levels = [part.strip() for part in re.split(r"\s{2,}", line.split(":", 1)[1]) if part.strip()]
        if len(levels) < 2:
            raise RuntimeError(f"Phân loại ngành của {ticker} không đủ cấp để tạo IndustryGroup/Industry: {line}")
        retrieved_at = datetime.now(timezone.utc).isoformat()
    finally:
        page.close()

    return levels, {
        "sourceName": "VietstockFinance",
        "url": vietstock_url,
        "retrievedAt": retrieved_at,
        "verifiedFields": "industryGroupName,industryName,taxonomyPath",
    }
