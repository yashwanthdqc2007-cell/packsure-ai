"""
Unit tests for Repository History queries (backend/app/database/connection.py).

Verifies:
1. Pagination behavior (page, limit, total, total_pages).
2. Verdict filtering (PASS, FAIL, NEEDS_REVIEW).
3. Category filtering (exact and partial match).
4. Free-text search across scan ID, product category, and extracted product name.
5. ISO date boundaries (from_date, to_date).
6. Resolution of product_name from extracted generic_name declaration.
7. Safe handling of empty repository results.
8. Chronological sorting (newest scans first).
"""

from datetime import datetime, timezone
import unittest

from app.database.connection import InMemoryScanRepository
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)


class TestRepositoryHistory(unittest.TestCase):
    """Test suite for repository history pagination, filtering, and search."""

    def setUp(self):
        self.repo = InMemoryScanRepository()

    def _seed_scan(self, scan_id: str, category: str, verdict: str, created_at: str, product_name: str = None):
        self.repo.scans[scan_id] = {
            "id": scan_id,
            "user_id": "inspector-1",
            "status": "complete",
            "verdict": verdict,
            "compliance_score": 90.0 if verdict == "PASS" else 50.0,
            "product_category": category,
            "image_url": f"storage/scans/{scan_id}/original.jpg",
            "processed_image_url": f"storage/scans/{scan_id}/original.jpg",
            "evidence_image_url": f"storage/scans/{scan_id}/evidence.jpg",
            "reviewer_notes": None,
            "created_at": created_at,
            "completed_at": created_at,
        }
        if product_name:
            self.repo.declarations[scan_id] = [
                ExtractedDeclaration(
                    field_name="generic_name",
                    status=DeclarationStatus.detected,
                    raw_value=product_name,
                    normalized_value=product_name,
                    confidence=0.98,
                    source=DeclarationSource.gemini,
                )
            ]

    def test_empty_history(self):
        """Querying an empty repository returns 0 totals and empty list."""
        res = self.repo.query_history(page=1, limit=20)
        self.assertEqual(res["total"], 0)
        self.assertEqual(res["page"], 1)
        self.assertEqual(res["limit"], 20)
        self.assertEqual(res["total_pages"], 0)
        self.assertEqual(res["results"], [])

    def test_history_pagination(self):
        """Test page and limit slicing with total_pages calculation."""
        for i in range(1, 6):
            self._seed_scan(
                scan_id=f"scan-00{i}",
                category="Edible Oil",
                verdict="PASS",
                created_at=f"2026-09-0{i}T10:00:00Z",
                product_name=f"Oil Product {i}",
            )

        # Page 1 with limit 2
        p1 = self.repo.query_history(page=1, limit=2)
        self.assertEqual(p1["total"], 5)
        self.assertEqual(p1["total_pages"], 3)
        self.assertEqual(len(p1["results"]), 2)
        self.assertEqual(p1["results"][0]["id"], "scan-005")  # Newest first

        # Page 3 with limit 2 (last item)
        p3 = self.repo.query_history(page=3, limit=2)
        self.assertEqual(len(p3["results"]), 1)
        self.assertEqual(p3["results"][0]["id"], "scan-001")

        # Page out of bounds
        p4 = self.repo.query_history(page=4, limit=2)
        self.assertEqual(len(p4["results"]), 0)

    def test_history_verdict_filtering(self):
        """Filter scans by PASS, FAIL, or NEEDS_REVIEW."""
        self._seed_scan("s-pass", "Food Grains", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-fail", "Food Grains", "FAIL", "2026-09-02T10:00:00Z")
        self._seed_scan("s-review", "Food Grains", "NEEDS_REVIEW", "2026-09-03T10:00:00Z")

        res_pass = self.repo.query_history(verdict="PASS")
        self.assertEqual(res_pass["total"], 1)
        self.assertEqual(res_pass["results"][0]["id"], "s-pass")

        res_fail = self.repo.query_history(verdict="FAIL")
        self.assertEqual(res_fail["total"], 1)
        self.assertEqual(res_fail["results"][0]["id"], "s-fail")

        res_review = self.repo.query_history(verdict="NEEDS_REVIEW")
        self.assertEqual(res_review["total"], 1)
        self.assertEqual(res_review["results"][0]["id"], "s-review")

    def test_history_category_filtering(self):
        """Filter scans by category name."""
        self._seed_scan("s-oil", "Edible Oil", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-grain", "Food Grains", "PASS", "2026-09-02T10:00:00Z")

        res = self.repo.query_history(category="Food Grains")
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["results"][0]["id"], "s-grain")

    def test_history_search_filter(self):
        """Search across scan ID, product category, and product name."""
        self._seed_scan("s-100", "Edible Oil", "PASS", "2026-09-01T10:00:00Z", product_name="SunFresh Refined Sunflower Oil")
        self._seed_scan("s-200", "Food Grains", "FAIL", "2026-09-02T10:00:00Z", product_name="Golden Harvest Basmati Rice")

        # Search by product name
        res_name = self.repo.query_history(search="SunFresh")
        self.assertEqual(res_name["total"], 1)
        self.assertEqual(res_name["results"][0]["id"], "s-100")

        # Search by scan ID
        res_id = self.repo.query_history(search="s-200")
        self.assertEqual(res_id["total"], 1)
        self.assertEqual(res_id["results"][0]["id"], "s-200")

        # Search by category keyword
        res_cat = self.repo.query_history(search="Grains")
        self.assertEqual(res_cat["total"], 1)
        self.assertEqual(res_cat["results"][0]["id"], "s-200")

    def test_history_date_boundary_filtering(self):
        """Filter scans with from_date and to_date boundaries."""
        self._seed_scan("s-aug", "Snacks", "PASS", "2026-08-25T10:00:00Z")
        self._seed_scan("s-sep-start", "Snacks", "PASS", "2026-09-01T12:00:00Z")
        self._seed_scan("s-sep-end", "Snacks", "PASS", "2026-09-05T15:00:00Z")

        res_from = self.repo.query_history(from_date="2026-09-01")
        self.assertEqual(res_from["total"], 2)

        res_to = self.repo.query_history(to_date="2026-08-31")
        self.assertEqual(res_to["total"], 1)
        self.assertEqual(res_to["results"][0]["id"], "s-aug")

        res_range = self.repo.query_history(from_date="2026-09-01", to_date="2026-09-03")
        self.assertEqual(res_range["total"], 1)
        self.assertEqual(res_range["results"][0]["id"], "s-sep-start")

    def test_generic_name_to_product_name_mapping(self):
        """Extracted generic_name declaration must map to product_name."""
        self._seed_scan("s-decl", "Beverages", "PASS", "2026-09-01T10:00:00Z", product_name="Sparkling Spring Water 500ml")
        res = self.repo.query_history()
        self.assertEqual(res["results"][0]["product_name"], "Sparkling Spring Water 500ml")
        self.assertEqual(res["results"][0]["scanned_at"], "2026-09-01T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
