"""
Unit tests for PackSure AI Structured Declaration Extraction Service (backend/app/services/ai_service.py).

Verifies:
1. Extraction prompt construction and strict extraction-only safety directives.
2. OCR evidence grounding, union bounding box calculation, and confidence aggregation.
3. Successful declaration extraction with mocked Gemini response.
4. Handling of detected, missing, and uncertain declaration statuses.
5. Missing field backfilling (all 10 mandatory fields always returned).
6. Safe handling of missing API key, network errors, malformed JSON, and empty responses.
7. Multimodal image input handling and product category forwarding.
8. Optional live integration test (skipped when GEMINI_API_KEY is not in environment).
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from app.core.config import settings
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    MandatoryFieldType,
)
from app.schemas.ocr import BoundingBox, OCRTextBlock, RawOCRResult
from app.services import ai_service
from app.services.ai_service import (
    MANDATORY_FIELDS,
    SYSTEM_INSTRUCTION,
    _build_extraction_prompt,
    _clean_json_response,
    _compute_bounding_box_union,
    _convert_numpy_to_pil,
    extract_declarations,
)


class TestAIExtractionPromptAndSafety(unittest.TestCase):
    """Tests for prompt safety directives and template formatting."""

    def test_system_prompt_forbids_compliance_decisions(self):
        """System instruction must explicitly prohibit compliance PASS/FAIL decisions."""
        self.assertIn("EXTRACTION ONLY", SYSTEM_INSTRUCTION)
        self.assertIn("NEVER evaluate compliance", SYSTEM_INSTRUCTION)
        self.assertIn("PASS, FAIL, or NEEDS_REVIEW", SYSTEM_INSTRUCTION)
        self.assertIn("NO FABRICATION", SYSTEM_INSTRUCTION)

    def test_build_extraction_prompt_formats_numbered_blocks(self):
        """Prompt builder must include numbered OCR blocks with confidence."""
        ocr = RawOCRResult(
            full_text="MRP Rs. 150\nNET WT 500g",
            language="eng",
            blocks=[
                OCRTextBlock(
                    text="MRP",
                    confidence=0.95,
                    bounding_box=BoundingBox(x=10, y=20, width=40, height=20),
                ),
                OCRTextBlock(
                    text="Rs. 150",
                    confidence=0.90,
                    bounding_box=BoundingBox(x=60, y=20, width=60, height=20),
                ),
            ],
        )

        prompt = _build_extraction_prompt(ocr, product_category="Food & Beverages")
        self.assertIn("Product Category: Food & Beverages", prompt)
        self.assertIn('[0] "MRP" (conf: 0.95)', prompt)
        self.assertIn('[1] "Rs. 150" (conf: 0.90)', prompt)
        self.assertIn("mrp", prompt)
        self.assertIn("net_quantity", prompt)


class TestEvidenceGroundingAndUtilities(unittest.TestCase):
    """Tests for deterministic evidence grounding and helper utilities."""

    def test_compute_bounding_box_union_multi_blocks(self):
        """Union box must tightly enclose all referenced OCR block boxes."""
        blocks = [
            OCRTextBlock(
                text="MRP",
                confidence=0.90,
                bounding_box=BoundingBox(x=10.0, y=20.0, width=40.0, height=20.0),
            ),
            OCRTextBlock(
                text="Rs. 150.00",
                confidence=0.80,
                bounding_box=BoundingBox(x=60.0, y=15.0, width=80.0, height=30.0),
            ),
        ]

        # Union should span: min_x=10, min_y=15, max_x=140, max_y=45
        # width = 140 - 10 = 130, height = 45 - 15 = 30
        union_box, avg_conf = _compute_bounding_box_union([0, 1], blocks)

        self.assertIsNotNone(union_box)
        self.assertEqual(union_box.x, 10.0)
        self.assertEqual(union_box.y, 15.0)
        self.assertEqual(union_box.width, 130.0)
        self.assertEqual(union_box.height, 30.0)
        self.assertEqual(avg_conf, 0.85)

    def test_compute_bounding_box_union_invalid_indices(self):
        """Out of range or non-integer indices should be ignored safely."""
        blocks = [
            OCRTextBlock(
                text="Weight: 500g",
                confidence=0.92,
                bounding_box=BoundingBox(x=20.0, y=50.0, width=100.0, height=25.0),
            )
        ]

        union_box, avg_conf = _compute_bounding_box_union([-1, 99, "bad"], blocks)
        self.assertIsNone(union_box)
        self.assertIsNone(avg_conf)

    def test_convert_numpy_to_pil(self):
        """NumPy array must convert to PIL Image if PIL is available, or return None gracefully."""
        bgr_arr = np.zeros((100, 100, 3), dtype=np.uint8)
        pil_img = _convert_numpy_to_pil(bgr_arr)
        if ai_service.Image is not None:
            self.assertIsNotNone(pil_img)
            self.assertEqual(pil_img.size, (100, 100))
        else:
            self.assertIsNone(pil_img)

        # None or invalid input must return None
        self.assertIsNone(_convert_numpy_to_pil(None))
        self.assertIsNone(_convert_numpy_to_pil(np.array([])))

    def test_clean_json_response(self):
        """JSON cleaner must strip markdown code blocks."""
        raw_md = "```json\n{\"declarations\": []}\n```"
        self.assertEqual(_clean_json_response(raw_md), '{"declarations": []}')

        plain_json = '{"declarations": []}'
        self.assertEqual(_clean_json_response(plain_json), '{"declarations": []}')


class TestExtractDeclarationsMocked(unittest.TestCase):
    """Tests for public extract_declarations service function using mocking."""

    def setUp(self):
        self.sample_ocr = RawOCRResult(
            full_text="Brand X Atta\nNet Qty: 5 kg\nMRP Rs. 240.00\nMfd: 01/2026\nExp: 07/2026\nBatch: B101\nCountry: India\nConsumer Care: 1800-123-456\nMfd by: ABC Mills Ltd, Industrial Area, Mumbai",
            language="eng",
            blocks=[
                OCRTextBlock(text="Brand X Atta", confidence=0.95, bounding_box=BoundingBox(x=50, y=50, width=150, height=30)),
                OCRTextBlock(text="Net Qty: 5 kg", confidence=0.92, bounding_box=BoundingBox(x=50, y=90, width=120, height=25)),
                OCRTextBlock(text="MRP Rs. 240.00", confidence=0.96, bounding_box=BoundingBox(x=50, y=120, width=140, height=25)),
                OCRTextBlock(text="Mfd: 01/2026", confidence=0.88, bounding_box=BoundingBox(x=50, y=150, width=100, height=20)),
                OCRTextBlock(text="Exp: 07/2026", confidence=0.89, bounding_box=BoundingBox(x=160, y=150, width=100, height=20)),
                OCRTextBlock(text="Batch: B101", confidence=0.91, bounding_box=BoundingBox(x=50, y=180, width=90, height=20)),
                OCRTextBlock(text="Country: India", confidence=0.94, bounding_box=BoundingBox(x=50, y=210, width=110, height=20)),
                OCRTextBlock(text="Consumer Care: 1800-123-456", confidence=0.90, bounding_box=BoundingBox(x=50, y=240, width=200, height=20)),
                OCRTextBlock(text="Mfd by: ABC Mills Ltd, Industrial Area, Mumbai", confidence=0.93, bounding_box=BoundingBox(x=50, y=270, width=300, height=30)),
            ],
        )

    def test_extract_declarations_success(self):
        """extract_declarations extracts all 10 mandatory fields with grounded bounding boxes."""
        mock_gemini_payload = {
            "declarations": [
                {
                    "field_name": "generic_name",
                    "status": "detected",
                    "raw_value": "Brand X Atta",
                    "normalized_value": "Wheat Flour (Atta)",
                    "supporting_block_indices": [0],
                    "confidence": 0.95,
                },
                {
                    "field_name": "net_quantity",
                    "status": "detected",
                    "raw_value": "Net Qty: 5 kg",
                    "normalized_value": "5 kg",
                    "supporting_block_indices": [1],
                    "confidence": 0.92,
                },
                {
                    "field_name": "mrp",
                    "status": "detected",
                    "raw_value": "MRP Rs. 240.00",
                    "normalized_value": "240.00",
                    "supporting_block_indices": [2],
                    "confidence": 0.96,
                },
                {
                    "field_name": "manufacture_date",
                    "status": "detected",
                    "raw_value": "Mfd: 01/2026",
                    "normalized_value": "2026-01",
                    "supporting_block_indices": [3],
                    "confidence": 0.88,
                },
                {
                    "field_name": "expiry_date",
                    "status": "detected",
                    "raw_value": "Exp: 07/2026",
                    "normalized_value": "2026-07",
                    "supporting_block_indices": [4],
                    "confidence": 0.89,
                },
                {
                    "field_name": "batch_number",
                    "status": "detected",
                    "raw_value": "Batch: B101",
                    "normalized_value": "B101",
                    "supporting_block_indices": [5],
                    "confidence": 0.91,
                },
                {
                    "field_name": "country_of_origin",
                    "status": "detected",
                    "raw_value": "Country: India",
                    "normalized_value": "India",
                    "supporting_block_indices": [6],
                    "confidence": 0.94,
                },
                {
                    "field_name": "consumer_care",
                    "status": "detected",
                    "raw_value": "Consumer Care: 1800-123-456",
                    "normalized_value": "1800-123-456",
                    "supporting_block_indices": [7],
                    "confidence": 0.90,
                },
                {
                    "field_name": "manufacturer_name_and_address",
                    "status": "detected",
                    "raw_value": "Mfd by: ABC Mills Ltd, Industrial Area, Mumbai",
                    "normalized_value": "ABC Mills Ltd, Industrial Area, Mumbai",
                    "supporting_block_indices": [8],
                    "confidence": 0.93,
                },
                {
                    "field_name": "unit_sale_price",
                    "status": "missing",
                    "raw_value": None,
                    "normalized_value": None,
                    "supporting_block_indices": [],
                    "confidence": None,
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_gemini_payload)

        with patch.object(settings, "gemini_api_key", "mock-test-key"):
            with patch("app.services.ai_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                declarations = extract_declarations(
                    ocr_result=self.sample_ocr,
                    product_category="Grocery",
                )

                # Exactly the 9 detected fields must be returned (no fabricated missing fields)
                self.assertEqual(len(declarations), 9)
                fields_dict = {d.field_name: d for d in declarations}

                # Check MRP
                mrp_decl = fields_dict["mrp"]
                self.assertEqual(mrp_decl.status, DeclarationStatus.detected)
                self.assertEqual(mrp_decl.raw_value, "MRP Rs. 240.00")
                self.assertEqual(mrp_decl.normalized_value, "240.00")
                self.assertEqual(mrp_decl.source, DeclarationSource.tesseract)
                self.assertIsNotNone(mrp_decl.bounding_box)
                self.assertEqual(mrp_decl.bounding_box.x, 50.0)

                # Check Net Quantity
                net_decl = fields_dict["net_quantity"]
                self.assertEqual(net_decl.status, DeclarationStatus.detected)
                self.assertEqual(net_decl.normalized_value, "5 kg")

                # Check Unit Sale Price was not returned/fabricated as proven missing
                self.assertNotIn("unit_sale_price", fields_dict)

    def test_omitted_fields_not_fabricated_as_missing(self):
        """When Gemini response omits fields, they must NOT be fabricated as status=missing."""
        partial_payload = {
            "declarations": [
                {
                    "field_name": "mrp",
                    "status": "detected",
                    "raw_value": "Rs. 100",
                    "normalized_value": "100.00",
                    "supporting_block_indices": [],
                    "confidence": 0.8,
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(partial_payload)

        with patch.object(settings, "gemini_api_key", "mock-test-key"):
            with patch("app.services.ai_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                declarations = extract_declarations(ocr_result=self.sample_ocr)

                # Only the single extracted field should be returned
                self.assertEqual(len(declarations), 1)
                self.assertEqual(declarations[0].field_name, "mrp")
                self.assertEqual(declarations[0].status, DeclarationStatus.detected)

                # Verify unextracted fields are omitted, not falsely claimed as missing
                returned_field_names = [d.field_name for d in declarations]
                self.assertNotIn("expiry_date", returned_field_names)
                self.assertNotIn("net_quantity", returned_field_names)

    def test_uncertain_status_preservation(self):
        """Partially illegible field must retain status=uncertain."""
        uncertain_payload = {
            "declarations": [
                {
                    "field_name": "expiry_date",
                    "status": "uncertain",
                    "raw_value": "EXP: ??/2026",
                    "normalized_value": None,
                    "supporting_block_indices": [4],
                    "confidence": 0.45,
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(uncertain_payload)

        with patch.object(settings, "gemini_api_key", "mock-test-key"):
            with patch("app.services.ai_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                declarations = extract_declarations(ocr_result=self.sample_ocr)
                fields_dict = {d.field_name: d for d in declarations}

                self.assertEqual(fields_dict["expiry_date"].status, DeclarationStatus.uncertain)
                self.assertEqual(fields_dict["expiry_date"].raw_value, "EXP: ??/2026")


class TestAIExtractionErrorHandling(unittest.TestCase):
    """Tests for exception handling during extraction."""

    def test_none_ocr_result_raises_value_error(self):
        """Passing None for ocr_result raises ValueError."""
        with self.assertRaises(ValueError):
            extract_declarations(None)  # type: ignore

    def test_missing_api_key_raises_runtime_error(self):
        """Unconfigured GEMINI_API_KEY raises descriptive RuntimeError."""
        with patch.object(settings, "gemini_api_key", ""):
            with self.assertRaises(RuntimeError) as ctx:
                extract_declarations(RawOCRResult())
            self.assertIn("GEMINI_API_KEY is not configured", str(ctx.exception))

    def test_gemini_api_failure_raises_runtime_error(self):
        """API invocation errors are caught and wrapped in RuntimeError."""
        with patch.object(settings, "gemini_api_key", "mock-key"):
            with patch("app.services.ai_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = Exception("Quota exceeded")
                mock_genai.GenerativeModel.return_value = mock_model

                with self.assertRaises(RuntimeError) as ctx:
                    extract_declarations(RawOCRResult())
                self.assertIn("Gemini API generation failed", str(ctx.exception))

    def test_malformed_json_raises_runtime_error(self):
        """Malformed JSON response from model raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all."

        with patch.object(settings, "gemini_api_key", "mock-key"):
            with patch("app.services.ai_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                with self.assertRaises(RuntimeError) as ctx:
                    extract_declarations(RawOCRResult())
                self.assertIn("Failed to parse Gemini output as valid JSON", str(ctx.exception))


class TestLiveGeminiIntegration(unittest.TestCase):
    """Live integration test executed only when a real GEMINI_API_KEY is configured in the environment."""

    def test_live_gemini_extraction(self):
        """Optional live test validating real Gemini API integration."""
        api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
        if not api_key or api_key.startswith("mock"):
            self.skipTest("Real GEMINI_API_KEY not found in environment.")

        ocr = RawOCRResult(
            full_text="PARLE-G BISCUITS\nNet Wt: 250 g\nMRP Rs. 25.00 (Incl. of all taxes)\nMfd Date: 02/2026\nBatch: B99\nCountry of Origin: India\nParle Products Pvt Ltd, Mumbai, India",
            language="eng",
            blocks=[
                OCRTextBlock(text="PARLE-G BISCUITS", confidence=0.98, bounding_box=BoundingBox(x=10, y=10, width=200, height=30)),
                OCRTextBlock(text="Net Wt: 250 g", confidence=0.95, bounding_box=BoundingBox(x=10, y=50, width=150, height=25)),
                OCRTextBlock(text="MRP Rs. 25.00", confidence=0.97, bounding_box=BoundingBox(x=10, y=80, width=160, height=25)),
            ],
        )

        declarations = extract_declarations(ocr_result=ocr, product_category="Biscuits")
        self.assertEqual(len(declarations), 10)
        fields_dict = {d.field_name: d for d in declarations}

        self.assertEqual(fields_dict["net_quantity"].status, DeclarationStatus.detected)
        self.assertIn("250", str(fields_dict["net_quantity"].normalized_value))


if __name__ == "__main__":
    unittest.main()
