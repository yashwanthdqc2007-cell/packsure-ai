"""
Unit tests for Analytics Pydantic schemas (backend/app/schemas/analytics.py).

Verifies:
1. Valid AnalyticsResponse construction with nested models.
2. Valid DailyTrendItem, TopViolationItem, and CategoryStats construction.
3. Strict non-negative constraints on all count fields.
4. Strict 0.0 to 100.0 boundary validation on pass_rate.
5. Exact field serialization matching docs/api.md Section 4 (including category 'pass' alias).
"""

import unittest
from pydantic import ValidationError

from app.schemas.analytics import (
    AnalyticsResponse,
    CategoryStats,
    DailyTrendItem,
    TopViolationItem,
)


class TestAnalyticsSchemas(unittest.TestCase):
    """Test suite for Analytics Pydantic v2 schemas and validation boundaries."""

    def test_valid_daily_trend_item(self):
        """Test valid DailyTrendItem instantiation."""
        item = DailyTrendItem(
            day="Mon",
            date="2026-08-31",
            scans=14,
            compliant=9,
            non_compliant=3,
            needs_review=2,
        )
        self.assertEqual(item.day, "Mon")
        self.assertEqual(item.date, "2026-08-31")
        self.assertEqual(item.scans, 14)
        self.assertEqual(item.compliant, 9)
        self.assertEqual(item.non_compliant, 3)
        self.assertEqual(item.needs_review, 2)

    def test_daily_trend_item_negative_counts_rejected(self):
        """DailyTrendItem must reject negative counts."""
        with self.assertRaises(ValidationError):
            DailyTrendItem(day="Mon", date="2026-08-31", scans=-1, compliant=0, non_compliant=0, needs_review=0)

        with self.assertRaises(ValidationError):
            DailyTrendItem(day="Mon", date="2026-08-31", scans=10, compliant=-5, non_compliant=0, needs_review=0)

    def test_valid_top_violation_item(self):
        """Test valid TopViolationItem instantiation."""
        item = TopViolationItem(
            rule_code="Rule-6(1)(e)",
            description="Missing Unit Sale Price",
            count=21,
        )
        self.assertEqual(item.rule_code, "Rule-6(1)(e)")
        self.assertEqual(item.description, "Missing Unit Sale Price")
        self.assertEqual(item.count, 21)

    def test_top_violation_negative_count_rejected(self):
        """TopViolationItem must reject negative count."""
        with self.assertRaises(ValidationError):
            TopViolationItem(rule_code="Rule-6(1)(e)", description="Missing Unit Sale Price", count=-1)

    def test_valid_category_stats(self):
        """Test valid CategoryStats instantiation and alias support."""
        # Instantiation via 'pass' alias
        stats_alias = CategoryStats.model_validate({"total": 42, "pass": 30, "fail": 8, "review": 4})
        self.assertEqual(stats_alias.total, 42)
        self.assertEqual(stats_alias.pass_, 30)
        self.assertEqual(stats_alias.fail, 8)
        self.assertEqual(stats_alias.review, 4)

        # Instantiation via 'pass_' field name
        stats_kw = CategoryStats(total=54, pass_=32, fail=16, review=6)
        self.assertEqual(stats_kw.total, 54)
        self.assertEqual(stats_kw.pass_, 32)
        self.assertEqual(stats_kw.fail, 16)
        self.assertEqual(stats_kw.review, 6)

    def test_category_stats_negative_counts_rejected(self):
        """CategoryStats must reject negative counts."""
        with self.assertRaises(ValidationError):
            CategoryStats(total=-1, pass_=0, fail=0, review=0)

        with self.assertRaises(ValidationError):
            CategoryStats(total=10, pass_=-2, fail=0, review=0)

    def test_valid_analytics_response_construction(self):
        """Test full AnalyticsResponse construction conforming to docs/api.md."""
        data = {
            "total_scans": 128,
            "pass_count": 76,
            "fail_count": 34,
            "review_count": 18,
            "pass_rate": 59.4,
            "daily_trend": [
                {
                    "day": "Mon",
                    "date": "2026-08-31",
                    "scans": 14,
                    "compliant": 9,
                    "non_compliant": 3,
                    "needs_review": 2,
                },
                {
                    "day": "Tue",
                    "date": "2026-09-01",
                    "scans": 18,
                    "compliant": 11,
                    "non_compliant": 5,
                    "needs_review": 2,
                },
            ],
            "top_violations": [
                {
                    "rule_code": "Rule-6(1)(e)",
                    "description": "Missing Unit Sale Price",
                    "count": 21,
                },
                {
                    "rule_code": "Rule-6(1)(a)",
                    "description": "Incomplete Manufacturer Address",
                    "count": 14,
                },
            ],
            "by_category": {
                "Edible Oil": {"total": 42, "pass": 30, "fail": 8, "review": 4},
                "Food Grains": {"total": 54, "pass": 32, "fail": 16, "review": 6},
            },
        }

        resp = AnalyticsResponse.model_validate(data)
        self.assertEqual(resp.total_scans, 128)
        self.assertEqual(resp.pass_count, 76)
        self.assertEqual(resp.fail_count, 34)
        self.assertEqual(resp.review_count, 18)
        self.assertEqual(resp.pass_rate, 59.4)
        self.assertEqual(len(resp.daily_trend), 2)
        self.assertEqual(len(resp.top_violations), 2)
        self.assertEqual(len(resp.by_category), 2)

    def test_analytics_response_negative_counts_rejected(self):
        """AnalyticsResponse must reject negative total, pass, fail, or review counts."""
        base = {"total_scans": 10, "pass_count": 5, "fail_count": 3, "review_count": 2, "pass_rate": 50.0}

        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "total_scans": -1})

        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "pass_count": -5})

        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "fail_count": -2})

        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "review_count": -1})

    def test_analytics_response_pass_rate_boundary_validation(self):
        """pass_rate must be constrained within [0.0, 100.0]."""
        base = {"total_scans": 10, "pass_count": 5, "fail_count": 3, "review_count": 2}

        # Valid boundaries
        self.assertEqual(AnalyticsResponse.model_validate({**base, "pass_rate": 0.0}).pass_rate, 0.0)
        self.assertEqual(AnalyticsResponse.model_validate({**base, "pass_rate": 100.0}).pass_rate, 100.0)

        # Invalid lower bound
        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "pass_rate": -0.1})

        # Invalid upper bound
        with self.assertRaises(ValidationError):
            AnalyticsResponse.model_validate({**base, "pass_rate": 100.1})

    def test_serialization_exact_field_names_and_aliases(self):
        """Serialization with by_alias=True must match docs/api.md JSON schema exactly."""
        resp = AnalyticsResponse(
            total_scans=10,
            pass_count=6,
            fail_count=2,
            review_count=2,
            pass_rate=60.0,
            daily_trend=[
                DailyTrendItem(day="Mon", date="2026-08-31", scans=5, compliant=3, non_compliant=1, needs_review=1)
            ],
            top_violations=[
                TopViolationItem(rule_code="Rule-6(1)(e)", description="Missing Unit Sale Price", count=3)
            ],
            by_category={
                "Edible Oil": CategoryStats(total=10, pass_=6, fail=2, review=2)
            },
        )

        dumped = resp.model_dump(by_alias=True)

        expected_top_keys = {
            "total_scans",
            "pass_count",
            "fail_count",
            "review_count",
            "pass_rate",
            "daily_trend",
            "top_violations",
            "by_category",
        }
        self.assertEqual(set(dumped.keys()), expected_top_keys)

        expected_trend_keys = {"day", "date", "scans", "compliant", "non_compliant", "needs_review"}
        self.assertEqual(set(dumped["daily_trend"][0].keys()), expected_trend_keys)

        expected_violation_keys = {"rule_code", "description", "count"}
        self.assertEqual(set(dumped["top_violations"][0].keys()), expected_violation_keys)

        expected_category_keys = {"total", "pass", "fail", "review"}
        self.assertEqual(set(dumped["by_category"]["Edible Oil"].keys()), expected_category_keys)
        self.assertEqual(dumped["by_category"]["Edible Oil"]["pass"], 6)


if __name__ == "__main__":
    unittest.main()
