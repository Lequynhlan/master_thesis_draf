from datetime import date
from decimal import Decimal

from wfkg.event_processing.effective_trading_date import HoseTradingCalendar
from wfkg.event_processing.candidates import generate_candidates
from wfkg.vertical_slice.end_to_end import (
    _classify_candidate_path,
    _reaction_for_candidate,
    deduplicate_event_stock_paths,
    resolve_event_t0,
)


def _calendar():
    sessions = frozenset(date.fromisoformat(x) for x in ("2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"))
    return HoseTradingCalendar(
        non_trading_dates=frozenset(), exceptional_trading_dates=frozenset(),
        observed_start=date(2026, 10, 19), observed_end=date(2026, 10, 22),
        observed_sessions=sessions,
    )


def test_midnight_precision_is_uncertain_even_when_raw_contains_time():
    event = {"eventId": "E1", "articleId": "A1", "sourceTimestampRaw": "2026-10-19T00:00:00+00:00"}
    row = resolve_event_t0(event, {"classification": "RAW_MIDNIGHT_VALUE_ASSUMED_ICT"}, _calendar())
    assert row["status"] == "UNCERTAIN_T0"
    assert not row["effectiveTradingDate"]


def test_raw_clock_is_interpreted_as_ict_wall_clock():
    event = {"eventId": "E1", "articleId": "A1", "sourceTimestampRaw": "2026-10-19T07:59:00+00:00"}
    row = resolve_event_t0(event, {"classification": "RAW_CLOCK_ASSUMED_ICT"}, _calendar())
    assert row["status"] == "RESOLVED"
    assert row["effectiveTradingDate"] == "2026-10-19"
    assert row["publicationTimestampLocal"].startswith("2026-10-19T07:59:00+07:00")


def test_verified_timestamp_converts_its_explicit_utc_offset():
    event = {"eventId": "E1", "articleId": "A1", "sourceTimestampRaw": "2026-10-19T02:00:00+00:00"}
    row = resolve_event_t0(event, {"classification": "VERIFIED_SOURCE_PAGE_TIME"}, _calendar())
    assert row["publicationTimestampLocal"].startswith("2026-10-19T09:00:00+07:00")
    assert row["effectiveTradingDate"] == "2026-10-20"


def test_candidate_gates_keep_source_context_and_t0_blocks_explicit():
    event = {"eventId": "E1"}
    uncertain = {"status": "UNCERTAIN_T0"}
    path = {"eventId": "E1", "candidateStockUri": "https://kg/HOSE:VIB", "path": "DIRECT"}
    assert _classify_candidate_path(path, event, uncertain, {}, {"VIB"}) == "STAGING_UNCERTAIN_T0"
    blocked_gate = {"promotionGate": "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"}
    assert _classify_candidate_path(path, event, uncertain, blocked_gate, {"VIB"}) == "BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW"
    out_of_scope = {**path, "candidateStockUri": "https://kg/HOSE:BIC"}
    assert _classify_candidate_path(out_of_scope, event, {"status": "RESOLVED"}, {}, {"VIB"}) == "BLOCKED_OUT_OF_SCOPE_TICKER"


def test_deduplication_keeps_each_supported_path_for_same_event_stock():
    rows = [
        {"eventId": "E1", "candidateStockUri": "HOSE:VIB", "path": "DIRECT", "evidenceId": "EV1"},
        {"eventId": "E1", "candidateStockUri": "HOSE:VIB", "path": "INDIRECT_LEADERSHIP", "evidenceId": "EV1"},
    ]
    candidates = deduplicate_event_stock_paths(rows)
    assert len(candidates) == 1
    assert {row["path"] for row in candidates[0]["supportingPaths"]} == {"DIRECT", "INDIRECT_LEADERSHIP"}


def test_candidate_generator_accepts_each_ontology_path_without_reaction_input():
    path_types = ("DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP", "INDIRECT_INDUSTRY")
    event = {"eventId": "E1", "confidenceScore": 0.8, "relationPaths": [
        {"candidateId": f"C{i}", "ticker": "VIB", "impactType": path,
         "relationStrength": 1, "evidence": {"evidenceId": "EV1"}}
        for i, path in enumerate(path_types)
    ]}
    candidates = generate_candidates([event], ("VIB",))
    assert {candidate["impactType"] for candidate in candidates} == set(path_types)
    assert all(candidate["scoreUsesReaction"] is False for candidate in candidates)
    assert all(candidate["candidateScore"] == 0.8 for candidate in candidates)


def test_market_reaction_computes_market_adjusted_car_zero_to_three():
    sessions = [date.fromisoformat(day) for day in ("2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23")]
    market = {}
    for ticker, closes in {"VIB": [100, 110, 110, 110, 110], "VNINDEX": [100, 100, 100, 100, 100]}.items():
        market[ticker] = {
            day: {"adjustedClose": Decimal(str(close)), "observationId": f"{ticker}-{day}"}
            for day, close in zip(sessions, closes)
        }
    result = _reaction_for_candidate(
        {"ticker": "VIB", "effectiveTradingDate": "2026-10-20"}, sessions, market
    )
    assert result["status"] == "EVALUATED"
    assert len(result["daily"]) == 4
    assert result["car_0_3"] == Decimal("0.1")
    assert result["car_1_3"] == Decimal(0)


def test_market_reaction_keeps_partial_window_pending_t3():
    sessions = [date.fromisoformat(day) for day in ("2026-10-19", "2026-10-20", "2026-10-21")]
    market = {ticker: {day: {"adjustedClose": Decimal(str(100 + i)), "observationId": f"{ticker}-{day}"}
                       for i, day in enumerate(sessions)} for ticker in ("VIB", "VNINDEX")}
    result = _reaction_for_candidate(
        {"ticker": "VIB", "effectiveTradingDate": "2026-10-20"}, sessions, market
    )
    assert result["status"] == "PENDING_T3"
    assert len(result["daily"]) == 2


def test_market_reaction_marks_missing_predecessor_insufficient():
    only_session = date(2026, 10, 20)
    market = {ticker: {only_session: {"adjustedClose": Decimal("100")}}
              for ticker in ("VIB", "VNINDEX")}
    result = _reaction_for_candidate(
        {"ticker": "VIB", "effectiveTradingDate": "2026-10-20"}, [only_session], market
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["reason"] == "MISSING_PREVIOUS_SESSION"

