"""
PackSure AI — QR Code & Electronic Product Declaration Compliance Service.

Implements Phase 4B: Deterministic QR Detection, Decoding, and Rule 6 / G.S.R. 456(E) Compliance Analysis.

Statutory Principles:
1. Under Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011 as amended by G.S.R. 456(E) (23 June 2023):
   - For specified Electronic Products, certain mandatory declarations (manufacturer/packer/importer name & address,
     country of origin, size/dimensions, date of manufacture/import) may be provided through a QR Code on the package.
   - The package MUST contain a clear consumer instruction to scan the QR code for the relevant information.
   - Physical Mandatory Invariants CANNOT be offloaded to QR:
     (i) Generic Name (Rule 6(1)(b))
     (ii) Net Quantity (Rule 6(1)(c))
     (iii) Maximum Retail Price (MRP) inclusive of all taxes (Rule 6(1)(e))
     (iv) Consumer Care contact details (Rule 6(1)(n))
2. For Non-Electronic Products (e.g. food, cosmetics, pharmaceuticals), QR offloading is NOT legally permitted.
3. Pure local deterministic OpenCV QR detection — zero external network requests to destination URLs.
4. AI/OCR extracts visual tokens; deterministic rules engine resolves legal standing; uncertainty yields NEEDS_REVIEW.
"""

import logging
import re
from typing import List, Optional, Sequence, Tuple, Union
import cv2
import numpy as np

from app.schemas.compliance import (
    ElectronicApplicability,
    QREvidence,
    QREvidenceStatus,
)
from app.schemas.declaration import BoundingBox, ExtractedDeclaration

logger = logging.getLogger(__name__)

ELECTRONIC_KEYWORDS = (
    "electronic", "electrical", "mobile", "phone", "smartphone", "laptop",
    "computer", "audio", "headphone", "earphone", "earbud", "smartwatch",
    "watch", "charger", "cable", "router", "tv", "television", "appliance",
    "gadget", "tablet", "speaker", "camera", "power bank", "adapter", "led",
    "display", "monitor", "keyboard", "mouse", "printer", "wearable",
)

NON_ELECTRONIC_KEYWORDS = (
    "food", "grocery", "edible", "grain", "oil", "spice", "snack", "flour",
    "atta", "rice", "wheat", "salt", "sugar", "tea", "coffee", "biscuit",
    "cookie", "cosmetic", "soap", "shampoo", "cream", "lotion", "pharma",
    "medicine", "drug", "syrup", "apparel", "clothing", "shirt", "pant",
    "textile", "fabric", "beverage", "juice", "dairy", "milk", "curd",
    "paneer", "water", "detergent", "cleaner", "clean", "personal care",
)

SCAN_INSTRUCTION_PATTERNS = [
    re.compile(r"scan\s+(?:the\s+)?qr(?:\s+code)?", re.IGNORECASE),
    re.compile(r"(?:see|check|refer|refer\s+to)\s+(?:the\s+)?qr(?:\s+code)?", re.IGNORECASE),
    re.compile(r"scan\s+(?:for\s+)?(?:info|information|details|more|mfg)", re.IGNORECASE),
    re.compile(r"for\s+(?:mfg|manufacturer|importer|packer|more|product|warranty)\s+details\s+scan", re.IGNORECASE),
    re.compile(r"qr\s+code\s+for\s+(?:details|information|mfg|more)", re.IGNORECASE),
    re.compile(r"scan\s+here\s+for", re.IGNORECASE),
    re.compile(r"scan\s+me", re.IGNORECASE),
    re.compile(r"scan\s+to\s+(?:verify|view|read|know|explore)", re.IGNORECASE),
]


OFFLOADABLE_RULE_CODES = {
    "Rule-6(1)(a)",   # Name and address of manufacturer/packer/importer
    "Rule-6(1)(aa)",  # Country of origin
    "Rule-6(1)(d)",   # Month and year of manufacture or pre-packing or import
}

OFFLOADABLE_FIELD_NAMES = {
    "manufacturer_name_and_address",
    "country_of_origin",
    "manufacture_date",
    "dimensions",
    "size",
}


def detect_qr_in_image_bytes(
    image_bytes: Optional[bytes],
    view_index: int = 0,
) -> Tuple[bool, Optional[str], Optional[BoundingBox], float]:
    """Detect and decode QR code from raw image bytes.

    Args:
        image_bytes: Raw JPEG/PNG byte buffer.
        view_index: Index of the package view.

    Returns:
        Tuple of (detected: bool, decoded_text: Optional[str], bbox: Optional[BoundingBox], confidence: float).
    """
    if not image_bytes:
        return False, None, None, 0.0
    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return detect_qr_from_image(img, view_index=view_index)
    except Exception as exc:
        logger.warning(f"Failed to decode image bytes for QR detection in view {view_index}: {exc}")
        return False, None, None, 0.0


