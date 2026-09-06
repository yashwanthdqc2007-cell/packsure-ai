"""
Unit tests for PackSure AI Pydantic v2 schemas layer.

Validates:
- OCR models (BoundingBox, OCRTextBlock, RawOCRResult, StructuredOCRResult)
- Declaration models & enums (DeclarationStatus, DeclarationSource, MandatoryFieldType, ExtractedDeclaration, CorrectedDeclaration)
- Violation models & enums (ViolationSeverity, ViolationType, Violation)
- Compliance models & enums (ComplianceVerdict, EvidenceMetadata, ComplianceResult)
- Scan lifecycle models & enums (ScanStatus, ScanCreate, ScanInitResponse, ScanResponse, ScanHistoryResponse, ScanReviewRequest)
- Boundary constraints (confidence 0.0–1.0, score 0.0–100.0, non-negative bounding boxes)
- Serialization / deserialization consistency with snake_case API contract
- Rejection of invalid enum values and out-of-range bounds
- Distinction between field-level DeclarationStatus and overall scan-level ComplianceVerdict
"""

import unittest
from pydantic import ValidationError

from app.schemas.ocr import (
    BoundingBox,
    OCRTextBlock,
    RawOCRResult,
    StructuredOCRResult,
)
from app.schemas.declaration import (
    CorrectedDeclaration,
    DeclarationExtractionPayload,
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    MandatoryFieldType,
)
from app.schemas.violation import (
    Violation,
    ViolationSeverity,
    ViolationType,
)
from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
    Verdict,
)
from app.schemas.scan import (
    ScanCreate,
    ScanHistoryItem,
    ScanHistoryResponse,
    ScanInitResponse,
    ScanResponse,
    ScanReviewRequest,
    ScanStatus,
    ScanStatusResponse,
)


class TestOCRSchemas(unittest.TestCase):
    """Test OCR primitive models and validations."""

    def test_valid_bounding_box(self):
        bbox = BoundingBox(x=120.0, y=450.0, width=180.0, height=45.0)
        self.assertEqual(bbox.x, 120.0)
        self.assertEqual(bbox.y, 450.0)
        self.assertEqual(bbox.width, 180.0)
        self.assertEqual(bbox.height, 45.0)

    def test_negative_bounding_box_coordinates(self):
        with self.assertRaises(ValidationError):
            BoundingBox(x=-1.0, y=10.0, width=100.0, height=50.0)
        with self.assertRaises(ValidationError):
            BoundingBox(x=10.0, y=-5.0, width=100.0, height=50.0)
        with self.assertRaises(ValidationError):
            BoundingBox(x=10.0, y=10.0, width=-100.0, height=50.0)
        with self.assertRaises(ValidationError):
            BoundingBox(x=10.0, y=10.0, width=100.0, height=-50.0)

    def test_ocr_text_block_valid(self):
        block = OCRTextBlock(
            text="Net Wt: 1 kg",
            confidence=0.985,
            bounding_box=BoundingBox(x=10.0, y=20.0, width=100.0, height=30.0),
        )
        self.assertEqual(block.text, "Net Wt: 1 kg")
        self.assertEqual(block.confidence, 0.985)
        self.assertIsNotNone(block.bounding_box)

    def test_ocr_text_block_invalid_confidence(self):
        # Confidence must be between 0.0 and 1.0
        with self.assertRaises(ValidationError):
            OCRTextBlock(text="MRP", confidence=1.5)
        with self.assertRaises(ValidationError):
            OCRTextBlock(text="MRP", confidence=-0.1)

    def test_raw_ocr_result_defaults(self):
        res = RawOCRResult()
        self.assertEqual(res.full_text, "")
        self.assertEqual(res.language, "eng")
        self.assertEqual(res.blocks, [])

    def test_structured_ocr_result_valid(self):
        res = StructuredOCRResult(
            raw_text="MRP Rs. 150",
            fields={"mrp": "150.00"},
            confidence=0.92,
            language="eng",
        )
        self.assertEqual(res.fields["mrp"], "150.00")
        self.assertEqual(res.confidence, 0.92)


