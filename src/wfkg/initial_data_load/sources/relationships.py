"""Thu thập các GovernmentOrganization và quan hệ công ty con cho vertical slice."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.request import Request, urlopen

from wfkg.initial_data_load.sources.news_sources import _TitleReader

GOVERNMENT_ORGANIZATIONS = (
    ("NHNN", "Ngân hàng Nhà nước Việt Nam", "https://www.sbv.gov.vn/"),
    ("CHINHPHU", "Chính phủ Việt Nam", "https://chinhphu.vn/"),
    ("THU_TUONG", "Thủ tướng Chính phủ", "https://chinhphu.vn/"),
    ("BO_TAI_CHINH", "Bộ Tài chính", "https://mof.gov.vn/"),
    ("UBCKNN", "Ủy ban Chứng khoán Nhà nước", "https://www.ssc.gov.vn/"),
)

# Các cặp này là mapping do người dùng cung cấp; tên pháp nhân và ticker cần được crawl xác minh.
SUBSIDIARIES = (
    ("BID", "BSI", "Chứng khoán BIDV", "https://www.bsc.com.vn/"),
    ("BID", "BIC", "Bảo hiểm BIDV", "https://bic.vn/"),
    ("CTG", "CTS", "Chứng khoán VietinBank", "https://www.cts.vn/"),
    ("MBB", "MBS", "Chứng khoán MB", "https://www.mbs.com.vn/"),
    ("MBB", "MIG", "Bảo hiểm Quân đội", "https://baohiem.mic.vn/"),
    ("TCB", "TCX", "Chứng khoán Kỹ thương", "https://tcbs.com.vn/"),
    ("VPB", "VPX", "Chứng khoán VPBank", "https://www.vpbanks.com.vn/"),
)


def collect_government_organizations() -> list[dict[str, object]]:
    """Mở cổng chính thức để xác nhận hoạt động, giữ nguyên tên do người dùng chốt."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, object]] = []
    for code, name, url in GOVERNMENT_ORGANIZATIONS:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 WFKG vertical slice"})
        with urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"Cổng chính thức trả HTTP {response.status}: {url}")
            html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            final_url = response.geturl()
        title_reader = _TitleReader()
        title_reader.feed(html)
        records.append({
                "organizationId": f"GOV_ORG:{code}",
                "organizationName": name,
                "sourceReferences": [{
                    "url": final_url,
                    "pageTitle": " ".join(" ".join(title_reader.parts).split()),
                    "retrievedAt": retrieved_at,
                    "verifiedFields": "officialPortalResponded",
                }],
            })
    return records


def collect_subsidiaries() -> list[dict[str, object]]:
    """Kiểm tra trang chính thức từng pháp nhân và đánh dấu mapping sở hữu còn provisional."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, object]] = []
    for parent, child, name, url in SUBSIDIARIES:
        title_reader = _TitleReader()
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 WFKG vertical slice"})
            with urlopen(request, timeout=25) as response:
                html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                final_url = response.geturl()
            title_reader.feed(html)
            homepage_status = "HTTP_200"
            page_title = " ".join(" ".join(title_reader.parts).split())
        except Exception as exc:  # Lưu được các mã còn lại, đồng thời chỉ rõ site nào chưa đọc được.
            final_url = url
            homepage_status = f"FETCH_FAILED:{type(exc).__name__}"
            page_title = ""
        records.append({
                "relationId": f"SUBSIDIARY:{parent}:{child}",
                "parentTicker": parent,
                "subsidiaryTicker": child,
                "subsidiaryName": name,
                "availableAt": retrieved_at,
                "dataQualityFlag": "USER_SEEDED_CANDIDATE_OWNERSHIP_UNVERIFIED",
                "sourceReference": final_url,
                "officialHomepageStatus": homepage_status,
                "officialHomepageTitle": page_title,
                "sourceName": "Official company homepage; parent mapping supplied by user",
            })
    return records
