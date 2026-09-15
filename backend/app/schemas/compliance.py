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

from app.schemas.declaration import BoundingBox, ExtractedDeclaration, PackageComposition
from app.schemas.guidance import InspectionGuidance
from app.schemas.inspection_state import InspectionState, NextBestAction
from app.schemas.violation import Violation


class ComplianceVerdict(str, Enum):
    """Deterministic compliance verdict computed across all applicable Legal Metrology rules."""

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# Alias for canonical nomenclature
Verdict = ComplianceVerdict


class QREvidenceStatus(str, Enum):
    """Status of QR code detection and decoding on package imagery."""

    detected = "detected"
    missing = "missing"
    uncertain = "uncertain"


class ElectronicApplicability(str, Enum):
    """Statutory applicability determination for electronic products under Rule 6 / G.S.R. 456(E)."""

    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class QREvidence(BaseModel):
    """Structured evidence package for QR code detection, decoding, and electronic product compliance."""

    detected: bool = Field(
        default=False, description="Whether a QR code was detected on the package view(s)"
    )
    status: QREvidenceStatus = Field(
        default=QREvidenceStatus.missing, description="QR code detection/decode status: detected | missing | uncertain"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Detection confidence score"
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None, description="Bounding box of the primary QR code in unscaled image coordinates"
    )
    decoded_payload: Optional[str] = Field(
        default=None, description="Decoded QR string payload (e.g. URL or text)"
    )
    payload_valid: Optional[bool] = Field(
        default=None, description="Whether the payload is a valid URL or structured payload"
    )
    source_image_index: Optional[int] = Field(
        default=None, description="Index of the package view where QR was detected"
    )
    instruction_detected: bool = Field(
        default=False, description="Whether consumer instruction to scan QR is present on the physical package"
    )
    instruction_text: Optional[str] = Field(
        default=None, description="Detected consumer scan instruction text snippet"
    )
    applicable_product: ElectronicApplicability = Field(
        default=ElectronicApplicability.NOT_APPLICABLE,
        description="Electronic product applicability determination under Rule 6 / G.S.R. 456(E)",
    )
    statutory_note: Optional[str] = Field(
        default=None, description="Statutory compliance interpretation under Rule 6 / G.S.R. 456(E)"
    )


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


class ScopeCoverageManifest(BaseModel):
    """Structured manifest declaring the exact statutory scope, automated visual coverage, and physical/external exclusions."""

    score_name: str = Field(
        default="Visual Label Compliance Score",
        description="Explicit title of the automated 0–100 compliance metric",
    )
    score_meaning: str = Field(
        default="Evaluates visible statutory text declarations on captured package views only under Legal Metrology (Packaged Commodities) Rules, 2011.",
        description="Clear statutory boundary definition of the compliance score",
    )
    image_verifiable_rules_checked: List[str] = Field(
        default_factory=list,
        description="Specific Legal Metrology statutory rules evaluated via automated visual inspection",
    )
    views_captured_count: int = Field(
        default=1,
        ge=0,
        description="Number of package view images captured and evaluated",
    )
    multi_view_status: str = Field(
        default="SINGLE_VIEW_PARTIAL",
        description="Multi-view completeness status: COMPLETE_PANEL_COVERAGE | MULTI_VIEW_PARTIAL | SINGLE_VIEW_PARTIAL",
    )
    is_complete_scan: bool = Field(
        default=False,
        description="Whether all outer packaging panels were captured during inspection",
    )
    physical_checks_excluded: List[str] = Field(
        default_factory=list,
        description="Physical metrological checks not evaluated from images requiring calibrated hardware",
    )
    external_data_checks_excluded: List[str] = Field(
        default_factory=list,
        description="Statutory registration and licensing checks not evaluated from images requiring registry lookup",
    )
    disclaimer: str = Field(
        default=(
            "This automated inspection evaluates visible text declarations on captured packaging images "
            "under the Legal Metrology (Packaged Commodities) Rules, 2011. It does NOT verify physical gravimetric "
            "net weight, volumetric measure, physical font dimensions in millimeters, or statutory regulatory "
            "registrations. This output is an automated visual audit aid and does not constitute a legal certification or statutory immunity."
        ),
        description="Mandatory legal boundary and non-certification notice",
    )