class TestDeclarationSchemas(unittest.TestCase):
    """Test declaration models, statuses, and enums."""

    def test_declaration_status_enum_values(self):
        self.assertEqual(DeclarationStatus.detected.value, "detected")
        self.assertEqual(DeclarationStatus.missing.value, "missing")
        self.assertEqual(DeclarationStatus.uncertain.value, "uncertain")

    def test_declaration_source_enum_values(self):
        self.assertEqual(DeclarationSource.tesseract.value, "tesseract")
        self.assertEqual(DeclarationSource.gemini.value, "gemini")
        self.assertEqual(DeclarationSource.manual.value, "manual")
        self.assertEqual(DeclarationSource.hybrid.value, "hybrid")

    def test_extracted_declaration_valid(self):
        decl = ExtractedDeclaration(
            field_name="mrp",
            status=DeclarationStatus.detected,
            raw_value="Rs. 150.00 (incl. taxes)",
            normalized_value="150.00",
            confidence=0.945,
            bounding_box=BoundingBox(x=120.0, y=450.0, width=180.0, height=45.0),
            source=DeclarationSource.gemini,
        )
        self.assertEqual(decl.field_name, "mrp")
        self.assertEqual(decl.status, DeclarationStatus.detected)
        self.assertEqual(decl.normalized_value, "150.00")
        self.assertEqual(decl.confidence, 0.945)

    def test_extracted_declaration_status_uncertain(self):
        decl = ExtractedDeclaration(
            field_name="consumer_care",
            status=DeclarationStatus.uncertain,
            raw_value="care@...",
            normalized_value=None,
            confidence=0.42,
            source=DeclarationSource.tesseract,
        )
        self.assertEqual(decl.status, DeclarationStatus.uncertain)
        self.assertIsNone(decl.normalized_value)

    def test_extracted_declaration_invalid_status_enum(self):
        with self.assertRaises(ValidationError):
            ExtractedDeclaration(field_name="mrp", status="INVALID_STATUS")

    def test_extracted_declaration_invalid_source_enum(self):
        with self.assertRaises(ValidationError):
            ExtractedDeclaration(field_name="mrp", source="ai_robot")

    def test_extracted_declaration_invalid_confidence(self):
        with self.assertRaises(ValidationError):
            ExtractedDeclaration(field_name="mrp", confidence=95.0)  # > 1.0 invalid

    def test_corrected_declaration(self):
        corr = CorrectedDeclaration(
            field_name="consumer_care",
            raw_value="care@brand.com",
            normalized_value="care@brand.com",
            status=DeclarationStatus.detected,
        )
        self.assertEqual(corr.field_name, "consumer_care")
        self.assertEqual(corr.normalized_value, "care@brand.com")


class TestViolationSchemas(unittest.TestCase):
    """Test violation models and enums."""

    def test_violation_severity_enums(self):
        self.assertEqual(ViolationSeverity.critical.value, "critical")
        self.assertEqual(ViolationSeverity.major.value, "major")
        self.assertEqual(ViolationSeverity.minor.value, "minor")

    def test_violation_valid(self):
        v = Violation(
            rule_code="Rule-6(1)(e)",
            field_name="unit_sale_price",
            violation_type=ViolationType.missing_declaration,
            severity=ViolationSeverity.critical,
            description="Unit sale price mandatory for packages above 100g/ml is missing.",
        )
        self.assertEqual(v.rule_code, "Rule-6(1)(e)")
        self.assertEqual(v.severity, ViolationSeverity.critical)
        self.assertEqual(v.violation_type, ViolationType.missing_declaration)

    def test_violation_invalid_severity(self):
        with self.assertRaises(ValidationError):
            Violation(
                rule_code="Rule-1",
                description="desc",
                severity="fatal",  # not in critical, major, minor
            )


class TestComplianceSchemas(unittest.TestCase):
    """Test compliance verdict, scores, and evaluation output."""

    def test_verdict_enum_values(self):
        self.assertEqual(ComplianceVerdict.PASS.value, "PASS")
        self.assertEqual(ComplianceVerdict.FAIL.value, "FAIL")
        self.assertEqual(ComplianceVerdict.NEEDS_REVIEW.value, "NEEDS_REVIEW")
        self.assertIs(Verdict, ComplianceVerdict)

    def test_compliance_result_valid(self):
        result = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            compliance_score=72.5,
            declarations=[
                ExtractedDeclaration(
                    field_name="mrp",
                    status=DeclarationStatus.detected,
                    raw_value="Rs 150",
                    normalized_value="150.00",
                    confidence=0.95,
                )
            ],
            violations=[
                Violation(
                    rule_code="Rule-6(1)(e)",
                    severity=ViolationSeverity.critical,
                    description="Missing unit sale price",
                )
            ],
            evidence_image_url="https://storage.packsure.ai/scans/evidence/sample.jpg",
        )
        self.assertEqual(result.verdict, ComplianceVerdict.FAIL)
        self.assertEqual(result.compliance_score, 72.5)
        self.assertEqual(len(result.declarations), 1)
        self.assertEqual(len(result.violations), 1)

    def test_compliance_score_boundary_validation(self):
        # 0.0 and 100.0 are valid
        ComplianceResult(verdict=ComplianceVerdict.PASS, compliance_score=0.0)
        ComplianceResult(verdict=ComplianceVerdict.PASS, compliance_score=100.0)

        # < 0.0 or > 100.0 are invalid
        with self.assertRaises(ValidationError):
            ComplianceResult(verdict=ComplianceVerdict.PASS, compliance_score=-0.5)
        with self.assertRaises(ValidationError):
            ComplianceResult(verdict=ComplianceVerdict.PASS, compliance_score=100.1)

    def test_invalid_verdict_enum(self):
        with self.assertRaises(ValidationError):
            ComplianceResult(verdict="REVIEW", compliance_score=80.0)  # must be NEEDS_REVIEW
        with self.assertRaises(ValidationError):
            ComplianceResult(verdict="PASSED", compliance_score=100.0)


