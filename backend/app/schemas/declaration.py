"""
Pydantic schemas for mandatory declaration fields.

Legal Metrology (Packaged Commodities) Rules, 2011 compliance schemas.

Enums:
- DeclarationStatus: detected | missing | uncertain
- DeclarationSource: tesseract | gemini | manual | hybrid
- MandatoryFieldType: Codified Legal Metrology mandatory fields

Models:
- ExtractedDeclaration: Single extracted declaration field with status, confidence (0.0–1.0), and bounding box
- CorrectedDeclaration: Schema for manual inspector corrections during review
- DeclarationExtractionPayload: Batch container for extracted declarations
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.ocr import BoundingBox


class DeclarationStatus(str, Enum):
    """Presence and detection status of an individual declaration field."""

    detected = "detected"
    missing = "missing"
    uncertain = "uncertain"


class DeclarationSource(str, Enum):
    """Source engine or modality for extracted declaration."""

    tesseract = "tesseract"
    gemini = "gemini"
    manual = "manual"
    hybrid = "hybrid"


class MandatoryFieldType(str, Enum):
    """Codified Legal Metrology (Packaged Commodities) Rules, 2011 mandatory declaration fields."""

    manufacturer_name_and_address = "manufacturer_name_and_address"
    net_quantity = "net_quantity"
    mrp = "mrp"
    unit_sale_price = "unit_sale_price"
    manufacture_date = "manufacture_date"
    expiry_date = "expiry_date"
    batch_number = "batch_number"
    consumer_care = "consumer_care"
    country_of_origin = "country_of_origin"
    generic_name = "generic_name"


class ExtractedDeclaration(BaseModel):
    """Extracted declaration field with OCR/AI metadata, normalized values, and bounding box."""

    id: Optional[str] = Field(default=None, description="UUID of the extracted declaration record")
    scan_id: Optional[str] = Field(default=None, description="Associated scan UUID")
    field_name: str = Field(..., description="Standard declaration field name")
    status: DeclarationStatus = Field(
        default=DeclarationStatus.detected,
        description="Declaration-level extraction status (detected, missing, uncertain)",
    )
    raw_value: Optional[str] = Field(default=None, description="Raw OCR/extracted text string")
    normalized_value: Optional[str] = Field(
        default=None, description="Normalized/standardized value (e.g. standard units, ISO dates, currency numbers)"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score normalized from 0.0 to 1.0",
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None, description="Pixel bounding box in original image coordinates"
    )
    source: Optional[DeclarationSource] = Field(
        default=None, description="Extraction source modality"
    )
    created_at: Optional[str] = Field(default=None, description="ISO8601 creation timestamp")


class CorrectedDeclaration(BaseModel):
    """Schema for manual reviewer overrides/corrections submitted via PATCH review endpoint."""

    field_name: str = Field(..., description="Standard declaration field name being corrected")
    raw_value: Optional[str] = Field(default=None, description="Updated raw text")
    normalized_value: Optional[str] = Field(default=None, description="Updated normalized value")
    status: Optional[DeclarationStatus] = Field(
        default=DeclarationStatus.detected, description="Updated detection status"
    )


class DeclarationExtractionPayload(BaseModel):
    """Container for batch extracted declarations."""

    declarations: List[ExtractedDeclaration] = Field(
        default_factory=list, description="List of extracted declarations"
    )
