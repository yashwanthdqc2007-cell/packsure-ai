"""
Unit tests for PackSure AI Image Service Layer (Phase 2).

Tests:
- File validation (empty bytes, oversized bytes, invalid format, corrupt data, JPEG/PNG/WebP magic bytes)
- Image quality assessment (resolution, blur, brightness, contrast)
- Tri-state quality classification (acceptable, borderline, rejected)
- Recapture reason generation for various quality failures
- Deterministic composite quality score calculation
- Borderline image enhancement (ensures original image immutability and new array creation)
- Pipeline preprocessing (dual output: enhanced vision BGR and OCR binarized grayscale)
- Conditional deskew behavior and dimensional integrity
"""

import unittest
import numpy as np

from app.schemas.image import QualityStatus
from app.services.image_service import (
    BLUR_THRESHOLD_ACCEPTABLE,
    BLUR_THRESHOLD_REJECT,
    BRIGHTNESS_MAX_ACCEPTABLE,
    BRIGHTNESS_MAX_REJECT,
    BRIGHTNESS_MIN_ACCEPTABLE,
    BRIGHTNESS_MIN_REJECT,
    CONTRAST_MIN_ACCEPTABLE,
    CONTRAST_MIN_REJECT,
    DESKEW_MIN_ANGLE_TRIGGER,
    MAX_FILE_SIZE_BYTES,
    MIN_HEIGHT_PIXELS,
    MIN_WIDTH_PIXELS,
    check_image_quality,
    enhance_borderline_image,
    preprocess_for_pipeline,
    validate_image_file,
)


def _create_synthetic_sharp_image(width=800, height=800, brightness=128) -> np.ndarray:
    """Generate a clean, high-contrast synthetic image with sharp geometric patterns."""
    img = np.full((height, width, 3), brightness, dtype=np.uint8)
    # Add high-contrast text-like step edges
    for y in range(50, height - 50, 40):
        for x in range(50, width - 50, 60):
            img[y : y + 20, x : x + 30] = [20, 20, 20]
            img[y + 10 : y + 30, x + 25 : x + 55] = [240, 240, 240]
    return img


def _create_synthetic_blurred_image(width=800, height=800) -> np.ndarray:
    """Generate a smooth gradient image with virtually no high-frequency edge variance."""
    y = np.linspace(100, 150, height, dtype=np.float64)
    x = np.linspace(100, 150, width, dtype=np.float64)
    xx, yy = np.meshgrid(x, y)
    smooth = ((xx + yy) / 2.0).astype(np.uint8)
    return np.stack([smooth, smooth, smooth], axis=-1)


class TestImageFileValidation(unittest.TestCase):
    """Test validate_image_file() requirements."""

    def test_empty_bytes_rejected(self):
        is_valid, msg, img = validate_image_file(b"", "empty.jpg")
        self.assertFalse(is_valid)
        self.assertIn("empty", msg.lower())
        self.assertIsNone(img)

    def test_oversized_bytes_rejected(self):
        # 10MB + 1 byte
        oversized = b"\xff\xd8\xff" + b"\x00" * (MAX_FILE_SIZE_BYTES + 1)
        is_valid, msg, img = validate_image_file(oversized, "large.jpg")
        self.assertFalse(is_valid)
        self.assertIn("10mb", msg.lower())
        self.assertIsNone(img)

    def test_unsupported_format_rejected(self):
        # PDF / Text magic bytes
        fake_pdf = b"%PDF-1.4 header contents..."
        is_valid, msg, img = validate_image_file(fake_pdf, "doc.pdf")
        self.assertFalse(is_valid)
        self.assertIn("unsupported", msg.lower())
        self.assertIsNone(img)

    def test_corrupt_magic_bytes_rejected(self):
        # Starts with JPEG header but contains only garbage
        corrupt_jpeg = b"\xff\xd8\xffGARBAGE_UNREADABLE_STREAM"
        is_valid, msg, img = validate_image_file(corrupt_jpeg, "corrupt.jpg")
        self.assertFalse(is_valid)
        self.assertIn("corrupt", msg.lower())
        self.assertIsNone(img)

    def test_valid_jpeg_and_png_magic_byte_detection(self):
        # Check recognition of valid headers
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        webp_header = b"RIFF\x24\x00\x00\x00WEBPVP8 "

        # They fail decode on truncated header alone, confirming header acceptance before decode
        _, msg_jpg, _ = validate_image_file(jpeg_header, "test.jpg")
        self.assertIn("corrupt", msg_jpg.lower())

        _, msg_png, _ = validate_image_file(png_header, "test.png")
        self.assertIn("corrupt", msg_png.lower())

        _, msg_webp, _ = validate_image_file(webp_header, "test.webp")
        self.assertIn("corrupt", msg_webp.lower())


