"""
Unit tests for PackSure AI Scan API & Database Persistence (Phase 7).

Verifies:
1. POST /api/v1/scans valid image returns HTTP 202 + pending status + valid UUID.
2. POST /api/v1/scans with invalid file format returns HTTP 400.
3. POST /api/v1/scans with corrupt/missing image returns appropriate error.
4. Background worker transitions scan from pending -> processing -> complete.
5. Completed ComplianceResult is accurately persisted to repository.
6. Extracted declarations are accurately persisted and retrieved.
7. Violations are accurately persisted and retrieved.
8. NEEDS_REVIEW verdict is persisted without converting to FAIL/PASS.
9. Upstream pipeline failures never produce PASS in persistence.
10. GET /api/v1/scans/{id} returns full completed ScanResponse payload.
11. GET /api/v1/scans/{id} on nonexistent UUID returns HTTP 404.
12. PATCH /api/v1/scans/{id}/review resolves NEEDS_REVIEW -> PASS.
13. PATCH /api/v1/scans/{id}/review resolves NEEDS_REVIEW -> FAIL.
14. PATCH /api/v1/scans/{id}/review rejects review of already finalized scan (HTTP 400).
15. Corrected declarations from review are stored with source=manual.
16. Retry replaces child declaration and violation rows idempotently without duplication.
17. Unsafe filenames cannot escape UUID-based storage path.
18. Database absence in production raises error and does NOT silently use in-memory fake.
19. Repository dependency injection allows clean test overrides.
20. Original uploaded bytes are stored accurately without corruption.
"""

import asyncio
from io import BytesIO
import os
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from fastapi import BackgroundTasks, HTTPException, UploadFile
from fastapi.datastructures import Headers

from app.api.dependencies import get_db_repository
from app.api.routes.scans import create_scan, get_scan, process_scan_background, review_scan
from app.database.connection import (
    BaseScanRepository,
    InMemoryScanRepository,
    SupabaseScanRepository,
    get_repository,
)
from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
)
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.image import ImageQualityReport, QualityMetrics, QualityStatus
from app.schemas.ocr import BoundingBox
from app.schemas.scan import (
    CorrectedDeclaration,
    ScanInitResponse,
    ScanResponse,
    ScanReviewRequest,
    ScanStatus,
)
from app.schemas.violation import Violation, ViolationSeverity, ViolationType


def _create_synthetic_sharp_image(width=800, height=800, brightness=128) -> np.ndarray:
    """Generate high-contrast sharp synthetic image array."""
    img = np.full((height, width, 3), brightness, dtype=np.uint8)
    for y in range(50, height - 50, 40):
        for x in range(50, width - 50, 60):
            img[y : y + 20, x : x + 30] = [20, 20, 20]
            img[y + 10 : y + 30, x + 25 : x + 55] = [240, 240, 240]
    return img


