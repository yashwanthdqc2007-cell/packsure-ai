"""
PackSure AI — Intelligent Recapture & Inspection Guidance Service.

Translates optical quality assessments, evidence fusion status, and declaration coverage
into deterministic, actionable physical camera instructions for field inspectors.

Invariants:
1. Pure inspection guidance — never alters or decides statutory legal compliance.
2. Strict priority hierarchy:
   1. Image-quality blockers (blur, glare, underexposure, low resolution, extreme skew)
   2. Cross-view fusion conflicts
   3. Missing / unestablished package evidence
3. Maximum 3 prioritized guidance items returned.
4. "Not observed" evidence on incomplete scans is treated as an uncaptured view recommendation,
   never as a confirmed statutory violation.
5. Multi-view fusion is authoritative: if an item is already established in another view,
   recapture for that field is suppressed.
"""

from typing import List, Optional, Sequence, Set
from app.schemas.compliance import ComplianceResult
from app.schemas.declaration import DeclarationStatus, ExtractedDeclaration
from app.schemas.guidance import (
    GuidanceIssue,
    GuidanceIssueCategory,
    GuidancePriority,
    GuidanceTargetPanel,
    InspectionGuidance,
)
from app.schemas.image import ImageQualityReport, QualityStatus
from app.schemas.violation import Violation, ViolationType

MAX_GUIDANCE_ITEMS: int = 3

# Mandatory Legal Metrology field groupings to physical panel mapping
PANEL_FIELD_MAPPING = {
    GuidanceTargetPanel.mrp_panel: {
        "mrp",
        "unit_sale_price",
        "manufacture_date",
        "expiry_date",
        "batch_number",
    },
    GuidanceTargetPanel.side: {
        "manufacturer_name_and_address",
        "consumer_care",
        "country_of_origin",
        "packer_name_and_address",
        "importer_name_and_address",
    },
    GuidanceTargetPanel.front: {
        "generic_name",
        "net_quantity",
    },
}


