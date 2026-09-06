"""
Pydantic schemas for Scan requests and responses.

Enums:
- ScanStatus: pending | processing | complete | failed

Models:
- ScanCreate: Input request model for initiating a scan
- ScanInitResponse: Response from POST /api/v1/scans (202 Accepted)
- ScanStatusResponse: Lightweight status polling response
- ScanResponse: Complete inspection response for GET /api/v1/scans/{id}
- ScanHistoryItem: Individual history record summary
- ScanHistoryResponse: Paginated history response for GET /api/v1/history
- ScanReviewRequest: Payload for human reviewer resolution via PATCH /api/v1/scans/{id}/review
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.compliance import ComplianceVerdict
from app.schemas.declaration import CorrectedDeclaration, ExtractedDeclaration
from app.schemas.violation import Violation


class ScanStatus(str, Enum):
    """Lifecycle status of a package compliance scan."""

    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class ScanCreate(BaseModel):
    """Input payload for creating a new scan (in addition to multipart image file)."""

    product_category: Optional[str] = Field(
        default=None, description="Optional category hint (e.g., 'Food Grains', 'Edible Oil')"
    )
    user_id: Optional[str] = Field(
        default=None, description="Optional UUID of the user/inspector initiating the scan"
    )


class ScanInitResponse(BaseModel):
    """Initial response returned upon image ingestion (POST /api/v1/scans — 202 Accepted)."""

    scan_id: str = Field(..., description="Unique UUID assigned to the scan")
    status: ScanStatus = Field(
        default=ScanStatus.pending, description="Initial queued status (pending)"
    )
    created_at: str = Field(..., description="ISO8601 creation timestamp")


class ScanStatusResponse(BaseModel):
    """Status polling response model."""

    scan_id: str = Field(..., description="Scan UUID")
    status: ScanStatus = Field(..., description="Current processing lifecycle status")


class ScanResponse(BaseModel):
    """Comprehensive inspection report payload returned by GET /api/v1/scans/{id} and PATCH /review."""

    scan_id: str = Field(..., description="Unique UUID of the scan record")
    status: ScanStatus = Field(..., description="Current scan lifecycle status")
    verdict: Optional[ComplianceVerdict] = Field(
        default=None,
        description="Deterministic compliance verdict (PASS, FAIL, NEEDS_REVIEW; null if not complete)",
    )
    compliance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Calculated compliance score from 0.0 to 100.0 (null if not complete)",
    )
    product_category: Optional[str] = Field(
        default=None, description="Detected or specified product category name"
    )
    image_url: Optional[str] = Field(
        default=None, description="Public storage URL of the raw uploaded package image"
    )
    processed_image_url: Optional[str] = Field(
        default=None, description="Public storage URL of the preprocessed image"
    )
    evidence_image_url: Optional[str] = Field(
        default=None, description="Public storage URL of the annotated evidence image with bounding boxes"
    )
    declarations: List[ExtractedDeclaration] = Field(
        default_factory=list, description="List of extracted mandatory declaration fields"
    )
    violations: List[Violation] = Field(
        default_factory=list, description="List of identified rule violations"
    )
    reviewer_notes: Optional[str] = Field(
        default=None, description="Audit notes appended during manual human review"
    )
    created_at: str = Field(..., description="ISO8601 creation timestamp")
    completed_at: Optional[str] = Field(
        default=None, description="ISO8601 completion timestamp (null if still processing)"
    )


class ScanHistoryItem(BaseModel):
    """Summary item in paginated scan history list."""

    id: str = Field(..., description="Unique UUID of the scan")
    product_name: Optional[str] = Field(
        default=None, description="Identified product/brand name"
    )
    category: Optional[str] = Field(
        default=None, description="Product category name"
    )
    scanned_at: str = Field(..., description="ISO8601 timestamp when scan was created")
    verdict: Optional[ComplianceVerdict] = Field(
        default=None, description="Compliance verdict (PASS, FAIL, NEEDS_REVIEW)"
    )
    compliance_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Compliance score (0.0 to 100.0)"
    )
    status: ScanStatus = Field(..., description="Scan status: pending, processing, complete, failed")


class ScanHistoryResponse(BaseModel):
    """Paginated scan history query response for GET /api/v1/history."""

    total: int = Field(..., ge=0, description="Total matching scans count")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Items limit per page")
    total_pages: int = Field(..., ge=0, description="Total calculated pages")
    results: List[ScanHistoryItem] = Field(
        default_factory=list, description="Array of historical scan summary objects"
    )


class ScanReviewRequest(BaseModel):
    """Human review submission payload for PATCH /api/v1/scans/{id}/review."""

    verdict: ComplianceVerdict = Field(
        ..., description="Target resolution verdict (must be PASS or FAIL)"
    )
    reviewer_notes: Optional[str] = Field(
        default=None, description="Optional explanation or audit notes from the human inspector"
    )
    corrected_declarations: List[CorrectedDeclaration] = Field(
        default_factory=list,
        description="Optional list of manual field overrides/corrections",
    )
