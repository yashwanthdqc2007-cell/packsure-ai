"""
Unit tests for PackSure AI History API (Phase 8C).

Verifies:
1. Default history request returns 200 OK + valid ScanHistoryResponse structure.
2. Pagination parameter handling (page, limit, total_pages).
3. Verdict filtering (PASS, FAIL, NEEDS_REVIEW).
4. Category filtering.
5. Text search query filtering across product name, category, and ID.
6. Date boundaries (from_date, to_date).
7. Empty history response structure and zero-state handling.
8. Exact response shape conforming to docs/api.md Section 3.
9. Invalid page validation (HTTP 422 / Query constraint).
10. Invalid limit validation (HTTP 422 / Query constraint).
11. Invalid verdict value rejected with HTTP 400 Bad Request.
12. Endpoint strictly relies on the repository abstraction.
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes.history import get_history
from app.database.connection import InMemoryScanRepository
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.scan import ScanHistoryResponse, ScanStatus


class TestHistoryAPI(unittest.TestCase):
    """Test suite for GET /api/v1/history endpoint."""

    def setUp(self):
        self.repo = InMemoryScanRepository()

    def _seed_scan(self, scan_id: str, category: str, verdict: str, created_at: str, product_name: str = None):
        self.repo.scans[scan_id] = {
            "id": scan_id,
            "user_id": "inspector-1",
            "status": "complete",
            "verdict": verdict,
            "compliance_score": 96.0 if verdict == "PASS" else 68.0,
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

    def test_empty_history_response(self):
        """Empty database returns valid ScanHistoryResponse with empty results."""
        resp: ScanHistoryResponse = get_history(repo=self.repo)
        self.assertEqual(resp.total, 0)
        self.assertEqual(resp.page, 1)
        self.assertEqual(resp.limit, 20)
        self.assertEqual(resp.total_pages, 0)
        self.assertEqual(resp.results, [])

    def test_default_history_request(self):
        """Default request returns paginated list with page=1, limit=20."""
        self._seed_scan("s-1", "Edible Oil", "PASS", "2026-09-06T10:42:00Z", product_name="SunFresh Refined Sunflower Oil")
        self._seed_scan("s-2", "Food Grains", "FAIL", "2026-09-06T09:18:00Z", product_name="Golden Harvest Rice")

        resp: ScanHistoryResponse = get_history(repo=self.repo)
        self.assertEqual(resp.total, 2)
        self.assertEqual(resp.page, 1)
        self.assertEqual(resp.limit, 20)
        self.assertEqual(resp.total_pages, 1)
        self.assertEqual(len(resp.results), 2)

        # Check newest first
        self.assertEqual(resp.results[0].id, "s-1")
        self.assertEqual(resp.results[0].product_name, "SunFresh Refined Sunflower Oil")
        self.assertEqual(resp.results[0].category, "Edible Oil")
        self.assertEqual(resp.results[0].verdict.value, "PASS")
        self.assertEqual(resp.results[0].compliance_score, 96.0)

    def test_pagination_parameters(self):
        """Test custom page and limit parameters."""
        for i in range(1, 6):
            self._seed_scan(f"scan-{i}", "Edible Oil", "PASS", f"2026-09-0{i}T10:00:00Z")

        # Page 1, limit 2
        p1: ScanHistoryResponse = get_history(page=1, limit=2, repo=self.repo)
        self.assertEqual(p1.total, 5)
        self.assertEqual(p1.total_pages, 3)
        self.assertEqual(len(p1.results), 2)

        # Page 2, limit 2
        p2: ScanHistoryResponse = get_history(page=2, limit=2, repo=self.repo)
        self.assertEqual(len(p2.results), 2)

        # Page 3, limit 2
        p3: ScanHistoryResponse = get_history(page=3, limit=2, repo=self.repo)
        self.assertEqual(len(p3.results), 1)

    def test_verdict_filter(self):
        """Filter history by verdict PASS, FAIL, or NEEDS_REVIEW."""
        self._seed_scan("s-pass", "Edible Oil", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-fail", "Edible Oil", "FAIL", "2026-09-02T10:00:00Z")

        resp_pass: ScanHistoryResponse = get_history(verdict="PASS", repo=self.repo)
        self.assertEqual(resp_pass.total, 1)
        self.assertEqual(resp_pass.results[0].id, "s-pass")

        resp_fail: ScanHistoryResponse = get_history(verdict="fail", repo=self.repo)  # case-insensitive
        self.assertEqual(resp_fail.total, 1)
        self.assertEqual(resp_fail.results[0].id, "s-fail")

    def test_category_filter(self):
        """Filter history by category."""
        self._seed_scan("s-oil", "Edible Oil", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-rice", "Food Grains", "FAIL", "2026-09-02T10:00:00Z")

        resp: ScanHistoryResponse = get_history(category="Food Grains", repo=self.repo)
        self.assertEqual(resp.total, 1)
        self.assertEqual(resp.results[0].id, "s-rice")

    def test_search_filter(self):
        """Search across product name, category, and ID."""
        self._seed_scan("s-abc-123", "Snacks", "PASS", "2026-09-01T10:00:00Z", product_name="Crispy Potato Chips")

        # Search by product name
        res1: ScanHistoryResponse = get_history(search="Potato", repo=self.repo)
        self.assertEqual(res1.total, 1)
        self.assertEqual(res1.results[0].id, "s-abc-123")

        # Search by scan ID
        res2: ScanHistoryResponse = get_history(search="abc-123", repo=self.repo)
        self.assertEqual(res2.total, 1)

        # Unmatched search
        res3: ScanHistoryResponse = get_history(search="NonExistent", repo=self.repo)
        self.assertEqual(res3.total, 0)

    def test_date_boundary_filters(self):
        """Filter history by from_date and to_date."""
        self._seed_scan("s-aug", "Snacks", "PASS", "2026-08-25T10:00:00Z")
        self._seed_scan("s-sep-1", "Snacks", "PASS", "2026-09-01T10:00:00Z")
        self._seed_scan("s-sep-5", "Snacks", "PASS", "2026-09-05T10:00:00Z")

        resp_from: ScanHistoryResponse = get_history(from_date="2026-09-01", repo=self.repo)
        self.assertEqual(resp_from.total, 2)

        resp_to: ScanHistoryResponse = get_history(to_date="2026-08-31", repo=self.repo)
        self.assertEqual(resp_to.total, 1)
        self.assertEqual(resp_to.results[0].id, "s-aug")

    def test_invalid_verdict_rejected(self):
        """Invalid verdict value must raise HTTP 400 Bad Request."""
        with self.assertRaises(HTTPException) as ctx:
            get_history(verdict="INVALID_VERDICT", repo=self.repo)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid verdict filter", ctx.exception.detail)

    def test_response_shape_exact_keys(self):
        """Response model serialization strictly matches docs/api.md Section 3."""
        self._seed_scan("s-shape", "Edible Oil", "PASS", "2026-09-06T10:42:00Z", product_name="SunFresh Refined Sunflower Oil")

        resp: ScanHistoryResponse = get_history(repo=self.repo)
        dumped = resp.model_dump()

        expected_top_keys = {"total", "page", "limit", "total_pages", "results"}
        self.assertEqual(set(dumped.keys()), expected_top_keys)

        expected_item_keys = {
            "id",
            "product_name",
            "category",
            "scanned_at",
            "verdict",
            "compliance_score",
            "status",
        }
        self.assertEqual(set(dumped["results"][0].keys()), expected_item_keys)

    def test_repository_dependency_used(self):
        """Verify endpoint queries repository via provided dependency."""
        mock_repo = MagicMock(spec=InMemoryScanRepository)
        mock_repo.query_history.return_value = {
            "total": 1,
            "page": 1,
            "limit": 20,
            "total_pages": 1,
            "results": [
                {
                    "id": "mock-scan-id",
                    "product_name": "Mock Product",
                    "category": "Mock Category",
                    "scanned_at": "2026-09-06T10:00:00Z",
                    "verdict": "PASS",
                    "compliance_score": 95.0,
                    "status": "complete",
                }
            ],
        }

        resp = get_history(page=1, limit=20, repo=mock_repo)
        mock_repo.query_history.assert_called_once_with(
            page=1,
            limit=20,
            verdict=None,
            category=None,
            search=None,
            from_date=None,
            to_date=None,
        )
        self.assertEqual(resp.total, 1)
        self.assertEqual(resp.results[0].id, "mock-scan-id")


    def test_invalid_page_rejected(self):
        """Invalid page parameter (< 1) must raise HTTP 400."""
        with self.assertRaises(HTTPException) as ctx:
            get_history(page=0, repo=self.repo)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("page", str(ctx.exception.detail))

    def test_invalid_limit_rejected(self):
        """Invalid limit parameter (< 1 or > 100) must raise HTTP 400."""
        with self.assertRaises(HTTPException) as ctx1:
            get_history(limit=0, repo=self.repo)
        self.assertEqual(ctx1.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx2:
            get_history(limit=101, repo=self.repo)
        self.assertEqual(ctx2.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

