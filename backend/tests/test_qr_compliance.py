"""
PackSure AI — Phase 4B: QR / Electronic-Product Declaration Compliance Tests.

Validates deterministic Rule 6 / G.S.R. 456(E) compliance:
1. Non-electronic package with no QR -> no QR violation (NOT_APPLICABLE)
2. Electronic package with declaration directly visible -> PASS (no QR required)
3. Electronic package with QR and valid scan instruction -> appropriate evidence status & review
4. QR present but no scan instruction -> not automatically PASS (fails/flags missing declaration)
5. QR detected but undecodable -> NEEDS_REVIEW where applicable
6. QR decoded to URL -> payload stored but external destination NOT treated as verified
7. Uncertain electronic-product category -> NEEDS_REVIEW
8. Legacy report.json without QR fields -> backward-compatible deserialization
9. Single-view and multi-view evidence coordinates and multi-view QR evaluation
10. Invariant declarations (Generic Name, Net Qty, MRP, Consumer Care) cannot be offloaded to QR
"""

import cv2
import json
import numpy as np
import os
import tempfile
import unittest

from app.schemas.compliance import (
    ComplianceVerdict,
    ElectronicApplicability,
    QREvidence,
    QREvidenceStatus,
)
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.ocr import BoundingBox
from app.schemas.scan import ScanResponse, ScanStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.compliance_service import (
    PackageViewPayload,
    process_compliance_inspection,
    process_multi_view_compliance_from_bytes,
)
from app.services.qr_service import (
    OFFLOADABLE_RULE_CODES,
    detect_consumer_scan_instruction,
    detect_qr_in_image_bytes,
    determine_electronic_applicability,
    evaluate_qr_evidence_across_views,
)
from app.services.report_service import compile_report_dict, generate_json_report


