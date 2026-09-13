"""
PackSure AI — Intelligent Recapture & Inspection Guidance Schemas.

Defines structured models for providing actionable, deterministic field-inspection
guidance when image quality is degraded or package evidence is incomplete.

Key Invariants:
- Guidance is an inspection-assistance feature; it does NOT make statutory legal decisions.
- RuleEngine remains the sole authority for legal compliance verdicts.
- Prioritization order:
  1. Image-quality blockers (blur, glare, underexposure, low resolution)
  2. Cross-view fusion conflicts
  3. Missing or unestablished mandatory evidence
- Capped at a maximum of 3 top-priority actionable guidance items.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class GuidancePriority(str, Enum):
    """Urgency / priority level of the recapture recommendation."""

    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GuidanceIssueCategory(str, Enum):
    """Root cause category of the inspection challenge."""

    quality = "quality"
    conflict = "conflict"
    missing_evidence = "missing_evidence"
    uncertain_evidence = "uncertain_evidence"


class GuidanceTargetPanel(str, Enum):
    """Suggested packaging face / panel for recapture."""

    front = "front"
    back = "back"
    side = "side"
    top = "top"
    bottom = "bottom"
    mrp_panel = "mrp_panel"
    nutrition_table = "nutrition_table"
    generic = "generic"


class GuidanceIssue(BaseModel):
    """Specific diagnosed issue requiring physical recapture or officer review."""

    code: str = Field(
        ...,
        description="Machine-readable guidance code (e.g., 'BLUR_DETECTED', 'GLARE_DETECTED', 'MISSING_MRP_PANEL')",
    )
    category: GuidanceIssueCategory = Field(
        ..., description="Root cause category of the issue"
    )
    title: str = Field(..., description="Short human-friendly title of the issue")
    description: str = Field(
        ..., description="Clear explanation of the diagnosed issue"
    )
    suggested_action: str = Field(
        ..., description="Specific physical camera / angle adjustment recommendation"
    )
    target_panel: Optional[GuidanceTargetPanel] = Field(
        default=None, description="Suggested physical package panel to target"
    )
    affected_view_index: Optional[int] = Field(
        default=None, description="0-indexed view index in multi-view inspection, if view-specific"
    )
    affected_fields: List[str] = Field(
        default_factory=list,
        description="Legal Metrology declaration field names affected by this issue",
    )


class InspectionGuidance(BaseModel):
    """Comprehensive inspection guidance report returned to inspector."""

    needs_recapture: bool = Field(
        default=False,
        description="True if physical recapture is recommended to improve inspection confidence",
    )
    priority: GuidancePriority = Field(
        default=GuidancePriority.none,
        description="Overall urgency of recapture (none, low, medium, high, critical)",
    )
    headline: str = Field(
        default="Scan complete and verifiable",
        description="Concise summary headline for inspector UI",
    )
    target_panels: List[str] = Field(
        default_factory=list,
        description="List of physical packaging panels recommended for capture",
    )
    issues: List[GuidanceIssue] = Field(
        default_factory=list,
        description="Prioritized list of diagnosed issues (max 3)",
    )
    actionable_steps: List[str] = Field(
        default_factory=list,
        description="Numbered, human-actionable checklist of steps for the inspector",
    )
    coverage_estimate_pct: Optional[float] = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Estimated declaration evidence coverage (0.0 to 100.0)",
    )
