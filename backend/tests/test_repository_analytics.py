"""
Unit tests for Repository Analytics queries (backend/app/database/connection.py).

Verifies:
1. Analytics calculations for periods: '7d', '30d', 'all'.
2. Accurate total_scans, pass_count, fail_count, review_count.
3. Accurate pass_rate percentage calculation and zero-scan fallback (0.0).
4. Daily trend chronological aggregation with compliant, non_compliant, needs_review counts.
5. Top violations aggregation ranked by occurrence count.
6. Category breakdown metrics (total, pass, fail, review).
7. Zero-scan empty state handling.
"""

from datetime import datetime, timedelta, timezone
import unittest

from app.database.connection import InMemoryScanRepository
from app.schemas.violation import Violation, ViolationSeverity, ViolationType


class TestRepositoryAnalytics(unittest.TestCase):
    """Test suite for repository analytics aggregations and time-windowing."""

    def setUp(self):
        self.repo = InMemoryScanRepository()

    def _seed_scan(self, scan_id: str, category: str, verdict: str, created_at: str, violations=None):
        self.repo.scans[scan_id] = {
            "id": scan_id,
            "user_id": "inspector-1",
            "status": "complete",
            "verdict": verdict,
            "compliance_score": 90.0 if verdict == "PASS" else 40.0,
            "product_category": category,
            "created_at": created_at,
            "completed_at": created_at,
        }
        if violations:
            self.repo.violations[scan_id] = violations

    def test_zero_scan_analytics(self):
        """Zero scans return 0 totals, 0.0 pass rate, and empty collections."""
        analytics = self.repo.query_analytics(period="7d")
        self.assertEqual(analytics["total_scans"], 0)
        self.assertEqual(analytics["pass_count"], 0)
        self.assertEqual(analytics["fail_count"], 0)
        self.assertEqual(analytics["review_count"], 0)
        self.assertEqual(analytics["pass_rate"], 0.0)
        self.assertEqual(analytics["daily_trend"], [])
        self.assertEqual(analytics["top_violations"], [])
        self.assertEqual(analytics["by_category"], {})

    def test_analytics_metrics_and_pass_rate(self):
        """Calculate pass, fail, review counts and pass_rate accurately."""
        now = datetime.now(timezone.utc)
        iso_now = now.isoformat()

        self._seed_scan("s1", "Edible Oil", "PASS", iso_now)
        self._seed_scan("s2", "Edible Oil", "PASS", iso_now)
        self._seed_scan("s3", "Edible Oil", "FAIL", iso_now)
        self._seed_scan("s4", "Food Grains", "NEEDS_REVIEW", iso_now)

        analytics = self.repo.query_analytics(period="7d")
        self.assertEqual(analytics["total_scans"], 4)
        self.assertEqual(analytics["pass_count"], 2)
        self.assertEqual(analytics["fail_count"], 1)
        self.assertEqual(analytics["review_count"], 1)
        self.assertEqual(analytics["pass_rate"], 50.0)  # 2 / 4 = 50.0%

    def test_analytics_period_windowing(self):
        """Ensure 7d, 30d, and all filter scans appropriately."""
        now = datetime.now(timezone.utc)

        ts_today = now.isoformat()
        ts_10d_ago = (now - timedelta(days=10)).isoformat()
        ts_40d_ago = (now - timedelta(days=40)).isoformat()

        self._seed_scan("s-recent", "Snacks", "PASS", ts_today)
        self._seed_scan("s-medium", "Snacks", "FAIL", ts_10d_ago)
        self._seed_scan("s-old", "Snacks", "PASS", ts_40d_ago)

        # 7d period should only include s-recent
        a_7d = self.repo.query_analytics(period="7d")
        self.assertEqual(a_7d["total_scans"], 1)
        self.assertEqual(a_7d["pass_count"], 1)

        # 30d period should include s-recent and s-medium
        a_30d = self.repo.query_analytics(period="30d")
        self.assertEqual(a_30d["total_scans"], 2)
        self.assertEqual(a_30d["pass_count"], 1)
        self.assertEqual(a_30d["fail_count"], 1)

        # all period should include all 3
        a_all = self.repo.query_analytics(period="all")
        self.assertEqual(a_all["total_scans"], 3)
        self.assertEqual(a_all["pass_count"], 2)

    def test_daily_trend_aggregation(self):
        """Aggregate daily activity chronologically."""
        self._seed_scan("s1", "Edible Oil", "PASS", "2026-08-31T10:00:00Z")
        self._seed_scan("s2", "Edible Oil", "FAIL", "2026-08-31T14:00:00Z")
        self._seed_scan("s3", "Edible Oil", "NEEDS_REVIEW", "2026-08-31T18:00:00Z")
        self._seed_scan("s4", "Food Grains", "PASS", "2026-09-01T09:00:00Z")

        analytics = self.repo.query_analytics(period="all")
        trend = analytics["daily_trend"]
        self.assertEqual(len(trend), 2)

        # 2026-08-31
        self.assertEqual(trend[0]["date"], "2026-08-31")
        self.assertEqual(trend[0]["scans"], 3)
        self.assertEqual(trend[0]["compliant"], 1)
        self.assertEqual(trend[0]["non_compliant"], 1)
        self.assertEqual(trend[0]["needs_review"], 1)

        # 2026-09-01
        self.assertEqual(trend[1]["date"], "2026-09-01")
        self.assertEqual(trend[1]["scans"], 1)
        self.assertEqual(trend[1]["compliant"], 1)

    def test_top_violations_ranking(self):
        """Top violations must be counted and ordered by frequency."""
        now = datetime.now(timezone.utc).isoformat()
        v_mrp = Violation(
            rule_code="Rule-6(1)(e)",
            field_name="mrp",
            violation_type=ViolationType.invalid_format,
            severity=ViolationSeverity.critical,
            description="Missing Unit Sale Price",
        )
        v_addr = Violation(
            rule_code="Rule-6(1)(a)",
            field_name="manufacturer_name_and_address",
            violation_type=ViolationType.missing_declaration,
            severity=ViolationSeverity.critical,
            description="Incomplete Manufacturer Address",
        )

        self._seed_scan("s1", "Edible Oil", "FAIL", now, violations=[v_mrp, v_addr])
        self._seed_scan("s2", "Edible Oil", "FAIL", now, violations=[v_mrp])

        analytics = self.repo.query_analytics(period="7d")
        top_v = analytics["top_violations"]
        self.assertEqual(len(top_v), 2)

        # Rule-6(1)(e) has count=2, Rule-6(1)(a) has count=1
        self.assertEqual(top_v[0]["rule_code"], "Rule-6(1)(e)")
        self.assertEqual(top_v[0]["count"], 2)
        self.assertEqual(top_v[0]["description"], "Missing Unit Sale Price")

        self.assertEqual(top_v[1]["rule_code"], "Rule-6(1)(a)")
        self.assertEqual(top_v[1]["count"], 1)

    def test_by_category_breakdown(self):
        """Group compliance counts by category."""
        now = datetime.now(timezone.utc).isoformat()
        self._seed_scan("s1", "Edible Oil", "PASS", now)
        self._seed_scan("s2", "Edible Oil", "FAIL", now)
        self._seed_scan("s3", "Food Grains", "PASS", now)
        self._seed_scan("s4", "Food Grains", "NEEDS_REVIEW", now)

        analytics = self.repo.query_analytics(period="7d")
        cats = analytics["by_category"]

        self.assertEqual(cats["Edible Oil"]["total"], 2)
        self.assertEqual(cats["Edible Oil"]["pass"], 1)
        self.assertEqual(cats["Edible Oil"]["fail"], 1)
        self.assertEqual(cats["Edible Oil"]["review"], 0)

        self.assertEqual(cats["Food Grains"]["total"], 2)
        self.assertEqual(cats["Food Grains"]["pass"], 1)
        self.assertEqual(cats["Food Grains"]["fail"], 0)
        self.assertEqual(cats["Food Grains"]["review"], 1)


if __name__ == "__main__":
    unittest.main()
