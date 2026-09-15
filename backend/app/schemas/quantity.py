"""
PackSure AI — Quantity Verification Schema.

Defines typed Pydantic models for physical metrological measurement,
Maximum Permissible Error (MPE) tolerance evaluation under the
Legal Metrology (Packaged Commodities) Rules, 2011 First Schedule [Rules 2(e) & 22],
and field officer inspection evidence.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MeasurementMethod(str, Enum):
    """Calibrated physical measurement apparatus or technique used by the field officer."""

    MANUAL_SCALE = "MANUAL_SCALE"  # Calibrated electronic weighing balance (Class II / Class III)
    VOLUMETRIC_MEASURE = "VOLUMETRIC_MEASURE"  # Calibrated volumetric glassware / flask
    LINEAR_MEASURE = "LINEAR_MEASURE"  # Calibrated steel rule / tape / micrometer
    PIECE_COUNT = "PIECE_COUNT"  # Physical verified unit count


class IndividualQuantityVerdict(str, Enum):
    """Deterministic physical quantity finding for an individual package."""

    NOT_EVALUATED = "NOT_EVALUATED"  # No physical measurement has been conducted
    PASS = "PASS"  # Measured net quantity is within First Schedule MPE tolerance
    FAIL = "FAIL"  # Deficiency exceeds statutory Maximum Permissible Error
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Incompatible units, ambiguous target, or missing tolerance lookup


class QuantityMeasurement(BaseModel):
    """Complete physical quantity measurement record and deterministic statutory evaluation."""

    declared_quantity: Decimal = Field(
        ..., description="Nominal declared quantity on the package label"
    )
    declared_unit: str = Field(
        ..., description="Unit of declared quantity (e.g., 'g', 'kg', 'ml', 'L', 'm', 'U')"
    )
    measured_quantity: Decimal = Field(
        ..., description="Actual measured net quantity determined by the field officer"
    )
    measured_unit: str = Field(
        ..., description="Unit of measured quantity (must match dimension of declared_unit)"
    )
    tare_weight: Optional[Decimal] = Field(
        default=None, description="Optional packaging tare weight if gravimetric measurement"
    )
    gross_weight: Optional[Decimal] = Field(
        default=None, description="Optional total package gross weight"
    )
    net_difference: Decimal = Field(
        ..., description="Signed difference (measured_quantity - declared_quantity) in normalized base unit"
    )
    deficiency: Decimal = Field(
        ..., description="Positive deficiency amount (max(0, declared - measured)) in normalized base unit"
    )
    percentage_deficiency: Decimal = Field(
        ..., description="Percentage deficiency relative to declared quantity"
    )
    statutory_mpe: Optional[Decimal] = Field(
        default=None, description="Applicable Maximum Permissible Error under First Schedule Table I"
    )
    double_mpe_limit: Optional[Decimal] = Field(
        default=None, description="Reference double-MPE threshold (2 * statutory_mpe) for individual packages"
    )
    is_excess: bool = Field(
        default=False, description="True if measured quantity equals or exceeds nominal declared quantity"
    )
    verdict: IndividualQuantityVerdict = Field(
        ..., description="Individual physical quantity finding (PASS, FAIL, NEEDS_REVIEW, NOT_EVALUATED)"
    )
    method: MeasurementMethod = Field(
        default=MeasurementMethod.MANUAL_SCALE, description="Apparatus or method used for physical verification"
    )
    instrument_id: Optional[str] = Field(
        default=None, description="Optional calibration certificate ID or instrument serial number"
    )
    inspector_id: Optional[str] = Field(
        default=None, description="Identifier of the Legal Metrology Officer performing measurement"
    )
    measured_at: str = Field(
        ..., description="ISO8601 timestamp of physical measurement"
    )
    notes: Optional[str] = Field(
        default=None, description="Auditor / field notes concerning measurement conditions"
    )
    statutory_reference: str = Field(
        default="Legal Metrology (Packaged Commodities) Rules, 2011 — First Schedule [Rules 2(e) & 22], Table I",
        description="Statutory legal metrology rule and schedule citation",
    )


class QuantityMeasurementInput(BaseModel):
    """Input payload submitted by field officer to record a physical package measurement."""

    declared_quantity: Optional[Decimal] = Field(
        default=None, description="Optional declared quantity override (if omitted, extracted from scan)"
    )
    declared_unit: Optional[str] = Field(
        default=None, description="Optional declared unit override (e.g., 'g', 'kg', 'ml', 'L')"
    )
    measured_quantity: Decimal = Field(
        ..., description="Actual measured net quantity from scale or gauge"
    )
    measured_unit: str = Field(
        ..., description="Unit of measurement ('g', 'kg', 'ml', 'L', 'm', 'cm', 'N', 'U')"
    )
    tare_weight: Optional[Decimal] = Field(
        default=None, description="Optional tare weight of packaging material"
    )
    gross_weight: Optional[Decimal] = Field(
        default=None, description="Optional gross package weight"
    )
    method: MeasurementMethod = Field(
        default=MeasurementMethod.MANUAL_SCALE, description="Measurement method"
    )
    instrument_id: Optional[str] = Field(
        default=None, description="Optional instrument calibration ID"
    )
    inspector_id: Optional[str] = Field(
        default=None, description="Optional inspector ID"
    )
    notes: Optional[str] = Field(
        default=None, description="Optional notes on measurement"
    )
