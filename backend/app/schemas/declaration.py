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
    image_index: Optional[int] = Field(
        default=None, description="Zero-based index of the originating image in a multi-view inspection"
    )
    image_name: Optional[str] = Field(
        default=None, description="Filename or view identifier of the originating image"
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


class PackageType(str, Enum):
    """Classification of packaging composition and multi-commodity bundling structure."""

    SINGLE = "SINGLE"
    MULTI_PIECE = "MULTI_PIECE"
    COMBINATION = "COMBINATION"
    GROUP = "GROUP"
    KIT = "KIT"
    UNCERTAIN = "UNCERTAIN"


class PackageItem(BaseModel):
    """Constituent commodity item within a multi-commodity, combination, or multi-piece package."""

    item_index: int = Field(..., description="1-based sequence index of the constituent item")
    commodity_name: str = Field(..., description="Common or generic name of the constituent commodity")
    item_count: Optional[int] = Field(default=1, description="Count of units for this item")
    unit_quantity: Optional[str] = Field(
        default=None, description="Metric quantity of this item (e.g. '500 ml', '100 g', '1 N')"
    )
    status: DeclarationStatus = Field(
        default=DeclarationStatus.detected, description="Detection status of the constituent item"
    )
    confidence: Optional[float] = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)"
    )
    source_image_index: Optional[int] = Field(
        default=0, description="Zero-based index of originating image view"
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None, description="Spatial bounding box on originating view"
    )


class PackageComposition(BaseModel):
    """Structured evidence model for package composition and constituent commodities."""

    package_type: PackageType = Field(
        default=PackageType.SINGLE, description="Determined package composition type"
    )
    total_item_count: int = Field(
        default=1, description="Total count of constituent items or units in the package"
    )
    items: List[PackageItem] = Field(
        default_factory=list, description="Extracted constituent items"
    )
    status: DeclarationStatus = Field(
        default=DeclarationStatus.detected, description="Overall composition confidence status"
    )
    confidence: Optional[float] = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall composition classification confidence"
    )
    statutory_note: Optional[str] = Field(
        default=None, description="Factual description or note regarding package composition"
    )
