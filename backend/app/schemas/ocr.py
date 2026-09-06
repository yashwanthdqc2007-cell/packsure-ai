"""
Pydantic schemas for OCR results.

Models:
- BoundingBox: Pixel coordinate bounding box relative to original image dimensions
- OCRTextBlock: Individual text block/token with confidence (0.0–1.0) and bounding box
- RawOCRResult: Aggregated OCR output from Tesseract/PaddleOCR
- StructuredOCRResult: Structured mapping of fields extracted by Gemini/pipeline
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box pixel coordinates relative to the original image dimensions (0.0, 0.0 is top-left)."""

    x: float = Field(..., ge=0.0, description="X coordinate of top-left corner in pixels")
    y: float = Field(..., ge=0.0, description="Y coordinate of top-left corner in pixels")
    width: float = Field(..., ge=0.0, description="Width of bounding box in pixels")
    height: float = Field(..., ge=0.0, description="Height of bounding box in pixels")


class OCRTextBlock(BaseModel):
    """An individual OCR recognized token or text block with confidence score."""

    text: str = Field(..., description="Recognized text content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score normalized from 0.0 to 1.0")
    bounding_box: Optional[BoundingBox] = Field(
        default=None, description="Bounding box location of the text block"
    )


class RawOCRResult(BaseModel):
    """Aggregated raw OCR extraction result."""

    full_text: str = Field(default="", description="Consolidated raw OCR text from image")
    language: str = Field(default="eng", description="Primary detected or processed language")
    blocks: List[OCRTextBlock] = Field(
        default_factory=list, description="List of recognized individual text blocks"
    )


class StructuredOCRResult(BaseModel):
    """Structured OCR result with extracted key-value fields and intermediate artifacts."""

    raw_text: str = Field(default="", description="Full raw OCR text")
    fields: Dict[str, Any] = Field(
        default_factory=dict, description="Parsed field-value dictionary"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall extraction confidence score (0.0 to 1.0)"
    )
    language: str = Field(default="eng", description="Language used for extraction")
