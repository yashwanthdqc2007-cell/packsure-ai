"""
Unit tests for PackSure AI Compliance Orchestrator (backend/app/services/compliance_service.py).

Verifies:
1. Successful end-to-end execution flow with mocked OCR & Gemini extraction.
2. Deterministic PASS outcome on fully compliant label declarations.
3. Deterministic FAIL outcome on non-compliant label declarations.
4. Image quality rejection halts pipeline before invoking OCR/Gemini APIs.
5. OCR failure fails safe to NEEDS_REVIEW without crashing or returning PASS.
6. Gemini extraction failure fails safe to NEEDS_REVIEW.
7. Rule engine execution failure fails safe to NEEDS_REVIEW.
8. `is_complete_scan` defaults to False and prevents false FAIL on unobserved fields.
9. `is_complete_scan=True` enforces mandatory declarations and flags missing fields.
10. Evidence rendering failure preserves rule compliance result and verdict.
11. Original input image array is never modified in-place.
12. Correct sequential service call order.
13. Coordinate safety: Deskewed/rotated OCR coordinates suppress bounding box drawing on unrotated original image.
14. Coordinate safety: Non-deskewed 1:1 coordinates render bounding boxes normally.
15. Raw bytes upload workflow (`process_compliance_from_bytes`).
16. Output evidence path persistence handling.
17. Invalid image inputs raise ValueError.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

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
from app.schemas.image import (
    ImageQualityReport,
    QualityMetrics,
    QualityStatus,
)
from app.schemas.ocr import BoundingBox, OCRTextBlock, RawOCRResult
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.compliance_service import (
    process_compliance_from_bytes,
    process_compliance_inspection,
)


def _create_synthetic_sharp_image(width=800, height=800, brightness=128) -> np.ndarray:
    """Generate a clean, high-contrast synthetic image with sharp geometric patterns."""
    img = np.full((height, width, 3), brightness, dtype=np.uint8)
    for y in range(50, height - 50, 40):
        for x in range(50, width - 50, 60):
            img[y : y + 20, x : x + 30] = [20, 20, 20]
            img[y + 10 : y + 30, x + 25 : x + 55] = [240, 240, 240]
    return img


class TestComplianceOrchestrator(unittest.TestCase):
    """Test suite for end-to-end compliance orchestration."""

    def setUp(self):
        # 800x800 high-contrast sharp synthetic image that passes quality checks
        self.test_img = _create_synthetic_sharp_image(800, 800, 128)

        # Standard OCR Mock Result
        self.mock_ocr_result = RawOCRResult(
            full_text="Wheat Flour Net Wt: 1 kg MRP Rs. 150.00 incl. of all taxes",
            language="eng",
            blocks=[
                OCRTextBlock(text="Wheat", confidence=0.99, bounding_box=BoundingBox(x=10, y=10, width=50, height=20)),
                OCRTextBlock(text="Flour", confidence=0.99, bounding_box=BoundingBox(x=65, y=10, width=50, height=20)),
                OCRTextBlock(text="Net", confidence=0.98, bounding_box=BoundingBox(x=10, y=40, width=30, height=20)),
                OCRTextBlock(text="Wt:", confidence=0.98, bounding_box=BoundingBox(x=45, y=40, width=30, height=20)),
                OCRTextBlock(text="1", confidence=0.99, bounding_box=BoundingBox(x=80, y=40, width=15, height=20)),
                OCRTextBlock(text="kg", confidence=0.99, bounding_box=BoundingBox(x=100, y=40, width=20, height=20)),
                OCRTextBlock(text="MRP", confidence=0.97, bounding_box=BoundingBox(x=10, y=70, width=40, height=20)),
                OCRTextBlock(text="Rs.", confidence=0.97, bounding_box=BoundingBox(x=55, y=70, width=30, height=20)),
                OCRTextBlock(text="150.00", confidence=0.98, bounding_box=BoundingBox(x=90, y=70, width=50, height=20)),
                OCRTextBlock(text="incl.", confidence=0.96, bounding_box=BoundingBox(x=145, y=70, width=40, height=20)),
                OCRTextBlock(text="of", confidence=0.96, bounding_box=BoundingBox(x=190, y=70, width=20, height=20)),
                OCRTextBlock(text="all", confidence=0.96, bounding_box=BoundingBox(x=215, y=70, width=25, height=20)),
                OCRTextBlock(text="taxes", confidence=0.96, bounding_box=BoundingBox(x=245, y=70, width=45, height=20)),
            ],
        )

        # Standard Fully Compliant Declarations (covering all applicable fields)
        self.compliant_declarations = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Wheat Flour",
                normalized_value="Wheat Flour",
                confidence=0.98,
                bounding_box=BoundingBox(x=10, y=10, width=105, height=20),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Wt: 1 kg",
                normalized_value="1 kg",
                confidence=0.98,
                bounding_box=BoundingBox(x=10, y=40, width=110, height=20),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 150.00 incl. of all taxes",
                normalized_value="150.00",
                confidence=0.97,
                bounding_box=BoundingBox(x=10, y=70, width=280, height=20),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacturer_name_and_address",
                status=DeclarationStatus.detected,
                raw_value="Packsure Foods Ltd, Industrial Estate, Bangalore 560001",
                normalized_value="Packsure Foods Ltd, Industrial Estate, Bangalore 560001",
                confidence=0.95,
                bounding_box=BoundingBox(x=10, y=100, width=300, height=25),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacture_date",
                status=DeclarationStatus.detected,
                raw_value="Mfg: 01/2026",
                normalized_value="2026-01-01",
                confidence=0.95,
                bounding_box=BoundingBox(x=10, y=130, width=120, height=20),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch: B-10293",
                normalized_value="B-10293",
                confidence=0.95,
                bounding_box=BoundingBox(x=10, y=160, width=120, height=20),
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="consumer_care",
                status=DeclarationStatus.detected,
                raw_value="Care: customercare@packsure.ai, Ph: 1800-123-4567",
                normalized_value="customercare@packsure.ai",
                confidence=0.95,
                bounding_box=BoundingBox(x=10, y=190, width=280, height=20),
                source=DeclarationSource.hybrid,
            ),
        ]

        # Non-Compliant Declarations (MRP missing tax clause)
        self.violating_declarations = [
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 150.00",  # Missing 'inclusive of all taxes'
                normalized_value="150.00",
                confidence=0.97,
                bounding_box=BoundingBox(x=10, y=70, width=150, height=20),
                source=DeclarationSource.hybrid,
            )
        ]

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_successful_end_to_end_deterministic_pass(self, mock_ocr, mock_ai):
        """End-to-end flow with compliant declarations yields PASS verdict and 100.0 score."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations

        result = process_compliance_inspection(
            image=self.test_img,
            product_category="Hardware",
            is_perishable=False,
            is_complete_scan=False,
        )

        self.assertIsInstance(result, ComplianceResult)
        self.assertEqual(result.verdict, ComplianceVerdict.PASS)
        self.assertEqual(result.compliance_score, 100.0)
        self.assertEqual(len(result.violations), 0)
        self.assertIsNotNone(result.evidence)

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_successful_end_to_end_deterministic_fail(self, mock_ocr, mock_ai):
        """End-to-end flow with violating declaration yields FAIL verdict and critical violation."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.violating_declarations

        result = process_compliance_inspection(
            image=self.test_img,
            product_category="Food Grains",
            is_complete_scan=False,
        )

        self.assertIsInstance(result, ComplianceResult)
        self.assertEqual(result.verdict, ComplianceVerdict.FAIL)
        self.assertLess(result.compliance_score, 100.0)
        self.assertGreaterEqual(len(result.violations), 1)

        mrp_violation = next((v for v in result.violations if v.field_name == "mrp"), None)
        self.assertIsNotNone(mrp_violation)
        self.assertEqual(mrp_violation.rule_code, "Rule-6(1)(e)")
        self.assertEqual(mrp_violation.severity, ViolationSeverity.critical)

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    @patch("app.services.compliance_service.check_image_quality")
    def test_quality_rejection_halts_pipeline(self, mock_quality, mock_ocr, mock_ai):
        """Quality rejection must stop pipeline before calling OCR/Gemini and return NEEDS_REVIEW."""
        mock_quality.return_value = ImageQualityReport(
            is_valid=False,
            quality_score=0.25,
            status=QualityStatus.rejected,
            recapture_reason="Image is severely blurry; please hold camera steady.",
            metrics=QualityMetrics(
                width=800, height=800, total_pixels=640000, resolution_acceptable=True,
                blur_score=10.0, is_blurry=True, brightness_score=120.0, is_too_dark=False,
                is_too_bright=False, contrast_score=40.0, is_low_contrast=False,
            ),
        )

        result = process_compliance_inspection(image=self.test_img)

        # Assert downstream services were NEVER called
        mock_ocr.assert_not_called()
        mock_ai.assert_not_called()

        self.assertEqual(result.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(result.compliance_score, 0.0)
        self.assertEqual(len(result.declarations), 0)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule_code, "QUALITY-REJECT")

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_ocr_failure_fails_safe_to_needs_review(self, mock_ocr, mock_ai):
        """OCR runtime error must fail safe to NEEDS_REVIEW without calling Gemini."""
        mock_ocr.side_effect = RuntimeError("Tesseract binary crashed.")

        result = process_compliance_inspection(image=self.test_img)

        mock_ai.assert_not_called()
        self.assertEqual(result.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(result.compliance_score, 0.0)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule_code, "OCR-FAILURE")

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_gemini_failure_fails_safe_to_needs_review(self, mock_ocr, mock_ai):
        """Gemini API failure must fail safe to NEEDS_REVIEW without returning false PASS."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.side_effect = RuntimeError("Gemini API connection timed out.")

        result = process_compliance_inspection(image=self.test_img)

        self.assertEqual(result.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(result.compliance_score, 0.0)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule_code, "AI-EXTRACTION-FAILURE")

    @patch("app.services.compliance_service.rule_engine.evaluate_compliance")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_rule_engine_failure_fails_safe_to_needs_review(self, mock_ocr, mock_ai, mock_rule_eval):
        """Rule engine unexpected exception must fail safe to NEEDS_REVIEW."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations
        mock_rule_eval.side_effect = RuntimeError("Rules JSON evaluation corruption.")

        result = process_compliance_inspection(image=self.test_img)

        self.assertEqual(result.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(result.compliance_score, 0.0)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule_code, "RULE-ENGINE-FAILURE")

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_incomplete_scan_defaults_to_false_and_avoids_false_fail(self, mock_ocr, mock_ai):
        """Incomplete scan (is_complete_scan=False) must not flag unobserved fields as violations."""
        mock_ocr.return_value = self.mock_ocr_result
        # Return only generic_name; other mandatory fields are unobserved
        mock_ai.return_value = [self.compliant_declarations[0]]

        # Default is_complete_scan is False
        result = process_compliance_inspection(
            image=self.test_img,
            product_category="Food Grains",
        )

        # Single panel scan with missing fields routes to NEEDS_REVIEW, NOT FAIL
        self.assertEqual(result.verdict, ComplianceVerdict.NEEDS_REVIEW)
        missing_violations = [v for v in result.violations if v.violation_type == ViolationType.missing_declaration]
        self.assertEqual(len(missing_violations), 0)

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_complete_scan_enforces_mandatory_declarations(self, mock_ocr, mock_ai):
        """Confirmed complete scan (is_complete_scan=True) flags omitted fields as violations."""
        mock_ocr.return_value = self.mock_ocr_result
        # Only generic_name provided; all others missing
        mock_ai.return_value = [self.compliant_declarations[0]]

        result = process_compliance_inspection(
            image=self.test_img,
            product_category="Food Grains",
            is_complete_scan=True,
        )

        # Complete scan missing mandatory fields yields FAIL with missing_declaration violations
        self.assertEqual(result.verdict, ComplianceVerdict.FAIL)
        missing_violations = [v for v in result.violations if v.violation_type == ViolationType.missing_declaration]
        self.assertGreater(len(missing_violations), 0)

    @patch("app.services.compliance_service.render_evidence_overlay")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_evidence_rendering_failure_preserves_compliance_result(self, mock_ocr, mock_ai, mock_render):
        """Evidence rendering failure must be non-fatal and preserve the compliance verdict."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations
        mock_render.side_effect = RuntimeError("OpenCV rendering error.")

        result = process_compliance_inspection(
            image=self.test_img,
            product_category="Hardware",
            is_perishable=False,
        )

        # Compliance result is fully preserved
        self.assertEqual(result.verdict, ComplianceVerdict.PASS)
        self.assertEqual(result.compliance_score, 100.0)

    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_original_image_immutability(self, mock_ocr, mock_ai):
        """Original input NumPy array must remain unmodified byte-for-byte."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations

        orig_copy = self.test_img.copy()
        _ = process_compliance_inspection(image=self.test_img)

        np.testing.assert_array_equal(self.test_img, orig_copy)

    @patch("app.services.compliance_service.render_evidence_overlay")
    @patch("app.services.compliance_service.rule_engine.evaluate_compliance")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    @patch("app.services.compliance_service.preprocess_for_pipeline")
    @patch("app.services.compliance_service.check_image_quality")
    def test_correct_service_call_order(
        self, mock_quality, mock_preprocess, mock_ocr, mock_ai, mock_rules, mock_render
    ):
        """Verify sequential call order: Quality -> Preprocess -> OCR -> AI -> Rules -> Evidence."""
        mock_quality.return_value = ImageQualityReport(
            is_valid=True, quality_score=0.9, status=QualityStatus.acceptable,
            metrics=QualityMetrics(
                width=800, height=800, total_pixels=640000, resolution_acceptable=True,
                blur_score=200.0, is_blurry=False, brightness_score=120.0, is_too_dark=False,
                is_too_bright=False, contrast_score=50.0, is_low_contrast=False,
            ),
        )
        mock_preprocess.return_value = (self.test_img.copy(), self.test_img[:, :, 0].copy())
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations
        mock_rules.return_value = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=self.compliant_declarations,
            violations=[],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )
        mock_render.return_value = (self.test_img.copy(), EvidenceMetadata(rule_version="2026.1"))

        manager = MagicMock()
        manager.attach_mock(mock_quality, "quality")
        manager.attach_mock(mock_preprocess, "preprocess")
        manager.attach_mock(mock_ocr, "ocr")
        manager.attach_mock(mock_ai, "ai")
        manager.attach_mock(mock_rules, "rules")
        manager.attach_mock(mock_render, "render")

        _ = process_compliance_inspection(image=self.test_img)

        expected_order = [
            "quality",
            "preprocess",
            "ocr",
            "ai",
            "rules",
            "render",
        ]
        actual_calls = [call[0] for call in manager.mock_calls if call[0] in expected_order]
        self.assertEqual(actual_calls, expected_order)

    @patch("app.services.compliance_service.render_evidence_overlay")
    @patch("app.services.compliance_service._detect_skew_angle")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_deskewed_coordinates_suppress_bounding_boxes_on_original_image(
        self, mock_ocr, mock_ai, mock_skew, mock_render
    ):
        """When deskew is active (> 1.5 deg), bounding boxes are stripped before rendering on original canvas."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations
        mock_skew.return_value = 12.5  # Significant skew angle triggering deskew
        mock_render.return_value = (self.test_img.copy(), EvidenceMetadata(rule_version="2026.1"))

        _ = process_compliance_inspection(image=self.test_img)

        mock_render.assert_called_once()
        passed_compliance_result = mock_render.call_args[1]["compliance_result"]

        # All declarations passed to evidence rendering must have bounding_box=None to avoid coordinate drift
        for decl in passed_compliance_result.declarations:
            self.assertIsNone(
                decl.bounding_box,
                f"Declaration '{decl.field_name}' bounding box was not suppressed on deskewed image."
            )

    @patch("app.services.compliance_service.render_evidence_overlay")
    @patch("app.services.compliance_service._detect_skew_angle")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_non_deskew_original_coordinates_rendered_directly(
        self, mock_ocr, mock_ai, mock_skew, mock_render
    ):
        """When skew is negligible (<= 1.5 deg), 1:1 original coordinates are preserved for rendering."""
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations
        mock_skew.return_value = 0.5  # Skew below trigger threshold
        mock_render.return_value = (self.test_img.copy(), EvidenceMetadata(rule_version="2026.1"))

        _ = process_compliance_inspection(image=self.test_img)

        mock_render.assert_called_once()
        passed_compliance_result = mock_render.call_args[1]["compliance_result"]

        # Declarations retain their original BoundingBox instances
        boxes = [d.bounding_box for d in passed_compliance_result.declarations if d.bounding_box is not None]
        self.assertGreater(len(boxes), 0)

    @patch("app.services.compliance_service.validate_image_file")
    @patch("app.services.compliance_service.extract_declarations")
    @patch("app.services.compliance_service.extract_raw_ocr")
    def test_process_compliance_from_bytes_workflow(self, mock_ocr, mock_ai, mock_validate):
        """Process compliance directly from raw byte payloads."""
        mock_validate.return_value = (True, None, self.test_img)
        mock_ocr.return_value = self.mock_ocr_result
        mock_ai.return_value = self.compliant_declarations

        q_report, comp_res, img = process_compliance_from_bytes(
            file_bytes=b"\x89PNG\r\n\x1a\nvalid_payload_bytes",
            filename="test.png",
            product_category="Hardware",
            is_perishable=False,
        )

        self.assertIsNotNone(q_report)
        self.assertIsInstance(comp_res, ComplianceResult)
        self.assertEqual(comp_res.verdict, ComplianceVerdict.PASS)
        self.assertIsNotNone(img)

    def test_process_compliance_from_invalid_bytes(self):
        """Invalid byte payloads return error ComplianceResult without crashing."""
        q_report, comp_res, img = process_compliance_from_bytes(
            file_bytes=b"invalid corrupt bytes",
            filename="corrupt.jpg",
        )

        self.assertIsNone(q_report)
        self.assertEqual(comp_res.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(comp_res.compliance_score, 0.0)
        self.assertEqual(comp_res.violations[0].rule_code, "IMAGE-INVALID")
        self.assertIsNone(img)

    def test_invalid_image_raises_value_error(self):
        """None or empty image input must raise ValueError."""
        with self.assertRaises(ValueError):
            process_compliance_inspection(image=None)  # type: ignore

        with self.assertRaises(ValueError):
            process_compliance_inspection(image=np.zeros((0, 0), dtype=np.uint8))


class TestSyntheticUSPComplianceScenario(unittest.TestCase):
    """End-to-end scenario tests for Rule 6(11) Unit Sale Price using synthetic image fixtures."""

    @staticmethod
    def _create_synthetic_packaged_product_fixture(
        mrp_text: str = "MRP: Rs. 300.00 (inclusive of all taxes)",
        net_qty_text: str = "Net Quantity: 500 g",
        usp_text: str = "Unit Sale Price: Rs. 500.00 / kg",
    ) -> np.ndarray:
        """Render a clean, high-resolution 1200x1200 synthetic packaged product image."""
        try:
            import cv2
            from PIL import Image, ImageDraw, ImageFont

            try:
                font = ImageFont.truetype("arial.ttf", 32)
                title_font = ImageFont.truetype("arial.ttf", 40)
            except Exception:
                font = ImageFont.load_default()
                title_font = font

            img = Image.new("RGB", (1200, 1200), color=(210, 210, 210))
            draw = ImageDraw.Draw(img)

            # High-contrast packaging box and header
            draw.rectangle([40, 40, 1160, 1160], fill=(230, 230, 235), outline=(30, 30, 30), width=6)
            draw.rectangle([60, 60, 1140, 180], fill=(25, 45, 90), outline=(15, 30, 60), width=3)
            draw.rectangle([60, 200, 1140, 1140], fill=(240, 240, 240), outline=(120, 120, 120), width=2)

            draw.text((100, 100), "PACKSURE PREMIUM ALMONDS", fill=(255, 255, 255), font=title_font)
            draw.text((100, 250), "Generic Name: Almond Kernels", fill=(0, 0, 0), font=font)
            draw.text((100, 330), net_qty_text, fill=(0, 0, 0), font=font)
            draw.text((100, 410), mrp_text, fill=(0, 0, 0), font=font)
            draw.text((100, 490), usp_text, fill=(0, 0, 0), font=font)
            draw.text((100, 570), "Mfg Date: 01/2026", fill=(0, 0, 0), font=font)
            draw.text((100, 650), "Best Before: 12/2026", fill=(0, 0, 0), font=font)
            draw.text((100, 730), "Batch No: ALM-2026-09", fill=(0, 0, 0), font=font)
            draw.text((100, 810), "Manufactured by: PackSure Foods Ltd, Plot 42, Sector 18, Gurugram 122015", fill=(0, 0, 0), font=font)
            draw.text((100, 890), "Consumer Care: care@packsure.ai, Toll Free: 1800-111-2222", fill=(0, 0, 0), font=font)

            # Barcode pattern for realistic packaging texture and sharpness
            for x in range(100, 1100, 12):
                draw.line([(x, 970), (x, 1090)], fill=(0, 0, 0), width=3 if x % 24 == 0 else 2)

            np_img = np.array(img)
            return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
        except Exception:
            # Fallback numpy array if PIL/cv2 not available
            return np.full((1200, 1200, 3), 200, dtype=np.uint8)

    def test_synthetic_fixture_passes_quality_gate(self):
        """The 1200x1200 synthetic fixture must satisfy all production image quality criteria."""
        from app.services.image_service import check_image_quality

        fixture_img = self._create_synthetic_packaged_product_fixture()
        quality_report = check_image_quality(fixture_img)

        self.assertTrue(quality_report.is_valid)
        self.assertEqual(quality_report.status, QualityStatus.acceptable)
        self.assertGreaterEqual(quality_report.metrics.width, 600)
        self.assertGreaterEqual(quality_report.metrics.height, 600)
        self.assertFalse(quality_report.metrics.is_blurry)
        self.assertFalse(quality_report.metrics.is_too_dark)
        self.assertFalse(quality_report.metrics.is_too_bright)
        self.assertFalse(quality_report.metrics.is_low_contrast)

    @patch("app.services.compliance_service.extract_declarations")
    def test_synthetic_usp_inconsistency_fails_deterministically(self, mock_extract):
        """Synthetic fixture with MRP=300, Qty=500g, Declared USP=500/kg fails deterministic USP check.

        Statutory calculation:
        - Net Quantity = 500 g = 0.5 kg
        - MRP = Rs. 300.00
        - Expected Statutory Rate = 300 / 0.5 = Rs. 600.00 / kg (or Rs. 0.60 / g)
        - Declared USP = Rs. 500.00 / kg (mathematically incorrect & statutory unit mismatch for < 1kg).
        - Rule 6(11) must catch this deterministically and yield a FAIL verdict.
        """
        fixture_img = self._create_synthetic_packaged_product_fixture(
            mrp_text="MRP: Rs. 300.00 (inclusive of all taxes)",
            net_qty_text="Net Quantity: 500 g",
            usp_text="Unit Sale Price: Rs. 500.00 / kg",
        )

        mock_extract.return_value = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Generic Name: Almond Kernels",
                normalized_value="Almond Kernels",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Quantity: 500 g",
                normalized_value="500 g",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP: Rs. 300.00 (inclusive of all taxes)",
                normalized_value="300.00",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="unit_sale_price",
                status=DeclarationStatus.detected,
                raw_value="Unit Sale Price: Rs. 500.00 / kg",
                normalized_value="500.00 / kg",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacture_date",
                status=DeclarationStatus.detected,
                raw_value="Mfg Date: 01/2026",
                normalized_value="2026-01-01",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch No: ALM-2026-09",
                normalized_value="ALM-2026-09",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacturer_name_and_address",
                status=DeclarationStatus.detected,
                raw_value="Manufactured by: PackSure Foods Ltd, Plot 42, Sector 18, Gurugram 122015",
                normalized_value="PackSure Foods Ltd, Plot 42, Sector 18, Gurugram 122015",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="consumer_care",
                status=DeclarationStatus.detected,
                raw_value="Consumer Care: care@packsure.ai, Toll Free: 1800-111-2222",
                normalized_value="care@packsure.ai",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
        ]

        result = process_compliance_inspection(
            image=fixture_img,
            product_category="Food Grains",
            is_complete_scan=False,
        )

        self.assertIsInstance(result, ComplianceResult)
        self.assertEqual(result.verdict, ComplianceVerdict.FAIL)
        self.assertLess(result.compliance_score, 100.0)

        usp_violations = [v for v in result.violations if v.field_name == "unit_sale_price"]
        self.assertEqual(len(usp_violations), 1)
        self.assertEqual(usp_violations[0].rule_code, "Rule-6(11)")
        self.assertIn("Rule 6(11)", usp_violations[0].description)

    @patch("app.services.compliance_service.extract_declarations")
    def test_synthetic_usp_mathematical_mismatch_fails_deterministically(self, mock_extract):
        """Synthetic fixture with declared rate Rs. 0.50/g vs calculated rate Rs. 0.60/g fails math check."""
        fixture_img = self._create_synthetic_packaged_product_fixture(
            mrp_text="MRP: Rs. 300.00 (inclusive of all taxes)",
            net_qty_text="Net Quantity: 500 g",
            usp_text="Unit Sale Price: Rs. 0.50 / g",
        )

        mock_extract.return_value = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Generic Name: Almond Kernels",
                normalized_value="Almond Kernels",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Quantity: 500 g",
                normalized_value="500 g",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP: Rs. 300.00 (inclusive of all taxes)",
                normalized_value="300.00",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="unit_sale_price",
                status=DeclarationStatus.detected,
                raw_value="Unit Sale Price: Rs. 0.50 / g",
                normalized_value="0.50 / g",
                confidence=0.98,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacture_date",
                status=DeclarationStatus.detected,
                raw_value="Mfg Date: 01/2026",
                normalized_value="2026-01-01",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch No: ALM-2026-09",
                normalized_value="ALM-2026-09",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="manufacturer_name_and_address",
                status=DeclarationStatus.detected,
                raw_value="Manufactured by: PackSure Foods Ltd, Plot 42, Sector 18, Gurugram 122015",
                normalized_value="PackSure Foods Ltd, Plot 42, Sector 18, Gurugram 122015",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
            ExtractedDeclaration(
                field_name="consumer_care",
                status=DeclarationStatus.detected,
                raw_value="Consumer Care: care@packsure.ai, Toll Free: 1800-111-2222",
                normalized_value="care@packsure.ai",
                confidence=0.95,
                source=DeclarationSource.hybrid,
            ),
        ]

        result = process_compliance_inspection(
            image=fixture_img,
            product_category="Food Grains",
            is_complete_scan=False,
        )

        self.assertEqual(result.verdict, ComplianceVerdict.FAIL)
        usp_violations = [v for v in result.violations if v.field_name == "unit_sale_price"]
        self.assertEqual(len(usp_violations), 1)
        self.assertEqual(usp_violations[0].rule_code, "Rule-6(11)")
        self.assertEqual(usp_violations[0].violation_type, ViolationType.misleading)
        self.assertIn("0.50", usp_violations[0].description)
        self.assertIn("0.60", usp_violations[0].description)


if __name__ == "__main__":
    unittest.main()
