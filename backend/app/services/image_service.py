"""
PackSure AI — Image Validation, Quality Assessment, and OpenCV Preprocessing Service.

Implements Phase 2 image pipeline operations:
1. validate_image_file: File integrity, byte length, magic byte headers, format decoding.
2. check_image_quality: Resolution, focus/blur (Laplacian variance), luminance, contrast, tri-state status.
3. enhance_borderline_image: Conservative contrast and edge enhancement for borderline scans.
4. preprocess_for_pipeline: Produces specialized derived artifacts (enhanced BGR for Gemini, binarized for Tesseract).

Key Invariants:
- The original input image is strictly immutable.
- All bounding box coordinate systems throughout the system remain anchored to the original unscaled image.
- Thresholds are initial configurable prototype baselines subject to empirical calibration.
"""

from typing import Optional, Tuple
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from scipy.signal import convolve2d
except ImportError:
    convolve2d = None

from app.schemas.image import (
    ImageQualityReport,
    QualityMetrics,
    QualityStatus,
)

# =====================================================================
# Constants & Configurable Prototype Engineering Baselines
# =====================================================================

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MiB limit per docs/api.md
SUPPORTED_IMAGE_TYPES: Tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")

# Resolution Baselines (Pixel Dimensions)
MIN_WIDTH_PIXELS: int = 600
MIN_HEIGHT_PIXELS: int = 600
MIN_TOTAL_PIXELS: int = 360000

# Focus / Blur Baselines (Laplacian Variance Score)
BLUR_THRESHOLD_REJECT: float = 60.0
BLUR_THRESHOLD_ACCEPTABLE: float = 120.0

# Brightness / Luminance Baselines (Mean Grayscale Intensity 0–255)
BRIGHTNESS_MIN_REJECT: float = 30.0
BRIGHTNESS_MIN_ACCEPTABLE: float = 50.0
BRIGHTNESS_MAX_ACCEPTABLE: float = 215.0
BRIGHTNESS_MAX_REJECT: float = 235.0

# Contrast Baselines (Standard Deviation of Grayscale Luminance)
CONTRAST_MIN_REJECT: float = 18.0
CONTRAST_MIN_ACCEPTABLE: float = 30.0

# Deskew Activation Limits (Degrees)
DESKEW_MIN_ANGLE_TRIGGER: float = 1.5
DESKEW_MAX_ANGLE_LIMIT: float = 45.0


# =====================================================================
# 1. Image File Validation
# =====================================================================


def validate_image_file(
    file_bytes: bytes, filename: str = ""
) -> Tuple[bool, Optional[str], Optional[np.ndarray]]:
    """Validate raw image file payload and decode to BGR NumPy array.

    Verifies:
    1. Non-empty byte sequence.
    2. File size <= 10 MiB limit.
    3. Magic byte header signatures (JPEG, PNG, WebP).
    4. Successful in-memory image decoding without corrupt blocks.

    Args:
        file_bytes: Raw binary payload of the uploaded image.
        filename: Optional filename for logging/diagnostics.

    Returns:
        Tuple of (is_valid, error_message, decoded_bgr_numpy_array)
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        return False, "Image payload must be a non-empty bytes object", None

    if len(file_bytes) == 0:
        return False, "Image file is empty", None

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, f"Image file size ({len(file_bytes)} bytes) exceeds the 10MB limit", None

    # Verify Magic Byte Signatures
    # JPEG: FF D8 FF
    # PNG:  89 50 4E 47 0D 0A 1A 0A
    # WebP: RIFF....WEBP
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = (
        len(file_bytes) >= 12
        and file_bytes[:4] == b"RIFF"
        and file_bytes[8:12] == b"WEBP"
    )

    if not (is_jpeg or is_png or is_webp):
        return (
            False,
            "Unsupported file format. Supported formats: JPEG, PNG, WebP.",
            None,
        )

    # Decode image in-memory
    decoded_image: Optional[np.ndarray] = None

    if cv2 is not None:
        np_arr = np.frombuffer(file_bytes, dtype=np.uint8)
        decoded_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    else:
        # Fallback decoding via Pillow if cv2 is not yet installed
        try:
            from io import BytesIO
            from PIL import Image

            pil_img = Image.open(BytesIO(file_bytes)).convert("RGB")
            # Convert RGB to BGR NumPy array
            rgb_arr = np.array(pil_img, dtype=np.uint8)
            decoded_image = rgb_arr[..., ::-1].copy()
        except Exception:
            decoded_image = None

    if decoded_image is None or decoded_image.size == 0:
        return False, "Corrupt or unreadable image file data", None

    return True, None, decoded_image


# =====================================================================
# 2. Image Quality Assessment
# =====================================================================


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert input image to 2D float64 grayscale array safely."""
    if image.ndim == 2:
        return image.astype(np.float64)
    if image.ndim == 3:
        if cv2 is not None:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float64)
        # Standard ITU-R BT.601 RGB/BGR luminance coefficients
        b = image[:, :, 0].astype(np.float64)
        g = image[:, :, 1].astype(np.float64)
        r = image[:, :, 2].astype(np.float64)
        return 0.299 * r + 0.587 * g + 0.114 * b
    raise ValueError(f"Unsupported image array dimensions: {image.shape}")


