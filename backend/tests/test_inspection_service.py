"""
PackSure AI — Phase 5A Inspection Completeness & Next Best Action Test Matrix.

Verifies:
CASE 1: Single front image only -> INCOMPLETE, next action = additional package view / appropriate recapture.
CASE 2: Front + back, all visible checks resolved -> READY_TO_FINALIZE, no unnecessary image request.
CASE 3: Image quality blocker -> INCOMPLETE, next action = image_recapture_quality.
CASE 4: Conflicting declaration evidence -> NEEDS_REVIEW, next action = review_conflicting_evidence.
CASE 5: Unreadable / uncertain declaration -> READY_TO_REVIEW, next action = review_findings.
CASE 6: Package composition UNCERTAIN -> NEEDS_REVIEW, next action = review_package_composition.
CASE 7: QR evidence unresolved for electronic product -> NEEDS_REVIEW, next action = review_qr_evidence.
CASE 8: All visual checks complete but officer review pending -> READY_TO_REVIEW, next action = review_findings.
CASE 9: Physical quantity verification not evaluated -> physical status = NOT_EVALUATED.
CASE 10: External regulatory verification not evaluated -> external status = NOT_EVALUATED.
CASE 11: Everything required completed -> READY_TO_FINALIZE, next action = finalize_inspection.
CASE 12: Officer has already reviewed/confirmed findings -> respects officer decision, transitions to READY_TO_FINALIZE.
CASE 13: Legacy scan without inspection-state fields -> deserializes cleanly to None.
CASE 14: Report serialization with inspection state and next best action.
"""

import unittest
from typing import List

from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    ElectronicApplicability,
    EvidenceMetadata,
    QREvidence,
    QREvidenceStatus,
    ScopeCoverageManifest,
    generate_scope_coverage_manifest,
)
from app.schemas.declaration import (
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageItem,
    PackageType,
)
from app.schemas.guidance import (
    GuidanceIssue,
    GuidanceIssueCategory,
    GuidancePriority,
    GuidanceTargetPanel,
    InspectionGuidance,
)
from app.schemas.image import ImageQualityReport, QualityMetrics, QualityStatus
from app.schemas.inspection_state import (
    ExternalChecksStatus,
    InspectionState,
    InspectionStateStatus,
    NextBestAction,
    OfficerReviewStatus,
    PhysicalChecksStatus,
)
from app.schemas.scan import ScanResponse, ScanStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.inspection_service import derive_inspection_state_and_next_action
from app.services.report_service import compile_report_dict


