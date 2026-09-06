"""
PackSure AI — OCR Extraction Service.

Implements Phase 3 OCR pipeline operations:
1. extract_raw_ocr: Extract raw OCR text, confidence scores, and bounding boxes using Tesseract.
2. Token parsing and line-level full_text assembly.
3. Coordinate mapping preserving original image spatial coordinates.
4. Normalization of confidence scores to [0.0, 1.0].

Invariants:
- The input image array is strictly immutable (never modified in-place).
- All bounding box coordinates are non-negative pixels relative to original image top-left (0, 0).
- Pure OCR extraction layer — no LLM extraction or Legal Metrology rule logic mixed in.
"""

import os
import shutil
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    import pytesseract
    # Auto-detect Tesseract binary on Windows if not already in system PATH
    if shutil.which("tesseract") is None:
        default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_win_path):
            pytesseract.pytesseract.tesseract_cmd = default_win_path
except ImportError:
    pytesseract = None

from app.schemas.ocr import BoundingBox, OCRTextBlock, RawOCRResult


# =====================================================================
# Private Helper Functions
# =====================================================================


def _validate_image_input(image: np.ndarray) -> Tuple[int, int]:
    """Validate input image array and return (height, width).

    Args:
        image: Input image as a NumPy array.

    Returns:
        Tuple of (height, width).

    Raises:
        ValueError: If image is None, not a NumPy array, empty, or has invalid dimensions.
    """
    if image is None or not isinstance(image, np.ndarray):
        raise ValueError("Image input must be a non-null NumPy array.")

    if image.size == 0:
        raise ValueError("Image array cannot be empty.")

    if image.ndim not in (2, 3):
        raise ValueError(
            f"Unsupported image array dimensions: expected 2D (grayscale) or 3D (color), got {image.ndim}D shape {image.shape}."
        )

    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height} pixels.")

    return height, width


def _normalize_confidence(raw_conf: Any) -> Optional[float]:
    """Normalize Tesseract confidence value to float in range [0.0, 1.0].

    Tesseract returns confidence scores between 0 and 100, and uses -1 for
    structural or non-text elements (page/block/paragraph delimiters).

    Args:
        raw_conf: Raw confidence value from Tesseract dictionary.

    Returns:
        Float confidence in [0.0, 1.0], or None if invalid/structural.
    """
    try:
        conf_val = float(raw_conf)
    except (ValueError, TypeError):
        return None

    # Tesseract uses -1 for block/par/line headers and non-word separators
    if conf_val < 0.0:
        return None

    # Scale 0-100 to 0.0-1.0 and clamp to valid range
    normalized = conf_val / 100.0
    return max(0.0, min(1.0, normalized))


