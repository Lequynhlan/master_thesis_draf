"""Thu thập CorporateLeader và LeadershipPosition từ hồ sơ lãnh đạo CafeF."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Browser


def _person_id(profile_url: str) -> str | None:
    """Lấy ID công khai trong đường dẫn hồ sơ cá nhân của CafeF."""
    match = re.search(r"(?:CEO_)(\d+)", profile_url, flags=re.IGNORECASE)
    return f"CEO_{match.group(1)}" if match else None


def _normalize_person_name(name: str) -> str:
    """Bỏ kính ngữ đầu tên nhưng giữ nguyên tên do CafeF hiển thị."""
    return re.sub(r"^(Ông|Bà|Ông bà|TS\.|PGS\.TS\.|GS\.TS\.)\s+", "", name.strip(), flags=re.IGNORECASE)


def _parse_source_date(value: str) -> str | None:
    """Đổi ngày bổ nhiệm d/m/yyyy trên CafeF sang định dạng xsd:date."""
    match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", value)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _visible_positions(page: Any, ticker: str) -> list[dict[str, str]]:
    """Đọc những dòng chức vụ hiện tại có mã công ty và cột Bổ nhiệm."""
    observations: list[dict[str, str]] = []
    for table in page.locator("table").all():
        table_text = " ".join(table.inner_text().split())
        if "Bổ nhiệm" not in table_text or "Tổ chức" not in table_text or "Chức vụ" not in table_text:
            continue
        for row in table.locator("tr").all():
            cells = [" ".join(cell.inner_text().split()) for cell in row.locator("th, td").all()]
            if len(cells) < 4 or cells[0].strip().upper() != ticker:
                continue
            organization, title = cells[1].strip(), cells[2].strip()
            if not organization or not title or title.lower() in {"chức vụ", "position"}:
                continue
            appointment_text = cells[3].strip()
            observations.append(
                {
                    "organization": organization,
                    "positionTitle": title,
                    "appointmentText": appointment_text,
                    "validFrom": _parse_source_date(appointment_text) or "",
                }
            )
    return observations


def _roster_position_title(listed_name: str, roster_context: str) -> str:
    """Đọc chức danh trong thẻ lãnh đạo khi trang hồ sơ cá nhân thiếu dòng chức vụ."""
    normalized_name = _normalize_person_name(listed_name).casefold()
    for line in (" ".join(part.split()) for part in roster_context.splitlines()):
        if not line or _normalize_person_name(line).casefold() == normalized_name:
            continue
        if re.fullmatch(r"\d+\s*tuổi", line, flags=re.IGNORECASE):
            continue
        if line.casefold() in {"chi tiết...", "chi tiết", "xem thêm"}:
            continue
        return line
    return ""


def collect_company_leaders(browser: Browser, ticker: str, profile_url: str) -> dict[str, Any]:
    """Crawl profile links visible trên hồ sơ công ty, giữ các vị trí đúng ticker."""
    roster_page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
    try:
        response = roster_page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or response.status != 200:
            status = response.status if response else "không nhận được phản hồi HTTP"
            raise RuntimeError(f"CafeF trả về trạng thái {status}: {profile_url}")

        # Một số mã có trang lãnh đạo riêng; mở trang đó bằng liên kết nhìn thấy trên hồ sơ.
        roster_page.wait_for_timeout(500)
        leadership_links = roster_page.locator("a[href*='ban-lanh-dao-so-huu']").evaluate_all(
            "els => els.map(a => a.href)"
        )
        if leadership_links:
            response = roster_page.goto(leadership_links[0], wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                raise RuntimeError(f"Không mở được trang lãnh đạo CafeF: {leadership_links[0]}")
            roster_page.wait_for_timeout(700)
            tabs = roster_page.locator(".owner-tab")
            if tabs.count():
                tabs.first.click()
                roster_page.wait_for_timeout(700)

        roster_retrieved_at = datetime.now(timezone.utc).isoformat()
        # Chỉ lấy link đang hiện và không nằm trong bảng cổ đông; các link cổ đông
        # cũng dùng hồ sơ /ceo/ nhưng không phải roster lãnh đạo của ngân hàng.
        candidates = roster_page.locator("a[href*='/ceo/']").evaluate_all(
            "els => els.filter(a => a.innerText.trim() && !a.closest('table') "
            "&& (a.offsetWidth || a.offsetHeight || a.getClientRects().length)) "
            ".map(a => ({name:a.innerText.trim(), url:a.href, "
            "rosterContext:(a.closest('li') || a.parentElement?.parentElement)?.innerText || a.innerText.trim()}))"
        )
    finally:
        roster_page.close()

    unique_candidates: dict[str, tuple[str, str, str]] = {}
    for candidate in candidates:
        if urlparse(candidate["url"]).netloc.lower() not in {"cafef.vn", "www.cafef.vn"}:
            continue
        person_id = _person_id(candidate["url"])
        if not person_id:
            continue
        existing = unique_candidates.get(person_id)
        candidate_has_company = ticker.lower() in parse_qs(urlparse(candidate["url"]).query).get("cs", [""])[0].lower()
        existing_has_company = bool(
            existing
            and ticker.lower()
            in parse_qs(urlparse(existing[1]).query).get("cs", [""])[0].lower()
        )
        if existing is None or (candidate_has_company and not existing_has_company):
            unique_candidates[person_id] = (
                candidate["name"],
                candidate["url"],
                candidate["rosterContext"],
            )

    leaders: dict[str, dict[str, Any]] = {}
    positions: list[dict[str, Any]] = []
    unresolved_positions: list[dict[str, str]] = []
    unresolved_profiles: list[dict[str, str]] = []

    if not unique_candidates:
        unresolved_profiles.append(
            {
                "fullName": "",
                "profileUrl": profile_url,
                "reason": "NO_LEADER_PROFILE_LINKS_FOUND",
            }
        )

    for person_id, (listed_name, person_url, roster_context) in unique_candidates.items():
        person_page = browser.new_page(locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
        try:
            response = person_page.goto(person_url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                unresolved_profiles.append(
                    {
                        "personId": person_id,
                        "fullName": _normalize_person_name(listed_name),
                        "profileUrl": person_url,
                        "reason": "PROFILE_HTTP_ERROR",
                        "httpStatus": str(response.status if response else "NO_RESPONSE"),
                    }
                )
                continue
            # CafeF nạp bảng chức vụ bằng JavaScript sau khi trang đã mở.
            person_page.wait_for_timeout(1_200)
            retrieved_at = datetime.now(timezone.utc).isoformat()
            observed_positions = _visible_positions(person_page, ticker)
            if not observed_positions:
                person_page.wait_for_timeout(1_000)
                observed_positions = _visible_positions(person_page, ticker)
        finally:
            person_page.close()

        full_name = _normalize_person_name(listed_name)
        if not observed_positions:
            # Roster lãnh đạo của CafeF cũng là bằng chứng cho chức danh hiện tại;
            # giữ quan hệ thiếu ngày ở unresolved thay vì loại nhầm người này.
            roster_title = _roster_position_title(listed_name, roster_context)
            if roster_title:
                leaders[person_id] = {
                    "personId": person_id,
                    "fullName": full_name,
                    "sourceReferences": [
                        {
                            "sourceName": "CafeF",
                            "url": profile_url,
                            "retrievedAt": roster_retrieved_at,
                            "verifiedFields": "personId,fullName,positionTitle",
                        },
                        {
                            "sourceName": "CafeF",
                            "url": person_url,
                            "retrievedAt": retrieved_at,
                            "verifiedFields": "personId",
                        },
                    ],
                }
                unresolved_positions.append(
                    {
                        "personId": person_id,
                        "fullName": full_name,
                        "positionTitle": roster_title,
                        "organization": f"COMPANY:{ticker}",
                        "appointmentText": "CafeF không hiển thị ngày bổ nhiệm trên hồ sơ cá nhân",
                        "sourceReference": profile_url,
                    }
                )
                continue

            unresolved_profiles.append(
                {
                    "personId": person_id,
                    "fullName": full_name,
                    "profileUrl": person_url,
                    "reason": "NO_MATCHING_TICKER_POSITION_ROW_OR_ROSTER_TITLE",
                }
            )
            continue

        leaders[person_id] = {
            "personId": person_id,
            "fullName": full_name,
            "sourceReferences": [
                {
                    "sourceName": "CafeF",
                    "url": profile_url,
                    "retrievedAt": roster_retrieved_at,
                    "verifiedFields": "personId,fullName",
                },
                {
                    "sourceName": "CafeF",
                    "url": person_url,
                    "retrievedAt": retrieved_at,
                    "verifiedFields": "personId,positionTitle",
                },
            ],
        }
        for observed in observed_positions:
            if not observed["validFrom"]:
                unresolved_positions.append(
                    {
                        "personId": person_id,
                        "fullName": full_name,
                        "positionTitle": observed["positionTitle"],
                        "organization": observed["organization"],
                        "appointmentText": observed["appointmentText"],
                        "sourceReference": person_url,
                    }
                )
                continue
            positions.append(
                {
                    "positionId": f"POSITION:{ticker}:{person_id}:{len(positions) + 1}",
                    "positionHolder": person_id,
                    "positionAtCompany": f"COMPANY:{ticker}",
                    "positionTitle": observed["positionTitle"],
                    "validFrom": observed["validFrom"],
                    "availableAt": retrieved_at,
                    "relationConfidence": "1.0",
                    "dataQualityFlag": "SOURCE_VERIFIED",
                    "sourceReference": person_url,
                    "sourceName": "CafeF",
                }
            )

    return {
        "leaders": list(leaders.values()),
        "positions": positions,
        "unresolvedPositions": unresolved_positions,
        "unresolvedProfiles": unresolved_profiles,
        "profileCount": len(unique_candidates),
    }
