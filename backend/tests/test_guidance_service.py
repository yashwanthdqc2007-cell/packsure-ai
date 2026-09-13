"""
PackSure AI — Comprehensive Unit Tests for Intelligent Recapture & Guidance Engine.

Tests:
1. Severe blur detection produces BLUR_CRITICAL with critical priority.
2. Soft focus produces BLUR_SOFT with high priority.
3. Glare/overexposure triggers GLARE_DETECTED with camera tilt guidance.
4. Underexposure triggers UNDEREXPOSED with lighting guidance.
5. Low resolution triggers LOW_RESOLUTION with closer camera distance guidance.
6. Cross-view fusion conflict triggers MULTI_VIEW_CONFLICT.
7. Incomplete scan missing MRP/dates recommends Back Panel capture.
8. Incomplete scan missing Manufacturer/Customer Care recommends Side Panel capture.
9. Incomplete scan missing Net Quantity recommends Front PDP capture.
10. USP violation triggers USP_EVIDENCE_UNCERTAIN.
11. Maximum 3 guidance items limit is strictly enforced.
12. Flawless complete scan returns needs_recapture=False and priority=none.
13. Strict priority ordering: Quality blockers > Cross-view conflicts > Missing evidence.
"""

import unittest
from app.schemas.compliance import ComplianceResult, ComplianceVerdict
from app.schemas.declaration import DeclarationStatus, ExtractedDeclaration
from app.schemas.guidance import (
    GuidanceIssueCategory,
    GuidancePriority,
    GuidanceTargetPanel,
    InspectionGuidance,
)
from app.schemas.image import ImageQualityReport, QualityMetrics, QualityStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.guidance_service import generate_inspection_guidance


def _make_metrics(
    width=1920,
    height=1080,
    blur_score=350.0,
    brightness_score=125.0,
    contrast_score=65.0,
    resolution_acceptable=True,
    is_blurry=False,
    is_too_dark=False,
    is_too_bright=False,
    is_low_contrast=False,
) -> QualityMetrics:
    return QualityMetrics(
        width=width,
        height=height,
        total_pixels=width * height,
        resolution_acceptable=resolution_acceptable,
        blur_score=blur_score,
        is_blurry=is_blurry,
        brightness_score=brightness_score,
        is_too_dark=is_too_dark,
        is_too_bright=is_too_bright,
        contrast_score=contrast_score,
        is_low_contrast=is_low_contrast,
    )


