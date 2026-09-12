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

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import shutil
from typing import List, Optional, Sequence, Tuple
import numpy as np

from app.rules.rule_engine import rule_engine
from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
)
from app.schemas.declaration import ExtractedDeclaration
from app.schemas.image import ImageQualityReport, QualityStatus
from app.schemas.violation import Violation, ViolationSeverity, ViolationType
from app.services.ai_service import extract_declarations
from app.services.evidence_service import render_evidence_overlay
from app.services.fusion_service import fuse_declarations
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


@dataclass
class PackageViewPayload:
    """Container for raw byte payload of a package view in multi-view inspection."""

    file_bytes: bytes
    filename: str = ""
    view_label: Optional[str] = None


def process_compliance_inspection(
    image: np.ndarray,
    product_category: Optional[str] = None,
    is_imported: Optional[bool] = None,
    is_perishable: Optional[bool] = None,
    is_complete_scan: bool = False,
    output_evidence_path: Optional[str] = None,
) -> ComplianceResult:
    """Execute the end-to-end Legal Metrology compliance inspection pipeline on a single image array.

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
    try:
        if is_deskewed:
            logger.info(
                f"Deskew rotation ({skew_angle:.2f}°) detected without inverse affine mapping. "
                "Suppressing visual bounding box overlays on original image to prevent coordinate drift."
            )
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

    return compliance_result


def process_multi_view_compliance_from_bytes(
    views: Sequence[PackageViewPayload],
    product_category: Optional[str] = None,
    is_imported: Optional[bool] = None,
    is_perishable: Optional[bool] = None,
    is_complete_scan: bool = False,
    output_dir: Optional[str] = None,
) -> Tuple[List[Optional[ImageQualityReport]], ComplianceResult, List[Optional[np.ndarray]], List[str]]:
    """Execute end-to-end multi-view Legal Metrology compliance pipeline with evidence fusion.

    Args:
        views: Sequence of PackageViewPayload objects representing all captured package views.
        product_category: Optional commodity category.
        is_imported: Optional import flag.
        is_perishable: Optional perishability flag.
        is_complete_scan: Flag indicating whether all packaging panels were captured.
        output_dir: Optional directory to persist raw & annotated evidence images.

    Returns:
        Tuple of (quality_reports_list, compliance_result, decoded_images_list, evidence_paths_list).
    """
    if not views:
        empty_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=[],
            violations=[
                Violation(
                    rule_code="IMAGE-INVALID",
                    violation_type=ViolationType.other,
                    severity=ViolationSeverity.major,
                    description="No package view image payloads provided for inspection.",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=0,
                total_violations_found=1,
            ),
        )
        return [], empty_res, [], []

    quality_reports: List[Optional[ImageQualityReport]] = []
    decoded_images: List[Optional[np.ndarray]] = []
    all_views_declarations: List[List[ExtractedDeclaration]] = []
    is_deskewed_flags: List[bool] = []

    # 1. Independent per-view processing
    for view_idx, view in enumerate(views):
        fname = view.filename or f"view_{view_idx}.jpg"
        is_valid, err_msg, decoded_img = validate_image_file(view.file_bytes, filename=fname)
        if not is_valid or decoded_img is None:
            err_desc = err_msg or f"Failed to validate or decode image bytes for view {view_idx} ({fname})."
            fail_res = ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=0.0,
                declarations=[],
                violations=[
                    Violation(
                        rule_code="IMAGE-INVALID",
                        violation_type=ViolationType.other,
                        severity=ViolationSeverity.major,
                        description=err_desc,
                    )
                ],
                evidence=EvidenceMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_version=rule_engine.rules_version,
                    total_declarations_checked=0,
                    total_violations_found=1,
                ),
            )
            return quality_reports, fail_res, decoded_images, []

        q_report = check_image_quality(decoded_img)
        quality_reports.append(q_report)
        decoded_images.append(decoded_img)

        if q_report.status == QualityStatus.rejected or not q_report.is_valid:
            recapture_info = q_report.recapture_reason or "Image quality rejected due to blur, lighting, or resolution."
            fail_res = ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=0.0,
                declarations=[],
                violations=[
                    Violation(
                        rule_code="QUALITY-REJECT",
                        violation_type=ViolationType.illegible,
                        severity=ViolationSeverity.major,
                        description=f"View {view_idx} ({fname}) quality insufficient for automated legal inspection: {recapture_info}",
                    )
                ],
                evidence=EvidenceMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_version=rule_engine.rules_version,
                    total_declarations_checked=0,
                    total_violations_found=1,
                ),
            )
            return quality_reports, fail_res, decoded_images, []

        # Preprocessing & Coordinate Tracking
        enhanced_vision, ocr_binarized = preprocess_for_pipeline(decoded_img)
        gray_img = _to_grayscale(decoded_img).astype(np.uint8)
        skew_angle = _detect_skew_angle(gray_img)
        is_deskewed = bool(DESKEW_MIN_ANGLE_TRIGGER < abs(skew_angle) <= DESKEW_MAX_ANGLE_LIMIT)
        is_deskewed_flags.append(is_deskewed)

        # OCR
        try:
            ocr_result = extract_raw_ocr(ocr_binarized)
        except Exception as ocr_err:
            logger.error(f"OCR extraction failed on view {view_idx}: {ocr_err}")
            fail_res = ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=0.0,
                declarations=[],
                violations=[
                    Violation(
                        rule_code="OCR-FAILURE",
                        violation_type=ViolationType.illegible,
                        severity=ViolationSeverity.major,
                        description=f"Optical character recognition failed on view {view_idx}: {ocr_err}",
                    )
                ],
                evidence=EvidenceMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_version=rule_engine.rules_version,
                    total_declarations_checked=0,
                    total_violations_found=1,
                ),
            )
            return quality_reports, fail_res, decoded_images, []

        # AI Extraction
        try:
            view_decls = extract_declarations(
                ocr_result=ocr_result,
                image=enhanced_vision,
                product_category=product_category,
            )
        except Exception as ai_err:
            logger.error(f"AI declaration extraction failed on view {view_idx}: {ai_err}")
            fail_res = ComplianceResult(
                verdict=ComplianceVerdict.NEEDS_REVIEW,
                compliance_score=0.0,
                declarations=[],
                violations=[
                    Violation(
                        rule_code="AI-EXTRACTION-FAILURE",
                        violation_type=ViolationType.other,
                        severity=ViolationSeverity.major,
                        description=f"AI structured declaration extraction failed on view {view_idx}: {ai_err}",
                    )
                ],
                evidence=EvidenceMetadata(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_version=rule_engine.rules_version,
                    total_declarations_checked=0,
                    total_violations_found=1,
                ),
            )
            return quality_reports, fail_res, decoded_images, []

        # Attach Provenance to view declarations
        tagged_view_decls = [
            decl.model_copy(update={"image_index": view_idx, "image_name": fname})
            for decl in view_decls
        ]
        all_views_declarations.append(tagged_view_decls)

    # 2. Evidence Fusion across all views
    fused_declarations, conflict_violations = fuse_declarations(all_views_declarations)

    # 3. Deterministic Legal Metrology Rule Evaluation on Fused Declarations
    try:
        compliance_result = rule_engine.evaluate_compliance(
            declarations=fused_declarations,
            product_category=product_category,
            is_imported=is_imported,
            is_perishable=is_perishable,
            is_complete_scan=is_complete_scan,
        )
    except Exception as rule_err:
        logger.error(f"Rule engine execution failed on fused declarations: {rule_err}")
        fail_res = ComplianceResult(
            verdict=ComplianceVerdict.NEEDS_REVIEW,
            compliance_score=0.0,
            declarations=fused_declarations,
            violations=[
                Violation(
                    rule_code="RULE-ENGINE-FAILURE",
                    violation_type=ViolationType.other,
                    severity=ViolationSeverity.critical,
                    description=f"Legal Metrology rule engine execution failed on fused evidence: {rule_err}",
                )
            ],
            evidence=EvidenceMetadata(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule_version=rule_engine.rules_version,
                total_declarations_checked=len(fused_declarations),
                total_violations_found=1,
            ),
        )
        return quality_reports, fail_res, decoded_images, []

    # If cross-view conflicts were detected during fusion, append them and fail safe to NEEDS_REVIEW
    if conflict_violations:
        compliance_result.violations.extend(conflict_violations)
        compliance_result.verdict = ComplianceVerdict.NEEDS_REVIEW
        compliance_result.compliance_score = min(compliance_result.compliance_score, 50.0)

    # 4. Evidence Rendering per View (Coordinate-safe, view-anchored)
    evidence_paths: List[str] = []
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    for view_idx, img in enumerate(decoded_images):
        if img is None:
            continue
        # Bounding boxes for this view only
        view_decls = [d for d in compliance_result.declarations if d.image_index == view_idx]

        if is_deskewed_flags[view_idx]:
            safe_view_decls = [d.model_copy(update={"bounding_box": None}) for d in view_decls]
        else:
            safe_view_decls = view_decls

        view_comp_res = compliance_result.model_copy(update={"declarations": safe_view_decls})
        ev_file_path = os.path.join(output_dir, f"evidence_{view_idx}.jpg") if output_dir else None

        try:
            _, updated_ev = render_evidence_overlay(
                image=img,
                compliance_result=view_comp_res,
                output_path=ev_file_path,
            )
            if ev_file_path:
                evidence_paths.append(ev_file_path)
                # Primary view alias
                if view_idx == 0:
                    primary_path = os.path.join(output_dir, "evidence.jpg")
                    try:
                        shutil.copyfile(ev_file_path, primary_path)
                    except Exception:
                        pass
        except Exception as rend_err:
            logger.warning(f"Visual evidence rendering encountered a non-fatal error for view {view_idx}: {rend_err}")

    # Set composite evidence metadata
    primary_annotated_path = evidence_paths[0] if evidence_paths else (os.path.join(output_dir, "evidence.jpg") if output_dir else None)
    compliance_result.evidence = EvidenceMetadata(
        annotated_image_path=primary_annotated_path,
        timestamp=datetime.now(timezone.utc).isoformat(),
        rule_version=rule_engine.rules_version,
        total_declarations_checked=len(compliance_result.declarations),
        total_violations_found=len(compliance_result.violations),
    )

    return quality_reports, compliance_result, decoded_images, evidence_paths


def process_compliance_from_bytes(
    file_bytes: bytes,
    filename: str = "",
    product_category: Optional[str] = None,
    is_imported: Optional[bool] = None,
    is_perishable: Optional[bool] = None,
    is_complete_scan: bool = False,
    output_evidence_path: Optional[str] = None,
) -> Tuple[Optional[ImageQualityReport], ComplianceResult, Optional[np.ndarray]]:
    """Decode raw uploaded single-image bytes and execute the compliance inspection pipeline.

    Backward-compatible single-view wrapper around process_multi_view_compliance_from_bytes.
    """
    out_dir = os.path.dirname(output_evidence_path) if output_evidence_path else None
    view = PackageViewPayload(file_bytes=file_bytes, filename=filename)

    q_reports, comp_res, decoded_imgs, ev_paths = process_multi_view_compliance_from_bytes(
        views=[view],
        product_category=product_category,
        is_imported=is_imported,
        is_perishable=is_perishable,
        is_complete_scan=is_complete_scan,
        output_dir=out_dir,
    )

    q_report = q_reports[0] if q_reports else None
    decoded_img = decoded_imgs[0] if decoded_imgs else None

    # If caller requested a specific output_evidence_path, ensure it exists
    if output_evidence_path and ev_paths and ev_paths[0] != output_evidence_path and os.path.exists(ev_paths[0]):
        try:
            shutil.copyfile(ev_paths[0], output_evidence_path)
        except Exception:
            pass

    return q_report, comp_res, decoded_img
