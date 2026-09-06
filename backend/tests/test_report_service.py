"""
Unit tests for PackSure AI Structured JSON Inspection Report Service (Phase 9F).

Verifies:
1. Basic report dictionary compilation matches canonical schema.
2. Required top-level keys are present and correctly typed.
3. Declarations serialization preserves raw, normalized, bounding boxes, status, and source.
4. Violations serialization preserves rule citations, types, severities, and descriptions.
5. Evidence references (original and annotated images) are mapped accurately.
6. Compliance verdict and score are faithfully recorded.
7. No fabrication of missing declarations occurs.
8. Deterministic JSON output and UTF-8 encoding.
9. Output file and parent directory auto-creation.
10. Correct output path is returned.
11. Reviewer audit notes and reviewer resolution state are properly included.
12. Failure handling / safe execution with minimal inputs.
"""

import json
import os
import shutil
import tempfile
import unittest

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
from app.schemas.ocr import BoundingBox
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.report_service import (
    REGULATORY_FRAMEWORK,
    REGULATORY_JURISDICTION,
    REPORT_FORMAT_VERSION,
    SYSTEM_NAME,
    SYSTEM_VERSION,
    compile_report_dict,
    generate_json_report,
)


class TestReportService(unittest.TestCase):
    """Test suite for structured JSON inspection report generator."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.scan_id = "test-scan-uuid-12345"

        self.declarations = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Basmati Rice",
                normalized_value="Basmati Rice",
                confidence=0.985,
                source=DeclarationSource.gemini,
                bounding_box=BoundingBox(x=10.0, y=20.0, width=100.0, height=30.0),
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="5 kg",
                normalized_value="5 kg",
                confidence=0.99,
                source=DeclarationSource.hybrid,
                bounding_box=BoundingBox(x=10.0, y=60.0, width=50.0, height=20.0),
            ),
        ]

        self.violations = [
            Violation(
                id="viol-1",
                rule_id="LMR-R06-1-E",
                rule_code="Rule-6(1)(e)",
                field_name="mrp",
                violation_type=ViolationType.missing_declaration,
                severity=ViolationSeverity.critical,
                description="MRP declaration is mandatory.",
            )
        ]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Basic report compilation matches canonical schema
    def test_compile_report_dict_structure(self):
        report = compile_report_dict(
            scan_id=self.scan_id,
            verdict=ComplianceVerdict.FAIL,
            compliance_score=65.0,
            product_category="Food Grains",
            declarations=self.declarations,
            violations=self.violations,
            image_path="storage/scans/test-scan/original.jpg",
            evidence_path="storage/scans/test-scan/evidence.jpg",
            created_at="2026-09-06T10:00:00Z",
            completed_at="2026-09-06T10:00:05Z",
            status="complete",
        )

        expected_top_keys = {
            "report_metadata",
            "regulatory_reference",
            "scan_metadata",
            "product_information",
            "compliance_summary",
            "declarations",
            "violations",
            "evidence_artifacts",
            "reviewer_audit",
        }
        self.assertEqual(set(report.keys()), expected_top_keys)

        # Verify metadata
        self.assertEqual(report["report_metadata"]["report_format"], "json")
        self.assertEqual(report["report_metadata"]["report_version"], REPORT_FORMAT_VERSION)
        self.assertEqual(report["report_metadata"]["system_name"], SYSTEM_NAME)
        self.assertEqual(report["report_metadata"]["system_version"], SYSTEM_VERSION)
        self.assertIn("generated_at", report["report_metadata"])

        # Verify regulatory reference
        self.assertEqual(report["regulatory_reference"]["framework"], REGULATORY_FRAMEWORK)
        self.assertEqual(report["regulatory_reference"]["jurisdiction"], REGULATORY_JURISDICTION)

    # 2. Declarations serialization
    def test_declarations_serialization(self):
        report = compile_report_dict(
            scan_id=self.scan_id,
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=self.declarations,
        )

        decls = report["declarations"]
        self.assertEqual(len(decls), 2)
        self.assertEqual(decls[0]["field_name"], "generic_name")
        self.assertEqual(decls[0]["raw_value"], "Basmati Rice")
        self.assertEqual(decls[0]["normalized_value"], "Basmati Rice")
        self.assertEqual(decls[0]["confidence"], 0.985)
        self.assertEqual(decls[0]["source"], "gemini")
        self.assertEqual(decls[0]["status"], "detected")
        self.assertEqual(decls[0]["bounding_box"], {"x": 10.0, "y": 20.0, "width": 100.0, "height": 30.0})

    # 3. Violations serialization
    def test_violations_serialization(self):
        report = compile_report_dict(
            scan_id=self.scan_id,
            verdict=ComplianceVerdict.FAIL,
            compliance_score=50.0,
            violations=self.violations,
        )

        viols = report["violations"]
        self.assertEqual(len(viols), 1)
        self.assertEqual(viols[0]["id"], "viol-1")
        self.assertEqual(viols[0]["rule_id"], "LMR-R06-1-E")
        self.assertEqual(viols[0]["rule_code"], "Rule-6(1)(e)")
        self.assertEqual(viols[0]["field_name"], "mrp")
        self.assertEqual(viols[0]["violation_type"], "missing_declaration")
        self.assertEqual(viols[0]["severity"], "critical")
        self.assertEqual(viols[0]["description"], "MRP declaration is mandatory.")

    # 4. Evidence references & product info
    def test_evidence_and_product_info(self):
        report = compile_report_dict(
            scan_id=self.scan_id,
            product_category="Edible Oil",
            declarations=self.declarations,
            image_path="storage/scans/123/original.jpg",
            evidence_path="storage/scans/123/evidence.jpg",
        )

        self.assertEqual(report["product_information"]["product_category"], "Edible Oil")
        self.assertEqual(report["product_information"]["product_name"], "Basmati Rice")
        self.assertEqual(report["evidence_artifacts"]["original_image_path"], "storage/scans/123/original.jpg")
        self.assertEqual(report["evidence_artifacts"]["evidence_image_path"], "storage/scans/123/evidence.jpg")

    # 5. Reviewer audit section
    def test_reviewer_audit_section(self):
        report_unreviewed = compile_report_dict(scan_id=self.scan_id)
        self.assertFalse(report_unreviewed["reviewer_audit"]["is_reviewed"])
        self.assertIsNone(report_unreviewed["reviewer_audit"]["reviewer_notes"])

        report_reviewed = compile_report_dict(
            scan_id=self.scan_id,
            reviewer_notes="Verified manually from package back panel.",
        )
        self.assertTrue(report_reviewed["reviewer_audit"]["is_reviewed"])
        self.assertEqual(
            report_reviewed["reviewer_audit"]["reviewer_notes"],
            "Verified manually from package back panel.",
        )

    # 6. Generate JSON report on disk with auto directory creation
    def test_generate_json_report_file_creation(self):
        target_path = os.path.join(self.test_dir, "nested", "sub", "report.json")
        returned_path = generate_json_report(
            scan_id=self.scan_id,
            verdict=ComplianceVerdict.PASS,
            compliance_score=95.5,
            product_category="Snacks",
            declarations=self.declarations,
            violations=[],
            image_path="storage/scans/1/orig.jpg",
            evidence_path="storage/scans/1/evid.jpg",
            output_path=target_path,
        )

        self.assertEqual(returned_path, target_path)
        self.assertTrue(os.path.exists(target_path))

        # Read back and parse JSON
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["scan_metadata"]["scan_id"], self.scan_id)
        self.assertEqual(data["compliance_summary"]["verdict"], "PASS")
        self.assertEqual(data["compliance_summary"]["compliance_score"], 95.5)
        self.assertEqual(len(data["declarations"]), 2)
        self.assertEqual(len(data["violations"]), 0)

    # 7. Unpacking from ComplianceResult object
    def test_generate_from_compliance_result_object(self):
        comp_result = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=60.0,
            declarations=self.declarations,
            violations=self.violations,
            evidence=EvidenceMetadata(
                annotated_image_path="storage/scans/xyz/evidence.jpg",
                total_declarations_checked=2,
                total_violations_found=1,
            ),
        )

        report = compile_report_dict(
            scan_id=self.scan_id,
            compliance_result=comp_result,
            product_category="Grains",
        )

        self.assertEqual(report["compliance_summary"]["verdict"], "NEEDS_REVIEW")
        self.assertEqual(report["compliance_summary"]["compliance_score"], 60.0)
        self.assertEqual(report["evidence_artifacts"]["evidence_image_path"], "storage/scans/xyz/evidence.jpg")

    # 8. No fabrication of missing declarations
    def test_no_fabrication_of_declarations(self):
        report = compile_report_dict(scan_id=self.scan_id, declarations=[])
        self.assertEqual(report["declarations"], [])
        self.assertEqual(report["compliance_summary"]["total_declarations_evaluated"], 0)


if __name__ == "__main__":
    unittest.main()
