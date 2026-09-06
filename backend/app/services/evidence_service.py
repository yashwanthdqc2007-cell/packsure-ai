"""
PackSure AI — Evidence Packaging & Visual Annotation Service.

Implements Phase 6A visual evidence generation operations:
1. render_evidence_overlay: Draw color-coded compliance bounding boxes on package images.
   - RED (BGR: 0, 0, 255) for deterministic rule violations.
   - YELLOW (BGR: 0, 255, 255) for uncertain declarations.
   - GREEN (BGR: 0, 255, 0) for verified compliant declarations.
2. Invariant preservation: Never mutates the original image array in-place.
3. Coordinate safety: Strict boundary clamping and zero coordinate hallucination (no boxes drawn for missing declarations).
4. Evidence metadata generation linking rule citations and visual artifacts.
"""

from datetime import datetime, timezone
import os
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from app.schemas.compliance import ComplianceResult, EvidenceMetadata
from app.schemas.declaration import DeclarationStatus, ExtractedDeclaration
from app.schemas.ocr import BoundingBox
from app.schemas.violation import Violation

# BGR Color Constants
COLOR_VIOLATION_RED: Tuple[int, int, int] = (0, 0, 255)       # Red
COLOR_UNCERTAIN_YELLOW: Tuple[int, int, int] = (0, 255, 255)  # Yellow
COLOR_COMPLIANT_GREEN: Tuple[int, int, int] = (0, 255, 0)     # Green
COLOR_TEXT_WHITE: Tuple[int, int, int] = (255, 255, 255)      # White
COLOR_TEXT_BLACK: Tuple[int, int, int] = (0, 0, 0)            # Black


# =====================================================================
# Private Helper Functions
# =====================================================================


def _clamp_box_to_image(
    bbox: BoundingBox,
    img_width: int,
    img_height: int,
) -> Optional[Tuple[int, int, int, int]]:
    """Clamp bounding box coordinates strictly within image pixel boundaries.

    Returns:
        Tuple of (x, y, w, h) in integer pixels, or None if box has zero area.
    """
    if bbox is None or bbox.width <= 0.0 or bbox.height <= 0.0:
        return None

    x0 = int(round(bbox.x))
    y0 = int(round(bbox.y))
    w = int(round(bbox.width))
    h = int(round(bbox.height))

    # Reject out-of-bounds start
    if x0 >= img_width or y0 >= img_height:
        return None

    clamped_x = max(0, min(img_width - 1, x0))
    clamped_y = max(0, min(img_height - 1, y0))
    clamped_w = max(1, min(img_width - clamped_x, w))
    clamped_h = max(1, min(img_height - clamped_y, h))

    return clamped_x, clamped_y, clamped_w, clamped_h


