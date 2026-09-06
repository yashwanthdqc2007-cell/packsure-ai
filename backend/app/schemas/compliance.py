"""
Pydantic schemas for compliance check results.

Enums:
- ComplianceVerdict (alias Verdict): PASS | FAIL | NEEDS_REVIEW

Models:
- EvidenceMetadata: Metadata for generated visual and cryptographic evidence
- ComplianceResult: Complete deterministic rules engine evaluation output
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.declaration import ExtractedDeclaration
from app.schemas.violation import Violation


class ComplianceVerdict(str, Enum):
    """Deterministic compliance verdict computed across all applicable Legal Metrology rules."""

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# Alias for canonical nomenclature
Verdict = ComplianceVerdict


class EvidenceMetadata(BaseModel):
    """Metadata container for generated inspection evidence artifacts and audit trails."""

    evidence_image_url: Optional[str] = Field(
        default=None, description="Public/storage URL of the annotated evidence image"
    )
    annotated_image_path: Optional[str] = Field(
        default=None, description="Local or object storage path of the annotated image"
    )
    timestamp: Optional[str] = Field(default=None, description="ISO8601 generation timestamp")
    rule_version: Optional[str] = Field(
        default="2011", description="Legal Metrology rule edition reference"
    )
    total_declarations_checked: int = Field(
        default=0, ge=0, description="Count of mandatory declarations evaluated"
    )
    total_violations_found: int = Field(
        default=0, ge=0, description="Count of non-compliant violations detected"
    )


class ComplianceResult(BaseModel):
    """Consolidated outcome of the deterministic rules engine evaluation."""

    verdict: ComplianceVerdict = Field(
        ..., description="Overall compliance outcome (PASS, FAIL, NEEDS_REVIEW)"
    )
    compliance_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Calculated compliance score from 0.0 to 100.0",
    )
    declarations: List[ExtractedDeclaration] = Field(
        default_factory=list, description="All evaluated mandatory declarations"
    )
    violations: List[Violation] = Field(
        default_factory=list, description="All detected rule violations"
    )
    evidence_image_url: Optional[str] = Field(
        default=None, description="URL of the annotated evidence image"
    )
    evidence: Optional[EvidenceMetadata] = Field(
        default=None, description="Detailed evidence package metadata"
    )
