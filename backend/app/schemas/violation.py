"""
Pydantic schemas for compliance violations.

Enums:
- ViolationSeverity: critical | major | minor
- ViolationType: Specific classification of legal violation

Models:
- Violation: Single rule non-compliance finding with citations and severity
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ViolationSeverity(str, Enum):
    """Severity tier for a compliance violation."""

    critical = "critical"
    major = "major"
    minor = "minor"


class ViolationType(str, Enum):
    """Categorization of violation according to Legal Metrology validation rules."""

    missing_declaration = "missing_declaration"
    invalid_format = "invalid_format"
    invalid_unit = "invalid_unit"
    out_of_range = "out_of_range"
    illegible = "illegible"
    misleading = "misleading"
    pdp_violation = "pdp_violation"
    font_size_violation = "font_size_violation"
    other = "other"


class Violation(BaseModel):
    """Detailed violation record linking rule code, affected field, and description."""

    id: Optional[str] = Field(default=None, description="UUID of the violation record")
    scan_id: Optional[str] = Field(default=None, description="Associated scan UUID")
    rule_id: Optional[str] = Field(default=None, description="Database UUID of the codified rule")
    rule_code: str = Field(..., description="Legal Metrology rule citation code (e.g. Rule-6(1)(e))")
    field_name: Optional[str] = Field(
        default=None, description="Declaration field associated with the violation"
    )
    violation_type: ViolationType = Field(
        default=ViolationType.other, description="Specific category of violation"
    )
    severity: ViolationSeverity = Field(
        default=ViolationSeverity.critical, description="Severity rating: critical, major, minor"
    )
    description: str = Field(..., description="Detailed explanation of the non-compliance")
    created_at: Optional[str] = Field(default=None, description="ISO8601 creation timestamp")
