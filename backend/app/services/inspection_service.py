"""
PackSure AI — Inspection Completeness & Next Best Action Service.

Implements Phase 5A deterministic operational inspection state evaluation:
1. Synthesizes visual declaration checks, multi-view panel coverage, and evidence review.
2. Formulates exactly ONE highest-priority next best action for the field inspector.
3. Distinguishes evaluated visual evidence from unperformed physical and external checks.
4. Preserves backward compatibility and respects officer review decisions.

Key Invariants:
- Operational assistance only: does NOT modify statutory legal compliance verdicts.
- Consumes existing guidance from guidance_service without duplicating recapture logic.
- Avoids over-claiming: explicitly marks physical and external checks as NOT_EVALUATED.
"""

import logging
from typing import List, Optional, Sequence, Tuple

from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    ElectronicApplicability,
    QREvidence,
    QREvidenceStatus,
    ScopeCoverageManifest,
)
from app.schemas.declaration import (
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageType,
)
from app.schemas.guidance import GuidanceIssueCategory, GuidancePriority, InspectionGuidance
from app.schemas.image import ImageQualityReport, QualityStatus
from app.schemas.inspection_state import (
    ExternalChecksStatus,
    InspectionState,
    InspectionStateStatus,
    NextBestAction,
    OfficerReviewStatus,
    PhysicalChecksStatus,
)
from app.schemas.violation import Violation

logger = logging.getLogger(__name__)


