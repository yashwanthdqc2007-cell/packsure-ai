"""
Unit tests for PackSure AI Analytics API (Phase 8D).

Verifies:
1. Default period "7d" returns 200 OK + valid AnalyticsResponse.
2. Explicit period "30d" filters and aggregates correctly.
3. Explicit period "all" includes all historical scans.
4. Invalid period raises HTTP 400 Bad Request.
5. Exact response shape conforming to docs/api.md Section 4.
6. Zero-scan response yields total_scans=0, pass_rate=0.0, and empty collections.
7. Repository dependency injection is strictly utilized.
8. Pass / fail / review metrics calculation.
9. Daily trend grouping and metrics.
10. Top violations aggregation and ordering.
11. Category breakdown mapping and category stats.
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.routes.analytics import get_analytics
from app.database.connection import InMemoryScanRepository
from app.schemas.analytics import AnalyticsResponse
from app.schemas.violation import Violation, ViolationSeverity, ViolationType


class TestAnalyticsAPI(unittest.TestCase):
    """Test suite for GET /api/v1/analytics endpoint."""

    def setUp(self):
        self.repo = InMemoryScanRepository()

    def _seed_scan(self, scan_id: str, category: str, verdict: str, created_at: str):
        self.repo.scans[scan_id] = {
            "id": scan_id,
            "user_id": "inspector-1",
            "status": "complete",
            "verdict": verdict,
            "compliance_score": 100.0 if verdict == "PASS" else 60.0,
            "product_category": category,
            "image_url": f"storage/scans/{scan_id}/original.jpg",
            "created_at": created_at,
            "completed_at": created_at,
        }

    def _seed_violation(self, scan_id: str, rule_code: str, description: str):
        if scan_id not in self.repo.violations:
            self.repo.violations[scan_id] = []
        self.repo.violations[scan_id].append(
            Violation(
                rule_code=rule_code,
                rule_id="LMR-RULE",
                field_name="test_field",
                violation_type=ViolationType.missing_declaration,
                severity=ViolationSeverity.critical,
                description=description,
            )
        )

    def test_zero_scan_response(self):
        """Empty database returns 0 totals, 0.0 pass rate, and empty collections."""
        resp: AnalyticsResponse = get_analytics(repo=self.repo)
        self.assertIsInstance(resp, AnalyticsResponse)
        self.assertEqual(resp.total_scans, 0)
        self.assertEqual(resp.pass_count, 0)
        self.assertEqual(resp.fail_count, 0)
        self.assertEqual(resp.review_count, 0)
        self.assertEqual(resp.pass_rate, 0.0)
        self.assertEqual(resp.daily_trend, [])
        self.assertEqual(resp.top_violations, [])
        self.assertEqual(resp.by_category, {})

    def test_default_period_7d(self):
        """Default period is '7d' and filters scans within the last 7 days."""
        self._seed_scan("s-now", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")
        self._seed_scan("s-old", "Edible Oil", "PASS", "2026-08-01T10:00:00Z")

        resp: AnalyticsResponse = get_analytics(repo=self.repo)
        self.assertEqual(resp.total_scans, 1)
        self.assertEqual(resp.pass_count, 1)

    def test_explicit_period_30d(self):
        """Explicit period '30d' includes scans within 30 days but excludes older."""
        self._seed_scan("s-recent", "Edible Oil", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-20d-old", "Snacks", "FAIL", "2026-08-20T10:00:00Z")
        self._seed_scan("s-60d-old", "Beverages", "PASS", "2026-07-01T10:00:00Z")

        resp: AnalyticsResponse = get_analytics(period="30d", repo=self.repo)
        self.assertEqual(resp.total_scans, 2)
        self.assertEqual(resp.pass_count, 1)
        self.assertEqual(resp.fail_count, 1)

    def test_explicit_period_all(self):
        """Explicit period 'all' includes all historical scans regardless of age."""
        self._seed_scan("s-1", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")
        self._seed_scan("s-2", "Snacks", "FAIL", "2026-08-01T10:00:00Z")
        self._seed_scan("s-3", "Beverages", "NEEDS_REVIEW", "2025-01-01T10:00:00Z")

        resp: AnalyticsResponse = get_analytics(period="all", repo=self.repo)
        self.assertEqual(resp.total_scans, 3)
        self.assertEqual(resp.pass_count, 1)
        self.assertEqual(resp.fail_count, 1)
        self.assertEqual(resp.review_count, 1)

    def test_invalid_period_raises_http_400(self):
        """Invalid period parameter value must raise HTTP 400 Bad Request."""
        with self.assertRaises(HTTPException) as ctx:
            get_analytics(period="invalid_period", repo=self.repo)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid period filter", ctx.exception.detail)

    def test_metrics_and_pass_rate(self):
        """Verify calculation of total_scans, pass_count, fail_count, review_count, pass_rate."""
        self._seed_scan("s1", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")
        self._seed_scan("s2", "Edible Oil", "PASS", "2026-09-06T11:00:00Z")
        self._seed_scan("s3", "Edible Oil", "FAIL", "2026-09-06T12:00:00Z")
        self._seed_scan("s4", "Edible Oil", "NEEDS_REVIEW", "2026-09-06T13:00:00Z")

        resp = get_analytics(period="all", repo=self.repo)
        self.assertEqual(resp.total_scans, 4)
        self.assertEqual(resp.pass_count, 2)
        self.assertEqual(resp.fail_count, 1)
        self.assertEqual(resp.review_count, 1)
        self.assertEqual(resp.pass_rate, 50.0)

    def test_daily_trend_aggregation(self):
        """Daily trend aggregates daily volume, compliant, non_compliant, needs_review."""
        self._seed_scan("s1", "Edible Oil", "PASS", "2026-09-05T10:00:00Z")
        self._seed_scan("s2", "Edible Oil", "FAIL", "2026-09-05T11:00:00Z")
        self._seed_scan("s3", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")

        resp = get_analytics(period="all", repo=self.repo)
        self.assertEqual(len(resp.daily_trend), 2)
        day1 = resp.daily_trend[0]
        self.assertEqual(day1.date, "2026-09-05")
        self.assertEqual(day1.scans, 2)
        self.assertEqual(day1.compliant, 1)
        self.assertEqual(day1.non_compliant, 1)

        day2 = resp.daily_trend[1]
        self.assertEqual(day2.date, "2026-09-06")
        self.assertEqual(day2.scans, 1)
        self.assertEqual(day2.compliant, 1)

    def test_top_violations_aggregation(self):
        """Top violations are grouped, counted, and ranked by frequency."""
        self._seed_scan("s1", "Edible Oil", "FAIL", "2026-09-06T10:00:00Z")
        self._seed_scan("s2", "Edible Oil", "FAIL", "2026-09-06T11:00:00Z")
        self._seed_violation("s1", "Rule-6(1)(e)", "Missing Unit Sale Price")
        self._seed_violation("s2", "Rule-6(1)(e)", "Missing Unit Sale Price")
        self._seed_violation("s2", "Rule-6(1)(a)", "Incomplete Manufacturer Address")

        resp = get_analytics(period="all", repo=self.repo)
        self.assertEqual(len(resp.top_violations), 2)
        self.assertEqual(resp.top_violations[0].rule_code, "Rule-6(1)(e)")
        self.assertEqual(resp.top_violations[0].count, 2)
        self.assertEqual(resp.top_violations[1].rule_code, "Rule-6(1)(a)")
        self.assertEqual(resp.top_violations[1].count, 1)

    def test_category_breakdown(self):
        """By-category breakdown aggregates total, pass, fail, and review counts."""
        self._seed_scan("s1", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")
        self._seed_scan("s2", "Edible Oil", "FAIL", "2026-09-06T11:00:00Z")
        self._seed_scan("s3", "Food Grains", "PASS", "2026-09-06T12:00:00Z")

        resp = get_analytics(period="all", repo=self.repo)
        self.assertIn("Edible Oil", resp.by_category)
        self.assertIn("Food Grains", resp.by_category)

        oil_stats = resp.by_category["Edible Oil"]
        self.assertEqual(oil_stats.total, 2)
        self.assertEqual(oil_stats.pass_, 1)
        self.assertEqual(oil_stats.fail, 1)
        self.assertEqual(oil_stats.review, 0)

        # Verify serialization alias 'pass'
        dumped = oil_stats.model_dump(by_alias=True)
        self.assertEqual(dumped["pass"], 1)

    def test_response_shape_exact_keys(self):
        """Verify response conforms strictly to docs/api.md Section 4 top-level keys."""
        self._seed_scan("s1", "Edible Oil", "PASS", "2026-09-06T10:00:00Z")
        resp = get_analytics(period="7d", repo=self.repo)
        dumped = resp.model_dump(by_alias=True)

        expected_keys = {
            "total_scans",
            "pass_count",
            "fail_count",
            "review_count",
            "pass_rate",
            "daily_trend",
            "top_violations",
            "by_category",
        }
        self.assertEqual(set(dumped.keys()), expected_keys)

    def test_repository_dependency_used(self):
        """Ensure endpoint delegates query to the injected BaseScanRepository dependency."""
        mock_repo = MagicMock(spec=InMemoryScanRepository)
        mock_repo.query_analytics.return_value = {
            "total_scans": 10,
            "pass_count": 8,
            "fail_count": 1,
            "review_count": 1,
            "pass_rate": 80.0,
            "daily_trend": [],
            "top_violations": [],
            "by_category": {},
        }

        resp = get_analytics(period="30d", repo=mock_repo)
        mock_repo.query_analytics.assert_called_once_with(period="30d")
        self.assertEqual(resp.total_scans, 10)
        self.assertEqual(resp.pass_rate, 80.0)


if __name__ == "__main__":
    unittest.main()
