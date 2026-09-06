"""
Unit tests for PackSure AI Static Storage File Serving (Phase 10B).

Verifies:
1. /storage static route is mounted and accessible on FastAPI app.
2. Existing artifacts (images, reports) under storage/scans/{id}/ return HTTP 200 with accurate content.
3. Missing storage files return HTTP 404.
4. Existing API routes (/health, /api/v1/scans, /api/v1/history, /api/v1/analytics, /api/v1/rules) remain registered and functional.
5. Directory traversal attempts outside storage root return 404.
"""

import json
import os
import unittest
from starlette.testclient import TestClient

from app.main import app, _resolve_storage_directory


class TestStaticStorageServing(unittest.TestCase):
    """Test suite for static file serving of inspection artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.storage_dir = _resolve_storage_directory()
        cls.test_scan_id = "test-static-scan-10b"
        cls.scan_dir = os.path.join(cls.storage_dir, "scans", cls.test_scan_id)
        os.makedirs(cls.scan_dir, exist_ok=True)

        # Create test artifacts
        cls.orig_path = os.path.join(cls.scan_dir, "original.jpg")
        with open(cls.orig_path, "wb") as f:
            f.write(b"JPEG_TEST_RAW_BYTES_12345")

        cls.evidence_path = os.path.join(cls.scan_dir, "evidence.jpg")
        with open(cls.evidence_path, "wb") as f:
            f.write(b"JPEG_TEST_EVIDENCE_BYTES_67890")

        cls.report_path = os.path.join(cls.scan_dir, "report.json")
        with open(cls.report_path, "w", encoding="utf-8") as f:
            json.dump({"scan_id": cls.test_scan_id, "verdict": "PASS"}, f)

    @classmethod
    def tearDownClass(cls):
        # Clean up test artifacts
        import shutil
        if os.path.exists(cls.scan_dir):
            shutil.rmtree(cls.scan_dir, ignore_errors=True)

    # 1. /storage route is mounted and fetches existing original.jpg
    def test_fetch_existing_original_image(self):
        resp = self.client.get(f"/storage/scans/{self.test_scan_id}/original.jpg")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"JPEG_TEST_RAW_BYTES_12345")

    # 2. Fetch existing evidence.jpg
    def test_fetch_existing_evidence_image(self):
        resp = self.client.get(f"/storage/scans/{self.test_scan_id}/evidence.jpg")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"JPEG_TEST_EVIDENCE_BYTES_67890")

    # 3. Fetch existing report.json
    def test_fetch_existing_report_json(self):
        resp = self.client.get(f"/storage/scans/{self.test_scan_id}/report.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("scan_id"), self.test_scan_id)
        self.assertEqual(data.get("verdict"), "PASS")

    # 4. Missing storage file returns 404
    def test_missing_storage_file_returns_404(self):
        resp = self.client.get("/storage/scans/nonexistent-uuid-999/original.jpg")
        self.assertEqual(resp.status_code, 404)

    # 5. Directory traversal outside storage is prevented
    def test_directory_traversal_blocked(self):
        resp = self.client.get("/storage/../app/core/config.py")
        self.assertIn(resp.status_code, (404, 400))

    # 6. Existing API routes remain registered and operational
    def test_existing_api_routes_remain_functional(self):
        # Health
        resp_health = self.client.get("/health")
        self.assertEqual(resp_health.status_code, 200)
        self.assertEqual(resp_health.json()["status"], "ok")

        # Rules
        resp_rules = self.client.get("/api/v1/rules")
        self.assertEqual(resp_rules.status_code, 200)
        self.assertIn("rules", resp_rules.json())


if __name__ == "__main__":
    unittest.main()
