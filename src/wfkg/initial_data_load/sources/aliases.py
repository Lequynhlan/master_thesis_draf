"""Chuẩn hóa alias mã giao dịch từ Company snapshot đã crawl."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CompanyAliasRecord:
    """Alias ticker được nguồn CafeF xác nhận trong lượt crawl Company."""

    aliasId: str
    aliasName: str
    aliasType: str
    companyId: str
    sourceReferences: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def from_company_snapshot(company: dict[str, Any]) -> CompanyAliasRecord:
    """Tạo một alias ticker, giữ lại provenance thay vì nhập alias dựng sẵn."""
    company_id = str(company["companyId"])
    ticker = str(company["shortName"]).strip().upper()
    if not ticker:
        raise ValueError(f"Company snapshot {company_id} không có shortName để tạo alias.")

    references = []
    for reference in company.get("sourceReferences", []):
        copied = dict(reference)
        copied["verifiedFields"] = "aliasName,aliasType"
        references.append(copied)
    if not references:
        raise ValueError(f"Company snapshot {company_id} không có provenance nguồn.")

    return CompanyAliasRecord(
        aliasId=f"ALIAS:{ticker}:TICKER",
        aliasName=ticker,
        aliasType="TICKER",
        companyId=company_id,
        sourceReferences=references,
    )