class TestInspectionServiceMatrix(unittest.TestCase):
    """Deterministic validation test suite for Phase 5A Inspection State & Next Best Action."""

    def test_case_01_single_front_image_incomplete(self):
        """CASE 1: Single front image only -> INCOMPLETE, next action = additional package view."""
        guidance = InspectionGuidance(
            needs_recapture=True,
            priority=GuidancePriority.medium,
            headline="Additional Package Views Recommended",
            target_panels=["back", "side"],
            issues=[
                GuidanceIssue(
                    code="MISSING_MRP_PANEL",
                    category=GuidanceIssueCategory.missing_evidence,
                    title="Capture Back / MRP Panel",
                    description="MRP panel not observed on front view.",
                    suggested_action="Capture the rear panel showing MRP and dates.",
                    target_panel=GuidanceTargetPanel.mrp_panel,
                )
            ],
            actionable_steps=["Capture the rear panel showing MRP and dates."],
            coverage_estimate_pct=40.0,
        )
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=50.0,
            declarations=[
                ExtractedDeclaration(
                    field_name="generic_name",
                    raw_value="Shampoo",
                    status=DeclarationStatus.detected,
                )
            ],
            violations=[],
            guidance=guidance,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=1,
            is_complete_scan=False,
        )

        self.assertEqual(state.status, InspectionStateStatus.INCOMPLETE)
        self.assertFalse(state.visual_checks_complete)
        self.assertEqual(state.views_captured, 1)
        self.assertEqual(next_act.action_code, "capture_additional_view")
        self.assertIn("Back", next_act.title)
        self.assertEqual(state.physical_checks_status, PhysicalChecksStatus.NOT_EVALUATED)
        self.assertEqual(state.external_checks_status, ExternalChecksStatus.NOT_EVALUATED)

    def test_case_02_front_and_back_complete(self):
        """CASE 2: Front + back, all visible checks resolved -> READY_TO_FINALIZE, no unnecessary request."""
        decls = [
            ExtractedDeclaration(field_name="generic_name", raw_value="Rice", status=DeclarationStatus.detected),
            ExtractedDeclaration(field_name="net_quantity", raw_value="1 kg", status=DeclarationStatus.detected),
            ExtractedDeclaration(field_name="mrp", raw_value="₹100", status=DeclarationStatus.detected),
            ExtractedDeclaration(field_name="unit_sale_price", raw_value="₹100/kg", status=DeclarationStatus.detected),
        ]
        guidance = InspectionGuidance(
            needs_recapture=False,
            priority=GuidancePriority.none,
            headline="All Mandatory Evidence Captured",
            target_panels=[],
            issues=[],
            actionable_steps=[],
            coverage_estimate_pct=100.0,
        )
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=decls,
            violations=[],
            guidance=guidance,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.READY_TO_FINALIZE)
        self.assertTrue(state.visual_checks_complete)
        self.assertTrue(state.ready_to_finalize)
        self.assertEqual(next_act.action_code, "finalize_inspection")

    def test_case_03_image_quality_blocker(self):
        """CASE 3: Image quality blocker -> INCOMPLETE, next action = image_recapture_quality."""
        q_report = ImageQualityReport(
            is_valid=False,
            quality_score=0.1,
            status=QualityStatus.rejected,
            recapture_reason="Severe image blur detected. Please hold camera steady.",
            metrics=QualityMetrics(
                width=1920,
                height=1080,
                total_pixels=2073600,
                resolution_acceptable=True,
                blur_score=12.5,
                is_blurry=True,
                brightness_score=120.0,
                is_too_dark=False,
                is_too_bright=False,
                contrast_score=45.0,
                is_low_contrast=False,
            ),
        )
        guidance = InspectionGuidance(
            needs_recapture=True,
            priority=GuidancePriority.critical,
            headline="Immediate Recapture Required — Image Quality Unusable",
            target_panels=["front"],
            issues=[
                GuidanceIssue(
                    code="BLUR_CRITICAL",
                    category=GuidanceIssueCategory.quality,
                    title="Severe Image Blur",
                    description="Photo is blurry.",
                    suggested_action="Hold camera steady.",
                )
            ],
            actionable_steps=["Hold camera steady."],
        )
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=[],
            violations=[],
            guidance=guidance,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            quality_reports=[q_report],
            views_captured_count=1,
            is_complete_scan=False,
        )

        self.assertEqual(state.status, InspectionStateStatus.INCOMPLETE)
        self.assertEqual(next_act.action_code, "image_recapture_quality")
        self.assertEqual(next_act.priority, "critical")
        self.assertIn("Severe Image Blur", state.quality_blockers)

    def test_case_04_conflicting_declaration_evidence(self):
        """CASE 4: Conflicting declaration evidence -> NEEDS_REVIEW, next action = review_conflicting_evidence."""
        viols = [
            Violation(
                rule_code="RULE-FUSION-CONFLICT",
                field_name="mrp",
                violation_type=ViolationType.missing_declaration,
                severity=ViolationSeverity.major,
                description="Conflicting values detected for 'mrp' across views: 150.00 vs 200.00.",
            )
        ]
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=50.0,
            declarations=[
                ExtractedDeclaration(field_name="mrp", raw_value="150.00", status=DeclarationStatus.uncertain)
            ],
            violations=viols,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.NEEDS_REVIEW)
        self.assertEqual(next_act.action_code, "review_conflicting_evidence")
        self.assertEqual(next_act.target_tab, "review")
        self.assertIn("mrp", state.evidence_conflicts)

    def test_case_05_unreadable_uncertain_declaration(self):
        """CASE 5: Uncertain declaration -> READY_TO_REVIEW, next action = review_findings."""
        decls = [
            ExtractedDeclaration(field_name="expiry_date", raw_value="??/2026", status=DeclarationStatus.uncertain),
        ]
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=85.0,
            declarations=decls,
            violations=[],
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.READY_TO_REVIEW)
        self.assertEqual(next_act.action_code, "review_findings")
        self.assertEqual(state.officer_review_status, OfficerReviewStatus.PENDING)

    def test_case_06_package_composition_uncertain(self):
        """CASE 6: Package composition UNCERTAIN -> NEEDS_REVIEW, next action = review_package_composition."""
        comp = PackageComposition(
            package_type=PackageType.UNCERTAIN,
            total_item_count=2,
            items=[],
            status=DeclarationStatus.uncertain,
        )
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=75.0,
            declarations=[],
            violations=[],
            composition=comp,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.NEEDS_REVIEW)
        self.assertEqual(next_act.action_code, "review_package_composition")

    def test_case_07_qr_evidence_unresolved(self):
        """CASE 7: QR evidence unresolved for electronic product -> NEEDS_REVIEW, next action = review_qr_evidence."""
        qr_ev = QREvidence(
            detected=True,
            status=QREvidenceStatus.uncertain,
            applicable_product=ElectronicApplicability.APPLICABLE,
            instruction_detected=False,
        )
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=70.0,
            declarations=[],
            violations=[],
            qr_evidence=qr_ev,
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.NEEDS_REVIEW)
        self.assertEqual(next_act.action_code, "review_qr_evidence")

    def test_case_08_officer_review_pending(self):
        """CASE 8: All visual checks complete but officer review pending -> READY_TO_REVIEW, next action = review_findings."""
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=90.0,
            declarations=[
                ExtractedDeclaration(field_name="generic_name", raw_value="Snack", status=DeclarationStatus.uncertain)
            ],
            violations=[],
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
            is_reviewed=False,
        )

        self.assertEqual(state.status, InspectionStateStatus.READY_TO_REVIEW)
        self.assertEqual(next_act.action_code, "review_findings")
        self.assertEqual(state.officer_review_status, OfficerReviewStatus.PENDING)

    def test_case_09_10_physical_and_external_checks_not_evaluated(self):
        """CASE 9 & 10: Physical metrology and external registry checks remain NOT_EVALUATED."""
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[],
            violations=[],
        )

        state, _ = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.physical_checks_status, PhysicalChecksStatus.NOT_EVALUATED)
        self.assertEqual(state.external_checks_status, ExternalChecksStatus.NOT_EVALUATED)

    def test_case_11_ready_to_finalize(self):
        """CASE 11: Everything completed -> READY_TO_FINALIZE, next action = finalize_inspection."""
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[],
            violations=[],
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
        )

        self.assertEqual(state.status, InspectionStateStatus.READY_TO_FINALIZE)
        self.assertTrue(state.visual_checks_complete)
        self.assertTrue(state.ready_to_finalize)
        self.assertEqual(next_act.action_code, "finalize_inspection")

    def test_case_12_officer_review_completed(self):
        """CASE 12: Officer has reviewed -> respects officer decision and transitions to READY_TO_FINALIZE."""
        comp_res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=95.0,
            declarations=[
                ExtractedDeclaration(field_name="generic_name", raw_value="Snack", status=DeclarationStatus.detected)
            ],
            violations=[],
        )

        state, next_act = derive_inspection_state_and_next_action(
            compliance_result=comp_res,
            views_captured_count=2,
            is_complete_scan=True,
            is_reviewed=True,
            reviewer_notes="Verified by Inspector Sharma: packaging text clear.",
        )

        self.assertEqual(state.status, InspectionStateStatus.READY_TO_FINALIZE)
        self.assertEqual(state.officer_review_status, OfficerReviewStatus.COMPLETED)
        self.assertEqual(next_act.action_code, "finalize_inspection")

    def test_case_13_legacy_scan_deserialization(self):
        """CASE 13: Legacy scan without inspection_state fields deserializes cleanly to None."""
        scan_resp = ScanResponse(
            scan_id="legacy-scan-uuid-13",
            status=ScanStatus.complete,
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[],
            violations=[],
            created_at="2026-09-15T00:00:00Z",
            inspection_state=None,
            next_best_action=None,
        )
        self.assertIsNone(scan_resp.inspection_state)
        self.assertIsNone(scan_resp.next_best_action)

    def test_case_14_report_serialization(self):
        """CASE 14: Compiling report includes serialized inspection_state and next_best_action."""
        state = InspectionState(
            status=InspectionStateStatus.READY_TO_FINALIZE,
            visual_checks_complete=True,
            views_captured=2,
            ready_to_finalize=True,
        )
        next_act = NextBestAction(
            action_code="finalize_inspection",
            title="Finalize Inspection Report",
            description="Ready for final sign-off.",
        )
        rep = compile_report_dict(
            scan_id="scan-report-14",
            verdict="PASS",
            compliance_score=100.0,
            declarations=[],
            violations=[],
            inspection_state=state,
            next_best_action=next_act,
        )
        self.assertIn("inspection_state", rep)
        self.assertEqual(rep["inspection_state"]["status"], "READY_TO_FINALIZE")
        self.assertIn("next_best_action", rep)
        self.assertEqual(rep["next_best_action"]["action_code"], "finalize_inspection")


if __name__ == "__main__":
    unittest.main()
