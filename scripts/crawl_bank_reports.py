"""Tìm và tải BCTC từ các trang IR chính thức, rồi lập chỉ mục các dòng metric cần rà.

Script này không tự biến con số nhận diện được thành snapshot KG. Bảng PDF ngân hàng
thường có nhiều cột kỳ/phạm vi; người dùng cần đối chiếu từng dòng với báo cáo gốc.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "initial_data_load" / "financial_metrics"
RUN_DIR = ROOT / "runs" / "financial_reports"

# Những URL này là trang IR do người dùng cung cấp trong yêu cầu.
BANK_PAGES = {
    "CTG": "https://investor.vietinbank.vn/vi/periodicreports.aspx/-/categories/471001",
    "HDB": "https://hdbank.com.vn/vi/investor/thong-tin-nha-dau-tu/quan-he-co-dong/cong-bo-thong-tin-thong-tin-khac",
    "LPB": "https://lpbank.com.vn/nha-dau-tu/",
    "MBB": "https://www.mbbank.com.vn/Investor/bao-cao-tai-chinh/0/0//documents",
    "STB": "https://www.sacombank.com.vn/trang-chu/nha-dau-tu/bao-cao.html",
    "TCB": "https://techcombank.com/nha-dau-tu/thong-tin-tai-chinh/bao-cao-tai-chinh-vas",
    "VCB": "https://vietcombank.com.vn/vi-VN/Nha-dau-tu",
    "VIB": "https://www.vib.com.vn/vn/nha-dau-tu",
    "VPB": "https://www.vpbank.com.vn/quan-he-nha-dau-tu",
    "SSB": "https://www.seabank.com.vn/nha-dau-tu/bao-cao-tai-chinh",
}

# STB's investor page states that copying/forwarding its information is prohibited.
# Keep it discoverable, but do not download or persist its page/document contents.
PERSISTENCE_BLOCKED = {
    "STB": "Trang IR Sacombank nêu hạn chế sao chép/chuyển tiếp tài liệu; chỉ ghi URL, không tải/lưu nội dung.",
}

REPORT_TERMS = re.compile(r"báo cáo tài chính|financial statements|bctc|hợp nhất|consolidated", re.IGNORECASE)
PERIOD_TERMS = re.compile(r"2026|6m26|q2.?26|half.year.?2026|bán niên.?2026|quý.?ii.?2026", re.IGNORECASE)
PDF_LINK = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)


@dataclass
class ReportLink:
    ticker: str
    page_url: str
    report_url: str
    link_text: str
    status: str
    local_file: str | None = None
    sha256: str | None = None
    error: str | None = None


class LinkParser(HTMLParser):
    """Đọc link hiển thị trên HTML, không gọi endpoint nội bộ của website."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(" ".join(self._text).split())))
            self._href = None
            self._text = []