def _compute_laplacian_variance(gray: np.ndarray) -> float:
    """Compute focus/blur metric using variance of the Laplacian operator."""
    if cv2 is not None:
        gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)
        laplacian = cv2.Laplacian(gray_u8, cv2.CV_64F)
        return float(laplacian.var())

    # Pure NumPy / SciPy fallback
    kernel = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float64)
    if convolve2d is not None:
        lap = convolve2d(gray, kernel, mode="valid")
        return float(lap.var())

    # Fast 2D finite difference approximation in pure NumPy
    center = gray[1:-1, 1:-1]
    lap = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * center
    )
    return float(lap.var())


def check_image_quality(image: np.ndarray) -> ImageQualityReport:
    """Evaluate image resolution, focus/blur, brightness, and contrast against prototype baselines.

    Determines:
    - QualityStatus: acceptable | borderline | rejected
    - Actionable user recapture reason when quality is insufficient.
    - Deterministic composite quality_score in [0.0, 1.0].

    Args:
        image: Original input image array (BGR or grayscale).

    Returns:
        ImageQualityReport

    Raises:
        ValueError: If image is None, not a numpy array, or has invalid dimensions.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Invalid or empty image array passed to check_image_quality()")

    height, width = image.shape[:2]
    if width < 1 or height < 1:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")

    total_pixels = width * height
    gray = _to_grayscale(image)

    # 1. Resolution
    resolution_acceptable = bool(
        width >= MIN_WIDTH_PIXELS
        and height >= MIN_HEIGHT_PIXELS
        and total_pixels >= MIN_TOTAL_PIXELS
    )

    # 2. Focus / Blur Assessment
    blur_score = _compute_laplacian_variance(gray)
    is_blurry = blur_score < BLUR_THRESHOLD_ACCEPTABLE
    blur_rejected = blur_score < BLUR_THRESHOLD_REJECT

    # 3. Brightness / Luminance Assessment
    brightness_score = float(np.mean(gray))
    is_too_dark = brightness_score < BRIGHTNESS_MIN_ACCEPTABLE
    is_too_bright = brightness_score > BRIGHTNESS_MAX_ACCEPTABLE
    brightness_rejected = (
        brightness_score < BRIGHTNESS_MIN_REJECT
        or brightness_score > BRIGHTNESS_MAX_REJECT
    )

    # 4. Contrast Assessment
    contrast_score = float(np.std(gray))
    is_low_contrast = contrast_score < CONTRAST_MIN_ACCEPTABLE
    contrast_rejected = contrast_score < CONTRAST_MIN_REJECT

    # 5. Tri-State Quality Determination
    has_hard_rejection = bool(
        (not resolution_acceptable)
        or blur_rejected
        or brightness_rejected
        or contrast_rejected
    )

    has_borderline_condition = bool(
        is_blurry or is_too_dark or is_too_bright or is_low_contrast
    )

    if has_hard_rejection:
        status = QualityStatus.rejected
        is_valid = False
    elif has_borderline_condition:
        status = QualityStatus.borderline
        is_valid = True
    else:
        status = QualityStatus.acceptable
        is_valid = True

    # 6. Actionable User Recapture Guidance
    reasons = []
    if not resolution_acceptable:
        reasons.append(
            f"Image resolution ({width}x{height}) is too low; minimum {MIN_WIDTH_PIXELS}x{MIN_HEIGHT_PIXELS} px required."
        )
    if blur_rejected:
        reasons.append("Image is severely blurry; please hold the camera steady and tap to focus.")
    elif is_blurry:
        reasons.append("Image focus is soft; hold camera steady for clearer text.")

    if brightness_score < BRIGHTNESS_MIN_REJECT:
        reasons.append("Image is too dark; please increase lighting on the package label.")
    elif is_too_dark:
        reasons.append("Image is slightly underexposed; additional lighting recommended.")
    elif brightness_score > BRIGHTNESS_MAX_REJECT:
        reasons.append("Image is severely overexposed with harsh glare; tilt camera to avoid reflections.")
    elif is_too_bright:
        reasons.append("Image is brightly overexposed; avoid direct glare on text.")

    if contrast_rejected:
        reasons.append("Image has very low contrast; ensure package text stands out clearly from the background.")
    elif is_low_contrast:
        reasons.append("Image has marginal contrast between text and background.")

    recapture_reason = " ".join(reasons) if reasons else None

    # 7. Deterministic Composite Quality Score [0.0, 1.0]
    # Transparent weighting: Resolution (25%), Focus (35%), Brightness (20%), Contrast (20%)
    res_factor = min(1.0, total_pixels / float(MIN_TOTAL_PIXELS))
    blur_factor = min(1.0, blur_score / (BLUR_THRESHOLD_ACCEPTABLE * 1.5))
    bright_factor = max(0.0, 1.0 - abs(brightness_score - 127.5) / 127.5)
    contrast_factor = min(1.0, contrast_score / (CONTRAST_MIN_ACCEPTABLE * 2.0))

    raw_composite = (
        0.25 * res_factor
        + 0.35 * blur_factor
        + 0.20 * bright_factor
        + 0.20 * contrast_factor
    )

    if status == QualityStatus.rejected:
        quality_score = round(min(0.45, max(0.0, raw_composite * 0.5)), 3)
    elif status == QualityStatus.borderline:
        quality_score = round(min(0.74, max(0.50, raw_composite)), 3)
    else:
        quality_score = round(min(1.0, max(0.75, raw_composite)), 3)

    metrics = QualityMetrics(
        width=width,
        height=height,
        total_pixels=total_pixels,
        resolution_acceptable=resolution_acceptable,
        blur_score=round(blur_score, 2),
        is_blurry=is_blurry,
        brightness_score=round(brightness_score, 2),
        is_too_dark=is_too_dark,
        is_too_bright=is_too_bright,
        contrast_score=round(contrast_score, 2),
        is_low_contrast=is_low_contrast,
    )

    return ImageQualityReport(
        is_valid=is_valid,
        quality_score=quality_score,
        status=status,
        recapture_reason=recapture_reason,
        metrics=metrics,
    )


# =====================================================================
# 3. Borderline Enhancement
# =====================================================================


def enhance_borderline_image(image: np.ndarray) -> np.ndarray:
    """Produce a conservatively enhanced derived copy of a borderline image.

    Applies mild Contrast Limited Adaptive Histogram Equalization (CLAHE)
    and gentle unsharp masking.

    Invariant: The original image is NEVER modified in-place.

    Args:
        image: Original BGR or grayscale image array.

    Returns:
        New derived enhanced NumPy array with identical dimensions.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Invalid image array provided to enhance_borderline_image()")

    enhanced = image.copy()

    if cv2 is not None:
        if enhanced.ndim == 3:
            # Apply CLAHE to L-channel in LAB color space
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l_chan)
            lab_enhanced = cv2.merge((l_enhanced, a_chan, b_chan))
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(enhanced)

        # Gentle unsharp mask for subtle edge clarity
        blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2.0)
        enhanced = cv2.addWeighted(enhanced, 1.2, blurred, -0.2, 0)
    else:
        # Fallback contrast stretch in pure NumPy
        p2, p98 = np.percentile(enhanced, (2, 98))
        if p98 > p2:
            stretched = np.clip((enhanced.astype(np.float64) - p2) * 255.0 / (p98 - p2), 0, 255)
            enhanced = stretched.astype(np.uint8)

    return enhanced