def _create_mock_upload_file(file_bytes: bytes, filename: str = "test.png", content_type: str = "image/png") -> UploadFile:
    """Create a mock FastAPI UploadFile instance."""
    return UploadFile(
        file=BytesIO(file_bytes),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class TestScansAPIAndPersistence(unittest.TestCase):
    """Test suite for Scan API routes, background workers, and repository persistence."""

    def setUp(self):
        self.repo = InMemoryScanRepository()
        self.sharp_img = _create_synthetic_sharp_image(800, 800, 128)

        # Valid PNG byte payload header
        self.valid_png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x03 \x00\x00\x03 \x08\x02\x00\x00\x00"
            + b"\x00" * 2000
        )

        self.compliant_declarations = [
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 150.00 incl. of all taxes",
                normalized_value="150.00",
                confidence=0.98,
                bounding_box=BoundingBox(x=10, y=10, width=100, height=20),
                source=DeclarationSource.hybrid,
            )
        ]

        self.violation_item = Violation(
            rule_code="Rule-6(1)(e)",
            rule_id="LMR-R06-1-E",
            field_name="mrp",
            violation_type=ViolationType.invalid_format,
            severity=ViolationSeverity.critical,
            description="MRP missing tax clause.",
        )

    # 1. POST valid image -> 202 + pending + UUID
    @patch("app.api.routes.scans.validate_image_file")
    def test_post_valid_image_returns_202_and_pending_status(self, mock_val):
        mock_val.return_value = (True, None, self.sharp_img)
        bg_tasks = BackgroundTasks()
        upload_file = _create_mock_upload_file(self.valid_png_bytes, "pkg.png")

        resp = asyncio.run(
            create_scan(
                background_tasks=bg_tasks,
                image=upload_file,
                product_category="Food",
                user_id="user-123",
                repo=self.repo,
            )
        )

        self.assertIsInstance(resp, ScanInitResponse)
        self.assertEqual(resp.status, ScanStatus.pending)
        self.assertTrue(len(resp.scan_id) > 10)

        # Verify initial pending record in repo
        persisted = self.repo.get_scan(resp.scan_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "pending")

    # 2. POST invalid file -> 400
    @patch("app.api.routes.scans.validate_image_file")
    def test_post_invalid_file_returns_400(self, mock_val):
        mock_val.return_value = (False, "Unsupported format. Supported: JPEG, PNG, WebP.", None)
        bg_tasks = BackgroundTasks()
        upload_file = _create_mock_upload_file(b"%PDF-1.4...", "doc.pdf")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                create_scan(
                    background_tasks=bg_tasks,
                    image=upload_file,
                    repo=self.repo,
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported format", str(ctx.exception.detail))

    # 3. POST corrupt payload raises 400
    @patch("app.api.routes.scans.validate_image_file")
    def test_post_corrupt_payload_returns_400(self, mock_val):
        mock_val.return_value = (False, "Corrupt or unreadable image file data", None)
        bg_tasks = BackgroundTasks()
        upload_file = _create_mock_upload_file(b"\xff\xd8\xffGARBAGE", "corrupt.jpg")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                create_scan(
                    background_tasks=bg_tasks,
                    image=upload_file,
                    repo=self.repo,
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    # 4. Background worker transitions pending -> processing -> complete
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_background_worker_transitions_to_complete(self, mock_pipeline):
        mock_pipeline.return_value = (
            ImageQualityReport(
                is_valid=True, quality_score=0.9, status=QualityStatus.acceptable,
                metrics=QualityMetrics(
                    width=800, height=800, total_pixels=640000, resolution_acceptable=True,
                    blur_score=200.0, is_blurry=False, brightness_score=120.0, is_too_dark=False,
                    is_too_bright=False, contrast_score=50.0, is_low_contrast=False,
                ),
            ),
            ComplianceResult(
                verdict=ComplianceVerdict.PASS,
                compliance_score=100.0,
                declarations=self.compliant_declarations,
                violations=[],
                evidence=EvidenceMetadata(rule_version="2026.1", annotated_image_path="storage/scans/s1/evidence.jpg"),
            ),
            self.sharp_img,
        )

        scan_id = "test-scan-101"
        self.repo.create_scan(scan_id=scan_id, product_category="Hardware")

        process_scan_background(
            scan_id=scan_id,
            image_bytes=self.valid_png_bytes,
            filename="pkg.png",
            product_category="Hardware",
            user_id="u1",
            repo=self.repo,
        )

        scan = self.repo.get_scan(scan_id)
        self.assertEqual(scan["status"], "complete")
        self.assertEqual(scan["verdict"], "PASS")
        self.assertEqual(scan["compliance_score"], 100.0)
        self.assertIsNotNone(scan["completed_at"])

    # 5. Completed ComplianceResult persisted correctly
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_completed_compliance_result_persisted_correctly(self, mock_pipeline):
        mock_pipeline.return_value = (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.FAIL,
                compliance_score=70.0,
                declarations=self.compliant_declarations,
                violations=[self.violation_item],
                evidence=EvidenceMetadata(rule_version="2026.1"),
            ),
            self.sharp_img,
        )

        scan_id = "test-scan-102"
        self.repo.create_scan(scan_id=scan_id)

        process_scan_background(
            scan_id=scan_id,
            image_bytes=self.valid_png_bytes,
            filename="pkg.png",
            product_category=None,
            user_id=None,
            repo=self.repo,
        )

        scan = self.repo.get_scan(scan_id)
        self.assertEqual(scan["status"], "complete")
        self.assertEqual(scan["verdict"], "FAIL")
        self.assertEqual(scan["compliance_score"], 70.0)

    # 6. Declarations persisted
    def test_declarations_persisted_and_retrieved(self):
        scan_id = "test-scan-103"
        self.repo.save_declarations(scan_id, self.compliant_declarations)
        fetched = self.repo.get_declarations(scan_id)
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0].field_name, "mrp")
        self.assertEqual(fetched[0].normalized_value, "150.00")

    # 7. Violations persisted
    def test_violations_persisted_and_retrieved(self):
        scan_id = "test-scan-104"
        self.repo.save_violations(scan_id, [self.violation_item])
        fetched = self.repo.get_violations(scan_id)
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0].rule_code, "Rule-6(1)(e)")

    # 8. NEEDS_REVIEW persisted without converting to FAIL/PASS
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_needs_review_persisted_without_converting_to_fail_or_pass(self, mock_pipeline):
        mock_pipeline.return_value = (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=85.0,
                declarations=self.compliant_declarations,
                violations=[],
                evidence=EvidenceMetadata(rule_version="2026.1"),
            ),
            self.sharp_img,
        )

        scan_id = "test-scan-105"
        self.repo.create_scan(scan_id=scan_id)

        process_scan_background(
            scan_id=scan_id,
            image_bytes=self.valid_png_bytes,
            filename="pkg.png",
            product_category=None,
            user_id=None,
            repo=self.repo,
        )

        scan = self.repo.get_scan(scan_id)
        self.assertEqual(scan["status"], "complete")
        self.assertEqual(scan["verdict"], "NEEDS_REVIEW")

    # 9. Upstream pipeline failure never produces PASS
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_upstream_pipeline_failure_never_produces_pass(self, mock_pipeline):
        mock_pipeline.side_effect = RuntimeError("Fatal hardware crash")

        scan_id = "test-scan-106"
        self.repo.create_scan(scan_id=scan_id)

        process_scan_background(
            scan_id=scan_id,
            image_bytes=self.valid_png_bytes,
            filename="pkg.png",
            product_category=None,
            user_id=None,
            repo=self.repo,
        )

        scan = self.repo.get_scan(scan_id)
        self.assertEqual(scan["status"], "failed")
        self.assertNotEqual(scan["verdict"], "PASS")

    # 10. GET existing scan returns ScanResponse
    def test_get_existing_scan(self):
        scan_id = "test-scan-107"
        self.repo.create_scan(scan_id=scan_id, product_category="Food Grains")
        self.repo.update_scan(
            scan_id,
            {
                "status": "complete",
                "verdict": "PASS",
                "compliance_score": 100.0,
                "image_url": "storage/scans/107/original.jpg",
                "completed_at": "2026-09-06T10:00:00Z",
            },
        )
        self.repo.save_declarations(scan_id, self.compliant_declarations)

        resp = get_scan(id=scan_id, repo=self.repo)
        self.assertIsInstance(resp, ScanResponse)
        self.assertEqual(resp.scan_id, scan_id)
        self.assertEqual(resp.status, ScanStatus.complete)
        self.assertEqual(resp.verdict, ComplianceVerdict.PASS)
        self.assertEqual(len(resp.declarations), 1)

    # 11. GET nonexistent scan -> 404
    def test_get_nonexistent_scan_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            get_scan(id="nonexistent-id-999", repo=self.repo)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Scan not found")

    # 12. PATCH review resolves NEEDS_REVIEW -> PASS
    def test_patch_review_resolves_needs_review_to_pass(self):
        scan_id = "test-scan-108"
        self.repo.create_scan(scan_id=scan_id)
        self.repo.update_scan(scan_id, {"status": "complete", "verdict": "NEEDS_REVIEW", "compliance_score": 80.0})

        req = ScanReviewRequest(
            verdict=ComplianceVerdict.PASS,
            reviewer_notes="Verified physical label in person.",
        )
        resp = review_scan(id=scan_id, review_req=req, repo=self.repo)

        self.assertEqual(resp.verdict, ComplianceVerdict.PASS)
        self.assertEqual(resp.reviewer_notes, "Verified physical label in person.")

    # 13. PATCH review resolves NEEDS_REVIEW -> FAIL
    def test_patch_review_resolves_needs_review_to_fail(self):
        scan_id = "test-scan-109"
        self.repo.create_scan(scan_id=scan_id)
        self.repo.update_scan(scan_id, {"status": "complete", "verdict": "NEEDS_REVIEW", "compliance_score": 80.0})

        req = ScanReviewRequest(
            verdict=ComplianceVerdict.FAIL,
            reviewer_notes="Confirmed mandatory address is omitted.",
        )
        resp = review_scan(id=scan_id, review_req=req, repo=self.repo)

        self.assertEqual(resp.verdict, ComplianceVerdict.FAIL)

    # 14. PATCH rejects review of finalized scan
    def test_patch_rejects_review_of_finalized_scan(self):
        scan_id = "test-scan-110"
        self.repo.create_scan(scan_id=scan_id)
        self.repo.update_scan(scan_id, {"status": "complete", "verdict": "PASS", "compliance_score": 100.0})

        req = ScanReviewRequest(verdict=ComplianceVerdict.FAIL)
        with self.assertRaises(HTTPException) as ctx:
            review_scan(id=scan_id, review_req=req, repo=self.repo)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cannot review finalized scan", ctx.exception.detail)

    # 15. Corrected declarations stored with source=manual
    def test_corrected_declarations_stored_with_source_manual(self):
        scan_id = "test-scan-111"
        self.repo.create_scan(scan_id=scan_id)
        self.repo.update_scan(scan_id, {"status": "complete", "verdict": "NEEDS_REVIEW"})
        self.repo.save_declarations(scan_id, self.compliant_declarations)

        req = ScanReviewRequest(
            verdict=ComplianceVerdict.PASS,
            corrected_declarations=[
                CorrectedDeclaration(
                    field_name="mrp",
                    raw_value="MRP Rs. 150.00 incl. of all taxes",
                    normalized_value="150.00",
                    status=DeclarationStatus.detected,
                )
            ],
        )
        resp = review_scan(id=scan_id, review_req=req, repo=self.repo)

        self.assertEqual(len(resp.declarations), 1)
        self.assertEqual(resp.declarations[0].source, DeclarationSource.manual)
        self.assertEqual(resp.declarations[0].confidence, 1.0)

    # 16. Retry replaces child rows without duplication
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_retry_replaces_child_rows_without_duplication(self, mock_pipeline):
        mock_pipeline.return_value = (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.PASS,
                compliance_score=100.0,
                declarations=self.compliant_declarations,
                violations=[],
                evidence=EvidenceMetadata(rule_version="2026.1"),
            ),
            self.sharp_img,
        )

        scan_id = "test-scan-112"
        self.repo.create_scan(scan_id=scan_id)

        # First run
        process_scan_background(scan_id, self.valid_png_bytes, "pkg.png", None, None, self.repo)
        self.assertEqual(len(self.repo.get_declarations(scan_id)), 1)

        # Second run (retry)
        process_scan_background(scan_id, self.valid_png_bytes, "pkg.png", None, None, self.repo)
        # Should still be exactly 1, not 2
        self.assertEqual(len(self.repo.get_declarations(scan_id)), 1)

    # 17. Unsafe filename cannot escape UUID storage directory
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_unsafe_filename_cannot_escape_uuid_directory(self, mock_pipeline):
        mock_pipeline.return_value = (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.PASS,
                compliance_score=100.0,
                declarations=[],
                violations=[],
            ),
            self.sharp_img,
        )
        scan_id = "test-scan-113"
        self.repo.create_scan(scan_id=scan_id)

        # Path traversal attack filename
        process_scan_background(
            scan_id=scan_id,
            image_bytes=self.valid_png_bytes,
            filename="../../etc/passwd",
            product_category=None,
            user_id=None,
            repo=self.repo,
        )

        # File is safely stored under storage/scans/test-scan-113/original.jpg
        expected_path = os.path.join("storage", "scans", scan_id, "original.jpg")
        self.assertTrue(os.path.exists(expected_path))

    # 18. Database absence in production does not silently use memory
    def test_database_absence_in_production_raises_error(self):
        repo = SupabaseScanRepository()
        repo.supabase_url = ""  # Unconfigured
        repo.supabase_key = ""

        with self.assertRaises(RuntimeError) as ctx:
            repo.get_scan("any-id")
        self.assertIn("Production database configuration missing", str(ctx.exception))

    # 19. Repository dependency injection works
    def test_repository_dependency_injection(self):
        repo = get_db_repository()
        self.assertIsInstance(repo, BaseScanRepository)

    # 20. Original uploaded bytes are stored accurately without corruption
    @patch("app.api.routes.scans.process_compliance_from_bytes")
    def test_original_uploaded_bytes_stored_accurately(self, mock_pipeline):
        mock_pipeline.return_value = (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.PASS,
                compliance_score=100.0,
                declarations=[],
                violations=[],
            ),
            self.sharp_img,
        )
        scan_id = "test-scan-114"
        self.repo.create_scan(scan_id=scan_id)
        test_bytes = b"\x89PNG\r\n\x1a\nEXACT_TEST_BYTES_STREAM_12345"

        process_scan_background(
            scan_id=scan_id,
            image_bytes=test_bytes,
            filename="exact.png",
            product_category=None,
            user_id=None,
            repo=self.repo,
        )

        stored_file_path = os.path.join("storage", "scans", scan_id, "original.jpg")
        with open(stored_file_path, "rb") as f:
            read_bytes = f.read()

        self.assertEqual(read_bytes, test_bytes)


if __name__ == "__main__":
    unittest.main()
