"""Research cutoff rule for mapping reliable publication time to a HOSE session."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    ICT = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:  # Windows Python may not ship the IANA database.
    # Vietnam has used UTC+07:00 without daylight saving time.
    ICT = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
CUTOFF = time(8, 0)
RULE_ID = "HOSE_PUBLICATION_CUTOFF_0800_ICT_V1"


@dataclass(frozen=True)
class HoseTradingCalendar:
    """Known HOSE holidays plus observed sessions for the project data range."""

    non_trading_dates: frozenset[date]
    exceptional_trading_dates: frozenset[date]
    observed_start: date | None = None
    observed_end: date | None = None
    observed_sessions: frozenset[date] = frozenset()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HoseTradingCalendar":
        observed = data.get("observedSessionRange", {})
        return cls(
            non_trading_dates=frozenset(date.fromisoformat(x) for x in data["officialNonTradingDates"]),
            exceptional_trading_dates=frozenset(date.fromisoformat(x) for x in data.get("exceptionalTradingDates", [])),
            observed_start=date.fromisoformat(observed["start"]) if observed.get("start") else None,
            observed_end=date.fromisoformat(observed["end"]) if observed.get("end") else None,
            observed_sessions=frozenset(date.fromisoformat(x) for x in observed.get("sessions", [])),
        )

    @classmethod
    def load(cls, path: Path) -> "HoseTradingCalendar":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def is_trading_day(self, day: date) -> bool:
        if day in self.exceptional_trading_dates:
            return True
        if day in self.non_trading_dates or day.weekday() >= 5:
            return False
        if self.observed_start and self.observed_end and self.observed_start <= day <= self.observed_end:
            return day in self.observed_sessions
        return True

    def next_session(self, day: date, *, include_day: bool = False) -> date:
        candidate = day if include_day else day + timedelta(days=1)
        for _ in range(370):
            if self.is_trading_day(candidate):
                return candidate
            candidate += timedelta(days=1)
        raise ValueError(f"No HOSE session found after {day.isoformat()} within one year")


def resolve_effective_trading_date(
    published_at: str | datetime | None,
    *,
    timestamp_reliable: bool,
    calendar: HoseTradingCalendar,
    assume_wall_clock_timezone: bool = False,
) -> dict[str, str | None]:
    """Resolve a publication timestamp; never infer missing or untrusted time."""

    base = {
        "ruleId": RULE_ID,
        "cutoffLocal": "08:00:00",
        "timezone": "Asia/Ho_Chi_Minh",
        "effectiveTradingDate": None,
        "status": "UNRESOLVED",
        "reason": None,
        "publicationTimestampLocal": None,
    }
    if not timestamp_reliable:
        base["reason"] = "PUBLICATION_TIMESTAMP_NOT_VERIFIED"
        return base
    if published_at is None:
        base["reason"] = "PUBLICATION_TIMESTAMP_MISSING"
        return base
    if isinstance(published_at, str):
        value = published_at.strip()
        if "T" not in value and " " not in value:
            base["reason"] = "PUBLICATION_HOUR_MISSING"
            return base
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            base["reason"] = "PUBLICATION_TIMESTAMP_INVALID"
            return base
    else:
        parsed = published_at
    if (parsed.tzinfo is None or parsed.utcoffset() is None) and not assume_wall_clock_timezone:
        base["reason"] = "PUBLICATION_TIMEZONE_MISSING"
        return base

    # Some project RAW publishers serialize their local clock fields with a
    # misleading +00:00 suffix. Callers may explicitly select the project
    # convention and preserve the wall-clock fields while replacing that zone.
    local = parsed.replace(tzinfo=ICT) if assume_wall_clock_timezone else parsed.astimezone(ICT)
    base["publicationTimestampLocal"] = local.isoformat()
    if calendar.is_trading_day(local.date()) and local.timetz().replace(tzinfo=None) < CUTOFF:
        result_day = local.date()
    else:
        result_day = calendar.next_session(local.date())
    base["effectiveTradingDate"] = result_day.isoformat()
    base["status"] = "RESOLVED"
    base["reason"] = "BEFORE_CUTOFF_CURRENT_SESSION" if result_day == local.date() else "CUTOFF_OR_NEXT_SESSION"
    return base
