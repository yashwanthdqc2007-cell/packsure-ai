"""
PackSure AI — Structured Declaration Extraction Service using Google Gemini.

Implements Phase 4 extraction operations:
1. extract_declarations: Extract structured Legal Metrology package declarations
   from OCR results (+ optional visual image evidence).
2. Deterministic evidence grounding: Maps Gemini-extracted fields to OCR token bounding boxes
   and calculates union bounding boxes and aggregated confidence scores.
3. Strict separation of concerns: Gemini is used ONLY for extraction and normalization,
   NEVER for Legal Metrology compliance PASS/FAIL decisions.
"""

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from app.core.config import settings
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    MandatoryFieldType,
)
from app.schemas.ocr import BoundingBox, OCRTextBlock, RawOCRResult

# All codified mandatory declaration field names under Legal Metrology Rules, 2011
MANDATORY_FIELDS: List[str] = [field.value for field in MandatoryFieldType]

# =====================================================================
# System & Extraction Prompts
# =====================================================================

SYSTEM_INSTRUCTION = """You are an expert packaging data extraction assistant for Legal Metrology compliance inspection.
Your role is to extract and standardize information from package labeling evidence.

CRITICAL INSTRUCTIONS:
1. EXTRACTION ONLY: Your job is ONLY to extract and structure observed declarations. You must NEVER evaluate compliance, make legal judgments, or output PASS, FAIL, or NEEDS_REVIEW verdicts.
2. NO FABRICATION: Never invent or hallucinate missing data. Do not mark a field as missing solely because OCR or your extraction process did not find it. Only return detected when supported by evidence, and uncertain when evidence is ambiguous.
3. GROUNDING: Ground your extractions in the provided OCR blocks by listing the supporting block indices whenever text originates from OCR evidence.
4. UNCERTAINTY: If text is partially obscured, truncated, smudged, or ambiguous, mark the field status as "uncertain".
5. OUTPUT FORMAT: Respond with valid JSON matching the exact requested schema only."""


def _build_extraction_prompt(
    ocr_result: RawOCRResult,
    product_category: Optional[str] = None,
) -> str:
    """Construct the structured extraction prompt with numbered OCR blocks."""
    category_context = (
        f"Product Category: {product_category}\n"
        if product_category
        else "Product Category: General Pre-packaged Commodity\n"
    )

    # Format numbered OCR blocks for reference
    formatted_blocks = []
    for idx, block in enumerate(ocr_result.blocks):
        clean_text = block.text.strip()
        if clean_text:
            formatted_blocks.append(f"[{idx}] \"{clean_text}\" (conf: {block.confidence:.2f})")

    blocks_section = (
        "\n".join(formatted_blocks)
        if formatted_blocks
        else "No OCR token blocks available."
    )

    prompt = f"""{category_context}
FULL OCR TEXT:
\"\"\"
{ocr_result.full_text if ocr_result.full_text else "[Empty OCR Text]"}
\"\"\"

NUMBERED OCR BLOCKS:
\"\"\"
{blocks_section}
\"\"\"

TASK:
Extract all Legal Metrology mandatory declarations for this product.

MANDATORY DECLARATION FIELDS TO EXTRACT:
1. manufacturer_name_and_address (Manufacturer / Packer / Importer name & address)
2. net_quantity (Weight, volume, or count with metric units e.g. "500 g", "1 L", "10 units")
3. mrp (Maximum Retail Price in INR inclusive of all taxes e.g. "150.00")
4. unit_sale_price (Unit sale price e.g. "₹0.30/g", "₹15.00/100ml" if declared)
5. manufacture_date (Date/month/year of manufacture/packing/import)
6. expiry_date (Best before / use by date if declared)
7. batch_number (Batch / lot / code number)
8. consumer_care (Customer care contact: email, phone, address, or designation)
9. country_of_origin (Country where manufactured/produced e.g. "India")
10. generic_name (Common or generic name of commodity e.g. "Wheat Flour", "Soap")

STATUS DEFINITIONS:
- "detected": Clearly and legibly identified from the available evidence.
- "uncertain": Ambiguous, partially obscured, smudged, truncated, or incomplete.
Note: Do not mark a field as missing solely because OCR or your extraction process did not find it. Only return detected when supported by evidence, and uncertain when evidence is ambiguous. Do not output declarations for fields where no evidence is observed.

NORMALIZATION GUIDELINES:
- mrp: Extract numeric string e.g. "150.00" from "MRP Rs. 150/- (incl. of all taxes)"
- net_quantity: Standardize metric units e.g. "500 gm" -> "500 g", "1000 ml" -> "1 L"
- country_of_origin: Standardized country name e.g. "Made in India" -> "India"
- If normalization is not straightforward or ambiguous, keep normalized_value same as raw_value or null.

JSON RESPONSE FORMAT:
{{
  "declarations": [
    {{
      "field_name": "<field_name>",
      "status": "detected" | "uncertain",
      "raw_value": "<exact string from label>",
      "normalized_value": "<standardized value>",
      "supporting_block_indices": [0, 1],
      "confidence": 0.95
  ]
}}"""
    return prompt


