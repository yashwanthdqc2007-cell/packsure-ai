"""
PackSure AI — History Routing Layer.

Implements Phase 8C paginated historical scans query adhering to docs/api.md:
- GET /api/v1/history
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_db_repository
from app.database.connection import BaseScanRepository
from app.schemas.compliance import ComplianceVerdict
from app.schemas.scan import ScanHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get(
    "",
    response_model=ScanHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query paginated historical scans with optional filters",
)
def get_history(
    page: int = Query(default=1, ge=1, description="Page number (min: 1)."),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page (min: 1, max: 100)."),
    verdict: Optional[str] = Query(default=None, description="Filter by verdict (PASS, FAIL, NEEDS_REVIEW)."),
    category: Optional[str] = Query(default=None, description="Filter by category name or UUID."),
    search: Optional[str] = Query(default=None, description="Search term across product/brand/scan ID."),
    from_date: Optional[str] = Query(default=None, description="Filter scans created on or after date (ISO8601)."),
    to_date: Optional[str] = Query(default=None, description="Filter scans created on or before date (ISO8601)."),
    repo: BaseScanRepository = Depends(get_db_repository),
) -> ScanHistoryResponse:
    """Retrieve paginated historical scans filtered by status, category, date, or keyword."""
    # Handle direct Python function calls where Query parameter defaults were not replaced by FastAPI
    if not isinstance(page, int):
        page = page.default if hasattr(page, "default") and isinstance(page.default, int) else 1
    if not isinstance(limit, int):
        limit = limit.default if hasattr(limit, "default") and isinstance(limit.default, int) else 20
    if not isinstance(verdict, str):
        verdict = verdict.default if hasattr(verdict, "default") and isinstance(verdict.default, str) else None
    if not isinstance(category, str):
        category = category.default if hasattr(category, "default") and isinstance(category.default, str) else None
    if not isinstance(search, str):
        search = search.default if hasattr(search, "default") and isinstance(search.default, str) else None
    if not isinstance(from_date, str):
        from_date = from_date.default if hasattr(from_date, "default") and isinstance(from_date.default, str) else None
    if not isinstance(to_date, str):
        to_date = to_date.default if hasattr(to_date, "default") and isinstance(to_date.default, str) else None

    # Validate pagination bounds for direct invocations
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'page' must be greater than or equal to 1.",
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'limit' must be between 1 and 100.",
        )

    # Validate verdict if supplied
    if verdict is not None:
        v_upper = verdict.strip().upper()
        valid_verdicts = {v.value for v in ComplianceVerdict}
        if v_upper not in valid_verdicts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verdict filter '{verdict}'. Allowed values: {sorted(valid_verdicts)}",
            )
        verdict = v_upper

    try:
        raw_res = repo.query_history(
            page=page,
            limit=limit,
            verdict=verdict,
            category=category,
            search=search,
            from_date=from_date,
            to_date=to_date,
        )
    except Exception as exc:
        logger.error(f"Failed to query scan history: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scan history from database.",
        ) from exc

    return ScanHistoryResponse.model_validate(raw_res)