def derive_inspection_state_and_next_action(
    compliance_result: Optional[ComplianceResult] = None,
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    violations: Optional[Sequence[Violation]] = None,
    guidance: Optional[InspectionGuidance] = None,
    scope_coverage: Optional[ScopeCoverageManifest] = None,
    qr_evidence: Optional[QREvidence] = None,
    composition: Optional[PackageComposition] = None,
    quality_reports: Optional[Sequence[Optional[ImageQualityReport]]] = None,
    views_captured_count: int = 1,
    is_complete_scan: bool = False,
    is_reviewed: bool = False,
    reviewer_notes: Optional[str] = None,
) -> Tuple[InspectionState, NextBestAction]:
    """Deterministically derive operational inspection state and the single next best action.

    Args:
        compliance_result: Optional evaluated ComplianceResult.
        declarations: List of extracted declarations.
        violations: List of statutory violations.
        guidance: Evaluated InspectionGuidance.
        scope_coverage: Evaluated ScopeCoverageManifest.
        qr_evidence: Evaluated QREvidence.
        composition: Evaluated PackageComposition.
        quality_reports: List of ImageQualityReport objects.
        views_captured_count: Number of package view images captured.
        is_complete_scan: Whether complete multi-view package panels were captured.
        is_reviewed: Whether manual officer review was completed.
        reviewer_notes: Audit notes from inspector review.

    Returns:
        Tuple of (InspectionState, NextBestAction).
    """
    # Unpack from compliance_result if provided and direct args were not passed
    if compliance_result is not None:
        if declarations is None:
            declarations = compliance_result.declarations
        if violations is None:
            violations = compliance_result.violations
        if guidance is None and hasattr(compliance_result, "guidance"):
            guidance = compliance_result.guidance
        if scope_coverage is None and hasattr(compliance_result, "scope_coverage"):
            scope_coverage = compliance_result.scope_coverage
        if qr_evidence is None and hasattr(compliance_result, "qr_evidence"):
            qr_evidence = compliance_result.qr_evidence
        if composition is None and hasattr(compliance_result, "composition"):
            composition = compliance_result.composition

    decls: List[ExtractedDeclaration] = list(declarations or [])
    viols: List[Violation] = list(violations or [])
    q_reports: List[Optional[ImageQualityReport]] = list(quality_reports or [])

    # 1. Analyze Quality Blockers
    quality_blockers: List[str] = []
    for q_rep in q_reports:
        if q_rep and q_rep.status == QualityStatus.rejected:
            if q_rep.recapture_reason:
                quality_blockers.append(q_rep.recapture_reason)
            elif hasattr(q_rep, "metrics") and q_rep.metrics and q_rep.metrics.is_blurry:
                quality_blockers.append(f"Severe optical blur detected (blur score {q_rep.metrics.blur_score:.1f}).")
            else:
                quality_blockers.append("Image quality rejected for inspection baseline.")

    # Check guidance for quality issues
    if guidance:
        for issue in guidance.issues:
            if issue.category == GuidanceIssueCategory.quality:
                if issue.title not in quality_blockers:
                    quality_blockers.append(issue.title)

    # Check violations for quality rejection
    for v in viols:
        if v.rule_code in ("QUALITY-REJECT", "IMAGE-INVALID", "BLUR_CRITICAL"):
            if v.description not in quality_blockers:
                quality_blockers.append(v.description)

    # 2. Analyze Cross-View Evidence Conflicts
    evidence_conflicts: List[str] = []
    for v in viols:
        if v.rule_code in ("RULE-FUSION-CONFLICT", "CONFLICTING_DECLARATIONS"):
            evidence_conflicts.append(v.field_name or v.description)
    if guidance:
        for issue in guidance.issues:
            if issue.category == GuidanceIssueCategory.conflict:
                for af in issue.affected_fields:
                    if af not in evidence_conflicts:
                        evidence_conflicts.append(af)

    # 3. Analyze Uncertain Declarations
    uncertain_declarations = [
        d.field_name for d in decls if d.status == DeclarationStatus.uncertain
    ]

    # 4. Officer Review Status
    verdict = compliance_result.verdict if compliance_result else None
    officer_has_reviewed = is_reviewed or bool(reviewer_notes and reviewer_notes.strip())

    if officer_has_reviewed:
        officer_review_status = OfficerReviewStatus.COMPLETED
    elif verdict == ComplianceVerdict.NEEDS_REVIEW or uncertain_declarations or evidence_conflicts:
        officer_review_status = OfficerReviewStatus.PENDING
    else:
        officer_review_status = OfficerReviewStatus.NOT_REQUIRED

    # Count total unresolved issues
    unresolved_count = (
        len(quality_blockers)
        + len(evidence_conflicts)
        + len(uncertain_declarations)
    )
    if composition and composition.package_type == PackageType.UNCERTAIN:
        unresolved_count += 1
    if qr_evidence and qr_evidence.applicable_product == ElectronicApplicability.APPLICABLE and qr_evidence.status == QREvidenceStatus.uncertain:
        unresolved_count += 1

    # 5. Prioritized Next Best Action Selection (Strict Hierarchy)
    next_action: NextBestAction
    state_status: InspectionStateStatus
    visual_checks_complete: bool = False
    ready_to_finalize: bool = False

    # Priority 1: Image Quality Blocker
    if quality_blockers or (guidance and guidance.priority == GuidancePriority.critical and guidance.needs_recapture):
        state_status = InspectionStateStatus.INCOMPLETE
        primary_blocker = quality_blockers[0] if quality_blockers else "Image quality degradation"
        next_action = NextBestAction(
            action_code="image_recapture_quality",
            title="Recapture Packaging Image",
            description=f"Inspection is blocked by optical quality issues ({primary_blocker}). Hold camera steady in good lighting and recapture.",
            priority="critical",
            target_tab="overview",
            target_panel=guidance.target_panels[0] if guidance and guidance.target_panels else "front",
            suggested_button_text="Retake Photo",
        )

    # Priority 2: Unresolved Cross-View Conflict
    elif evidence_conflicts:
        state_status = InspectionStateStatus.NEEDS_REVIEW
        conflicts_str = ", ".join(evidence_conflicts[:2])
        next_action = NextBestAction(
            action_code="review_conflicting_evidence",
            title="Review Conflicting Evidence",
            description=f"Contradictory declaration values were detected across package views ({conflicts_str}). Inspector review is required to confirm printed text.",
            priority="high",
            target_tab="review",
            suggested_button_text="Review Conflicts",
        )

    # Priority 3: Targeted Recapture Required (Incomplete Scan / Missing Mandatory View)
    elif not is_complete_scan and guidance and guidance.needs_recapture and guidance.target_panels:
        state_status = InspectionStateStatus.INCOMPLETE
        target_panel = guidance.target_panels[0]
        panel_label = target_panel.replace("_", " ").title()
        next_action = NextBestAction(
            action_code="capture_additional_view",
            title=f"Capture Additional Package View ({panel_label})",
            description=f"Only {views_captured_count} view captured. Capture the {panel_label} panel to establish complete statutory packaging declarations.",
            priority="medium",
            target_tab="overview",
            target_panel=target_panel,
            suggested_button_text=f"Capture {panel_label}",
        )

    # Priority 4: Unresolved Package Composition
    elif composition and (composition.package_type == PackageType.UNCERTAIN or composition.status == DeclarationStatus.uncertain):
        state_status = InspectionStateStatus.NEEDS_REVIEW
        next_action = NextBestAction(
            action_code="review_package_composition",
            title="Review Package Composition",
            description="Package text indicates multiple contained items or combination products, but constituent breakdown is unverified. Confirm individual commodities.",
            priority="medium",
            target_tab="review",
            suggested_button_text="Review Composition",
        )

    # Priority 5: Unresolved QR Evidence for Electronic Product
    elif (
        qr_evidence
        and qr_evidence.applicable_product == ElectronicApplicability.APPLICABLE
        and (qr_evidence.status == QREvidenceStatus.uncertain or (not qr_evidence.instruction_detected and qr_evidence.status == QREvidenceStatus.detected))
    ):
        state_status = InspectionStateStatus.NEEDS_REVIEW
        next_action = NextBestAction(
            action_code="review_qr_evidence",
            title="Review QR & Electronic Declarations",
            description="Electronic product declarations require verification of on-package consumer scan instruction and decoded payload.",
            priority="medium",
            target_tab="overview",
            suggested_button_text="Review QR Evidence",
        )

    # Priority 6: Pending Officer Review (Uncertain Declarations / Rule Verification)
    elif officer_review_status == OfficerReviewStatus.PENDING and not officer_has_reviewed:
        state_status = InspectionStateStatus.READY_TO_REVIEW
        next_action = NextBestAction(
            action_code="review_findings",
            title="Perform Human Officer Review",
            description="One or more declarations or validation rules require manual inspector verification before finalizing.",
            priority="medium",
            target_tab="review",
            suggested_button_text="Review Scan",
        )

    # Priority 7 / 9: Ready to Finalize
    else:
        state_status = InspectionStateStatus.READY_TO_FINALIZE
        visual_checks_complete = True
        ready_to_finalize = True
        next_action = NextBestAction(
            action_code="finalize_inspection",
            title="Finalize Inspection Report",
            description="All required visual label declarations have been audited. Inspection is ready for final verification and export.",
            priority="info",
            target_tab="overview",
            suggested_button_text="Finalize Report",
        )

    # Construct concise summary text
    if state_status == InspectionStateStatus.READY_TO_FINALIZE:
        summary_text = "All visual label checks complete. Ready to finalize inspection."
    elif state_status == InspectionStateStatus.READY_TO_REVIEW:
        summary_text = "Visual evidence captured. Pending human officer review verification."
    elif state_status == InspectionStateStatus.NEEDS_REVIEW:
        summary_text = "Evidence ambiguities or cross-view conflicts detected requiring review."
    else:
        summary_text = "Inspection incomplete. Additional view or image recapture required."

    inspection_state = InspectionState(
        status=state_status,
        visual_checks_complete=visual_checks_complete,
        views_captured=max(1, views_captured_count),
        unresolved_count=unresolved_count,
        quality_blockers=quality_blockers,
        evidence_conflicts=evidence_conflicts,
        officer_review_status=officer_review_status,
        physical_checks_status=PhysicalChecksStatus.NOT_EVALUATED,
        external_checks_status=ExternalChecksStatus.NOT_EVALUATED,
        ready_to_finalize=ready_to_finalize,
        summary=summary_text,
    )

    return inspection_state, next_action