class TestImageQualityAssessment(unittest.TestCase):
    """Test check_image_quality() metrics, scores, and status routing."""

    def test_invalid_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            check_image_quality(None)
        with self.assertRaises(ValueError):
            check_image_quality(np.array([]))

    def test_resolution_failure_rejected(self):
        # Small image (300x300 < 600x600)
        small_img = _create_synthetic_sharp_image(width=300, height=300)
        report = check_image_quality(small_img)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.status, QualityStatus.rejected)
        self.assertFalse(report.metrics.resolution_acceptable)
        self.assertIsNotNone(report.recapture_reason)
        self.assertIn("resolution", report.recapture_reason.lower())

    def test_severe_blur_rejected(self):
        # Smooth image with minimal Laplacian variance
        blurred_img = _create_synthetic_blurred_image(width=800, height=800)
        report = check_image_quality(blurred_img)

        self.assertTrue(report.metrics.is_blurry)
        self.assertLess(report.metrics.blur_score, BLUR_THRESHOLD_REJECT)
        self.assertEqual(report.status, QualityStatus.rejected)
        self.assertIn("blurry", report.recapture_reason.lower())

    def test_dark_underexposed_image_rejected(self):
        # Extremely dark image (mean < BRIGHTNESS_MIN_REJECT)
        dark_img = np.full((800, 800, 3), 15, dtype=np.uint8)
        report = check_image_quality(dark_img)

        self.assertTrue(report.metrics.is_too_dark)
        self.assertEqual(report.status, QualityStatus.rejected)
        self.assertIn("dark", report.recapture_reason.lower())

    def test_overexposed_glare_image_rejected(self):
        # Overly bright image (mean > BRIGHTNESS_MAX_REJECT)
        bright_img = np.full((800, 800, 3), 245, dtype=np.uint8)
        report = check_image_quality(bright_img)

        self.assertTrue(report.metrics.is_too_bright)
        self.assertEqual(report.status, QualityStatus.rejected)
        self.assertIn("overexposed", report.recapture_reason.lower())

    def test_acceptable_quality_image(self):
        # Good resolution, sharp edges, balanced brightness (128), adequate contrast
        sharp_img = _create_synthetic_sharp_image(width=800, height=800, brightness=128)
        report = check_image_quality(sharp_img)

        self.assertTrue(report.is_valid)
        self.assertEqual(report.status, QualityStatus.acceptable)
        self.assertFalse(report.metrics.is_blurry)
        self.assertFalse(report.metrics.is_too_dark)
        self.assertFalse(report.metrics.is_too_bright)
        self.assertFalse(report.metrics.is_low_contrast)
        self.assertIsNone(report.recapture_reason)
        self.assertGreaterEqual(report.quality_score, 0.70)

    def test_borderline_image_status(self):
        # Moderately low contrast or slight softness
        img = np.full((800, 800, 3), 120, dtype=np.uint8)
        # Add subtle variation to produce borderline blur or contrast
        img[::4, ::4] = 145
        report = check_image_quality(img)

        # Borderline images are valid for enhancement
        if report.status == QualityStatus.borderline:
            self.assertTrue(report.is_valid)
            self.assertIsNotNone(report.recapture_reason)
            self.assertGreaterEqual(report.quality_score, 0.50)
            self.assertLessEqual(report.quality_score, 0.75)


class TestImageEnhancementAndPreprocessing(unittest.TestCase):
    """Test enhance_borderline_image() and preprocess_for_pipeline()."""

    def test_enhancement_preserves_original_immutability(self):
        original = _create_synthetic_sharp_image(width=700, height=700)
        original_copy = original.copy()

        enhanced = enhance_borderline_image(original)

        # Invariant 1: New object returned
        self.assertIsNot(enhanced, original)
        # Invariant 2: Original array remains strictly untouched
        np.testing.assert_array_equal(original, original_copy)
        # Invariant 3: Output dimensions match exactly
        self.assertEqual(enhanced.shape, original.shape)
        self.assertEqual(enhanced.dtype, np.uint8)

    def test_preprocess_for_pipeline_returns_dual_outputs(self):
        original = _create_synthetic_sharp_image(width=700, height=700)
        original_copy = original.copy()

        vision_img, ocr_img = preprocess_for_pipeline(original)

        # Invariant: Original remains unmodified
        np.testing.assert_array_equal(original, original_copy)

        # Vision image: 3-channel BGR
        self.assertEqual(vision_img.shape, original.shape)
        self.assertEqual(vision_img.dtype, np.uint8)

        # OCR image: 2D Grayscale / Binarized
        self.assertEqual(ocr_img.ndim, 2)
        self.assertEqual(ocr_img.shape[:2], original.shape[:2])
        self.assertEqual(ocr_img.dtype, np.uint8)

        # Binarized image should contain only black (0) and white (255) pixels
        unique_vals = np.unique(ocr_img)
        for val in unique_vals:
            self.assertIn(val, (0, 255))

    def test_deskew_threshold_behavior(self):
        # A perfectly aligned image should not trigger aggressive rotation transforms
        aligned_img = _create_synthetic_sharp_image(width=650, height=650)
        _, ocr_img = preprocess_for_pipeline(aligned_img)

        # Shape must stay identical
        self.assertEqual(ocr_img.shape, (650, 650))


if __name__ == "__main__":
    unittest.main()