# =====================================================================
# Evidence Grounding & Bounding Box Utilities
# =====================================================================


def _compute_bounding_box_union(
    indices: Sequence[int],
    ocr_blocks: List[OCRTextBlock],
) -> Tuple[Optional[BoundingBox], Optional[float]]:
    """Compute the union bounding box and average confidence from referenced OCR blocks.

    Args:
        indices: List of integer indices referencing ocr_blocks.
        ocr_blocks: Full list of OCRTextBlock objects from RawOCRResult.

    Returns:
        Tuple of (union_bounding_box, average_confidence).
    """
    valid_boxes: List[BoundingBox] = []
    confidences: List[float] = []

    for idx in indices:
        if isinstance(idx, int) and 0 <= idx < len(ocr_blocks):
            block = ocr_blocks[idx]
            confidences.append(block.confidence)
            if block.bounding_box is not None:
                valid_boxes.append(block.bounding_box)

    if not valid_boxes:
        avg_conf = (
            round(float(np.mean(confidences)), 4) if confidences else None
        )
        return None, avg_conf

    min_x = min(box.x for box in valid_boxes)
    min_y = min(box.y for box in valid_boxes)
    max_x = max(box.x + box.width for box in valid_boxes)
    max_y = max(box.y + box.height for box in valid_boxes)

    union_width = max_x - min_x
    union_height = max_y - min_y

    union_box = BoundingBox(
        x=round(float(min_x), 2),
        y=round(float(min_y), 2),
        width=round(float(union_width), 2),
        height=round(float(union_height), 2),
    )

    avg_conf = round(float(np.mean(confidences)), 4) if confidences else None
    return union_box, avg_conf


def _convert_numpy_to_pil(image: np.ndarray) -> Optional[Any]:
    """Convert a NumPy image array (BGR or Grayscale) to RGB PIL Image for Gemini Vision."""
    if Image is None or image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return None

    try:
        if image.ndim == 2:
            return Image.fromarray(image, mode="L").convert("RGB")
        elif image.ndim == 3:
            # Assume BGR from OpenCV and convert to RGB
            rgb_arr = image[..., ::-1] if image.shape[2] == 3 else image
            return Image.fromarray(rgb_arr, mode="RGB")
        return None
    except Exception:
        return None


def _clean_json_response(raw_response_text: str) -> str:
    """Strip markdown formatting (e.g. ```json ... ```) from model response."""
    text = raw_response_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


# =====================================================================
# Public Service API
# =====================================================================


