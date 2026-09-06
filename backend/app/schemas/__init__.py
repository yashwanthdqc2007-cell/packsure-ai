"""
PackSure AI — Schemas Package

Exports all Pydantic v2 data models and canonical enums for the Legal Metrology compliance system.
"""

from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
    Verdict,
)
from app.schemas.declaration import (
    CorrectedDeclaration,
    DeclarationExtractionPayload,
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    MandatoryFieldType,
)
from app.schemas.ocr import (
    BoundingBox,
    OCRTextBlock,
    RawOCRResult,
    StructuredOCRResult,
)
from app.schemas.scan import (
    ScanCreate,
    ScanHistoryItem,
    ScanHistoryResponse,
    ScanInitResponse,
    ScanResponse,
    ScanReviewRequest,
    ScanStatus,
    ScanStatusResponse,
)
from app.schemas.violation import (
    Violation,
    ViolationSeverity,
    ViolationType,
)

__all__ = [
    # OCR
    "BoundingBox",
    "OCRTextBlock",
    "RawOCRResult",
    "StructuredOCRResult",
    # Declarations
    "DeclarationStatus",
    "DeclarationSource",
    "MandatoryFieldType",
    "ExtractedDeclaration",
    "CorrectedDeclaration",
    "DeclarationExtractionPayload",
    # Violations
    "ViolationSeverity",
    "ViolationType",
    "Violation",
    # Compliance
    "ComplianceVerdict",
    "Verdict",
    "EvidenceMetadata",
    "ComplianceResult",
    # Scan & API Lifecycle
    "ScanStatus",
    "ScanCreate",
    "ScanInitResponse",
    "ScanStatusResponse",
    "ScanResponse",
    "ScanHistoryItem",
    "ScanHistoryResponse",
    "ScanReviewRequest",
]
