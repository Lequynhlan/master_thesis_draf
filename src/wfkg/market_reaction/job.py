"""Pure, reproducible market-reaction calculations used by the PoC runner."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Mapping, Sequence

from wfkg.config import ProjectConfig

ICT = timezone(timedelta(hours=7))
REACTION_WINDOWS = ((0, 0), (0, 1), (-1, 1), (0, 3))


def day0_from_sessions(available_at: datetime, sessions: Sequence[date]) -> date | None:
    """First session with 09:00 ICT strictly later than disclosure availability."""
    if available_at.tzinfo is None or available_at.utcoffset() is None:
        raise ValueError("available_at must be timezone-aware; naive timestamps are unsafe for Day 0.")
    local = available_at.astimezone(ICT)
    return next((day for day in sorted(sessions) if datetime.combine(day, time(9), ICT) > local), None)


def calculate_car(
    stock_close: Mapping[date, Decimal | float | str],
    benchmark_close: Mapping[date, Decimal | float | str],
    day0: date,
    window: tuple[int, int],
    sessions: Sequence[date] | None = None,
) -> dict[str, object]:
    """Compute daily AR and CAR from closing levels; missing inputs are explicit."""
    start, end = window
    calendar = sorted(sessions if sessions is not None else set(stock_close) | set(benchmark_close))
    if day0 not in calendar:
        return {"status": "NOT_EVALUATED", "reason": "DAY0_NOT_IN_TRADING_CALENDAR", "car": None}
    index = calendar.index(day0)
    left, right = index + start, index + end
    if left < 0 or right >= len(calendar):
        return {"status": "NOT_EVALUATED", "reason": "INCOMPLETE_TRADING_WINDOW", "car": None}
    dates = calendar[left:right + 1]
    returns: list[Decimal] = []
    for day in dates:
        position = calendar.index(day)
        if position == 0:
            return {"status": "NOT_EVALUATED", "reason": "MISSING_PREVIOUS_SESSION", "car": None}
        previous = calendar[position - 1]
        if day not in stock_close or day not in benchmark_close or previous not in stock_close or previous not in benchmark_close:
            return {"status": "NOT_EVALUATED", "reason": f"MISSING_CLOSE:{day.isoformat()}", "car": None}
        sr = _decimal(stock_close[day]) / _decimal(stock_close[previous]) - 1
        br = _decimal(benchmark_close[day]) / _decimal(benchmark_close[previous]) - 1
        returns.append(sr - br)
    return {"status": "EVALUATED", "reason": None, "car": sum(returns, Decimal(0)), "dailyAR": returns}


def reaction_weights(car: Decimal | float | str, confidence: Decimal | float | str,
                     relation_strength: Decimal | float | str) -> dict[str, Decimal]:
    c, conf, strength = _decimal(car), _decimal(confidence), _decimal(relation_strength)
    impact = min(Decimal(1), abs(c) / Decimal("0.10"))
    weight = impact * conf * strength
    signed = (Decimal(1) if c > 0 else Decimal(-1) if c < 0 else Decimal(0)) * weight
    return {"impactScore": impact, "reactionWeight": weight, "signedWeight": signed}


def run(config: ProjectConfig, output_dir: str | None = None) -> dict[str, object]:
    """Run the configured frozen reviewed PoC through the package orchestrator."""
    from pathlib import Path
    from wfkg.vertical_slice.job import run_vertical_slice

    settings = config.values.get("integration", {})
    manifest_value = settings.get("release_manifest")
    output_value = output_dir or settings.get("output_dir")
    if not manifest_value or not output_value:
        raise ValueError("integration.release_manifest and output_dir are required for the reviewed PoC job.")
    root = config.path.parent.parent
    manifest = Path(manifest_value)
    if not manifest.is_absolute():
        manifest = root / manifest
    destination = Path(output_value)
    if not destination.is_absolute():
        destination = root / destination
    return run_vertical_slice(manifest, destination, config.path)


def _decimal(value: Decimal | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))
