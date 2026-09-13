"""
PackSure AI — Scans Routing Layer.

Implements Phase 7 scan lifecycle endpoints adhering to docs/api.md:
1. POST /api/v1/scans: Validate upload, create pending record, dispatch background task, return 202.
2. GET /api/v1/scans/{id}: Fetch full scan report, declarations, violations, and evidence.
3. PATCH /api/v1/scans/{id}/review: Human inspector resolution for NEEDS_REVIEW scans.
"""

from datetime import datetime, timezone
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
from app.schemas.compliance import ComplianceVerdict
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.guidance import InspectionGuidance
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

        try:
            report_json_path = os.path.join(scan_dir, "report.json")
            report_path = generate_json_report(
                scan_id=scan_id,
                compliance_result=compliance_result,
                product_category=product_category,
                image_path=primary_raw,
                evidence_path=primary_evidence,
                output_path=report_json_path,
            )
            repo.save_report(scan_id, report_url=report_path, format_type="json")
        except Exception as report_err:
            logger.error(f"Failed to generate inspection report for {scan_id}: {report_err}", exc_info=True)

        # 6. Finalize Scan Record
        normalized_ev_paths = [p.replace("\\", "/") for p in evidence_paths]
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
            ) from exc

        fname = file.filename or f"upload_{idx}.jpg"
        is_valid, err_msg, _ = validate_image_file(content, filename=fname)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg or f"Invalid image file format for {fname} or size exceeds 20MB limit.",
            )
        view_payloads.append(PackageViewPayload(file_bytes=content, filename=fname))

    # 3. Create Pending Scan Record
    scan_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    repo.create_scan(
        scan_id=scan_id,
        product_category=product_category,
        user_id=user_id,
        image_url=None,
    )

    # 4. Enqueue Background Processing Job
    background_tasks.add_task(
        process_scan_background,
        scan_id=scan_id,
        views=view_payloads,
        product_category=product_category,
        user_id=user_id,
        is_complete_scan=is_complete_scan,
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
    guidance_obj = None
    if raw_guidance:
        if isinstance(raw_guidance, dict):
            try:
                guidance_obj = InspectionGuidance.model_validate(raw_guidance)
            except Exception:
                guidance_obj = None
        elif isinstance(raw_guidance, InspectionGuidance):
            guidance_obj = raw_guidance

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
        is_complete_scan=scan.get("is_complete_scan", False),
        declarations=declarations,
        violations=violations,
        reviewer_notes=scan.get("reviewer_notes"),
        guidance=guidance_obj,
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
        )
        repo.save_report(id, report_url=report_path, format_type="json")
    except Exception as report_err:
        logger.error(f"Failed to refresh inspection report after review for {id}: {report_err}", exc_info=True)

    # Return updated full scan payload
    return get_scan(id=id, repo=repo)