def _map_coordinates_to_original(
    x: float,
    y: float,
    width: float,
    height: float,
    orig_width: int,
    orig_height: int,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> Optional[BoundingBox]:
    """Map token coordinates back to the original image pixel coordinate space.

    Clamps values to remain within original image boundaries and ensures non-negative coordinates
    with positive dimensions.

    Args:
        x: Left pixel position on OCR image.
        y: Top pixel position on OCR image.
        width: Box width on OCR image.
        height: Box height on OCR image.
        orig_width: Original image width in pixels.
        orig_height: Original image height in pixels.
        scale_x: Horizontal scaling factor from OCR image to original.
        scale_y: Vertical scaling factor from OCR image to original.
        offset_x: Horizontal offset in pixels.
        offset_y: Vertical offset in pixels.

    Returns:
        BoundingBox instance or None if invalid box dimensions.
    """
    if width <= 0.0 or height <= 0.0:
        return None

    mapped_x = (x * scale_x) + offset_x
    mapped_y = (y * scale_y) + offset_y
    mapped_w = width * scale_x
    mapped_h = height * scale_y

    # Clamp to non-negative coordinates within original image boundaries
    clamped_x = max(0.0, min(float(orig_width), mapped_x))
    clamped_y = max(0.0, min(float(orig_height), mapped_y))
    clamped_w = max(0.0, min(float(orig_width) - clamped_x, mapped_w))
    clamped_h = max(0.0, min(float(orig_height) - clamped_y, mapped_h))

    if clamped_w <= 0.0 or clamped_h <= 0.0:
        return None

    return BoundingBox(
        x=round(clamped_x, 2),
        y=round(clamped_y, 2),
        width=round(clamped_w, 2),
        height=round(clamped_h, 2),
    )


def _parse_tesseract_dict(
    data: Dict[str, List[Any]],
    orig_width: int,
    orig_height: int,
) -> Tuple[List[OCRTextBlock], str]:
    """Parse Tesseract image_to_data dictionary into OCRTextBlock list and assembled full_text.

    Assembles full_text while respecting block, paragraph, and line structural boundaries.

    Args:
        data: Tesseract Output.DICT containing keys:
              ['text', 'conf', 'left', 'top', 'width', 'height', 'block_num', 'par_num', 'line_num', 'word_num']
        orig_width: Original image width.
        orig_height: Original image height.

    Returns:
        Tuple of (blocks, assembled_full_text).
    """
    blocks: List[OCRTextBlock] = []

    texts = data.get("text", [])
    confs = data.get("conf", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    widths = data.get("width", [])
    heights = data.get("height", [])
    block_nums = data.get("block_num", [])
    par_nums = data.get("par_num", [])
    line_nums = data.get("line_num", [])

    n_tokens = len(texts)
    if n_tokens == 0:
        return [], ""

    lines: List[List[str]] = []
    current_line: List[str] = []
    prev_line_key = None

    for i in range(n_tokens):
        raw_text = str(texts[i]) if i < len(texts) else ""
        cleaned_text = raw_text.strip()

        # Extract confidence
        raw_conf = confs[i] if i < len(confs) else -1
        norm_conf = _normalize_confidence(raw_conf)

        # Skip non-text or empty tokens
        if not cleaned_text or norm_conf is None:
            continue

        # Extract coordinates
        x = float(lefts[i]) if i < len(lefts) else 0.0
        y = float(tops[i]) if i < len(tops) else 0.0
        w = float(widths[i]) if i < len(widths) else 0.0
        h = float(heights[i]) if i < len(heights) else 0.0

        bbox = _map_coordinates_to_original(
            x=x,
            y=y,
            width=w,
            height=h,
            orig_width=orig_width,
            orig_height=orig_height,
        )

        block = OCRTextBlock(
            text=cleaned_text,
            confidence=round(norm_conf, 4),
            bounding_box=bbox,
        )
        blocks.append(block)

        # Line structure tracking for clean full_text assembly
        b_num = block_nums[i] if i < len(block_nums) else 0
        p_num = par_nums[i] if i < len(par_nums) else 0
        l_num = line_nums[i] if i < len(line_nums) else 0
        line_key = (b_num, p_num, l_num)

        if prev_line_key is not None and line_key != prev_line_key:
            if current_line:
                lines.append(current_line)
                current_line = []

        current_line.append(cleaned_text)
        prev_line_key = line_key

    if current_line:
        lines.append(current_line)

    assembled_full_text = "\n".join(" ".join(line_words) for line_words in lines if line_words).strip()

    return blocks, assembled_full_text


# =====================================================================
# Public Service API
# =====================================================================


def extract_raw_ocr(
    image: np.ndarray,
    lang: str = "eng",
) -> RawOCRResult:
    """Extract raw OCR text, confidence scores, and bounding boxes using Tesseract.

    Accepts an image NumPy array (either original BGR or OCR-preprocessed binarized image).
    Does NOT mutate the input array.

    Args:
        image: 2D or 3D NumPy array representing the image to process.
        lang: Tesseract language code(s) (e.g. 'eng', 'eng+hin'). Default is 'eng'.

    Returns:
        RawOCRResult populated with consolidated full_text, language, and token blocks.

    Raises:
        ValueError: If image input is None, empty, or invalid shape.
        RuntimeError: If pytesseract is not installed or Tesseract execution encounters a fatal error.
    """
    height, width = _validate_image_input(image)

    # Work strictly on an immutable copy
    image_copy = image.copy()

    if pytesseract is None:
        raise RuntimeError(
            "pytesseract is not available in the current environment. "
            "Please ensure pytesseract is installed and Tesseract-OCR binary is configured."
        )

    try:
        # Request detailed word/token positional data
        ocr_data = pytesseract.image_to_data(
            image_copy,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )
    except Exception as exc:
        exc_type_name = type(exc).__name__
        err_msg = str(exc)

        if "TesseractNotFoundError" in exc_type_name or "tesseract is not installed" in err_msg.lower():
            raise RuntimeError(
                f"Tesseract binary not found on system PATH. Details: {err_msg}"
            ) from exc

        # Check if error was due to missing language pack (e.g. 'hin')
        if any(keyword in err_msg.lower() for keyword in ("traineddata", "tessdata", "language")):
            raise RuntimeError(
                f"Tesseract failed executing language '{lang}'. Ensure the traineddata file exists. Details: {err_msg}"
            ) from exc

        raise RuntimeError(f"Tesseract OCR extraction failed: {err_msg}") from exc

    blocks, full_text = _parse_tesseract_dict(
        data=ocr_data,
        orig_width=width,
        orig_height=height,
    )

    return RawOCRResult(
        full_text=full_text,
        language=lang,
        blocks=blocks,
    )
