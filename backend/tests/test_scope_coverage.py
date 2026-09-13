"""
Unit and integration tests for PackSure Phase 4A Scope & Legal Coverage Transparency.

Validates:
1. Deterministic ScopeCoverageManifest generation with accurate statutory tier categorization.
2. ComplianceResult and ScanResponse inclusion of scope coverage.
3. Deserialization safety: backward compatibility for legacy scan payloads without scope manifests.
4. Proper score description and naming: "Visual Label Compliance Score".
5. Complete exclusion lists for physical metrology and external database checks.
6. Multi-view and single-view status representation in the manifest.
7. report.json artifact serialization including the scope manifest and score definition.
"""

import json
import os
import tempfile
import unittest

from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    DEFAULT_EXTERNAL_DATA_CHECKS_EXCLUDED,
    DEFAULT_IMAGE_VERIFIABLE_RULES,
    DEFAULT_PHYSICAL_CHECKS_EXCLUDED,
    ScopeCoverageManifest,
    generate_scope_coverage_manifest,
)
from app.schemas.declaration import DeclarationStatus, ExtractedDeclaration
from app.schemas.scan import ScanResponse, ScanStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.report_service import compile_report_dict, generate_json_report


class TestScopeCoverageManifest(unittest.TestCase):
    """Test suite for deterministic ScopeCoverageManifest generation and schemas."""

    def test_single_view_manifest_generation(self):
        """Verify default single-view manifest creation."""
        manifest = generate_scope_coverage_manifest(
            views_captured_count=1,
            is_complete_scan=False,
        )
        self.assertIsInstance(manifest, ScopeCoverageManifest)
        self.assertEqual(manifest.score_name, "Visual Label Compliance Score")
        self.assertIn("Visual Label Compliance Score", manifest.score_name)
        self.assertTrue("LMR 2011" in manifest.score_meaning or "Legal Metrology" in manifest.score_meaning)
        self.assertEqual(manifest.views_captured_count, 1)
        self.assertFalse(manifest.is_complete_scan)
        self.assertIn("SINGLE_VIEW_PARTIAL", manifest.multi_view_status)
        self.assertEqual(len(manifest.image_verifiable_rules_checked), len(DEFAULT_IMAGE_VERIFIABLE_RULES))
        self.assertEqual(len(manifest.physical_checks_excluded), len(DEFAULT_PHYSICAL_CHECKS_EXCLUDED))
        self.assertEqual(len(manifest.external_data_checks_excluded), len(DEFAULT_EXTERNAL_DATA_CHECKS_EXCLUDED))
        self.assertIn("does not constitute a legal certification", manifest.disclaimer)

    def test_multi_view_partial_manifest_generation(self):
        """Verify multi-view incomplete manifest creation."""
        manifest = generate_scope_coverage_manifest(
            views_captured_count=4,
            is_complete_scan=False,
        )
        self.assertEqual(manifest.views_captured_count, 4)
        self.assertFalse(manifest.is_complete_scan)
        self.assertIn("MULTI_VIEW_PARTIAL (4 views captured", manifest.multi_view_status)

    def test_multi_view_complete_manifest_generation(self):
        """Verify multi-view complete manifest creation."""
        manifest = generate_scope_coverage_manifest(
            views_captured_count=6,
            is_complete_scan=True,
        )
        self.assertEqual(manifest.views_captured_count, 6)
        self.assertTrue(manifest.is_complete_scan)
        self.assertIn("COMPLETE_PANEL_COVERAGE", manifest.multi_view_status)

    def test_physical_checks_exclusion_content(self):
        """Verify physical metrology checks are explicitly listed as excluded."""
        manifest = generate_scope_coverage_manifest()
        excluded_text = " ".join(manifest.physical_checks_excluded).lower()
        self.assertIn("gravimetric", excluded_text)
        self.assertIn("first schedule", excluded_text)
        self.assertIn("font height", excluded_text)
        self.assertIn("second schedule", excluded_text)
        self.assertIn("deceptive packaging", excluded_text)

    def test_external_data_checks_exclusion_content(self):
        """Verify external regulatory/registry checks are explicitly listed as excluded."""
        manifest = generate_scope_coverage_manifest()
        excluded_text = " ".join(manifest.external_data_checks_excluded).lower()
        self.assertIn("rule 27", excluded_text)
        self.assertIn("registration", excluded_text)
        self.assertIn("epr", excluded_text)
        self.assertIn("fssai", excluded_text)

    def test_compliance_result_with_scope_manifest(self):
        """Verify ComplianceResult serializes and deserializes scope_coverage correctly."""
        manifest = generate_scope_coverage_manifest(views_captured_count=2, is_complete_scan=False)
        result = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[
                ExtractedDeclaration(field_name="generic_name", status=DeclarationStatus.detected, raw_value="Atta")
            ],
            violations=[],
            scope_coverage=manifest,
        )
        self.assertIsNotNone(result.scope_coverage)
        self.assertEqual(result.scope_coverage.views_captured_count, 2)
        dumped = result.model_dump()
        self.assertIn("scope_coverage", dumped)
        self.assertEqual(dumped["scope_coverage"]["score_name"], "Visual Label Compliance Score")

    def test_backward_compatibility_legacy_deserialization(self):
        """Verify that legacy scans without scope_coverage deserialize without error."""
        legacy_compliance_data = {
            "verdict": "PASS",
            "compliance_score": 95.0,
            "declarations": [],
            "violations": [],
        }
        res = ComplianceResult.model_validate(legacy_compliance_data)
        self.assertIsNone(res.scope_coverage)
        self.assertEqual(res.compliance_score, 95.0)

        legacy_scan_response_data = {
            "scan_id": "legacy-scan-001",
            "status": "complete",
            "verdict": "PASS",
            "compliance_score": 95.0,
            "declarations": [],
            "violations": [],
            "created_at": "2026-01-01T00:00:00Z",
        }
        scan_resp = ScanResponse.model_validate(legacy_scan_response_data)
        self.assertIsNone(scan_resp.scope_coverage)
        self.assertEqual(scan_resp.scan_id, "legacy-scan-001")

    def test_report_dict_contains_scope_coverage_and_score_definition(self):
        """Verify compile_report_dict embeds scope_coverage and score definition."""
        manifest = generate_scope_coverage_manifest(views_captured_count=3, is_complete_scan=True)
        report = compile_report_dict(
            scan_id="test-scan-scope-1",
            verdict="PASS",
            compliance_score=100.0,
            product_category="Food Grains",
            scope_coverage=manifest,
        )
        self.assertIn("scope_coverage", report)
        self.assertEqual(report["scope_coverage"]["views_captured_count"], 3)
        self.assertTrue(report["scope_coverage"]["is_complete_scan"])
        self.assertEqual(report["compliance_summary"]["score_name"], "Visual Label Compliance Score")
        self.assertIn("Evaluates visible declarations", report["compliance_summary"]["score_definition"])

    def test_json_report_file_generation_includes_scope(self):
        """Verify generate_json_report writes scope_coverage to disk."""
        manifest = generate_scope_coverage_manifest(views_captured_count=2, is_complete_scan=False)
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "report.json")
            path = generate_json_report(
                scan_id="test-file-report",
                verdict="NEEDS_REVIEW",
                compliance_score=60.0,
                product_category="Cosmetics",
                output_path=out_file,
                scope_coverage=manifest,
            )
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("scope_coverage", data)
            self.assertEqual(data["scope_coverage"]["score_name"], "Visual Label Compliance Score")
            self.assertEqual(data["scope_coverage"]["views_captured_count"], 2)
            self.assertIn("physical_checks_excluded", data["scope_coverage"])
            self.assertIn("external_data_checks_excluded", data["scope_coverage"])


if __name__ == "__main__":
    unittest.main()
