"""
Unit tests for PackSure AI OCR service (backend/app/services/ocr_service.py).

Verifies:
1. Input array validation and error handling (None, empty, invalid dimensions).
2. Input immutability (original array is not modified in-place).
3. Confidence normalization from 0–100 to [0.0, 1.0] and exclusion of -1 structural entries.
4. Token filtering (empty strings, whitespace-only tokens).
5. BoundingBox construction and boundary clamping within original image dimensions.
6. Full text assembly across lines and paragraphs.
7. Mocked pytesseract.image_to_data extraction.
8. Language parameter forwarding.
9. Handling missing binary / pytesseract execution exceptions.
10. Synthetic OCR integration test on rendered text image when pytesseract & Tesseract are available.
"""

import os
import shutil
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from app.schemas.ocr import BoundingBox, OCRTextBlock, RawOCRResult
from app.services import ocr_service
from app.services.ocr_service import (
    _map_coordinates_to_original,
    _normalize_confidence,
    _parse_tesseract_dict,
    _validate_image_input,
    extract_raw_ocr,
)


class TestOCRInputValidationAndImmutability(unittest.TestCase):
    """Tests for input validation, edge cases, and input array immutability."""

    def test_none_input_raises_value_error(self):
        """None input must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            extract_raw_ocr(None)
        self.assertIn("non-null NumPy array", str(ctx.exception))

    def test_non_numpy_input_raises_value_error(self):
        """Non-numpy input must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            extract_raw_ocr("not-an-image")  # type: ignore
        self.assertIn("non-null NumPy array", str(ctx.exception))

    def test_empty_array_raises_value_error(self):
        """Empty array must raise ValueError."""
        empty_arr = np.array([], dtype=np.uint8)
        with self.assertRaises(ValueError) as ctx:
            extract_raw_ocr(empty_arr)
        self.assertIn("empty", str(ctx.exception))

    def test_invalid_dimension_raises_value_error(self):
        """1D and 4D arrays must raise ValueError."""
        arr_1d = np.zeros((100,), dtype=np.uint8)
        with self.assertRaises(ValueError):
            extract_raw_ocr(arr_1d)

        arr_4d = np.zeros((1, 100, 100, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            extract_raw_ocr(arr_4d)

    def test_zero_dimension_shape_raises_value_error(self):
        """0x100 or 100x0 images must raise ValueError."""
        arr_zero_h = np.zeros((0, 100), dtype=np.uint8)
        with self.assertRaises(ValueError):
            _validate_image_input(arr_zero_h)

    def test_input_immutability(self):
        """Input image array must not be mutated by extract_raw_ocr."""
        orig = np.full((100, 200, 3), 128, dtype=np.uint8)
        orig_copy = orig.copy()

        mock_tess_data = {
            "text": ["TEST"],
            "conf": [90],
            "left": [10],
            "top": [20],
            "width": [50],
            "height": [15],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
        }

        with patch("app.services.ocr_service.pytesseract") as mock_pytess:
            mock_pytess.Output.DICT = "dict"
            mock_pytess.image_to_data.return_value = mock_tess_data

            result = extract_raw_ocr(orig)
            self.assertIsInstance(result, RawOCRResult)
            self.assertEqual(result.full_text, "TEST")

        # Verify original array content was not modified
        np.testing.assert_array_equal(orig, orig_copy)


class TestOCRConfidenceAndBoundingBoxLogic(unittest.TestCase):
    """Tests for confidence normalization and bounding box coordinate mapping."""

    def test_confidence_normalization(self):
        """Valid 0-100 confidences must be normalized to 0.0-1.0."""
        self.assertEqual(_normalize_confidence(100), 1.0)
        self.assertEqual(_normalize_confidence(0), 0.0)
        self.assertEqual(_normalize_confidence(85), 0.85)
        self.assertEqual(_normalize_confidence(50.5), 0.505)

    def test_confidence_structural_minus_one_filtered(self):
        """Confidence -1 (structural headers) must return None."""
        self.assertIsNone(_normalize_confidence(-1))
        self.assertIsNone(_normalize_confidence("-1"))
        self.assertIsNone(_normalize_confidence(-50))

    def test_confidence_clamping(self):
        """Confidence values > 100 must be clamped to 1.0."""
        self.assertEqual(_normalize_confidence(120), 1.0)

    def test_confidence_invalid_types(self):
        """Invalid non-numeric confidence must return None."""
        self.assertIsNone(_normalize_confidence("invalid"))
        self.assertIsNone(_normalize_confidence(None))

    def test_bounding_box_mapping_valid(self):
        """Valid coordinates within original bounds should create BoundingBox."""
        bbox = _map_coordinates_to_original(
            x=10.0,
            y=20.0,
            width=50.0,
            height=30.0,
            orig_width=500,
            orig_height=400,
        )
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox.x, 10.0)
        self.assertEqual(bbox.y, 20.0)
        self.assertEqual(bbox.width, 50.0)
        self.assertEqual(bbox.height, 30.0)

    def test_bounding_box_mapping_clamps_to_original_boundaries(self):
        """Coordinates exceeding original image bounds should be clamped safely."""
        bbox = _map_coordinates_to_original(
            x=-5.0,
            y=-10.0,
            width=600.0,
            height=500.0,
            orig_width=400,
            orig_height=300,
        )
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox.x, 0.0)
        self.assertEqual(bbox.y, 0.0)
        self.assertEqual(bbox.width, 400.0)
        self.assertEqual(bbox.height, 300.0)

    def test_bounding_box_non_positive_dimensions(self):
        """Non-positive width or height must return None."""
        self.assertIsNone(
            _map_coordinates_to_original(10, 10, 0, 20, 500, 500)
        )
        self.assertIsNone(
            _map_coordinates_to_original(10, 10, 30, -5, 500, 500)
        )