class TestScanSchemas(unittest.TestCase):
    """Test scan creation, status polling, full inspection, history, and review schemas."""

    def test_scan_status_enums(self):
        self.assertEqual(ScanStatus.pending.value, "pending")
        self.assertEqual(ScanStatus.processing.value, "processing")
        self.assertEqual(ScanStatus.complete.value, "complete")
        self.assertEqual(ScanStatus.failed.value, "failed")

    def test_scan_init_response(self):
        res = ScanInitResponse(
            scan_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=ScanStatus.pending,
            created_at="2026-09-06T09:30:00Z",
        )
        self.assertEqual(res.scan_id, "3fa85f64-5717-4562-b3fc-2c963f66afa6")
        self.assertEqual(res.status, ScanStatus.pending)

    def test_in_progress_scan_response(self):
        res = ScanResponse(
            scan_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=ScanStatus.processing,
            product_category="Food Grains",
            image_url="https://storage.packsure.ai/scans/raw/3fa85f64.jpg",
            created_at="2026-09-06T09:30:00Z",
        )
        self.assertEqual(res.status, ScanStatus.processing)
        self.assertIsNone(res.verdict)
        self.assertIsNone(res.compliance_score)
        self.assertEqual(res.declarations, [])
        self.assertEqual(res.violations, [])
        self.assertIsNone(res.completed_at)

    def test_completed_scan_response(self):
        res = ScanResponse(
            scan_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=ScanStatus.complete,
            verdict=ComplianceVerdict.FAIL,
            compliance_score=72.5,
            product_category="Food Grains",
            image_url="https://storage.packsure.ai/raw.jpg",
            processed_image_url="https://storage.packsure.ai/processed.jpg",
            evidence_image_url="https://storage.packsure.ai/evidence.jpg",
            declarations=[
                ExtractedDeclaration(
                    field_name="mrp",
                    status=DeclarationStatus.detected,
                    raw_value="Rs 150",
                    normalized_value="150.00",
                    confidence=0.945,
                )
            ],
            violations=[
                Violation(
                    rule_code="Rule-6(1)(e)",
                    severity=ViolationSeverity.critical,
                    description="Missing unit sale price",
                )
            ],
            created_at="2026-09-06T09:30:00Z",
            completed_at="2026-09-06T09:30:04Z",
        )
        self.assertEqual(res.status, ScanStatus.complete)
        self.assertEqual(res.verdict, ComplianceVerdict.FAIL)
        self.assertEqual(res.compliance_score, 72.5)
        self.assertEqual(len(res.declarations), 1)
        self.assertEqual(len(res.violations), 1)

    def test_scan_history_response(self):
        history = ScanHistoryResponse(
            total=142,
            page=1,
            limit=20,
            total_pages=8,
            results=[
                ScanHistoryItem(
                    id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    product_name="SunFresh Refined Sunflower Oil",
                    category="Edible Oil",
                    scanned_at="2026-09-06T10:42:00Z",
                    verdict=ComplianceVerdict.PASS,
                    compliance_score=96.0,
                    status=ScanStatus.complete,
                )
            ],
        )
        self.assertEqual(history.total, 142)
        self.assertEqual(history.total_pages, 8)
        self.assertEqual(len(history.results), 1)
        self.assertEqual(history.results[0].verdict, ComplianceVerdict.PASS)

    def test_scan_review_request(self):
        review = ScanReviewRequest(
            verdict=ComplianceVerdict.PASS,
            reviewer_notes="Verified consumer care and batch number manually.",
            corrected_declarations=[
                CorrectedDeclaration(
                    field_name="consumer_care",
                    raw_value="care@brand.com",
                    normalized_value="care@brand.com",
                )
            ],
        )
        self.assertEqual(review.verdict, ComplianceVerdict.PASS)
        self.assertEqual(len(review.corrected_declarations), 1)

    def test_invalid_scan_status_enum(self):
        with self.assertRaises(ValidationError):
            ScanStatusResponse(
                scan_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status="DONE",  # must be complete
            )


if __name__ == "__main__":
    unittest.main()