DEFAULT_IMAGE_VERIFIABLE_RULES: List[str] = [
    "Rule 6(1)(a) — Name & complete address of manufacturer, packer, or importer",
    "Rule 6(1)(aa) — Country of origin (for imported products)",
    "Rule 6(1)(b) — Common or generic name of the commodity",
    "Rule 6(1)(c) — Net quantity in standard SI metric units (g, kg, ml, L, m, cm, mm, N, U)",
    "Rule 6(1)(d) — Month and year of manufacture, pre-packing, or import",
    "Rule 6(1)(e) — Maximum Retail Price (MRP) inclusive of all taxes",
    "Rule 6(1)(g) — Batch, lot, or code number for supply chain traceability",
    "Rule 6(1)(m) — Best before or use by expiry date (for perishable commodities)",
    "Rule 6(1)(n) — Consumer care cell designation, phone number, and email address",
    "Rule 6(11) — Unit Sale Price (USP) calculation & mandatory statutory denominator",
    "Rule 26(a) — Small package statutory exemption threshold assessment (<= 10g or <= 10ml)",
    "Rule 6(1) & G.S.R. 456(E) — Electronic product QR declaration applicability & scan-instruction checks",
    "Multi-commodity package composition & constituent evidence extraction",
]

DEFAULT_PHYSICAL_CHECKS_EXCLUDED: List[str] = [
    "Net Quantity Gravimetric Verification (Rules 14–18 & First Schedule Maximum Permissible Errors on net/tare/gross weight)",
    "Calibrated Optical PDP Font Height in Millimeters (Rule 8 & Second Schedule relative to surface area cm²)",
    "Container Fill Level & Deceptive Packaging Volumetric Inspection (Rule 21)",
    "Physical Package Tamper-Evident Seal & Integrity Verification",
]

DEFAULT_EXTERNAL_DATA_CHECKS_EXCLUDED: List[str] = [
    "DCA Central Legal Entity Registration Verification (Rule 27 Director/Controller of Legal Metrology registry)",
    "State Legal Metrology Verification Stamp & Weight Calibration Certificate Verification",
    "Central Pollution Control Board (CPCB) Extended Producer Responsibility (EPR) Plastic Waste Registration",
    "FSSAI Food Safety License / CDSCO Medical Device Manufacturing License Verification",
    "External QR Destination Web Content & Dynamic Landing Page Verification (Not Evaluated)",
    "Physical verification of internal constituent contents within sealed multi-packs (verifies outer container declarations only)",
]


def generate_scope_coverage_manifest(
    views_captured_count: int = 1,
    is_complete_scan: bool = False,
    rules_checked: Optional[List[str]] = None,
) -> ScopeCoverageManifest:
    """Generate a deterministic ScopeCoverageManifest detailing visual coverage and statutory exclusions.

    Args:
        views_captured_count: Number of package view images processed.
        is_complete_scan: Flag indicating whether all packaging panels were captured.
        rules_checked: Optional custom list of image-verifiable rules. Defaults to standard codified catalog.

    Returns:
        ScopeCoverageManifest instance.
    """
    count = max(0, views_captured_count)
    if is_complete_scan:
        mv_status = "COMPLETE_PANEL_COVERAGE (All package panels captured & evaluated)"
    elif count > 1:
        mv_status = f"MULTI_VIEW_PARTIAL ({count} views captured — unobserved panels not cited as violations)"
    else:
        mv_status = "SINGLE_VIEW_PARTIAL (1 view captured — unobserved panels not cited as violations)"

    return ScopeCoverageManifest(
        image_verifiable_rules_checked=rules_checked or list(DEFAULT_IMAGE_VERIFIABLE_RULES),
        views_captured_count=count,
        multi_view_status=mv_status,
        is_complete_scan=is_complete_scan,
        physical_checks_excluded=list(DEFAULT_PHYSICAL_CHECKS_EXCLUDED),
        external_data_checks_excluded=list(DEFAULT_EXTERNAL_DATA_CHECKS_EXCLUDED),
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
        description="Calculated Visual Label Compliance Score from 0.0 to 100.0 based on image-verifiable declarations",
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
    guidance: Optional[InspectionGuidance] = Field(
        default=None, description="Intelligent recapture and field inspection guidance recommendations"
    )
    scope_coverage: Optional[ScopeCoverageManifest] = Field(
        default=None, description="Explicit statutory inspection scope, visual coverage, and physical/external exclusions"
    )
    qr_evidence: Optional[QREvidence] = Field(
        default=None, description="Structured QR code detection, decoding, and electronic product compliance evidence"
    )
    composition: Optional[PackageComposition] = Field(
        default=None, description="Structured package composition and constituent items evidence"
    )
    inspection_state: Optional[InspectionState] = Field(
        default=None, description="Deterministic operational inspection state and completeness metrics"
    )
    next_best_action: Optional[NextBestAction] = Field(
        default=None, description="The single most useful deterministic operational action recommended to the field inspector"
    )

