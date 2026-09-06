"""
PackSure AI — Compliance Orchestration Service.

Implements Phase 6B end-to-end inspection pipeline:
1. Image validation & quality assessment (Phase 2).
2. Specialized OpenCV preprocessing (Phase 2).
3. Raw OCR extraction & token bounding boxes (Phase 3).
4. Structured Legal Metrology declaration extraction via Gemini (Phase 4).
5. Deterministic compliance rule evaluation via RuleEngine (Phase 5).
6. Color-coded visual evidence generation via EvidenceService (Phase 6A).

Core Architectural Invariants:
- AI extracts evidence; the deterministic RuleEngine alone decides legal compliance.
- Orchestrator only coordinates — zero duplicate validation or rule logic.
- An upstream failure (image rejection, OCR error, AI failure) NEVER results in a false PASS.
- Incomplete scans (is_complete_scan=False) do NOT treat unobserved declarations as physical violations.
- Coordinate safety: original image coordinates are strictly preserved; original image is immutable.
  If deskew rotation was applied during preprocessing without inverse affine metadata,
  visual bounding box overlays are suppressed on the original image to prevent coordinate drift.
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Tuple
import numpy as np

from app.rules.rule_engine import rule_engine
from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
)
from app.schemas.image import ImageQualityReport, QualityStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.ai_service import extract_declarations
from app.services.evidence_service import render_evidence_overlay
from app.services.image_service import (
    DESKEW_MAX_ANGLE_LIMIT,
    DESKEW_MIN_ANGLE_TRIGGER,
    _detect_skew_angle,
    _to_grayscale,
    check_image_quality,
    preprocess_for_pipeline,
    validate_image_file,
)
from app.services.ocr_service import extract_raw_ocr

logger = logging.getLogger(__name__)


def process_compliance_inspection(
    image: np.ndarray,
    product_category: Optional[str] = None,
    is_imported: Optional[bool] = None,
    is_perishable: Optional[bool] = None,
    is_complete_scan: bool = False,
    output_evidence_path: Optional[str] = None,
) -> ComplianceResult:
    """Execute the end-to-end Legal Metrology compliance inspection pipeline on an image array.

    Args:
        image: Original BGR NumPy array.
        product_category: Optional product category hint (e.g., 'Food Grains', 'Cosmetics').
        is_imported: Optional flag for import status. If None, auto-inferred by rule engine.
        is_perishable: Optional flag for perishability. If None, auto-inferred by rule engine.
        is_complete_scan: Flag indicating whether all package panels were captured.
                          MUST default to False to prevent false missing-declaration violations.
        output_evidence_path: Optional file path to save the annotated evidence image.

    Returns:
        ComplianceResult containing verdict, compliance score, declarations, violations, and evidence.

    Raises:
        ValueError: If image input is invalid or has wrong dimensions.
    """
    # 1. Image Validation
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Image input must be a non-empty NumPy array.")

    if image.ndim not in (2, 3):
        raise ValueError(f"Image array must be 2D or 3D, got {image.ndim}D array with shape {image.shape}.")

    # 2. Image Quality Assessment
    quality_report = check_image_quality(image)
    if quality_report.status == QualityStatus.rejected or not quality_report.is_valid:
        recapture_info = quality_report.recapture_reason or "Image quality rejected due to blur, lighting, or resolution."
        logger.warning(f"Inspection halted: {recapture_info}")
        return ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=[],
            violations=[
                Violation(
                    rule_code="QUALITY-REJECT",
                    violation_type=ViolationType.illegible,
                    severity=ViolationSeverity.major,
                    description=f"Image quality insufficient for automated legal inspection: {recapture_info}",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=0,
                total_violations_found=1,
            ),
        )

    # 3. OpenCV Preprocessing & Coordinate Safety Tracking
    enhanced_vision, ocr_binarized = preprocess_for_pipeline(image)

    # Detect if deskew transformation was activated during preprocessing
    gray_img = _to_grayscale(image).astype(np.uint8)
    skew_angle = _detect_skew_angle(gray_img)
    is_deskewed = bool(DESKEW_MIN_ANGLE_TRIGGER < abs(skew_angle) <= DESKEW_MAX_ANGLE_LIMIT)

    # 4. OCR Extraction
    try:
        ocr_result = extract_raw_ocr(ocr_binarized)
    except Exception as ocr_err:
        logger.error(f"OCR extraction failed: {ocr_err}")
        return ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=[],
            violations=[
                Violation(
                    rule_code="OCR-FAILURE",
                    violation_type=ViolationType.illegible,
                    severity=ViolationSeverity.major,
                    description=f"Optical character recognition failed: {ocr_err}",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=0,
                total_violations_found=1,
            ),
        )

    # 5. Gemini Structured Declaration Extraction
    try:
        declarations = extract_declarations(
            ocr_result=ocr_result,
            image=enhanced_vision,
            product_category=product_category,
        )
    except Exception as ai_err:
        logger.error(f"AI declaration extraction failed: {ai_err}")
        return ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=[],
            violations=[
                Violation(
                    rule_code="AI-EXTRACTION-FAILURE",
                    violation_type=ViolationType.other,
                    severity=ViolationSeverity.major,
                    description=f"AI structured declaration extraction failed: {ai_err}",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=0,
                total_violations_found=1,
            ),
        )

    # 6. Deterministic Legal Metrology Rule Evaluation
    try:
        compliance_result = rule_engine.evaluate_compliance(
            declarations=declarations,
            product_category=product_category,
            is_imported=is_imported,
            is_perishable=is_perishable,
            is_complete_scan=is_complete_scan,
        )
    except Exception as rule_err:
        logger.error(f"Rule engine execution failed: {rule_err}")
        return ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=declarations,
            violations=[
                Violation(
                    rule_code="RULE-ENGINE-FAILURE",
                    violation_type=ViolationType.other,
                    severity=ViolationSeverity.critical,
                    description=f"Legal Metrology rule engine execution failed: {rule_err}",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=len(declarations),
                total_violations_found=1,
            ),
        )

    # 7. Visual Evidence Rendering & Coordinate Safety Verification
    # Evidence rendering strictly operates on the original unscaled, unrotated BGR image.
    # If deskew was applied during OCR preprocessing, those bounding box coordinates reside
    # in the rotated coordinate frame and cannot be safely projected onto the original image
    # without an inverse affine matrix. To prevent coordinate drift, suppress bounding boxes.
    try:
        if is_deskewed:
            logger.info(
                f"Deskew rotation ({skew_angle:.2f}°) detected without inverse affine mapping. "
                "Suppressing visual bounding box overlays on original image to prevent coordinate drift."
            )
            # Create a safe copy of declarations with bounding_box=None for rendering
            safe_declarations_for_rendering = [
                decl.model_copy(update={"bounding_box": None}) for decl in compliance_result.declarations
            ]
            safe_compliance_result = compliance_result.model_copy(
                update={"declarations": safe_declarations_for_rendering}
            )
            _, updated_evidence = render_evidence_overlay(
                image=image,
                compliance_result=safe_compliance_result,
                output_path=output_evidence_path,
            )
        else:
            _, updated_evidence = render_evidence_overlay(
                image=image,
                compliance_result=compliance_result,
                output_path=output_evidence_path,
            )
        compliance_result.evidence = updated_evidence
    except Exception as rend_err:
        logger.warning(f"Visual evidence rendering encountered a non-fatal error: {rend_err}")
        # Preserves rule compliance result and verdict unchanged

    return compliance_result


def process_compliance_from_bytes(
    file_bytes: bytes,
    filename: str = "",
    product_category: Optional[str] = None,
    is_imported: Optional[bool] = None,
    is_perishable: Optional[bool] = None,
    is_complete_scan: bool = False,
    output_evidence_path: Optional[str] = None,
) -> Tuple[Optional[ImageQualityReport], ComplianceResult, Optional[np.ndarray]]:
    """Decode raw uploaded image file bytes and execute the compliance inspection pipeline.

    Args:
        file_bytes: Raw binary bytes of uploaded image.
        filename: Optional filename for logging/diagnostics.
        product_category: Optional product category hint.
        is_imported: Optional import flag.
        is_perishable: Optional perishability flag.
        is_complete_scan: Multi-panel complete scan flag (defaults to False).
        output_evidence_path: Optional file path to save annotated evidence image.

    Returns:
        Tuple of (ImageQualityReport, ComplianceResult, decoded_bgr_image)
    """
    is_valid, err_msg, decoded_image = validate_image_file(file_bytes, filename=filename)
    if not is_valid or decoded_image is None:
        error_description = err_msg or "Failed to validate or decode image bytes."
        return (
            None,
            ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=0.0,
                declarations=[],
                violations=[
                    Violation(
                        rule_code="IMAGE-INVALID",
                        violation_type=ViolationType.other,
                        severity=ViolationSeverity.major,
                        description=error_description,
                    )
                ],
                evidence=EvidenceMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_version=rule_engine.rules_version,
                    total_declarations_checked=0,
                    total_violations_found=1,
                ),
            ),
            None,
        )

    quality_report = check_image_quality(decoded_image)
    compliance_result = process_compliance_inspection(
        image=decoded_image,
        product_category=product_category,
        is_imported=is_imported,
        is_perishable=is_perishable,
        is_complete_scan=is_complete_scan,
        output_evidence_path=output_evidence_path,
    )

    return quality_report, compliance_result, decoded_image
