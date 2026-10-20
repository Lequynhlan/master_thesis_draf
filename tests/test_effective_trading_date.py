from datetime import date
from pathlib import Path
import unittest

from wfkg.event_processing.effective_trading_date import (
    HoseTradingCalendar,
    RULE_ID,
    resolve_effective_trading_date,
)


ROOT = Path(__file__).resolve().parents[1]
CALENDAR = HoseTradingCalendar.load(ROOT / "config/hose_trading_calendar_2026.json")


class EffectiveTradingDateTests(unittest.TestCase):
    def resolve(self, stamp, reliable=True):
        return resolve_effective_trading_date(stamp, timestamp_reliable=reliable, calendar=CALENDAR)

    def test_0759_uses_current_trading_session(self):
        result = self.resolve("2026-10-15T07:59:00+07:00")
        self.assertEqual(result["effectiveTradingDate"], "2026-10-15")
        self.assertEqual(result["status"], "RESOLVED")

    def test_raw_wall_clock_policy_ignores_serialized_utc_offset(self):
        result = resolve_effective_trading_date(
            "2026-10-15T07:59:00+00:00",
            timestamp_reliable=True,
            calendar=CALENDAR,
            assume_wall_clock_timezone=True,
        )
        self.assertEqual(result["publicationTimestampLocal"], "2026-10-15T07:59:00+07:00")
        self.assertEqual(result["effectiveTradingDate"], "2026-10-15")

    def test_raw_wall_clock_policy_accepts_naive_local_timestamp(self):
        result = resolve_effective_trading_date(
            "2026-10-15T07:59:00",
            timestamp_reliable=True,
            calendar=CALENDAR,
            assume_wall_clock_timezone=True,
        )
        self.assertEqual(result["publicationTimestampLocal"], "2026-10-15T07:59:00+07:00")
        self.assertEqual(result["effectiveTradingDate"], "2026-10-15")

    def test_0800_uses_next_trading_session(self):
        self.assertEqual(self.resolve("2026-10-15T08:00:00+07:00")["effectiveTradingDate"], "2026-10-16")

    def test_0801_uses_next_trading_session(self):
        self.assertEqual(self.resolve("2026-10-15T08:01:00+07:00")["effectiveTradingDate"], "2026-10-16")

    def test_during_session_uses_next_session(self):
        self.assertEqual(self.resolve("2026-10-15T11:30:00+07:00")["effectiveTradingDate"], "2026-10-16")

    def test_after_session_uses_next_session(self):
        self.assertEqual(self.resolve("2026-10-15T15:00:00+07:00")["effectiveTradingDate"], "2026-10-16")

    def test_weekend_uses_monday_session(self):
        self.assertEqual(self.resolve("2026-10-17T10:00:00+07:00")["effectiveTradingDate"], "2026-10-19")

    def test_official_holiday_uses_next_observed_session(self):
        self.assertFalse(CALENDAR.is_trading_day(date(2026, 9, 2)))
        self.assertEqual(self.resolve("2026-09-02T07:00:00+07:00")["effectiveTradingDate"], "2026-09-03")

    def test_date_without_hour_remains_unresolved(self):
        result = self.resolve("2026-10-15", reliable=True)
        self.assertIsNone(result["effectiveTradingDate"])
        self.assertEqual(result["reason"], "PUBLICATION_HOUR_MISSING")

    def test_unverified_timestamp_remains_unresolved(self):
        result = self.resolve("2026-10-15T07:00:00+07:00", reliable=False)
        self.assertIsNone(result["effectiveTradingDate"])
        self.assertEqual(result["reason"], "PUBLICATION_TIMESTAMP_NOT_VERIFIED")

    def test_naive_timestamp_remains_unresolved(self):
        result = self.resolve("2026-10-15T07:00:00")
        self.assertIsNone(result["effectiveTradingDate"])
        self.assertEqual(result["reason"], "PUBLICATION_TIMEZONE_MISSING")

    def test_result_records_rule_and_timezone(self):
        result = self.resolve("2026-10-15T07:59:00+07:00")
        self.assertEqual(result["ruleId"], RULE_ID)
        self.assertEqual(result["timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(result["cutoffLocal"], "08:00:00")


if __name__ == "__main__":
    unittest.main()