def extract_declarations(
    ocr_result: RawOCRResult,
    image: Optional[np.ndarray] = None,
    product_category: Optional[str] = None,
) -> List[ExtractedDeclaration]:
    """Extract structured Legal Metrology declarations using Google Gemini.

    Grounds all extracted fields back to OCR evidence coordinates and confidence scores.

    Args:
        ocr_result: Raw OCR result containing full text and token bounding boxes.
        image: Optional NumPy image array for multimodal vision disambiguation.
        product_category: Optional product category context (e.g. 'food', 'cosmetics').

    Returns:
        List of ExtractedDeclaration objects covering all mandatory declaration fields.

    Raises:
        ValueError: If ocr_result is invalid.
        RuntimeError: If Gemini SDK is unavailable, API key is unconfigured, or API call fails.
    """
    if ocr_result is None or not isinstance(ocr_result, RawOCRResult):
        raise ValueError("ocr_result must be a valid RawOCRResult instance.")

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in application settings. "
            "Please set GEMINI_API_KEY in your environment or .env file."
        )

    if genai is None:
        raise RuntimeError(
            "google-generativeai package is not available in the current environment."
        )

    # Configure Gemini client
    genai.configure(api_key=settings.gemini_api_key)

    # Prepare Multimodal Content
    prompt_text = _build_extraction_prompt(
        ocr_result=ocr_result,
        product_category=product_category,
    )

    contents: List[Any] = []
    if image is not None:
        pil_image = _convert_numpy_to_pil(image)
        if pil_image is not None:
            contents.append(pil_image)

    contents.append(prompt_text)

    # Invoke Gemini Model
    model_name = settings.gemini_model or "gemini-1.5-flash"
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_INSTRUCTION,
        )

        response = model.generate_content(
            contents,
            generation_config={"response_mime_type": "application/json", "temperature": 0.0},
        )
    except Exception as exc:
        raise RuntimeError(f"Gemini API generation failed: {exc}") from exc

    if not response or not hasattr(response, "text") or not response.text:
        raise RuntimeError("Gemini returned an empty or invalid response.")

    # Parse JSON
    cleaned_json = _clean_json_response(response.text)
    try:
        parsed_data = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse Gemini output as valid JSON: {exc}. Response was: {cleaned_json[:200]}"
        ) from exc

    raw_declarations = parsed_data.get("declarations", [])
    if not isinstance(raw_declarations, list):
        raise RuntimeError("Gemini response missing 'declarations' list.")

    # Map raw extractions by field name
    extractions_by_field: Dict[str, Dict[str, Any]] = {}
    for item in raw_declarations:
        if isinstance(item, dict) and "field_name" in item:
            extractions_by_field[item["field_name"]] = item

    results: List[ExtractedDeclaration] = []

    # Process only observed/extracted fields without fabricating missing records
    for field_name in MANDATORY_FIELDS:
        if field_name not in extractions_by_field:
            continue

        field_data = extractions_by_field[field_name]
        if not isinstance(field_data, dict):
            continue

        raw_status = field_data.get("status", "detected")
        try:
            status = DeclarationStatus(raw_status)
        except ValueError:
            status = DeclarationStatus.uncertain

        # If a field was labeled as missing by the model, do not fabricate a declaration record
        if status == DeclarationStatus.missing:
            continue

        raw_val = field_data.get("raw_value")
        raw_val_str = str(raw_val).strip() if raw_val is not None else None
        if raw_val_str == "":
            raw_val_str = None

        norm_val = field_data.get("normalized_value")
        norm_val_str = str(norm_val).strip() if norm_val is not None else None
        if norm_val_str == "":
            norm_val_str = None

        # Evidence Grounding via referenced OCR block indices
        block_indices = field_data.get("supporting_block_indices", [])
        union_bbox, ocr_avg_conf = _compute_bounding_box_union(
            indices=block_indices,
            ocr_blocks=ocr_result.blocks,
        )

        # Determine confidence
        model_conf = field_data.get("confidence")
        try:
            model_conf_float = float(model_conf) if model_conf is not None else None
            if model_conf_float is not None:
                model_conf_float = max(0.0, min(1.0, model_conf_float))
        except (ValueError, TypeError):
            model_conf_float = None

        if ocr_avg_conf is not None:
            # Prioritize/blend OCR confidence
            final_conf = (
                round((ocr_avg_conf + model_conf_float) / 2.0, 4)
                if model_conf_float is not None
                else ocr_avg_conf
            )
        else:
            final_conf = model_conf_float if model_conf_float is not None else (
                0.85 if status == DeclarationStatus.detected else (0.5 if status == DeclarationStatus.uncertain else None)
            )

        # Determine source
        if union_bbox is not None or ocr_avg_conf is not None:
            source = DeclarationSource.hybrid if image is not None else DeclarationSource.tesseract
        elif status in (DeclarationStatus.detected, DeclarationStatus.uncertain):
            source = DeclarationSource.gemini
        else:
            source = None

        results.append(
            ExtractedDeclaration(
                field_name=field_name,
                status=status,
                raw_value=raw_val_str,
                normalized_value=norm_val_str,
                confidence=final_conf,
                bounding_box=union_bbox,
                source=source,
            )
        )

    return results