# =====================================================================
# 4. Pipeline Preprocessing
# =====================================================================


def _detect_skew_angle(gray_img: np.ndarray) -> float:
    """Detect dominant text line skew angle in degrees using edge contours.

    Returns:
        Skew angle in degrees between -45.0 and 45.0. Returns 0.0 if undetectable.
    """
    if cv2 is None or gray_img is None or gray_img.size == 0:
        return 0.0

    try:
        # Edge detection followed by minimum bounding rectangle analysis
        thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 50:
            return 0.0

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45.0:
            angle = -(90.0 + angle)
        elif angle > 45.0:
            angle = 90.0 - angle
        else:
            angle = -angle

        if abs(angle) > DESKEW_MAX_ANGLE_LIMIT:
            return 0.0
        return float(angle)
    except Exception:
        return 0.0


def preprocess_for_pipeline(
    original_image: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Produce specialized derived artifacts for Gemini Vision and Tesseract OCR.

    Outputs:
    1. enhanced_vision_image (BGR):
       - Conservative contrast and luminance balancing for Gemini Vision extraction.
    2. ocr_binarized_image (Grayscale / Binary):
       - Grayscale conversion.
       - Conditional deskew (only triggered if abs(angle) > DESKEW_MIN_ANGLE_TRIGGER).
       - Noise smoothing and Otsu binarization for Tesseract character segmentation.

    Invariant:
    - The original_image parameter is never modified in-place.
    - All bounding boxes remain referenced to original image coordinates.

    Args:
        original_image: Original BGR image array.

    Returns:
        Tuple of (enhanced_vision_image, ocr_binarized_image)
    """
    if original_image is None or not isinstance(original_image, np.ndarray) or original_image.size == 0:
        raise ValueError("Invalid original_image array provided to preprocess_for_pipeline()")

    # 1. Enhanced Vision Image (BGR) for Gemini
    enhanced_vision = enhance_borderline_image(original_image)

    # 2. OCR Binarized Image for Tesseract
    gray = _to_grayscale(original_image).astype(np.uint8)

    # Conditional Deskew
    angle = _detect_skew_angle(gray)
    if cv2 is not None and DESKEW_MIN_ANGLE_TRIGGER < abs(angle) <= DESKEW_MAX_ANGLE_LIMIT:
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        gray_deskewed = cv2.warpAffine(
            gray, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
    else:
        gray_deskewed = gray.copy()

    # Noise reduction & Binarization
    if cv2 is not None:
        denoised = cv2.medianBlur(gray_deskewed, 3)
        _, ocr_binarized = cv2.threshold(
            denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        # Pure NumPy Otsu binarization fallback
        otsu_thresh = float(np.mean(gray_deskewed))
        ocr_binarized = np.where(gray_deskewed > otsu_thresh, 255, 0).astype(np.uint8)

    return enhanced_vision, ocr_binarized
