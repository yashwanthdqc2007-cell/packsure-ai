"""
PackSure AI — Inspection Completeness & Operational State Schemas.

Defines typed deterministic models for operational field-inspection workflow state
and next best action guidance under Phase 5A.

Key Invariants:
1. Operational layer only — does NOT alter statutory legal compliance (PASS/FAIL/NEEDS_REVIEW).
2. Distinguishes evaluated visual evidence from unperformed physical/external checks.
3. Provides exactly ONE highest-priority next best action.
4. Does NOT claim 100% legal compliance or certification.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class InspectionStateStatus(str, Enum):
    """Operational status of the field inspection workflow."""

    INCOMPLETE = "INCOMPLETE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY_TO_REVIEW = "READY_TO_REVIEW"
    READY_TO_FINALIZE = "READY_TO_FINALIZE"


class OfficerReviewStatus(str, Enum):
    """Status of certified human officer review verification."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class PhysicalChecksStatus(str, Enum):
    """Status of physical metrological measurements (gravimetric weight, font mm, fill level)."""

    NOT_EVALUATED = "NOT_EVALUATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class ExternalChecksStatus(str, Enum):
    """Status of external statutory registry verifications (Rule 27 DCA, FSSAI, EPR)."""

    NOT_EVALUATED = "NOT_EVALUATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class NextBestAction(BaseModel):
    """The single most useful deterministic operational action recommended to the field inspector."""

    action_code: str = Field(
        ...,
        description="Machine-readable action identifier (e.g., 'image_recapture_quality', 'capture_additional_view', 'review_conflicting_evidence', 'review_package_composition', 'review_qr_evidence', 'review_findings', 'finalize_inspection')",
    )
    title: str = Field(..., description="Short, actionable title for the inspector")
    description: str = Field(
        ..., description="Clear explanation of why this action is recommended and what to do"
    )
    priority: str = Field(
        default="medium",
        description="Priority level: critical | high | medium | low | info",
    )
    target_tab: Optional[str] = Field(
        default="overview",
        description="Recommended frontend tab to navigate to (overview, declarations, violations, evidence, review)",
    )
    target_panel: Optional[str] = Field(
        default=None,
        description="Physical packaging panel to target if camera recapture action",
    )
    suggested_button_text: Optional[str] = Field(
        default=None,
        description="Recommended button label (e.g., 'Review Evidence', 'Capture Back Panel', 'Finalize Inspection')",
    )


class InspectionState(BaseModel):
    """Deterministic operational inspection state synthesizing visual coverage, evidence review, and workflow readiness."""

    status: InspectionStateStatus = Field(
        default=InspectionStateStatus.INCOMPLETE,
        description="Operational workflow status: INCOMPLETE | NEEDS_REVIEW | READY_TO_REVIEW | READY_TO_FINALIZE",
    )
    visual_checks_complete: bool = Field(
        default=False,
        description="Whether all mandatory visual declarations for the provided views are established without blockers",
    )
    views_captured: int = Field(
        default=1,
        description="Number of package views captured and analyzed",
    )
    unresolved_count: int = Field(
        default=0,
        description="Total count of unresolved issues (quality blockers, evidence conflicts, uncertain declarations)",
    )
    quality_blockers: List[str] = Field(
        default_factory=list,
        description="List of severe optical/quality issues preventing reliable inspection",
    )
    evidence_conflicts: List[str] = Field(
        default_factory=list,
        description="List of fields with contradictory declarations across package views",
    )
    officer_review_status: OfficerReviewStatus = Field(
        default=OfficerReviewStatus.NOT_REQUIRED,
        description="Status of human inspector review: NOT_REQUIRED | PENDING | COMPLETED",
    )
    physical_checks_status: PhysicalChecksStatus = Field(
        default=PhysicalChecksStatus.NOT_EVALUATED,
        description="Status of physical metrological measurements: NOT_EVALUATED | PENDING | COMPLETED",
    )
    external_checks_status: ExternalChecksStatus = Field(
        default=ExternalChecksStatus.NOT_EVALUATED,
        description="Status of external regulatory registry verifications: NOT_EVALUATED | PENDING | COMPLETED",
    )
    ready_to_finalize: bool = Field(
        default=False,
        description="Whether the inspection has cleared all blockers and review steps and is ready to finalize",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Concise human-readable operational status summary",
    )