def generate_inspection_guidance(
    quality_reports: Sequence[Optional[ImageQualityReport]],
    compliance_result: Optional[ComplianceResult] = None,
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    violations: Optional[Sequence[Violation]] = None,
    is_complete_scan: bool = False,
    product_category: Optional[str] = None,
) -> InspectionGuidance:
    """Evaluate quality diagnostics, fusion results, and declaration coverage to produce guidance.

    Args:
        quality_reports: List of ImageQualityReport for each view (or single view).
        compliance_result: Optional evaluated ComplianceResult.
        declarations: Optional extracted declarations (defaults to compliance_result.declarations if provided).
        violations: Optional evaluated violations (defaults to compliance_result.violations if provided).
        is_complete_scan: Flag indicating whether user captured all packaging faces.
        product_category: Commodity category hint.

    Returns:
        InspectionGuidance with prioritized issues (max 3), target panels, and actionable steps.
    """
    if declarations is None and compliance_result is not None:
        declarations = compliance_result.declarations
    declarations = declarations or []

    if violations is None and compliance_result is not None:
        violations = compliance_result.violations
    violations = violations or []

    quality_issues: List[GuidanceIssue] = []
    conflict_issues: List[GuidanceIssue] = []
    evidence_issues: List[GuidanceIssue] = []

    target_panels_set: Set[str] = set()

    # =========================================================================
    # Tier 1: Image Quality Diagnostics (Highest Priority)
    # =========================================================================
    for view_idx, q_report in enumerate(quality_reports):
        if not q_report:
            continue

        metrics = q_report.metrics
        view_label = f"View {view_idx + 1}" if len(quality_reports) > 1 else "Package Image"

        # 1. Hard Rejection / Severe Blur
        if q_report.status == QualityStatus.rejected or (metrics and metrics.blur_score < 60.0):
            quality_issues.append(
                GuidanceIssue(
                    code="BLUR_CRITICAL",
                    category=GuidanceIssueCategory.quality,
                    title=f"Severe Motion Blur ({view_label})",
                    description=f"{view_label} is severely blurry, making text illegible for automated inspection.",
                    suggested_action="Hold the camera steady with both hands and tap the screen on the label text to lock focus before capturing.",
                    target_panel=GuidanceTargetPanel.generic,
                    affected_view_index=view_idx if len(quality_reports) > 1 else None,
                    affected_fields=[],
                )
            )
        elif metrics and metrics.is_blurry:
            quality_issues.append(
                GuidanceIssue(
                    code="BLUR_SOFT",
                    category=GuidanceIssueCategory.quality,
                    title=f"Soft Focus Detected ({view_label})",
                    description=f"{view_label} has soft focus which may degrade small print recognition (e.g. MRP or batch numbers).",
                    suggested_action="Ensure the camera is focused directly on the printed declarations before shooting.",
                    target_panel=GuidanceTargetPanel.generic,
                    affected_view_index=view_idx if len(quality_reports) > 1 else None,
                    affected_fields=[],
                )
            )

        # 2. Glare / Specular Reflection / Overexposure
        if metrics and (metrics.is_too_bright or metrics.brightness_score > 215.0):
            is_critical_glare = metrics.brightness_score > 235.0
            quality_issues.append(
                GuidanceIssue(
                    code="GLARE_DETECTED",
                    category=GuidanceIssueCategory.quality,
                    title=f"Excessive Glare / Overexposure ({view_label})",
                    description=f"{view_label} contains harsh white reflections or excessive brightness obscuring label declarations.",
                    suggested_action="Tilt the camera 15°–30° to an angle to eliminate reflections from overhead lights, or move away from direct spotlighting.",
                    target_panel=GuidanceTargetPanel.generic,
                    affected_view_index=view_idx if len(quality_reports) > 1 else None,
                    affected_fields=[],
                )
            )

        # 3. Underexposure / Low Light
        if metrics and (metrics.is_too_dark or metrics.brightness_score < 50.0):
            quality_issues.append(
                GuidanceIssue(
                    code="UNDEREXPOSED",
                    category=GuidanceIssueCategory.quality,
                    title=f"Low Lighting / Underexposed ({view_label})",
                    description=f"{view_label} is too dark, reducing contrast on fine Legal Metrology text.",
                    suggested_action="Increase ambient lighting on the package or enable the camera flash.",
                    target_panel=GuidanceTargetPanel.generic,
                    affected_view_index=view_idx if len(quality_reports) > 1 else None,
                    affected_fields=[],
                )
            )

        # 4. Low Resolution
        if metrics and not metrics.resolution_acceptable:
            quality_issues.append(
                GuidanceIssue(
                    code="LOW_RESOLUTION",
                    category=GuidanceIssueCategory.quality,
                    title=f"Low Resolution ({view_label})",
                    description=f"{view_label} resolution is below the minimum required 600px shortest dimension and 360,000 total pixels.",
                    suggested_action="Move the camera closer to fill the frame with the package label, or use a higher camera resolution.",
                    target_panel=GuidanceTargetPanel.generic,
                    affected_view_index=view_idx if len(quality_reports) > 1 else None,
                    affected_fields=[],
                )
            )

    # =========================================================================
    # Tier 2: Cross-View Conflicts & Fusion Discrepancies
    # =========================================================================
    for viol in violations:
        if viol.rule_code == "FUSION-CONFLICT":
            f_name = viol.field_name or "declaration"
            conflict_issues.append(
                GuidanceIssue(
                    code="MULTI_VIEW_CONFLICT",
                    category=GuidanceIssueCategory.conflict,
                    title=f"Cross-View Discrepancy on {f_name.replace('_', ' ').title()}",
                    description=viol.description,
                    suggested_action=f"Recapture direct, unshadowed photos of both panels declaring {f_name.replace('_', ' ')} to resolve conflicting values.",
                    target_panel=GuidanceTargetPanel.mrp_panel if f_name in PANEL_FIELD_MAPPING[GuidanceTargetPanel.mrp_panel] else GuidanceTargetPanel.generic,
                    affected_view_index=None,
                    affected_fields=[f_name] if viol.field_name else [],
                )
            )
            target_panels_set.add("mrp_panel")

    # =========================================================================
    # Tier 3: Missing / Unestablished Evidence & Partial Coverage
    # =========================================================================
    # Determine established fields from fused declarations
    established_fields: Set[str] = {
        d.field_name for d in declarations if d.status == DeclarationStatus.detected and d.raw_value
    }
    uncertain_fields: Set[str] = {
        d.field_name for d in declarations if d.status == DeclarationStatus.uncertain
    }

    # Check for specific unestablished panel clusters if not a confirmed complete scan
    # or if mandatory fields are missing
    mrp_cluster = PANEL_FIELD_MAPPING[GuidanceTargetPanel.mrp_panel]
    side_cluster = PANEL_FIELD_MAPPING[GuidanceTargetPanel.side]
    front_cluster = PANEL_FIELD_MAPPING[GuidanceTargetPanel.front]

    missing_mrp_items = mrp_cluster - established_fields
    missing_side_items = side_cluster - established_fields
    missing_front_items = front_cluster - established_fields

    # Check USP specific guidance based on RuleEngine violation
    usp_violation = next((v for v in violations if "USP" in (v.rule_code or "") or "6(11)" in (v.rule_code or "")), None)
    if usp_violation:
        evidence_issues.append(
            GuidanceIssue(
                code="USP_EVIDENCE_UNCERTAIN",
                category=GuidanceIssueCategory.uncertain_evidence,
                title="Unit Sale Price (USP) Verification",
                description=usp_violation.description,
                suggested_action="Ensure the photo clearly captures both the Total MRP and the Unit Sale Price (₹/g, ₹/ml, or ₹/unit) statement.",
                target_panel=GuidanceTargetPanel.mrp_panel,
                affected_view_index=None,
                affected_fields=["unit_sale_price", "mrp"],
            )
        )
        target_panels_set.add("mrp_panel")

    # If scan is incomplete and MRP/Date cluster is unobserved
    if not is_complete_scan and len(missing_mrp_items) >= 2 and "mrp" not in established_fields:
        evidence_issues.append(
            GuidanceIssue(
                code="MISSING_MRP_PANEL",
                category=GuidanceIssueCategory.missing_evidence,
                title="Capture Back / Price Stamping Panel",
                description="MRP, Date of Manufacture, Expiry Date, and Batch Number were not observed in the provided view(s).",
                suggested_action="Capture an additional photo of the back panel or stamped area displaying MRP, Batch, and Manufacturing dates.",
                target_panel=GuidanceTargetPanel.mrp_panel,
                affected_view_index=None,
                affected_fields=list(missing_mrp_items),
            )
        )
        target_panels_set.add("back")
        target_panels_set.add("mrp_panel")

    # If scan is incomplete and Manufacturer / Customer Care is unobserved
    if not is_complete_scan and ("manufacturer_name_and_address" not in established_fields or "consumer_care" not in established_fields):
        evidence_issues.append(
            GuidanceIssue(
                code="MISSING_SIDE_PANEL",
                category=GuidanceIssueCategory.missing_evidence,
                title="Capture Side / Contact Details Panel",
                description="Manufacturer / Packer name & address or Consumer Care contact details were not observed in the provided view(s).",
                suggested_action="Capture the side panel or bottom flap containing manufacturer information and customer helpline details.",
                target_panel=GuidanceTargetPanel.side,
                affected_view_index=None,
                affected_fields=["manufacturer_name_and_address", "consumer_care"],
            )
        )
        target_panels_set.add("side")

    # If Net Quantity is missing on front
    if "net_quantity" not in established_fields:
        evidence_issues.append(
            GuidanceIssue(
                code="MISSING_NET_QTY",
                category=GuidanceIssueCategory.missing_evidence,
                title="Capture Principal Display Panel (Front)",
                description="Net Quantity declaration was not detected.",
                suggested_action="Capture a direct frontal photo of the package's Principal Display Panel showing Net Quantity clearly.",
                target_panel=GuidanceTargetPanel.front,
                affected_view_index=None,
                affected_fields=["net_quantity"],
            )
        )
        target_panels_set.add("front")

    # If fields are uncertain (low confidence OCR / AI)
    for u_field in sorted(uncertain_fields):
        if len(evidence_issues) + len(quality_issues) + len(conflict_issues) >= MAX_GUIDANCE_ITEMS:
            break
        evidence_issues.append(
            GuidanceIssue(
                code="UNCERTAIN_DECLARATION",
                category=GuidanceIssueCategory.uncertain_evidence,
                title=f"Unclear Print on {u_field.replace('_', ' ').title()}",
                description=f"The text for {u_field.replace('_', ' ')} has low OCR confidence or faint stamping.",
                suggested_action=f"Zoom in and capture a close-up photo directly over the {u_field.replace('_', ' ')} text.",
                target_panel=GuidanceTargetPanel.generic,
                affected_view_index=None,
                affected_fields=[u_field],
            )
        )

    # =========================================================================
    # Prioritized Consolidation (Max 3 Items)
    # =========================================================================
    all_issues_sorted = quality_issues + conflict_issues + evidence_issues
    final_issues = all_issues_sorted[:MAX_GUIDANCE_ITEMS]

    # Calculate overall priority
    has_critical_quality = any(
        i.code in ("BLUR_CRITICAL", "LOW_RESOLUTION") for i in quality_issues
    )
    has_glare_or_quality = bool(quality_issues)
    has_conflicts = bool(conflict_issues)
    has_missing = bool(evidence_issues)

    if has_critical_quality:
        priority = GuidancePriority.critical
        headline = "Immediate Recapture Required — Image Quality Unusable"
        needs_recapture = True
    elif has_glare_or_quality:
        priority = GuidancePriority.high
        headline = "Recapture Recommended — Glare or Focus Degradation Detected"
        needs_recapture = True
    elif has_conflicts:
        priority = GuidancePriority.high
        headline = "Recapture Recommended — Cross-View Discrepancy Detected"
        needs_recapture = True
    elif has_missing and not is_complete_scan:
        priority = GuidancePriority.medium
        headline = "Additional Package Views Recommended for Full Legal Coverage"
        needs_recapture = True
    elif has_missing:
        priority = GuidancePriority.low
        headline = "Inspection Complete — Minor Declaration Verification Advised"
        needs_recapture = False
    else:
        priority = GuidancePriority.none
        headline = "All Mandatory Evidence Successfully Captured"
        needs_recapture = False

    # Synthesize human-actionable checklist steps (Max 3 steps)
    actionable_steps: List[str] = []
    for issue in final_issues:
        actionable_steps.append(issue.suggested_action)

    # Deduplicate steps while preserving order
    seen_steps = set()
    deduped_steps = []
    for s in actionable_steps:
        if s not in seen_steps:
            seen_steps.add(s)
            deduped_steps.append(s)

    # Calculate estimated coverage percentage against core mandatory declarations
    core_statutory_fields = {
        "generic_name",
        "net_quantity",
        "mrp",
        "unit_sale_price",
        "manufacture_date",
        "expiry_date",
        "batch_number",
        "manufacturer_name_and_address",
        "consumer_care",
    }
    established_core = established_fields.intersection(core_statutory_fields)
    est_coverage = min(
        100.0,
        round((len(established_core) / float(len(core_statutory_fields))) * 100.0, 1),
    ) if core_statutory_fields else 100.0

    return InspectionGuidance(
        needs_recapture=needs_recapture,
        priority=priority,
        headline=headline,
        target_panels=sorted(list(target_panels_set)),
        issues=final_issues,
        actionable_steps=deduped_steps[:MAX_GUIDANCE_ITEMS],
        coverage_estimate_pct=est_coverage,
    )