def detect_qr_from_image(
    image: Optional[np.ndarray],
    view_index: int = 0,
) -> Tuple[bool, Optional[str], Optional[BoundingBox], float]:
    """Detect and attempt to decode a QR code from a single BGR/grayscale image array.

    Args:
        image: NumPy image array.
        view_index: Index of the package view.

    Returns:
        Tuple of (detected: bool, decoded_text: Optional[str], bbox: Optional[BoundingBox], confidence: float).
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return False, None, None, 0.0

    try:
        detector = cv2.QRCodeDetector()
        decoded_info, points, _ = detector.detectAndDecode(image)

        if points is not None and len(points) > 0:
            pts = points.reshape(-1, 2)
            img_h, img_w = image.shape[:2]
            min_x = max(0.0, float(np.min(pts[:, 0])))
            min_y = max(0.0, float(np.min(pts[:, 1])))
            max_x = min(float(img_w), float(np.max(pts[:, 0])))
            max_y = min(float(img_h), float(np.max(pts[:, 1])))

            bbox = BoundingBox(
                x=round(min_x, 2),
                y=round(min_y, 2),
                width=round(max(1.0, max_x - min_x), 2),
                height=round(max(1.0, max_y - min_y), 2),
            )

            if decoded_info and len(decoded_info.strip()) > 0:
                return True, decoded_info.strip(), bbox, 0.95
            else:
                # QR candidate pattern detected, but content unreadable (e.g. low resolution/blur)
                return True, None, bbox, 0.60
    except Exception as exc:
        logger.warning(f"QR detection encountered non-fatal OpenCV exception for view {view_index}: {exc}")

    return False, None, None, 0.0


def detect_consumer_scan_instruction(
    ocr_texts: Optional[Union[Sequence[str], str]] = None,
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    raw_ocr_text: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Determine whether the package contains a consumer instruction to scan the QR code.

    Args:
        ocr_texts: Sequence of raw OCR strings extracted from package views, or single string.
        declarations: List of structured declarations extracted from packaging.
        raw_ocr_text: Optional single combined raw OCR text.

    Returns:
        Tuple of (instruction_detected: bool, matched_text_snippet: Optional[str]).
    """
    candidates: List[str] = []
    if raw_ocr_text:
        candidates.append(raw_ocr_text)
    if ocr_texts:
        if isinstance(ocr_texts, str):
            candidates.append(ocr_texts)
        else:
            candidates.extend([t for t in ocr_texts if t])
    if declarations:
        for d in declarations:
            if d.raw_value:
                candidates.append(d.raw_value)
            if d.normalized_value:
                candidates.append(d.normalized_value)

    combined_text = "\n".join(candidates)
    for pattern in SCAN_INSTRUCTION_PATTERNS:
        match = pattern.search(combined_text)
        if match:
            matched_str = match.group(0)
            return True, matched_str

    return False, None


def determine_electronic_applicability(
    product_category: Optional[str] = None,
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    generic_name: Optional[str] = None,
) -> Tuple[ElectronicApplicability, str]:
    """Determine statutory electronic product applicability under Rule 6 / G.S.R. 456(E).

    Args:
        product_category: Optional product category string.
        declarations: Optional list of extracted declarations.
        generic_name: Optional commodity name string.

    Returns:
        Tuple of (ElectronicApplicability, explanation_reason: str).
    """
    if product_category:
        cat_lower = product_category.lower()
        if any(k in cat_lower for k in ELECTRONIC_KEYWORDS):
            return ElectronicApplicability.APPLICABLE, f"Product category '{product_category}' matches electronic commodity keywords."
        if any(k in cat_lower for k in NON_ELECTRONIC_KEYWORDS):
            return ElectronicApplicability.NOT_APPLICABLE, f"Product category '{product_category}' is non-electronic."

    if generic_name:
        name_lower = generic_name.lower()
        if any(k in name_lower for k in ELECTRONIC_KEYWORDS):
            return ElectronicApplicability.APPLICABLE, f"Generic commodity name '{generic_name}' matches electronic keywords."
        if any(k in name_lower for k in NON_ELECTRONIC_KEYWORDS):
            return ElectronicApplicability.NOT_APPLICABLE, f"Generic commodity name '{generic_name}' is non-electronic."

    # Inspect generic commodity name declarations
    if declarations:
        for d in declarations:
            if d.field_name in ("generic_name", "product_name") and (d.raw_value or d.normalized_value):
                name_lower = (d.normalized_value or d.raw_value or "").lower()
                if any(k in name_lower for k in ELECTRONIC_KEYWORDS):
                    return ElectronicApplicability.APPLICABLE, f"Generic name declaration '{d.normalized_value or d.raw_value}' matches electronic keywords."
                if any(k in name_lower for k in NON_ELECTRONIC_KEYWORDS):
                    return ElectronicApplicability.NOT_APPLICABLE, f"Generic name declaration '{d.normalized_value or d.raw_value}' is non-electronic."

    # Default to UNCERTAIN if category cannot be verified
    return ElectronicApplicability.UNCERTAIN, "Product category or generic commodity type could not be deterministically resolved."


