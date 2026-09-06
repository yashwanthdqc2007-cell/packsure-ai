"""
Pydantic schemas for Image Quality Assessment and Preprocessing layer.

Enums:
- QualityStatus: acceptable | borderline | rejected

Models:
- QualityMetrics: Detailed image dimension, focus, luminance, and contrast measurements
- ImageQualityReport: Comprehensive quality report and workflow routing decision
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class QualityStatus(str, Enum):
    """Tri-state image quality status governing downstream pipeline routing."""

    acceptable = "acceptable"
    borderline = "borderline"
    rejected = "rejected"


class QualityMetrics(BaseModel):
    """Individual image quality measurements across resolution, focus, luminance, and contrast."""

    width: int = Field(..., ge=1, description="Image width in pixels")
    height: int = Field(..., ge=1, description="Image height in pixels")
    total_pixels: int = Field(..., ge=1, description="Total pixel count (width * height)")
    resolution_acceptable: bool = Field(..., description="Whether image resolution meets baseline")

    blur_score: float = Field(..., ge=0.0, description="Laplacian variance focus score (higher = sharper)")
    is_blurry: bool = Field(..., description="Flag indicating image focus is below acceptable threshold")

    brightness_score: float = Field(
        ..., ge=0.0, le=255.0, description="Mean luminance value (0 = pitch black, 255 = pure white)"
    )
    is_too_dark: bool = Field(..., description="Flag indicating underexposure")
    is_too_bright: bool = Field(..., description="Flag indicating overexposure or harsh glare")

    contrast_score: float = Field(
        ..., ge=0.0, description="Standard deviation of grayscale luminance distribution"
    )
    is_low_contrast: bool = Field(..., description="Flag indicating insufficient contrast for text legibility")


class ImageQualityReport(BaseModel):
    """Consolidated image quality assessment report returned by check_image_quality()."""

    is_valid: bool = Field(
        ..., description="True if image can proceed (acceptable or recovered borderline)"
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic normalized composite quality score (0.0 to 1.0)",
    )
    status: QualityStatus = Field(
        ..., description="Workflow decision status: acceptable | borderline | rejected"
    )
    recapture_reason: Optional[str] = Field(
        default=None,
        description="Actionable user-facing guidance when image is borderline or rejected",
    )
    metrics: QualityMetrics = Field(..., description="Detailed individual quality metrics breakdown")