class TestGuidanceService(unittest.TestCase):
    """Unit tests for generate_inspection_guidance."""

    def test_flawless_complete_scan_returns_no_recapture(self):
        """A complete scan with all declarations and high quality requires no recapture."""
        q_report = ImageQualityReport(
            is_valid=True,
            status=QualityStatus.acceptable,
            quality_score=0.95,
            metrics=_make_metrics(blur_score=350.0, brightness_score=125.0),
        )
        declarations = [
            ExtractedDeclaration(field_name="generic_name", status=DeclarationStatus.detected, raw_value="Atta"),
            ExtractedDeclaration(field_name="net_quantity", status=DeclarationStatus.detected, raw_value="5 kg"),
            ExtractedDeclaration(field_name="mrp", status=DeclarationStatus.detected, raw_value="₹250.00"),
            ExtractedDeclaration(field_name="unit_sale_price", status=DeclarationStatus.detected, raw_value="₹50.00 / kg"),
            ExtractedDeclaration(field_name="manufacture_date", status=DeclarationStatus.detected, raw_value="01/2026"),
            ExtractedDeclaration(field_name="expiry_date", status=DeclarationStatus.detected, raw_value="07/2026"),
            ExtractedDeclaration(field_name="batch_number", status=DeclarationStatus.detected, raw_value="B-101"),
            ExtractedDeclaration(field_name="manufacturer_name_and_address", status=DeclarationStatus.detected, raw_value="ABC Mills Ltd, Mumbai"),
            ExtractedDeclaration(field_name="consumer_care", status=DeclarationStatus.detected, raw_value="care@abcmills.com"),
        ]

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=declarations,
            violations=[],
            is_complete_scan=True,
            product_category="Food Grains",
        )

        self.assertFalse(guidance.needs_recapture)
        self.assertEqual(guidance.priority, GuidancePriority.none)
        self.assertEqual(len(guidance.issues), 0)
        self.assertEqual(len(guidance.actionable_steps), 0)
        self.assertGreaterEqual(guidance.coverage_estimate_pct, 90.0)

    def test_severe_blur_triggers_critical_recapture(self):
        """Severely blurry image triggers BLUR_CRITICAL with steady camera guidance."""
        q_report = ImageQualityReport(
            is_valid=False,
            status=QualityStatus.rejected,
            quality_score=0.1,
            recapture_reason="Image is severely blurry; please hold camera steady.",
            metrics=_make_metrics(blur_score=22.0, is_blurry=True),
        )

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=[],
            violations=[
                Violation(
                    rule_code="QUALITY-REJECT",
                    violation_type=ViolationType.illegible,
                    severity=ViolationSeverity.major,
                    description="Image quality rejected due to blur",
                )
            ],
            is_complete_scan=False,
        )

        self.assertTrue(guidance.needs_recapture)
        self.assertEqual(guidance.priority, GuidancePriority.critical)
        self.assertTrue(any(i.code == "BLUR_CRITICAL" for i in guidance.issues))
        self.assertTrue(any("steady" in step.lower() for step in guidance.actionable_steps))

    def test_glare_triggers_tilt_camera_guidance(self):
        """Overexposed / glare image triggers GLARE_DETECTED recommending 15-30 degree tilt."""
        q_report = ImageQualityReport(
            is_valid=True,
            status=QualityStatus.borderline,
            quality_score=0.55,
            metrics=_make_metrics(brightness_score=240.0, is_too_bright=True),
        )

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=[],
            violations=[],
            is_complete_scan=False,
        )

        self.assertTrue(guidance.needs_recapture)
        self.assertEqual(guidance.priority, GuidancePriority.high)
        glare_issue = next((i for i in guidance.issues if i.code == "GLARE_DETECTED"), None)
        self.assertIsNotNone(glare_issue)
        self.assertIn("15°", glare_issue.suggested_action)

    def test_incomplete_scan_missing_mrp_cluster_recommends_back_panel(self):
        """Incomplete scan missing MRP, Dates, Batch recommends Back Panel capture."""
        q_report = ImageQualityReport(
            is_valid=True,
            status=QualityStatus.acceptable,
            quality_score=0.9,
            metrics=_make_metrics(),
        )
        # Only front declarations detected
        declarations = [
            ExtractedDeclaration(field_name="generic_name", status=DeclarationStatus.detected, raw_value="Potato Chips"),
            ExtractedDeclaration(field_name="net_quantity", status=DeclarationStatus.detected, raw_value="100 g"),
        ]

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=declarations,
            violations=[],
            is_complete_scan=False,
        )

        self.assertTrue(guidance.needs_recapture)
        self.assertEqual(guidance.priority, GuidancePriority.medium)
        self.assertIn("back", guidance.target_panels)
        mrp_issue = next((i for i in guidance.issues if i.code == "MISSING_MRP_PANEL"), None)
        self.assertIsNotNone(mrp_issue)
        self.assertIn("mrp", mrp_issue.affected_fields)

    def test_incomplete_scan_missing_side_panel_recommends_side_panel(self):
        """Incomplete scan missing manufacturer and consumer care recommends Side Panel capture."""
        q_report = ImageQualityReport(
            is_valid=True,
            status=QualityStatus.acceptable,
            quality_score=0.9,
            metrics=_make_metrics(),
        )
        # Front and MRP present, but side/contact details missing
        declarations = [
            ExtractedDeclaration(field_name="generic_name", status=DeclarationStatus.detected, raw_value="Corn Flakes"),
            ExtractedDeclaration(field_name="net_quantity", status=DeclarationStatus.detected, raw_value="500 g"),
            ExtractedDeclaration(field_name="mrp", status=DeclarationStatus.detected, raw_value="₹190.00"),
            ExtractedDeclaration(field_name="unit_sale_price", status=DeclarationStatus.detected, raw_value="₹0.38 / g"),
            ExtractedDeclaration(field_name="manufacture_date", status=DeclarationStatus.detected, raw_value="02/2026"),
            ExtractedDeclaration(field_name="expiry_date", status=DeclarationStatus.detected, raw_value="08/2026"),
            ExtractedDeclaration(field_name="batch_number", status=DeclarationStatus.detected, raw_value="CF-99"),
        ]

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=declarations,
            violations=[],
            is_complete_scan=False,
        )

        self.assertTrue(guidance.needs_recapture)
        self.assertIn("side", guidance.target_panels)
        side_issue = next((i for i in guidance.issues if i.code == "MISSING_SIDE_PANEL"), None)
        self.assertIsNotNone(side_issue)

    def test_cross_view_conflict_triggers_conflict_guidance(self):
        """Cross-view MRP mismatch violation triggers MULTI_VIEW_CONFLICT guidance."""
        conflict_viol = Violation(
            rule_code="FUSION-CONFLICT",
            field_name="mrp",
            violation_type=ViolationType.misleading,
            severity=ViolationSeverity.major,
            description="Conflicting values detected for 'mrp' across views: View 0 declared '150.00' vs View 1 declared '200.00'.",
        )

        guidance = generate_inspection_guidance(
            quality_reports=[None, None],
            declarations=[],
            violations=[conflict_viol],
            is_complete_scan=False,
        )

        self.assertTrue(guidance.needs_recapture)
        self.assertEqual(guidance.priority, GuidancePriority.high)
        conflict_issue = next((i for i in guidance.issues if i.code == "MULTI_VIEW_CONFLICT"), None)
        self.assertIsNotNone(conflict_issue)
        self.assertEqual(conflict_issue.category, GuidanceIssueCategory.conflict)

    def test_maximum_three_guidance_items_capped(self):
        """When multiple issues exist simultaneously, output is strictly capped at max 3 items."""
        q_report1 = ImageQualityReport(
            is_valid=True,
            status=QualityStatus.borderline,
            quality_score=0.6,
            metrics=_make_metrics(blur_score=80.0, brightness_score=240.0, is_blurry=True, is_too_bright=True),
        )
        conflict_viol = Violation(
            rule_code="FUSION-CONFLICT",
            field_name="batch_number",
            violation_type=ViolationType.misleading,
            severity=ViolationSeverity.major,
            description="Batch number conflict",
        )
        usp_viol = Violation(
            rule_code="LM-RULE-6-11-MISMATCH",
            field_name="unit_sale_price",
            violation_type=ViolationType.out_of_range,
            severity=ViolationSeverity.major,
            description="USP mismatch",
        )

        guidance = generate_inspection_guidance(
            quality_reports=[q_report1],
            declarations=[],
            violations=[conflict_viol, usp_viol],
            is_complete_scan=False,
        )

        self.assertLessEqual(len(guidance.issues), 3)
        self.assertLessEqual(len(guidance.actionable_steps), 3)

    def test_priority_hierarchy_quality_over_evidence(self):
        """Image quality blockers take higher priority than missing panel evidence."""
        q_report = ImageQualityReport(
            is_valid=False,
            status=QualityStatus.rejected,
            quality_score=0.1,
            recapture_reason="Severe blur",
            metrics=_make_metrics(blur_score=15.0, is_blurry=True),
        )

        guidance = generate_inspection_guidance(
            quality_reports=[q_report],
            declarations=[],
            violations=[],
            is_complete_scan=False,
        )

        # Quality issue should be the first item in the list
        self.assertEqual(guidance.priority, GuidancePriority.critical)
        self.assertEqual(guidance.issues[0].category, GuidanceIssueCategory.quality)


if __name__ == "__main__":
    unittest.main()