def evaluate_qr_evidence_across_views(
    images: Optional[Sequence[Optional[Union[np.ndarray, bytes]]]] = None,
    ocr_texts: Optional[Sequence[str]] = None,
    product_category: Optional[str] = None,
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    image_bytes_list: Optional[Sequence[bytes]] = None,
    raw_ocr_text: Optional[str] = None,
    generic_name: Optional[str] = None,
) -> QREvidence:
    """Consolidate QR detection, payload validation, and statutory applicability across all views.

    Args:
        images: Sequence of NumPy image arrays or raw image bytes.
        ocr_texts: Sequence of OCR strings.
        product_category: Commodity category hint.
        declarations: Evaluated declarations.
        image_bytes_list: Optional list of raw image bytes (alias for images).
        raw_ocr_text: Optional single combined raw OCR text.
        generic_name: Optional generic commodity name.

    Returns:
        Structured QREvidence instance.
    """
    best_detected = False
    best_payload: Optional[str] = None
    best_bbox: Optional[BoundingBox] = None
    best_conf = 0.0
    best_view_idx: Optional[int] = None
    best_status = QREvidenceStatus.missing

    img_inputs = image_bytes_list if image_bytes_list is not None else (images or [])

    for idx, img in enumerate(img_inputs):
        if img is None:
            continue
        if isinstance(img, bytes):
            det, payload, bbox, conf = detect_qr_in_image_bytes(img, view_index=idx)
        elif isinstance(img, np.ndarray):
            det, payload, bbox, conf = detect_qr_from_image(img, view_index=idx)
        else:
            continue

        if det:
            best_detected = True
            if payload:
                best_payload = payload
                best_bbox = bbox
                best_conf = conf
                best_view_idx = idx
                best_status = QREvidenceStatus.detected
                break  # Found high-confidence decoded QR
            elif best_payload is None:
                # Preserve undecodable candidate
                best_bbox = bbox
                best_conf = conf
                best_view_idx = idx
                best_status = QREvidenceStatus.uncertain

    # Validate payload format (e.g. URL or structured content)
    payload_valid: Optional[bool] = None
    if best_payload:
        clean_payload = best_payload.strip().lower()
        payload_valid = clean_payload.startswith("http://") or clean_payload.startswith("https://") or ("." in clean_payload and "/" in clean_payload)

    # Detect consumer scan instruction on packaging
    instruction_detected, instruction_text = detect_consumer_scan_instruction(
        ocr_texts=ocr_texts,
        declarations=declarations,
        raw_ocr_text=raw_ocr_text,
    )

    # Determine electronic applicability
    applicability, _ = determine_electronic_applicability(
        product_category=product_category,
        declarations=declarations,
        generic_name=generic_name,
    )

    # Formulate statutory interpretation note
    if applicability == ElectronicApplicability.APPLICABLE:
        if best_detected and best_payload and instruction_detected:
            statutory_note = (
                "Applicable electronic product with detected QR code and on-package scan instruction under Rule 6 / G.S.R. 456(E). "
                "External destination link stored as unverified audit evidence; physical inspector verification of online declarations required."
            )
        elif best_detected and best_payload and not instruction_detected:
            statutory_note = (
                "QR code detected on electronic product, but mandatory on-package consumer scan instruction was not detected. "
                "G.S.R. 456(E) requires an explicit scan instruction on the physical package for offloaded declarations."
            )
        elif best_detected and not best_payload:
            statutory_note = (
                "QR code pattern detected on electronic product but unreadable due to blur or resolution. "
                "Physical inspector verification recommended."
            )
        else:
            statutory_note = (
                "No QR code detected on electronic product. All statutory declarations must appear directly on the physical label (QR is not legally mandatory)."
            )
    elif applicability == ElectronicApplicability.NOT_APPLICABLE:
        if best_detected:
            statutory_note = (
                "QR code detected on non-electronic commodity. Under Legal Metrology Rules, QR offloading of mandatory declarations "
                "applies exclusively to electronic products under G.S.R. 456(E). All mandatory declarations must appear directly on package label."
            )
        else:
            statutory_note = "Non-electronic commodity. All mandatory declarations must appear directly on package label."
    else:
        statutory_note = (
            "Product category is uncertain; electronic product QR declaration applicability under Rule 6 cannot be "
            "deterministically established without category confirmation."
        )

    return QREvidence(
        detected=best_detected,
        status=best_status,
        confidence=best_conf,
        bounding_box=best_bbox,
        decoded_payload=best_payload,
        payload_valid=payload_valid,
        source_image_index=best_view_idx,
        instruction_detected=instruction_detected,
        instruction_text=instruction_text,
        applicable_product=applicability,
        statutory_note=statutory_note,
    )
