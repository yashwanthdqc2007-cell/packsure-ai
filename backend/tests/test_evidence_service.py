"""
Unit tests for PackSure AI Evidence Packaging & Visual Annotation Service (backend/app/services/evidence_service.py).

Verifies:
1. Color-coded bounding box rendering:
   - RED for deterministic rule violations.
   - YELLOW for uncertain declarations / compliance uncertainty.
   - GREEN for verified compliant declarations (even with low extraction confidence).
2. Low extraction confidence with deterministic rule PASS does NOT force yellow.
3. Input image immutability (original NumPy array is not modified in-place).
4. Coordinate safety: Boundary clamping, handling out-of-bounds boxes, zero coordinate hallucination.
5. Handling of missing declarations (where bounding_box is None).
6. EvidenceMetadata generation and count parity.
"""

import unittest
import numpy as np

from app.schemas.compliance import ComplianceResult, ComplianceVerdict, EvidenceMetadata
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.ocr import BoundingBox
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.evidence_service import (
    COLOR_COMPLIANT_GREEN,
    COLOR_UNCERTAIN_YELLOW,
    COLOR_VIOLATION_RED,
    _clamp_box_to_image,
    render_evidence_overlay,
)


class TestEvidenceRendering(unittest.TestCase):
    """Tests for visual annotation, color mapping, and evidence metadata."""

    def setUp(self):
        # 400x400 blank white BGR test canvas
        self.test_img = np.full((400, 400, 3), 255, dtype=np.uint8)

        # Standard declarations
        self.compliant_decl = ExtractedDeclaration(
            field_name="generic_name",
            status=DeclarationStatus.detected,
            raw_value="Wheat Flour",
            bounding_box=BoundingBox(x=50, y=50, width=150, height=30),
            confidence=0.98,
        )

        self.violating_decl = ExtractedDeclaration(
            field_name="mrp",
            status=DeclarationStatus.detected,
            raw_value="MRP Rs. 150",
            bounding_box=BoundingBox(x=50, y=100, width=150, height=30),
            confidence=0.95,
        )

        self.uncertain_decl = ExtractedDeclaration(
            field_name="consumer_care",
            status=DeclarationStatus.uncertain,
            raw_value="care@...",
            bounding_box=BoundingBox(x=50, y=150, width=150, height=30),
            confidence=0.40,
        )

        self.missing_decl = ExtractedDeclaration(
            field_name="unit_sale_price",
            status=DeclarationStatus.missing,
            raw_value=None,
            bounding_box=None,
        )

        self.violation = Violation(
            rule_code="Rule-6(1)(e)",
            rule_id="LMR-R06-1-E",
            field_name="mrp",
            violation_type=ViolationType.invalid_format,
            severity=ViolationSeverity.critical,
            description="MRP is missing mandatory tax clause.",
        )

    def test_color_coded_bounding_box_overlays(self):
        """Renderer must apply Red to violations, Green to compliant, and Yellow to uncertain."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            compliance_score=70.0,
            declarations=[self.compliant_decl, self.violating_decl, self.uncertain_decl, self.missing_decl],
            violations=[self.violation],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        annotated_img, meta = render_evidence_overlay(self.test_img, compliance_res)

        self.assertIsInstance(annotated_img, np.ndarray)
        self.assertEqual(annotated_img.shape, (400, 400, 3))

        # Check violating MRP box region has prominent RED component (BGR channel 2)
        # Bounding box is at (50, 100, 150, 30) -> sample at center (100, 110)
        mrp_sample = annotated_img[110, 100]
        self.assertGreater(int(mrp_sample[2]), int(mrp_sample[0]))

        # Check compliant Generic Name box region has prominent GREEN component (BGR channel 1)
        # Bounding box is at (50, 50, 150, 30) -> sample at center (100, 60)
        gen_sample = annotated_img[60, 100]
        self.assertGreater(int(gen_sample[1]), int(gen_sample[0]))

    def test_low_confidence_with_deterministic_pass_remains_green(self):
        """Low OCR/AI extraction confidence must NOT force yellow when deterministic rules PASS."""
        low_conf_decl = ExtractedDeclaration(
            field_name="net_quantity",
            status=DeclarationStatus.detected,
            raw_value="1 kg",
            normalized_value="1 kg",
            confidence=0.25,  # low confidence (< 0.50)
            bounding_box=BoundingBox(x=50, y=50, width=150, height=30),
        )

        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[low_conf_decl],
            violations=[],  # Deterministic PASS: zero violations
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        annotated_img, _ = render_evidence_overlay(self.test_img, compliance_res)

        # Sample box region: green (BGR channel 1) must be dominant over red (BGR channel 2)
        sample = annotated_img[60, 100]
        self.assertGreater(
            int(sample[1]),
            int(sample[2]),
            "Low confidence compliant declaration must be rendered GREEN, not YELLOW/RED.",
        )

    def test_actual_violation_becomes_red(self):
        """Actual rule violation must be rendered RED."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            compliance_score=70.0,
            declarations=[self.violating_decl],
            violations=[self.violation],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        annotated_img, _ = render_evidence_overlay(self.test_img, compliance_res)
        sample = annotated_img[110, 100]
        # Red channel (index 2) must dominate blue (index 0) and green (index 1)
        self.assertGreater(int(sample[2]), int(sample[0]))
        self.assertGreater(int(sample[2]), int(sample[1]))

    def test_uncertain_status_becomes_yellow(self):
        """Uncertain status / compliance review must be rendered YELLOW."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=85.0,
            declarations=[self.uncertain_decl],
            violations=[],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        annotated_img, _ = render_evidence_overlay(self.test_img, compliance_res)
        sample = annotated_img[160, 100]
        # Yellow in BGR: (0, 255, 255) -> Red (ch 2) and Green (ch 1) are both high, Blue (ch 0) is lower
        self.assertGreater(int(sample[1]), int(sample[0]))
        self.assertGreater(int(sample[2]), int(sample[0]))

    def test_confirmed_compliant_field_becomes_green(self):
        """Confirmed compliant field must be rendered GREEN."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[self.compliant_decl],
            violations=[],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        annotated_img, _ = render_evidence_overlay(self.test_img, compliance_res)
        sample = annotated_img[60, 100]
        self.assertGreater(int(sample[1]), int(sample[0]))
        self.assertGreater(int(sample[1]), int(sample[2]))

    def test_original_image_immutability(self):
        """Input NumPy array must not be modified in place."""
        orig_copy = self.test_img.copy()

        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[self.compliant_decl],
            violations=[],
        )

        annotated_img, _ = render_evidence_overlay(self.test_img, compliance_res)

        # Original array must be byte-for-byte identical
        np.testing.assert_array_equal(self.test_img, orig_copy)

        # Annotated image must differ from original canvas
        self.assertFalse(np.array_equal(annotated_img, self.test_img))

    def test_missing_declarations_handled_without_drawing_boxes(self):
        """Missing declarations (bounding_box=None) must not cause errors or draw boxes."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            compliance_score=70.0,
            declarations=[self.missing_decl],
            violations=[
                Violation(
                    rule_code="Rule-6(1)(f)",
                    rule_id="LMR-R06-1-F",
                    field_name="unit_sale_price",
                    violation_type=ViolationType.missing_declaration,
                    severity=ViolationSeverity.major,
                    description="Missing USP.",
                )
            ],
        )

        annotated_img, meta = render_evidence_overlay(self.test_img, compliance_res)
        # Because no box was present, image canvas remains clean
        self.assertIsInstance(annotated_img, np.ndarray)
        self.assertEqual(meta.total_violations_found, 1)
        # Canvas should be unmodified since no bbox was drawn
        np.testing.assert_array_equal(annotated_img, self.test_img)

    def test_clamp_box_to_image_boundaries(self):
        """Out of bounds boxes are clamped cleanly to image dimensions."""
        # Box extending past 400x400 canvas
        box_overflow = BoundingBox(x=350, y=350, width=100, height=100)
        clamped = _clamp_box_to_image(box_overflow, 400, 400)

        self.assertIsNotNone(clamped)
        x, y, w, h = clamped
        self.assertEqual(x, 350)
        self.assertEqual(y, 350)
        self.assertEqual(x + w, 400)
        self.assertEqual(y + h, 400)

        # Negative / zero dimension box
        box_invalid = BoundingBox(x=0, y=0, width=0, height=0)
        self.assertIsNone(_clamp_box_to_image(box_invalid, 400, 400))

    def test_evidence_metadata_population(self):
        """EvidenceMetadata must accurately capture counts and timestamps."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            compliance_score=70.0,
            declarations=[self.compliant_decl, self.violating_decl],
            violations=[self.violation],
            evidence=EvidenceMetadata(rule_version="2026.1"),
        )

        _, meta = render_evidence_overlay(self.test_img, compliance_res)
        self.assertEqual(meta.rule_version, "2026.1")
        self.assertEqual(meta.total_declarations_checked, 2)
        self.assertEqual(meta.total_violations_found, 1)
        self.assertIsNotNone(meta.timestamp)

    def test_invalid_image_input_raises_value_error(self):
        """None or invalid array shapes must raise ValueError."""
        compliance_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[],
            violations=[],
        )

        with self.assertRaises(ValueError):
            render_evidence_overlay(None, compliance_res)  # type: ignore

        with self.assertRaises(ValueError):
            render_evidence_overlay(np.zeros((100, 100), dtype=np.uint8), compliance_res)


if __name__ == "__main__":
    unittest.main()
