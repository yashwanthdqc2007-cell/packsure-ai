"""
PackSure AI — Analytics Routing Layer.

Implements Phase 8D aggregated compliance telemetry and trend queries adhering to docs/api.md:
- GET /api/v1/analytics
"""

import logging
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_db_repository
from app.database.connection import BaseScanRepository
from app.schemas.analytics import AnalyticsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

ALLOWED_PERIODS: Set[str] = {"7d", "30d", "all"}


@router.get(
    "",
    response_model=AnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve aggregated compliance metrics, trends, top violations, and category breakdown",
)
def get_analytics(
    period: str = Query(
        default="7d",
        description="Time period: '7d', '30d', or 'all'.",
    ),
    repo: BaseScanRepository = Depends(get_db_repository),
) -> AnalyticsResponse:
    """Retrieve aggregated compliance metrics, pass rates, category distributions, and daily trends."""
    # Handle direct Python function calls where Query parameter default was not replaced by FastAPI
    if not isinstance(period, str):
        period = period.default if hasattr(period, "default") and isinstance(period.default, str) else "7d"

    clean_period = period.strip().lower()
    if clean_period not in ALLOWED_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period filter '{period}'. Allowed values: {sorted(ALLOWED_PERIODS)}",
        )

    try:
        raw_res = repo.query_analytics(period=clean_period)
    except Exception as exc:
        logger.error(f"Failed to query analytics: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics from database.",
        ) from exc

    return AnalyticsResponse.model_validate(raw_res)
