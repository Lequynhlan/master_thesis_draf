"""Thu thập quan hệ thành phần VN30 từ thông báo PDF chính thức của HOSE."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.request import Request, urlopen

from pypdf import PdfReader


@dataclass(frozen=True)
class IndexMembershipRecord:
    """Quan hệ Stock thuộc MarketIndex với thời gian và nguồn có thể kiểm tra."""

    membershipId: str
    memberStock: str
    memberIndex: str
    validFrom: str
    availableAt: str
    relationConfidence: str
    dataQualityFlag: str
    sourceReference: str
    sourceName: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_vn30_codes(source_url: str) -> tuple[set[str], str]:
    """Tải PDF HOSE vào bộ nhớ và đọc mã ở bảng VN30, không lưu bản PDF thô."""
    request = Request(source_url, headers={"User-Agent": "WFKG vertical-slice research crawler"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HOSE trả về trạng thái HTTP {response.status}: {source_url}")
        pdf_bytes = response.read()

    reader = PdfReader(BytesIO(pdf_bytes))
    page_text = reader.pages[0].extract_text() or ""
    # Trang đầu đặt bảng VN30 trước bảng dự phòng; giữ đúng 30 dòng đầu tiên.
    rows: list[str] = []
    for match in re.finditer(r"(?m)^\s*\d+\s+([A-Z]{3})\s+", page_text):
        rows.append(match.group(1))
        if len(rows) == 30:
            break
    if len(rows) != 30 or len(set(rows)) != 30:
        raise RuntimeError(
            f"Không đọc được chính xác 30 ticker từ bảng VN30 trong PDF HOSE; đọc được {len(rows)}."
        )
    return set(rows), datetime.now(timezone.utc).isoformat()


def collect_vn30_memberships(
    source_url: str,
    effective_from: str,
    stock_ids: dict[str, str],
    index_id: str,
) -> list[IndexMembershipRecord]:
    """Đọc thành phần VN30 từ PDF HOSE, chỉ xuất các mã thuộc vertical slice."""
    codes, retrieved_at = _read_vn30_codes(source_url)
    missing = sorted(set(stock_ids) - codes)
    if missing:
        raise RuntimeError(f"HOSE không liệt kê các mã cấu hình trong rổ VN30: {', '.join(missing)}")

    return [
        IndexMembershipRecord(
            membershipId=f"MEMBERSHIP:VN30:{ticker}:{effective_from}",
            memberStock=stock_id,
            memberIndex=index_id,
            validFrom=effective_from,
            availableAt=retrieved_at,
            relationConfidence="1.0",
            dataQualityFlag="OFFICIAL_HOSE_COMPONENT_LIST",
            sourceReference=source_url,
            sourceName="HOSE",
        )
        for ticker, stock_id in sorted(stock_ids.items())
    ]
