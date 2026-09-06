"""
Pydantic schemas for Analytics API requests and responses.

Models:
- DailyTrendItem: Daily scan volume and compliance outcome breakdown
- TopViolationItem: Aggregated violation frequency item
- CategoryStats: Per-category compliance breakdown metrics
- AnalyticsResponse: Full aggregated analytics response payload (GET /api/v1/analytics)
"""

from typing import Dict, List
from pydantic import BaseModel, ConfigDict, Field


class DailyTrendItem(BaseModel):
    """Daily scan activity and compliance outcome metrics."""

    day: str = Field(..., description="Day of week abbreviation (e.g., 'Mon', 'Tue')")
    date: str = Field(..., description="ISO calendar date string (e.g., '2026-08-31')")
    scans: int = Field(..., ge=0, description="Total scans performed on this day")
    compliant: int = Field(..., ge=0, description="Count of compliant scans (PASS)")
    non_compliant: int = Field(..., ge=0, description="Count of non-compliant scans (FAIL)")
    needs_review: int = Field(..., ge=0, description="Count of scans flagged for review (NEEDS_REVIEW)")


class TopViolationItem(BaseModel):
    """Aggregated occurrence frequency for a codified rule violation."""

    rule_code: str = Field(..., description="Statutory rule citation code (e.g., 'Rule-6(1)(e)')")
    description: str = Field(..., description="Human-readable violation summary")
    count: int = Field(..., ge=0, description="Total occurrences of this violation")


class CategoryStats(BaseModel):
    """Compliance breakdown metrics for an individual product category."""

    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(..., ge=0, description="Total scans in this category")
    pass_: int = Field(
        ...,
        ge=0,
        alias="pass",
        serialization_alias="pass",
        description="Compliant scans count",
    )
    fail: int = Field(..., ge=0, description="Non-compliant scans count")
    review: int = Field(..., ge=0, description="Scans requiring manual review count")


class AnalyticsResponse(BaseModel):
    """Aggregated compliance metrics and telemetry payload for GET /api/v1/analytics."""

    total_scans: int = Field(..., ge=0, description="Total scans recorded across the period")
    pass_count: int = Field(..., ge=0, description="Total compliant scans (PASS)")
    fail_count: int = Field(..., ge=0, description="Total non-compliant scans (FAIL)")
    review_count: int = Field(..., ge=0, description="Total scans needing review (NEEDS_REVIEW)")
    pass_rate: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Compliance pass percentage rate (0.0 to 100.0)",
    )
    daily_trend: List[DailyTrendItem] = Field(
        default_factory=list,
        description="Chronological daily activity and outcome trend list",
    )
    top_violations: List[TopViolationItem] = Field(
        default_factory=list,
        description="Most frequent rule violations ranked by count",
    )
    by_category: Dict[str, CategoryStats] = Field(
        default_factory=dict,
        description="Category-level compliance breakdown mapping",
    )