def fetch(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": "WFKG-ResearchBot/1.0 (local thesis research)"})
    with urlopen(request, timeout=35) as response:
        return response.read(), response.headers.get("Content-Type", ""), response.geturl()


def safe_filename(ticker: str, url: str) -> str:
    tail = Path(urlparse(url).path).name or "report.pdf"
    tail = re.sub(r"[^A-Za-z0-9._-]+", "_", tail)[:100]
    if not tail.lower().endswith(".pdf"):
        tail += ".pdf"
    return f"{ticker}_{tail}"


def extract_pdf_text(pdf_path: Path) -> str:
    """Lấy lớp văn bản nếu có; bản scan cần OCR thủ công/Hermes."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Thiếu pypdf; cài nhóm phụ thuộc pdf của project.") from exc
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def metric_hits(text: str) -> list[dict[str, object]]:
    """Ghi các đoạn chứa nhãn metric, để người rà mở đúng trang/dòng báo cáo."""
    labels = {
        "TOTAL_ASSETS": r"tổng tài sản|total assets",
        "GROSS_LOANS": r"cho vay khách hàng|loans and advances to customers|gross loans",
        "CUSTOMER_DEPOSITS": r"tiền gửi của khách hàng|deposits from customers|customer deposits",
        "PRE_TAX_PROFIT": r"lợi nhuận trước thuế|profit before tax",
        "NET_INTEREST_INCOME": r"thu nhập lãi thuần|net interest income",
        "TOTAL_OPERATING_INCOME": r"tổng thu nhập hoạt động|total operating income",
        "CREDIT_GROWTH": r"dư nợ cho vay khách hàng|customer loans",
    }
    lines = [" ".join(line.split()) for line in text.splitlines()]
    hits: list[dict[str, object]] = []
    for metric, pattern in labels.items():
        regex = re.compile(pattern, re.IGNORECASE)
        for index, line in enumerate(lines):
            if regex.search(line):
                context = " | ".join(lines[max(0, index - 1): min(len(lines), index + 2)])
                hits.append({"metric": metric, "lineIndex": index + 1, "textContext": context[:1200]})
    return hits


def discover(ticker: str, page_url: str, download: bool) -> list[ReportLink]:
    if ticker in PERSISTENCE_BLOCKED:
        return [ReportLink(ticker, page_url, page_url, "", "persistence_blocked", error=PERSISTENCE_BLOCKED[ticker])]
    try:
        body, content_type, final_url = fetch(page_url)
    except Exception as exc:  # Lỗi từng ngân hàng không dừng cả lượt crawl.
        return [ReportLink(ticker, page_url, page_url, "", "page_fetch_error", error=str(exc))]

    # Một số IR trả PDF trực tiếp; còn lại tìm các link PDF hiển thị trong danh mục.
    candidates: list[tuple[str, str]] = []
    if "pdf" in content_type.lower() or PDF_LINK.search(final_url):
        candidates.append((final_url, "direct PDF"))
    else:
        parser = LinkParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        for href, label in parser.links:
            absolute = urljoin(final_url, href)
            # Cho phép CDN cùng tên miền gốc (ví dụ cloud-cdn.bank.vn).
            source_domain = ".".join((urlparse(final_url).hostname or "").split(".")[-2:])
            link_domain = ".".join((urlparse(absolute).hostname or "").split(".")[-2:])
            host_ok = source_domain == link_domain
            searchable = label + " " + absolute
            if (
                host_ok
                and PDF_LINK.search(absolute)
                and REPORT_TERMS.search(searchable)
                and PERIOD_TERMS.search(searchable)
            ):
                candidates.append((absolute, label))

    # Deduplicate while keeping page order. If the visible page has no PDF links,
    # report that explicitly so a human can inspect its document list.
    unique = list(dict.fromkeys(candidates))
    if not unique:
        return [ReportLink(ticker, page_url, final_url, "", "no_visible_pdf_links",
                           error=f"Trang tải được ({len(body)} bytes, {content_type}) nhưng HTML không có link PDF hiển thị; cần kiểm tra danh mục/JS.")]

    results: list[ReportLink] = []
    for report_url, label in unique:
        item = ReportLink(ticker, page_url, report_url, label, "discovered")
        if download:
            try:
                data, kind, final_report_url = fetch(report_url)
                if "pdf" not in kind.lower() and not data.startswith(b"%PDF"):
                    raise ValueError(f"URL trả {kind}, không phải PDF")
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                path = RAW_DIR / safe_filename(ticker, final_report_url)
                path.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                item.status = "downloaded"
                item.report_url = final_report_url
                item.local_file = str(path.relative_to(ROOT))
                item.sha256 = digest
                # Giữ trích đoạn nhãn, không copy toàn văn PDF vào runs.
                text = extract_pdf_text(path)
                excerpts = metric_hits(text)
                extraction_dir = RUN_DIR / "excerpts"
                extraction_dir.mkdir(parents=True, exist_ok=True)
                excerpt_path = extraction_dir / f"{ticker}_{path.stem}_metric_hits.json"
                excerpt_path.write_text(json.dumps({
                    "ticker": ticker, "reportUrl": final_report_url,
                    "localPdf": item.local_file, "sha256": digest,
                    "pageCount": len(text.split("\f")), "textLayerChars": len(text),
                    "needsOcr": len(text.strip()) < 500, "metricCandidates": excerpts,
                    "reviewStatus": "UNVERIFIED_CANDIDATES",
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                item.status = "download_or_extract_error"
                item.error = str(exc)
        results.append(item)
        time.sleep(0.25)
    return results


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Khám phá/tải BCTC từ trang IR ngân hàng đã cấu hình.")
    parser.add_argument("--ticker", action="append", choices=sorted(BANK_PAGES), help="Mã ngân hàng; mặc định chạy tất cả")
    parser.add_argument("--download", action="store_true", help="Tải PDF hiển thị từ nguồn chính thức và tạo danh sách dòng metric cần rà")
    args = parser.parse_args()

    tickers = args.ticker or list(BANK_PAGES)
    records: list[ReportLink] = []
    for ticker in tickers:
        found = discover(ticker, BANK_PAGES[ticker], args.download)
        records.extend(found)
        print(f"{ticker}: {len(found)} kết quả — " + ", ".join(x.status for x in found))

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "scope": "consolidated H1/Q2 2026 financial statements; crawl results are not yet KG-verified",
        "downloadEnabled": args.download,
        "records": [asdict(item) for item in records],
    }
    path = RUN_DIR / "discovery_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {path.relative_to(ROOT)}")
    print(f"Tệp PDF tải được: {sum(item.status == 'downloaded' for item in records)}")
    print(f"URL PDF tìm thấy: {sum(item.status in {'discovered', 'downloaded'} for item in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