def _draw_tagged_box(
    canvas: np.ndarray,
    overlay: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    color: Tuple[int, int, int],
    label: str,
) -> None:
    """Draw a translucent filled box with solid border and field tag banner."""
    if cv2 is None:
        # Fallback pure-NumPy bounding box outline
        canvas[y:y+h, x:x+w] = (
            canvas[y:y+h, x:x+w] * 0.7 + np.array(color, dtype=np.uint8) * 0.3
        ).astype(np.uint8)
        return

    # 1. Fill translucent box on overlay layer
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)

    # 2. Draw solid border on canvas
    cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)

    # 3. Draw solid label banner above or inside top edge
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.42
    thickness = 1
    (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    banner_h = text_h + baseline + 4
    banner_w = text_w + 6

    # Position banner above box if space permits, else inside
    banner_y1 = max(0, y - banner_h) if y >= banner_h else y
    banner_y2 = banner_y1 + banner_h
    banner_x1 = x
    banner_x2 = min(canvas.shape[1], banner_x1 + banner_w)

    cv2.rectangle(canvas, (banner_x1, banner_y1), (banner_x2, banner_y2), color, -1)

    # Text color: black on yellow/green, white on red
    text_color = COLOR_TEXT_BLACK if color in (COLOR_UNCERTAIN_YELLOW, COLOR_COMPLIANT_GREEN) else COLOR_TEXT_WHITE
    text_pos_y = banner_y1 + text_h + 2
    cv2.putText(
        canvas,
        label,
        (banner_x1 + 3, text_pos_y),
        font,
        font_scale,
        text_color,
        thickness,
        cv2.LINE_AA,
    )


# =====================================================================
# Public Service API
# =====================================================================


def render_evidence_overlay(
    image: np.ndarray,
    compliance_result: ComplianceResult,
    output_path: Optional[str] = None,
) -> Tuple[np.ndarray, EvidenceMetadata]:
    """Render color-coded compliance bounding boxes on a copy of the package image.

    RED: Deterministic rule violation.
    YELLOW: Uncertain declaration.
    GREEN: Verified compliant declaration.

    Invariants:
    - The input `image` array is never modified in-place.
    - Missing declarations do not draw hallucinated bounding boxes.
    - All coordinates remain strictly anchored to original image pixels.

    Args:
        image: Original BGR NumPy array.
        compliance_result: Consolidated compliance result from Phase 5 rule engine.
        output_path: Optional file path to save annotated JPEG image.

    Returns:
        Tuple of (annotated_bgr_image, evidence_metadata).

    Raises:
        ValueError: If image input is invalid or not a 3D NumPy array.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Image input must be a non-empty NumPy array.")

    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Image must be 3-channel BGR format, got shape {image.shape}.")

    # Work strictly on an isolated copy (original image immutability)
    canvas = image.copy()
    overlay = canvas.copy()
    h_img, w_img = canvas.shape[:2]

    # Map violating field names
    violations_by_field: Dict[str, Violation] = {}
    for v in compliance_result.violations:
        if v.field_name:
            violations_by_field[v.field_name] = v

    declarations = compliance_result.declarations or []

    # Render each detected declaration
    for decl in declarations:
        if not decl.bounding_box:
            # Missing or unlocalized declaration -> zero coordinate hallucination
            continue

        clamped_coords = _clamp_box_to_image(decl.bounding_box, w_img, h_img)
        if not clamped_coords:
            continue

        x, y, w, h = clamped_coords

        # Determine color and banner tag
        if decl.field_name in violations_by_field:
            # Violation -> RED
            color = COLOR_VIOLATION_RED
            v = violations_by_field[decl.field_name]
            label = f"{decl.field_name} | {v.rule_code} FAIL"
        elif decl.status == DeclarationStatus.uncertain:
            # Compliance uncertainty / NEEDS_REVIEW -> YELLOW
            color = COLOR_UNCERTAIN_YELLOW
            label = f"{decl.field_name} | UNCERTAIN"
        else:
            # Deterministic PASS / Verified compliant -> GREEN
            color = COLOR_COMPLIANT_GREEN
            label = f"{decl.field_name} | PASS"

        _draw_tagged_box(
            canvas=canvas,
            overlay=overlay,
            x=x,
            y=y,
            w=w,
            h=h,
            color=color,
            label=label,
        )

    # Blend translucent overlay onto canvas with 25% opacity
    if cv2 is not None:
        cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, dst=canvas)

    # Persist to disk if output path is specified
    annotated_path = None
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if cv2 is not None:
            cv2.imwrite(output_path, canvas)
        annotated_path = output_path

    # Construct EvidenceMetadata
    rule_ver = (
        compliance_result.evidence.rule_version
        if compliance_result.evidence and compliance_result.evidence.rule_version
        else "2026.1"
    )

    metadata = EvidenceMetadata(
        annotated_image_path=annotated_path,
        timestamp=datetime.now(timezone.utc).isoformat(),
        rule_version=rule_ver,
        total_declarations_checked=len(declarations),
        total_violations_found=len(compliance_result.violations),
    )

    return canvas, metadata