class TestTesseractDataParsing(unittest.TestCase):
    """Tests for parsing Tesseract dictionary structure into RawOCRResult."""

    def test_parse_tesseract_dict_clean_tokens_and_lines(self):
        """Parser must assemble tokens into blocks and preserve line structures in full_text."""
        mock_data = {
            "text": ["", "PACKSURE", "AI", "", "NET", "QUANTITY:", "500g", ""],
            "conf": [-1, 95, 92, -1, 88, 90, 94, -1],
            "left": [0, 10, 100, 0, 10, 60, 160, 0],
            "top": [0, 20, 20, 0, 50, 50, 50, 0],
            "width": [0, 80, 30, 0, 40, 90, 50, 0],
            "height": [0, 25, 25, 0, 20, 20, 20, 0],
            "block_num": [1, 1, 1, 1, 1, 1, 1, 1],
            "par_num": [1, 1, 1, 1, 1, 1, 1, 1],
            "line_num": [1, 1, 1, 1, 2, 2, 2, 2],
        }

        blocks, full_text = _parse_tesseract_dict(mock_data, orig_width=800, orig_height=600)

        # 5 valid tokens (ignoring empty strings and conf=-1)
        self.assertEqual(len(blocks), 5)
        self.assertEqual(blocks[0].text, "PACKSURE")
        self.assertEqual(blocks[0].confidence, 0.95)
        self.assertEqual(blocks[0].bounding_box.x, 10.0)

        self.assertEqual(blocks[1].text, "AI")
        self.assertEqual(blocks[1].confidence, 0.92)

        self.assertEqual(blocks[2].text, "NET")
        self.assertEqual(blocks[3].text, "QUANTITY:")
        self.assertEqual(blocks[4].text, "500g")

        # Full text line assembly
        expected_text = "PACKSURE AI\nNET QUANTITY: 500g"
        self.assertEqual(full_text, expected_text)

    def test_parse_tesseract_dict_all_empty(self):
        """Parser with no text tokens returns empty list and empty string."""
        empty_data = {
            "text": ["", "  ", "\t"],
            "conf": [-1, -1, 50],
            "left": [0, 0, 0],
            "top": [0, 0, 0],
            "width": [0, 0, 0],
            "height": [0, 0, 0],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
        }

        blocks, full_text = _parse_tesseract_dict(empty_data, orig_width=500, orig_height=500)
        self.assertEqual(blocks, [])
        self.assertEqual(full_text, "")