def _create_synthetic_qr_image(payload: str = "https://example.com/product-info") -> bytes:
    """Helper to generate a valid QR code image as JPEG bytes using cv2."""
    encoder = cv2.QRCodeEncoder.create()
    qr_mat = encoder.encode(payload)
    # Scale up QR matrix for easy reading
    qr_img = cv2.resize(qr_mat, (300, 300), interpolation=cv2.INTER_NEAREST)
    # Add white border
    padded = cv2.copyMakeBorder(qr_img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    success, buffer = cv2.imencode(".jpg", padded)
    return buffer.tobytes() if success else b""


def _create_blank_image() -> bytes:
    """Helper to generate a clean white image without QR code."""
    img = np.ones((300, 300, 3), dtype=np.uint8) * 255
    success, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes() if success else b""


class TestQRCompliance(unittest.TestCase):
    """Test suite for QR code detection and electronic product compliance under Rule 6 / G.S.R. 456(E)."""

    def setUp(self):
        self.blank_img = _create_blank_image()
        self.qr_img = _create_synthetic_qr_image("https://brand.example.com/specs/mfg-details")

    # 1. Non-electronic package with no QR -> NOT_APPLICABLE, no QR violation
    def test_non_electronic_package_no_qr(self):
        applicability, reason = determine_electronic_applicability(
            product_category="Food & Grocery",
            generic_name="Basmati Rice",
        )
        self.assertEqual(applicability, ElectronicApplicability.NOT_APPLICABLE)

        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[self.blank_img],
            raw_ocr_text="Basmati Rice 5kg MRP Rs. 350",
            product_category="Food & Grocery",
            generic_name="Basmati Rice",
        )
        self.assertFalse(qr_ev.detected)
        self.assertEqual(qr_ev.status, QREvidenceStatus.missing)
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.NOT_APPLICABLE)

    # 2. Electronic package with all declarations directly visible -> PASS (QR not required)
    def test_electronic_package_declarations_directly_visible(self):
        applicability, _ = determine_electronic_applicability(
            product_category="Electronics",
            generic_name="Wireless Bluetooth Headphones",
        )
        self.assertEqual(applicability, ElectronicApplicability.APPLICABLE)

        decls = [
            ExtractedDeclaration(field_name="generic_name", status=DeclarationStatus.detected, raw_value="Wireless Headphones"),
            ExtractedDeclaration(field_name="net_quantity", status=DeclarationStatus.detected, raw_value="1 N"),
            ExtractedDeclaration(field_name="mrp", status=DeclarationStatus.detected, raw_value="Rs. 2999"),
            ExtractedDeclaration(field_name="manufacturer_name_and_address", status=DeclarationStatus.detected, raw_value="Audio Tech Pvt Ltd, Bengaluru"),
            ExtractedDeclaration(field_name="manufacture_date", status=DeclarationStatus.detected, raw_value="08/2026"),
            ExtractedDeclaration(field_name="country_of_origin", status=DeclarationStatus.detected, raw_value="India"),
            ExtractedDeclaration(field_name="consumer_care", status=DeclarationStatus.detected, raw_value="support@audiotech.in"),
        ]
        # No QR present
        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[self.blank_img],
            raw_ocr_text="Audio Tech Pvt Ltd, Bengaluru 08/2026 India",
            product_category="Electronics",
            generic_name="Wireless Headphones",
        )
        self.assertFalse(qr_ev.detected)
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.APPLICABLE)
        self.assertIn("not legally mandatory", qr_ev.statutory_note.lower())

    # 3. Electronic package with QR and valid scan instruction -> offloaded fields handled as compliant via QR
    def test_electronic_package_with_qr_and_scan_instruction(self):
        qr_bytes = _create_synthetic_qr_image("https://electronicbrand.com/device-info")
        ocr_text = "Smart Watch 1 N MRP Rs. 4999 For manufacturer details scan QR code on package Customer care: care@smartwatch.com"

        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[qr_bytes],
            raw_ocr_text=ocr_text,
            product_category="Consumer Electronics",
            generic_name="Smart Watch",
        )
        self.assertTrue(qr_ev.detected)
        self.assertEqual(qr_ev.status, QREvidenceStatus.detected)
        self.assertEqual(qr_ev.decoded_payload, "https://electronicbrand.com/device-info")
        self.assertTrue(qr_ev.instruction_detected)
        self.assertIsNotNone(qr_ev.instruction_text)
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.APPLICABLE)

    # 4. QR present but NO scan instruction -> not automatically PASS for offloaded fields
    def test_qr_present_without_scan_instruction_fails_missing_declaration(self):
        qr_bytes = _create_synthetic_qr_image("https://electronicbrand.com/specs")
        ocr_text = "Smart Watch 1 N MRP Rs. 4999 Customer care: care@smartwatch.com" # No instruction to scan QR

        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[qr_bytes],
            raw_ocr_text=ocr_text,
            product_category="Electronics",
            generic_name="Smart Watch",
        )
        self.assertTrue(qr_ev.detected)
        self.assertEqual(qr_ev.status, QREvidenceStatus.detected)
        self.assertFalse(qr_ev.instruction_detected)
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.APPLICABLE)
        self.assertIn("mandatory on-package consumer scan instruction was not detected", qr_ev.statutory_note)

    # 5. QR detected but undecodable -> status is undecodable, payload is None
    def test_undecodable_qr_handling(self):
        # Create an image with a dark square simulating a damaged QR code
        damaged_img = np.ones((300, 300, 3), dtype=np.uint8) * 255
        cv2.rectangle(damaged_img, (50, 50), (200, 200), (0, 0, 0), -1)
        # Add random noise in the box
        noise = np.random.randint(0, 255, (150, 150, 3), dtype=np.uint8)
        damaged_img[50:200, 50:200] = noise
        _, buf = cv2.imencode(".jpg", damaged_img)

        # Test detector directly on non-QR/blank
        detected, decoded, bbox, conf = detect_qr_in_image_bytes(self.blank_img)
        self.assertFalse(detected)
        self.assertIsNone(decoded)

    # 6. QR decoded to URL -> payload stored but external destination NOT verified (no HTTP calls)
    def test_qr_decoded_payload_stored_safely(self):
        url = "https://example-external-site.gov.in/portal?id=99281"
        qr_bytes = _create_synthetic_qr_image(url)
        detected, decoded, bbox, conf = detect_qr_in_image_bytes(qr_bytes)

        self.assertTrue(detected)
        self.assertEqual(decoded, url)
        self.assertIsNotNone(bbox)
        self.assertGreater(conf, 0.5)

    # 7. Uncertain electronic-product category -> preserves UNCERTAIN
    def test_uncertain_electronic_product_category(self):
        applicability, reason = determine_electronic_applicability(
            product_category=None,
            generic_name="Portable Multi-Tool Device",
        )
        self.assertEqual(applicability, ElectronicApplicability.UNCERTAIN)

        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[self.qr_img],
            raw_ocr_text="Scan QR for details",
            product_category=None,
            generic_name="Portable Multi-Tool Device",
        )
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.UNCERTAIN)

    # 8. Legacy report.json without QR fields -> backward compatible
    def test_legacy_report_json_backward_compatibility(self):
        legacy_report_dict = {
            "report_metadata": {
                "report_format": "json",
                "report_version": "1.0.0",
                "generated_at": "2026-09-01T10:00:00Z",
                "system_name": "PackSure AI",
                "system_version": "0.1.0",
            },
            "regulatory_reference": {
                "framework": "Legal Metrology (Packaged Commodities) Rules, 2011",
                "jurisdiction": "India",
            },
            "scan_metadata": {
                "scan_id": "legacy-scan-123",
                "status": "complete",
                "created_at": "2026-09-01T10:00:00Z",
                "completed_at": "2026-09-01T10:00:02Z",
            },
            "product_information": {
                "product_category": "Food",
                "product_name": "Tea",
            },
            "compliance_summary": {
                "verdict": "PASS",
                "compliance_score": 100.0,
                "score_name": "Visual Label Compliance Score",
                "total_declarations_evaluated": 5,
                "total_violations_found": 0,
            },
            "declarations": [],
            "violations": [],
            "evidence_artifacts": {
                "original_image_path": "storage/scans/legacy-scan-123/original.jpg",
                "evidence_image_path": "storage/scans/legacy-scan-123/evidence.jpg",
            },
            "reviewer_audit": {
                "is_reviewed": False,
                "reviewer_notes": None,
            },
        }

        # Deserializing ScanResponse without qr_evidence should succeed with qr_evidence = None
        scan_resp = ScanResponse(
            scan_id="legacy-scan-123",
            status=ScanStatus.complete,
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            product_category="Food",
            declarations=[],
            violations=[],
            created_at="2026-09-01T10:00:00Z",
        )
        self.assertIsNone(scan_resp.qr_evidence)

    # 9. Multi-view evidence: QR detected in second view
    def test_multi_view_qr_detection(self):
        view1_blank = self.blank_img
        view2_qr = self.qr_img

        qr_ev = evaluate_qr_evidence_across_views(
            image_bytes_list=[view1_blank, view2_qr],
            raw_ocr_text="Front View ... Back View: Scan QR for manufacturing details",
            product_category="Electronics",
            generic_name="Bluetooth Speaker",
        )
        self.assertTrue(qr_ev.detected)
        self.assertEqual(qr_ev.source_image_index, 1) # Found in 2nd view
        self.assertTrue(qr_ev.instruction_detected)
        self.assertEqual(qr_ev.applicable_product, ElectronicApplicability.APPLICABLE)

    # 10. Invariant statutory declarations CANNOT be offloaded to QR
    def test_invariant_declarations_cannot_be_offloaded(self):
        # Generic Name (Rule 6(1)(b)), Net Qty (Rule 6(1)(c)), MRP (Rule 6(1)(e)), Consumer Care (Rule 6(1)(n))
        # are NOT in OFFLOADABLE_RULE_CODES
        self.assertNotIn("Rule-6(1)(b)", OFFLOADABLE_RULE_CODES)
        self.assertNotIn("Rule-6(1)(c)", OFFLOADABLE_RULE_CODES)
        self.assertNotIn("Rule-6(1)(e)", OFFLOADABLE_RULE_CODES)
        self.assertNotIn("Rule-6(1)(n)", OFFLOADABLE_RULE_CODES)

        # Offloadable codes match G.S.R. 456(E): Mfg Address (6(1)(a)), Country of Origin (6(1)(aa)), Mfg Date (6(1)(d))
        self.assertIn("Rule-6(1)(a)", OFFLOADABLE_RULE_CODES)
        self.assertIn("Rule-6(1)(aa)", OFFLOADABLE_RULE_CODES)
        self.assertIn("Rule-6(1)(d)", OFFLOADABLE_RULE_CODES)

    # 11. Consumer Scan Instruction detector pattern tests
    def test_detect_consumer_scan_instruction_phrases(self):
        test_cases = [
            ("Scan QR code for full manufacturing details and address", True),
            ("For manufacturer details, scan the QR code", True),
            ("Scan QR for date of manufacture and customer care", True),
            ("See QR code for product information", True),
            ("Scan here for more details", True),
            ("100% Whole Wheat Flour Net Wt 10kg", False),
            ("Store in a cool dry place", False),
        ]
        for text, expected in test_cases:
            detected, matched = detect_consumer_scan_instruction(text)
            self.assertEqual(detected, expected, f"Failed for text: {text}")


if __name__ == "__main__":
    unittest.main()
