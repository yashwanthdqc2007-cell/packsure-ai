"""
PackSure AI — Scans Routing Layer.

Implements Phase 7 scan lifecycle endpoints adhering to docs/api.md:
1. POST /api/v1/scans: Validate upload, create pending record, dispatch background task, return 202.
2. GET /api/v1/scans/{id}: Fetch full scan report, declarations, violations, and evidence.
3. PATCH /api/v1/scans/{id}/review: Human inspector resolution for NEEDS_REVIEW scans.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from app.api.dependencies import get_db_repository
from app.core.config import settings
from app.database.connection import BaseScanRepository
from app.schemas.compliance import (
    ComplianceVerdict,
    QREvidence,
    ScopeCoverageManifest,
    generate_scope_coverage_manifest,
)
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
)
from app.schemas.guidance import InspectionGuidance
from app.schemas.inspection_state import InspectionState, NextBestAction
from app.schemas.quantity import QuantityMeasurement, QuantityMeasurementInput
from app.schemas.scan import (
    ScanInitResponse,
    ScanResponse,
    ScanReviewRequest,
    ScanStatus,
)
from app.services.compliance_service import (
    process_compliance_from_bytes,
    process_multi_view_compliance_from_bytes,
)
from app.services.image_service import validate_image_file
from app.services.inspection_service import derive_inspection_state_and_next_action
from app.services.quantity_service import evaluate_physical_quantity
from app.services.report_service import generate_json_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])

LOCAL_STORAGE_BASE = "storage/scans"


def process_scan_background(
    scan_id: str,
    image_bytes: Optional[bytes] = None,
    filename: str = "upload.jpg",
    product_category: Optional[str] = None,
    user_id: Optional[str] = None,
    repo: Optional[BaseScanRepository] = None,
    is_complete_scan: bool = False,
    views: Optional[list] = None,  # List of PackageViewPayload
) -> None:
    """Asynchronous background worker executing full compliance pipeline and persistence.

    Invariants:
    - Never produce status='complete' + verdict='PASS' if upstream services fail.
    - Idempotently cleans child records on retry.
    - Preserves diagnostic error records on fatal pipeline failure.
    """
    if views is None and image_bytes is not None:
        from app.services.compliance_service import PackageViewPayload
        views = [PackageViewPayload(file_bytes=image_bytes, filename=filename)]
    elif views is None:
        views = []

    logger.info(f"Starting background compliance scan: {scan_id} with {len(views)} view(s)")
    try:
        # 1. Update status to processing
        repo.update_scan(scan_id, {"status": "processing"})

        # 2. Isolate file storage path by scan UUID
        scan_dir = os.path.join(LOCAL_STORAGE_BASE, scan_id)
        os.makedirs(scan_dir, exist_ok=True)

        raw_image_paths = []
        for idx, view in enumerate(views):
            raw_path = os.path.join(scan_dir, f"raw_{idx}.jpg")
            with open(raw_path, "wb") as f:
                f.write(view.file_bytes)
            raw_image_paths.append(raw_path.replace("\\", "/"))

        # Primary alias
        if raw_image_paths and views:
            primary_raw_path = os.path.join(scan_dir, "original.jpg")
            with open(primary_raw_path, "wb") as f:
                f.write(views[0].file_bytes)

        # 3. Execute Compliance Pipeline (Unified Collection of Views)
        q_reports, compliance_result, decoded_imgs, evidence_paths = process_multi_view_compliance_from_bytes(
            views=views,
            product_category=product_category,
            is_complete_scan=is_complete_scan,
            output_dir=scan_dir,
        )

        # 4. Idempotently Purge Any Existing Child Records (Retry Safety)
        repo.delete_child_records(scan_id)

        # 5. Persist Declarations, Violations, AI Audit Trail, and Report
        repo.save_declarations(scan_id, compliance_result.declarations)
        repo.save_violations(scan_id, compliance_result.violations)
        repo.save_ai_analysis(
            scan_id=scan_id,
            model=settings.gemini_model,
            prompt_tokens=None,
            response_tokens=None,
            raw_response={"declarations_count": len(compliance_result.declarations), "views_count": len(views)},
        )

        primary_raw = raw_image_paths[0] if raw_image_paths else os.path.join(scan_dir, "original.jpg").replace("\\", "/")
        primary_evidence = evidence_paths[0].replace("\\", "/") if evidence_paths else None
        normalized_ev_paths = [p.replace("\\", "/") for p in evidence_paths]

        try:
            report_json_path = os.path.join(scan_dir, "report.json")
            report_path = generate_json_report(
                scan_id=scan_id,
                compliance_result=compliance_result,
                product_category=product_category,
                image_path=primary_raw,
                evidence_path=primary_evidence,
                output_path=report_json_path,
                image_urls=raw_image_paths if raw_image_paths else ([primary_raw] if primary_raw else []),
                evidence_image_urls=normalized_ev_paths if normalized_ev_paths else ([primary_evidence] if primary_evidence else []),
                is_complete_scan=is_complete_scan,
                guidance=compliance_result.guidance,
            )
            repo.save_report(scan_id, report_url=report_path, format_type="json")
        except Exception as report_err:
            logger.error(f"Failed to generate inspection report for {scan_id}: {report_err}", exc_info=True)

        # 6. Finalize Scan Record
        repo.update_scan(
            scan_id,
            {
                "status": "complete",
                "verdict": compliance_result.verdict.value,
                "compliance_score": compliance_result.compliance_score,
                "product_category": product_category,
                "image_url": primary_raw,
                "image_urls": raw_image_paths if raw_image_paths else ([primary_raw] if primary_raw else []),
                "processed_image_url": primary_raw,
                "evidence_image_url": primary_evidence,
                "evidence_image_urls": normalized_ev_paths if normalized_ev_paths else ([primary_evidence] if primary_evidence else []),
                "is_complete_scan": is_complete_scan,
                "guidance": compliance_result.guidance.model_dump() if compliance_result.guidance else None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(f"Completed scan {scan_id} with verdict {compliance_result.verdict.value}")

    except Exception as exc:
        logger.error(f"Fatal background scan error for {scan_id}: {exc}", exc_info=True)
        repo.update_scan(
            scan_id,
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.post(
    "",
    response_model=ScanInitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload package image(s) to initiate compliance inspection",
)
async def create_scan(
    background_tasks: BackgroundTasks,
    image: Optional[UploadFile] = File(default=None, description="Single package image file (backward compatibility)"),
    images: Optional[list[UploadFile]] = File(default=None, description="Multiple package view images (e.g., Front, Back, Side)"),
    is_complete_scan: bool = Form(default=False, description="Flag indicating complete package panel capture"),
    product_category: Optional[str] = Form(default=None, description="Optional product category"),
    user_id: Optional[str] = Form(default=None, description="Optional inspector UUID"),
    repo: BaseScanRepository = Depends(get_db_repository),
) -> ScanInitResponse:
    """Ingest image upload(s), validate format, create pending scan record, and schedule background pipeline."""
    from app.services.compliance_service import PackageViewPayload

    # 1. Normalize single vs multi file inputs
    uploaded_files: list[UploadFile] = []
    if images and isinstance(images, (list, tuple)):
        for item in images:
            if hasattr(item, "read"):
                uploaded_files.append(item)
    elif images and hasattr(images, "read"):
        uploaded_files.append(images)

    if image and hasattr(image, "read"):
        uploaded_files.append(image)
    elif image and isinstance(image, (list, tuple)):
        for item in image:
            if hasattr(item, "read"):
                uploaded_files.append(item)

    if not uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one package image must be provided.",
        )

    # 2. Read and Validate Every View Synchronously
    view_payloads: list[PackageViewPayload] = []
    for idx, file in enumerate(uploaded_files):
        try:
            content = await file.read()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read image payload for view {idx}: {exc}",
            )

        fname = file.filename or f"view_{idx}.jpg"
        is_valid, err_msg, _ = validate_image_file(content, filename=fname)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image validation failed for view {idx} ({fname}): {err_msg}",
            )
        view_payloads.append(PackageViewPayload(file_bytes=content, filename=fname))

    # 3. Create Pending Scan Record in Database
    scan_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        repo.create_scan(
            scan_id=scan_id,
            product_category=product_category,
            user_id=user_id,
            image_url=f"{LOCAL_STORAGE_BASE}/{scan_id}/original.jpg",
        )
    except Exception as exc:
        logger.error(f"Database error creating scan {scan_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize scan record in database.",
        )

    # 4. Enqueue Asynchronous Compliance Inspection Task
    background_tasks.add_task(
        process_scan_background,
        scan_id=scan_id,
        image_bytes=None,
        filename=view_payloads[0].filename,
        product_category=product_category,
        user_id=user_id,
        is_complete_scan=is_complete_scan,
        views=view_payloads,
        repo=repo,
    )

    return ScanInitResponse(
        scan_id=scan_id,
        status=ScanStatus.pending,
        created_at=now_iso,
    )


@router.get(
    "/{id}",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve full scan result and compliance details",
)
def get_scan(
    id: str,
    repo: BaseScanRepository = Depends(get_db_repository),
) -> ScanResponse:
    """Fetch complete inspection report for a scan by UUID."""
    scan = repo.get_scan(id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    declarations = repo.get_declarations(id)
    violations = repo.get_violations(id)

    raw_status = scan.get("status", "pending")
    try:
        scan_status_enum = ScanStatus(raw_status)
    except ValueError:
        scan_status_enum = ScanStatus.failed

    raw_verdict = scan.get("verdict")
    verdict_enum = ComplianceVerdict(raw_verdict) if raw_verdict else None

    raw_img_urls = scan.get("image_urls")
    raw_ev_urls = scan.get("evidence_image_urls")
    raw_guidance = scan.get("guidance")
    is_complete_scan_val = scan.get("is_complete_scan", False)

    # Recover multi-view and guidance metadata from report.json artifact if not present directly in DB row
    if not raw_guidance or not raw_img_urls or not raw_ev_urls:
        report_json_path = os.path.join(LOCAL_STORAGE_BASE, id, "report.json")
        if os.path.exists(report_json_path):
            try:
                with open(report_json_path, "r", encoding="utf-8") as rf:
                    report_data = json.load(rf)
                    if not raw_guidance and "guidance" in report_data:
                        raw_guidance = report_data.get("guidance")
                    artifacts = report_data.get("evidence_artifacts", {})
                    if not raw_img_urls and "image_urls" in artifacts:
                        raw_img_urls = artifacts.get("image_urls")
                    if not raw_ev_urls and "evidence_image_urls" in artifacts:
                        raw_ev_urls = artifacts.get("evidence_image_urls")
                    if not is_complete_scan_val and "is_complete_scan" in artifacts:
                        is_complete_scan_val = artifacts.get("is_complete_scan", False)
            except Exception as e:
                logger.debug(f"Could not load metadata from report artifact for {id}: {e}")

    guidance_obj = None
    if raw_guidance:
        if isinstance(raw_guidance, dict):
            try:
                guidance_obj = InspectionGuidance.model_validate(raw_guidance)
            except Exception:
                guidance_obj = None
        elif isinstance(raw_guidance, InspectionGuidance):
            guidance_obj = raw_guidance

    # Construct deterministic ScopeCoverageManifest, QREvidence, PackageComposition, InspectionState, NextBestAction, and QuantityMeasurement
    scope_manifest_obj = None
    qr_evidence_obj = None
    composition_obj = None
    inspection_state_obj = None
    next_best_action_obj = None
    quantity_measurement_obj = None
    report_json_path = os.path.join(LOCAL_STORAGE_BASE, id, "report.json")
    if os.path.exists(report_json_path):
        try:
            with open(report_json_path, "r", encoding="utf-8") as rf:
                report_data = json.load(rf)
                if "scope_coverage" in report_data:
                    scope_manifest_obj = ScopeCoverageManifest.model_validate(report_data["scope_coverage"])
                if "qr_evidence" in report_data and report_data["qr_evidence"]:
                    qr_evidence_obj = QREvidence.model_validate(report_data["qr_evidence"])
                if "composition" in report_data and report_data["composition"]:
                    composition_obj = PackageComposition.model_validate(report_data["composition"])
                if "inspection_state" in report_data and report_data["inspection_state"]:
                    inspection_state_obj = InspectionState.model_validate(report_data["inspection_state"])
                if "next_best_action" in report_data and report_data["next_best_action"]:
                    next_best_action_obj = NextBestAction.model_validate(report_data["next_best_action"])
                if "quantity_measurement" in report_data and report_data["quantity_measurement"]:
                    quantity_measurement_obj = QuantityMeasurement.model_validate(report_data["quantity_measurement"])
        except Exception as e:
            logger.debug(f"Could not load metadata from report artifact for {id}: {e}")

    if scope_manifest_obj is None:
        views_cnt = len(raw_img_urls) if raw_img_urls else (1 if scan.get("image_url") else 1)
        scope_manifest_obj = generate_scope_coverage_manifest(
            views_captured_count=views_cnt,
            is_complete_scan=is_complete_scan_val,
        )

    return ScanResponse(
        scan_id=scan["id"],
        status=scan_status_enum,
        verdict=verdict_enum,
        compliance_score=scan.get("compliance_score"),
        product_category=scan.get("product_category"),
        image_url=scan.get("image_url"),
        image_urls=raw_img_urls if raw_img_urls else ([scan.get("image_url")] if scan.get("image_url") else None),
        processed_image_url=scan.get("processed_image_url"),
        evidence_image_url=scan.get("evidence_image_url"),
        evidence_image_urls=raw_ev_urls if raw_ev_urls else ([scan.get("evidence_image_url")] if scan.get("evidence_image_url") else None),
        is_complete_scan=is_complete_scan_val,
        declarations=declarations,
        violations=violations,
        reviewer_notes=scan.get("reviewer_notes"),
        guidance=guidance_obj,
        scope_coverage=scope_manifest_obj,
        qr_evidence=qr_evidence_obj,
        composition=composition_obj,
        quantity_measurement=quantity_measurement_obj,
        inspection_state=inspection_state_obj,
        next_best_action=next_best_action_obj,
        created_at=scan.get("created_at", datetime.now(timezone.utc).isoformat()),
        completed_at=scan.get("completed_at"),
    )


@router.patch(
    "/{id}/review",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit human inspector review resolution for a scan",
)
def review_scan(
    id: str,
    review_req: ScanReviewRequest,
    repo: BaseScanRepository = Depends(get_db_repository),
) -> ScanResponse:
    """Resolve NEEDS_REVIEW scan verdict with manual human overrides and audit notes."""
    scan = repo.get_scan(id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    current_verdict = scan.get("verdict")
    current_status = scan.get("status")

    # Enforce review applicability: scan must be complete and in NEEDS_REVIEW state
    if current_status != "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review scan in '{current_status}' status. Scan must be complete.",
        )

    if current_verdict != ComplianceVerdict.NEEDS_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review finalized scan with verdict '{current_verdict}'. Only NEEDS_REVIEW scans can be reviewed.",
        )

    target_verdict = review_req.verdict
    if target_verdict not in (ComplianceVerdict.PASS, ComplianceVerdict.FAIL):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer verdict must be PASS or FAIL.",
        )

    # 1. Update Scan Verdict & Reviewer Notes
    repo.update_scan(
        id,
        {
            "verdict": target_verdict.value,
            "reviewer_notes": review_req.reviewer_notes,
        },
    )

    # 2. Apply Manual Corrected Declarations
    if review_req.corrected_declarations:
        existing_decls = repo.get_declarations(id)
        decl_map = {d.field_name: d for d in existing_decls}

        for corr in review_req.corrected_declarations:
            existing = decl_map.get(corr.field_name)
            updated_status = corr.status or (existing.status if existing else DeclarationStatus.detected)
            bbox = existing.bounding_box if existing else None

            decl_map[corr.field_name] = ExtractedDeclaration(
                field_name=corr.field_name,
                status=updated_status,
                raw_value=corr.raw_value or (existing.raw_value if existing else None),
                normalized_value=corr.normalized_value or (existing.normalized_value if existing else None),
                confidence=1.0,
                bounding_box=bbox,
                source=DeclarationSource.manual,
            )

        repo.delete_child_records(id)
        repo.save_declarations(id, list(decl_map.values()))

    # 3. Regenerate JSON inspection report to reflect review resolution
    try:
        scan_dir = os.path.join(LOCAL_STORAGE_BASE, id)
        report_json_path = os.path.join(scan_dir, "report.json")
        current_decls = repo.get_declarations(id)
        current_viols = repo.get_violations(id)

        # Load existing artifacts to preserve metadata
        existing_composition = None
        existing_qr = None
        existing_guidance = None
        existing_scope = None
        existing_meas = None
        if os.path.exists(report_json_path):
            try:
                with open(report_json_path, "r", encoding="utf-8") as rf:
                    rdata = json.load(rf)
                    if "composition" in rdata and rdata["composition"]:
                        existing_composition = PackageComposition.model_validate(rdata["composition"])
                    if "qr_evidence" in rdata and rdata["qr_evidence"]:
                        existing_qr = QREvidence.model_validate(rdata["qr_evidence"])
                    if "guidance" in rdata and rdata["guidance"]:
                        existing_guidance = InspectionGuidance.model_validate(rdata["guidance"])
                    if "scope_coverage" in rdata and rdata["scope_coverage"]:
                        existing_scope = ScopeCoverageManifest.model_validate(rdata["scope_coverage"])
                    if "quantity_measurement" in rdata and rdata["quantity_measurement"]:
                        existing_meas = QuantityMeasurement.model_validate(rdata["quantity_measurement"])
            except Exception:
                pass

        if review_req.quantity_measurement:
            existing_meas = evaluate_physical_quantity(
                measurement_input=review_req.quantity_measurement,
                declarations=current_decls,
                composition=existing_composition,
            )

        updated_state, updated_nba = derive_inspection_state_and_next_action(
            declarations=current_decls,
            violations=current_viols,
            guidance=existing_guidance,
            scope_coverage=existing_scope,
            qr_evidence=existing_qr,
            composition=existing_composition,
            views_captured_count=len(scan.get("image_urls") or [1]),
            is_complete_scan=scan.get("is_complete_scan", False),
            is_reviewed=True,
            reviewer_notes=review_req.reviewer_notes,
            quantity_measurement=existing_meas,
        )

        report_path = generate_json_report(
            scan_id=id,
            verdict=target_verdict,
            compliance_score=scan.get("compliance_score"),
            product_category=scan.get("product_category"),
            declarations=current_decls,
            violations=current_viols,
            image_path=scan.get("image_url"),
            evidence_path=scan.get("evidence_image_url"),
            output_path=report_json_path,
            created_at=scan.get("created_at"),
            completed_at=scan.get("completed_at"),
            status=scan.get("status", "complete"),
            reviewer_notes=review_req.reviewer_notes,
            guidance=existing_guidance,
            scope_coverage=existing_scope,
            qr_evidence=existing_qr,
            composition=existing_composition,
            inspection_state=updated_state,
            next_best_action=updated_nba,
            quantity_measurement=existing_meas,
        )
        repo.save_report(id, report_url=report_path, format_type="json")
    except Exception as report_err:
        logger.error(f"Failed to refresh inspection report after review for {id}: {report_err}", exc_info=True)

    # Return updated full scan payload
    return get_scan(id=id, repo=repo)


@router.post(
    "/{id}/quantity",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit physical net quantity measurement for individual package verification",
)
def record_physical_quantity(
    id: str,
    measurement_input: QuantityMeasurementInput,
    repo: BaseScanRepository = Depends(get_db_repository),
) -> ScanResponse:
    """Record physical scale/gauge measurement and evaluate First Schedule Table I MPE tolerance."""
    scan = repo.get_scan(id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    current_status = scan.get("status")
    if current_status != "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record physical measurement for scan in '{current_status}' status. Scan must be complete.",
        )

    # 1. Fetch current declarations & metadata
    current_decls = repo.get_declarations(id)
    current_viols = repo.get_violations(id)

    scan_dir = os.path.join(LOCAL_STORAGE_BASE, id)
    report_json_path = os.path.join(scan_dir, "report.json")
    composition_obj = None
    qr_evidence_obj = None
    guidance_obj = None
    scope_manifest_obj = None
    existing_evidence_conflicts: list[str] = []

    if os.path.exists(report_json_path):
        try:
            with open(report_json_path, "r", encoding="utf-8") as rf:
                report_data = json.load(rf)
                if "composition" in report_data and report_data["composition"]:
                    composition_obj = PackageComposition.model_validate(report_data["composition"])
                if "qr_evidence" in report_data and report_data["qr_evidence"]:
                    qr_evidence_obj = QREvidence.model_validate(report_data["qr_evidence"])
                if "guidance" in report_data and report_data["guidance"]:
                    guidance_obj = InspectionGuidance.model_validate(report_data["guidance"])
                if "scope_coverage" in report_data and report_data["scope_coverage"]:
                    scope_manifest_obj = ScopeCoverageManifest.model_validate(report_data["scope_coverage"])
                if "inspection_state" in report_data and report_data["inspection_state"]:
                    existing_state = report_data["inspection_state"]
                    existing_evidence_conflicts = existing_state.get("evidence_conflicts", [])
        except Exception as e:
            logger.debug(f"Could not load metadata from report for {id}: {e}")

    # 2. Evaluate physical measurement deterministically via quantity_service
    measurement = evaluate_physical_quantity(
        measurement_input=measurement_input,
        declarations=current_decls,
        composition=composition_obj,
        evidence_conflicts=existing_evidence_conflicts,
    )

    # 3. Derive updated operational inspection state and next best action
    is_reviewed_flag = scan.get("reviewer_notes") is not None
    updated_state, updated_nba = derive_inspection_state_and_next_action(
        declarations=current_decls,
        violations=current_viols,
        guidance=guidance_obj,
        scope_coverage=scope_manifest_obj,
        qr_evidence=qr_evidence_obj,
        composition=composition_obj,
        views_captured_count=len(scan.get("image_urls") or [1]),
        is_complete_scan=scan.get("is_complete_scan", False),
        is_reviewed=is_reviewed_flag,
        reviewer_notes=scan.get("reviewer_notes"),
        quantity_measurement=measurement,
    )

    # 4. Save updated JSON inspection report artifact
    try:
        report_path = generate_json_report(
            scan_id=id,
            verdict=scan.get("verdict"),
            compliance_score=scan.get("compliance_score"),
            product_category=scan.get("product_category"),
            declarations=current_decls,
            violations=current_viols,
            image_path=scan.get("image_url"),
            evidence_path=scan.get("evidence_image_url"),
            output_path=report_json_path,
            created_at=scan.get("created_at"),
            completed_at=scan.get("completed_at"),
            status=scan.get("status", "complete"),
            reviewer_notes=scan.get("reviewer_notes"),
            guidance=guidance_obj,
            scope_coverage=scope_manifest_obj,
            qr_evidence=qr_evidence_obj,
            composition=composition_obj,
            inspection_state=updated_state,
            next_best_action=updated_nba,
            quantity_measurement=measurement,
        )
        repo.save_report(id, report_url=report_path, format_type="json")
    except Exception as report_err:
        logger.error(f"Failed to refresh inspection report after physical measurement for {id}: {report_err}", exc_info=True)

    return get_scan(id=id, repo=repo)