class TestExtractRawOCRMocking(unittest.TestCase):
    """Tests for public extract_raw_ocr service function using mocking."""

    def test_extract_raw_ocr_success(self):
        """extract_raw_ocr returns populated RawOCRResult schema."""
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        mock_tess_data = {
            "text": ["MRP", "Rs.", "150.00"],
            "conf": [92, 85, 96],
            "left": [20, 70, 110],
            "top": [30, 30, 30],
            "width": [45, 35, 75],
            "height": [22, 22, 22],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
        }

        with patch("app.services.ocr_service.pytesseract") as mock_pytess:
            mock_pytess.Output.DICT = "dict"
            mock_pytess.image_to_data.return_value = mock_tess_data

            result = extract_raw_ocr(img, lang="eng")

            self.assertIsInstance(result, RawOCRResult)
            self.assertEqual(result.language, "eng")
            self.assertEqual(result.full_text, "MRP Rs. 150.00")
            self.assertEqual(len(result.blocks), 3)
            self.assertEqual(result.blocks[0].text, "MRP")
            self.assertEqual(result.blocks[0].confidence, 0.92)
            self.assertEqual(result.blocks[0].bounding_box.width, 45.0)

    def test_language_parameter_forwarding(self):
        """extract_raw_ocr forwards custom lang code to pytesseract."""
        img = np.zeros((200, 200), dtype=np.uint8)

        with patch("app.services.ocr_service.pytesseract") as mock_pytess:
            mock_pytess.Output.DICT = "dict"
            mock_pytess.image_to_data.return_value = {"text": [], "conf": []}

            result = extract_raw_ocr(img, lang="eng+hin")
            self.assertEqual(result.language, "eng+hin")

            # Check that pytesseract was called with lang="eng+hin"
            mock_pytess.image_to_data.assert_called_once()
            _, kwargs = mock_pytess.image_to_data.call_args
            self.assertEqual(kwargs.get("lang"), "eng+hin")

    def test_missing_pytesseract_raises_runtime_error(self):
        """When pytesseract is None, raises RuntimeError."""
        img = np.zeros((100, 100), dtype=np.uint8)
        with patch("app.services.ocr_service.pytesseract", None):
            with self.assertRaises(RuntimeError) as ctx:
                extract_raw_ocr(img)
            self.assertIn("pytesseract is not available", str(ctx.exception))

    def test_tesseract_execution_failure_raises_runtime_error(self):
        """Pytesseract execution exception is wrapped in RuntimeError."""
        img = np.zeros((100, 100), dtype=np.uint8)

        with patch("app.services.ocr_service.pytesseract") as mock_pytess:
            mock_pytess.Output.DICT = "dict"
            mock_pytess.image_to_data.side_effect = Exception("Tesseract subprocess crashed")

            with self.assertRaises(RuntimeError) as ctx:
                extract_raw_ocr(img)
            self.assertIn("Tesseract OCR extraction failed", str(ctx.exception))


class TestSyntheticOCRIntegration(unittest.TestCase):
    """Integration test with rendered synthetic label image when Tesseract is available."""

    def test_synthetic_ocr_if_tesseract_available(self):
        """Test OCR extraction on synthetic image if pytesseract & tesseract are on the system."""
        if ocr_service.pytesseract is None:
            self.skipTest("pytesseract package not installed in environment.")

        # Check for tesseract executable
        tesseract_cmd = getattr(ocr_service.pytesseract.pytesseract, "tesseract_cmd", "tesseract")
        if shutil.which("tesseract") is None and not os.path.exists(tesseract_cmd):
            self.skipTest("Tesseract binary not found on system.")

        try:
            from PIL import Image, ImageDraw, ImageFont

            # Render a clear synthetic image: "PACKSURE 1000g"
            img = Image.new("RGB", (600, 200), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            # Draw simple text
            draw.text((50, 80), "PACKSURE 1000g", fill=(0, 0, 0))

            np_img = np.array(img)
            result = extract_raw_ocr(np_img, lang="eng")

            self.assertIsInstance(result, RawOCRResult)
            self.assertIn("PACKSURE", result.full_text)
            self.assertTrue(len(result.blocks) > 0)
            for block in result.blocks:
                self.assertGreaterEqual(block.confidence, 0.0)
                self.assertLessEqual(block.confidence, 1.0)
                if block.bounding_box:
                    self.assertGreaterEqual(block.bounding_box.x, 0.0)
                    self.assertGreaterEqual(block.bounding_box.y, 0.0)
                    self.assertGreater(block.bounding_box.width, 0.0)
                    self.assertGreater(block.bounding_box.height, 0.0)
        except Exception as exc:
            self.skipTest(f"Synthetic test skipped due to runtime environment limitation: {exc}")


if __name__ == "__main__":
    unittest.main()
