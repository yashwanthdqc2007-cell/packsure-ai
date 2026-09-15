"""
PackSure AI — Quantity Verification & Metrology Service.

Implements Phase 6B deterministic physical quantity verification for individual packages
under the Legal Metrology (Packaged Commodities) Rules, 2011 — First Schedule [Rules 2(e) & 22], Table I.

Key Invariants:
- Pure, deterministic calculation using Decimal arithmetic.
- Decoupled from Visual Label Compliance Score (label score remains 100% unaffected).
- Safe unit normalization within dimensions (mass, volume, length); strict cross-dimension barrier.
- Multi-piece and composition ambiguity protection.
- Reference double-MPE calculation without enforcement automation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import logging
import math
import re
from typing import List, Optional, Tuple, Union

from app.schemas.declaration import (
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageType,
)
from app.schemas.quantity import (
    IndividualQuantityVerdict,
    MeasurementMethod,
    QuantityMeasurement,
    QuantityMeasurementInput,
)

logger = logging.getLogger(__name__)

STATUTORY_REF_FIRST_SCHEDULE = (
    "Legal Metrology (Packaged Commodities) Rules, 2011 — First Schedule [Rules 2(e) & 22], Table I"
)


@dataclass(frozen=True)
class FirstScheduleMPETier:
    """Immutable statutory tier under First Schedule Table I for weight or volume."""

    tier_id: str
    min_qty: Decimal  # In base units: grams (g) or millilitres (ml)
    max_qty: Optional[Decimal]  # In base units; None indicates unbounded upper tier (> 15000)
    percentage_error: Optional[Decimal]  # e.g. Decimal("9.0") for 9%
    fixed_error: Optional[Decimal]  # e.g. Decimal("4.5") for 4.5 g/ml
    rounding_rule: str  # "nearest_tenth" | "next_whole"
    effective_from: str = "2011-04-01"
    statutory_reference: str = STATUTORY_REF_FIRST_SCHEDULE


# Immutable, versioned First Schedule Table I registry for weight and volume
FIRST_SCHEDULE_TABLE_I_TIERS: Tuple[FirstScheduleMPETier, ...] = (
    FirstScheduleMPETier(
        tier_id="tier_1_up_to_50",
        min_qty=Decimal("0.0"),
        max_qty=Decimal("50.0"),
        percentage_error=Decimal("9.0"),
        fixed_error=None,
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_2_50_to_100",
        min_qty=Decimal("50.0"),
        max_qty=Decimal("100.0"),
        percentage_error=None,
        fixed_error=Decimal("4.5"),
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_3_100_to_200",
        min_qty=Decimal("100.0"),
        max_qty=Decimal("200.0"),
        percentage_error=Decimal("4.5"),
        fixed_error=None,
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_4_200_to_300",
        min_qty=Decimal("200.0"),
        max_qty=Decimal("300.0"),
        percentage_error=None,
        fixed_error=Decimal("9.0"),
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_5_300_to_500",
        min_qty=Decimal("300.0"),
        max_qty=Decimal("500.0"),
        percentage_error=Decimal("3.0"),
        fixed_error=None,
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_6_500_to_1000",
        min_qty=Decimal("500.0"),
        max_qty=Decimal("1000.0"),
        percentage_error=None,
        fixed_error=Decimal("15.0"),
        rounding_rule="nearest_tenth",
    ),
    FirstScheduleMPETier(
        tier_id="tier_7_1000_to_10000",
        min_qty=Decimal("1000.0"),
        max_qty=Decimal("10000.0"),
        percentage_error=Decimal("1.5"),
        fixed_error=None,
        rounding_rule="next_whole",
    ),
    FirstScheduleMPETier(
        tier_id="tier_8_10000_to_15000",
        min_qty=Decimal("10000.0"),
        max_qty=Decimal("15000.0"),
        percentage_error=None,
        fixed_error=Decimal("150.0"),
        rounding_rule="next_whole",
    ),
    FirstScheduleMPETier(
        tier_id="tier_9_above_15000",
        min_qty=Decimal("15000.0"),
        max_qty=None,
        percentage_error=Decimal("1.0"),
        fixed_error=None,
        rounding_rule="next_whole",
    ),
)


def normalize_unit_and_dimension(unit_raw: str) -> Tuple[str, str]:
    """Normalize raw unit symbol and identify its physical metrological dimension.

    Args:
        unit_raw: Raw unit string (e.g., 'g', 'kg', 'ml', 'L', 'ltr', 'm', 'N', 'U').

    Returns:
        Tuple of (normalized_unit, dimension) where dimension is:
        'mass', 'volume', 'length', 'count', or 'unsupported'.
    """
    cleaned = (unit_raw or "").strip().lower()

    # Mass
    if cleaned in ("g", "gm", "gms", "gram", "grams", "grm"):
        return "g", "mass"
    if cleaned in ("kg", "kgs", "kilo", "kilogram", "kilograms"):
        return "kg", "mass"

    # Volume
    if cleaned in ("ml", "m.l.", "m.l", "millilitre", "millilitres", "milliliter", "milliliters"):
        return "ml", "volume"
    if cleaned in ("l", "ltr", "ltrs", "litre", "litres", "liter", "liters"):
        return "L", "volume"

    # Length
    if cleaned in ("cm", "c.m.", "centimetre", "centimeter", "centimetres"):
        return "cm", "length"
    if cleaned in ("m", "mtr", "mtrs", "metre", "metres", "meter", "meters"):
        return "m", "length"

    # Count / Number
    if cleaned in ("u", "unit", "units", "n", "no", "nos", "number", "numbers", "piece", "pieces", "pc", "pcs"):
        return "U", "count"

    return cleaned, "unsupported"


def to_base_unit(magnitude: Decimal, normalized_unit: str) -> Decimal:
    """Convert magnitude to canonical base unit for its dimension (g, ml, m, U)."""
    if normalized_unit == "kg":
        return magnitude * Decimal("1000")
    if normalized_unit == "L":
        return magnitude * Decimal("1000")
    if normalized_unit == "cm":
        return magnitude / Decimal("100")
    return magnitude


def lookup_first_schedule_table_i_mpe(base_quantity: Decimal) -> Tuple[Optional[Decimal], Optional[str]]:
    """Determine Maximum Permissible Error (MPE) for weight/volume under First Schedule Table I.

    Args:
        base_quantity: Nominal declared quantity in base units (g or ml).

    Returns:
        Tuple of (calculated_mpe, tier_id).
    """
    if base_quantity <= Decimal("0"):
        return None, None

    for tier in FIRST_SCHEDULE_TABLE_I_TIERS:
        # Check lower boundary
        if tier.tier_id == "tier_1_up_to_50":
            in_tier = (base_quantity <= tier.max_qty)
        elif tier.max_qty is None:
            in_tier = (base_quantity > tier.min_qty)
        else:
            in_tier = (tier.min_qty < base_quantity <= tier.max_qty)

        if in_tier:
            if tier.fixed_error is not None:
                mpe = tier.fixed_error
            elif tier.percentage_error is not None:
                raw_mpe = (base_quantity * tier.percentage_error) / Decimal("100")
                if tier.rounding_rule == "nearest_tenth":
                    mpe = raw_mpe.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                else:
                    # Round off to next whole gram/ml
                    mpe = Decimal(str(math.ceil(float(raw_mpe))))
            else:
                mpe = None
            return mpe, tier.tier_id

    return None, None


def parse_declaration_quantity(text: Optional[str]) -> Optional[Tuple[Decimal, str]]:
    """Extract numerical quantity and unit from declared net_quantity text string."""
    if not text:
        return None

    cleaned = text.strip()
    # Strip common prefixes
    cleaned = re.sub(
        r"^(?:net\s*(?:qty|quantity|wt|weight|contents?)|qty|wt)\s*[:\-]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Match number + unit
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*([a-zA-Z\.]+)",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None

    mag_str, unit_str = match.groups()
    try:
        magnitude = Decimal(mag_str)
        return magnitude, unit_str
    except Exception:
        return None


def evaluate_physical_quantity(
    measurement_input: QuantityMeasurementInput,
    declarations: Optional[List[ExtractedDeclaration]] = None,
    composition: Optional[PackageComposition] = None,
    evidence_conflicts: Optional[List[str]] = None,
) -> QuantityMeasurement:
    """Deterministically evaluate an officer-entered physical measurement against declared quantity.

    Args:
        measurement_input: Submitted physical scale or gauge measurement.
        declarations: Optional list of OCR/AI extracted declarations from scan.
        composition: Optional PackageComposition model.
        evidence_conflicts: Optional list of fields with cross-view conflicts.

    Returns:
        Fully evaluated QuantityMeasurement record with verdict, MPE, and double-MPE reference.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Resolve Declared Quantity & Unit
    decl_qty: Optional[Decimal] = measurement_input.declared_quantity
    decl_unit_raw: Optional[str] = measurement_input.declared_unit

    if decl_qty is None or decl_unit_raw is None:
        if declarations:
            for decl in declarations:
                if decl.field_name == "net_quantity" and decl.raw_value:
                    parsed = parse_declaration_quantity(decl.raw_value)
                    if parsed:
                        decl_qty, decl_unit_raw = parsed
                        break

    # If declared quantity could not be determined
    if decl_qty is None or decl_unit_raw is None:
        return QuantityMeasurement(
            declared_quantity=Decimal("0"),
            declared_unit="unknown",
            measured_quantity=measurement_input.measured_quantity,
            measured_unit=measurement_input.measured_unit,
            tare_weight=measurement_input.tare_weight,
            gross_weight=measurement_input.gross_weight,
            net_difference=Decimal("0"),
            deficiency=Decimal("0"),
            percentage_deficiency=Decimal("0"),
            statutory_mpe=None,
            double_mpe_limit=None,
            is_excess=False,
            verdict=IndividualQuantityVerdict.NEEDS_REVIEW,
            method=measurement_input.method,
            instrument_id=measurement_input.instrument_id,
            inspector_id=measurement_input.inspector_id,
            measured_at=now_iso,
            notes="Declared net quantity is missing or could not be parsed from packaging.",
            statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
        )

    # 2. Check Cross-View Evidence Conflicts on net_quantity
    if evidence_conflicts and "net_quantity" in evidence_conflicts:
        return QuantityMeasurement(
            declared_quantity=decl_qty,
            declared_unit=decl_unit_raw,
            measured_quantity=measurement_input.measured_quantity,
            measured_unit=measurement_input.measured_unit,
            tare_weight=measurement_input.tare_weight,
            gross_weight=measurement_input.gross_weight,
            net_difference=Decimal("0"),
            deficiency=Decimal("0"),
            percentage_deficiency=Decimal("0"),
            statutory_mpe=None,
            double_mpe_limit=None,
            is_excess=False,
            verdict=IndividualQuantityVerdict.NEEDS_REVIEW,
            method=measurement_input.method,
            instrument_id=measurement_input.instrument_id,
            inspector_id=measurement_input.inspector_id,
            measured_at=now_iso,
            notes="Conflicting net quantity declarations detected across package views. Officer must confirm declared quantity.",
            statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
        )

    # 3. Check Multi-Piece / Composition Ambiguity
    if composition and composition.package_type in (
        PackageType.UNCERTAIN,
        PackageType.COMBINATION,
        PackageType.GROUP,
        PackageType.KIT,
        PackageType.MULTI_PIECE,
    ):
        # If measurement_input did not provide an explicit declared_quantity override
        if measurement_input.declared_quantity is None and composition.package_type != PackageType.SINGLE:
            # Ambiguous multi-item target
            if (composition.total_item_count and composition.total_item_count > 1) or (composition.items and len(composition.items) > 1):
                return QuantityMeasurement(
                    declared_quantity=decl_qty,
                    declared_unit=decl_unit_raw,
                    measured_quantity=measurement_input.measured_quantity,
                    measured_unit=measurement_input.measured_unit,
                    tare_weight=measurement_input.tare_weight,
                    gross_weight=measurement_input.gross_weight,
                    net_difference=Decimal("0"),
                    deficiency=Decimal("0"),
                    percentage_deficiency=Decimal("0"),
                    statutory_mpe=None,
                    double_mpe_limit=None,
                    is_excess=False,
                    verdict=IndividualQuantityVerdict.NEEDS_REVIEW,
                    method=measurement_input.method,
                    instrument_id=measurement_input.instrument_id,
                    inspector_id=measurement_input.inspector_id,
                    measured_at=now_iso,
                    notes=f"Multi-item / {composition.package_type.value} package requires officer-confirmed individual constituent measurement target.",
                    statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
                )

    # 4. Normalize Units & Metrological Dimensions
    norm_decl_unit, decl_dim = normalize_unit_and_dimension(decl_unit_raw)
    norm_meas_unit, meas_dim = normalize_unit_and_dimension(measurement_input.measured_unit)

    if decl_dim == "unsupported" or meas_dim == "unsupported":
        return QuantityMeasurement(
            declared_quantity=decl_qty,
            declared_unit=norm_decl_unit,
            measured_quantity=measurement_input.measured_quantity,
            measured_unit=norm_meas_unit,
            tare_weight=measurement_input.tare_weight,
            gross_weight=measurement_input.gross_weight,
            net_difference=Decimal("0"),
            deficiency=Decimal("0"),
            percentage_deficiency=Decimal("0"),
            statutory_mpe=None,
            double_mpe_limit=None,
            is_excess=False,
            verdict=IndividualQuantityVerdict.NEEDS_REVIEW,
            method=measurement_input.method,
            instrument_id=measurement_input.instrument_id,
            inspector_id=measurement_input.inspector_id,
            measured_at=now_iso,
            notes=f"Unsupported or non-standard metric unit ('{decl_unit_raw}' / '{measurement_input.measured_unit}').",
            statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
        )

    # Cross-dimensional barrier (e.g., mass vs volume)
    if decl_dim != meas_dim:
        return QuantityMeasurement(
            declared_quantity=decl_qty,
            declared_unit=norm_decl_unit,
            measured_quantity=measurement_input.measured_quantity,
            measured_unit=norm_meas_unit,
            tare_weight=measurement_input.tare_weight,
            gross_weight=measurement_input.gross_weight,
            net_difference=Decimal("0"),
            deficiency=Decimal("0"),
            percentage_deficiency=Decimal("0"),
            statutory_mpe=None,
            double_mpe_limit=None,
            is_excess=False,
            verdict=IndividualQuantityVerdict.NEEDS_REVIEW,
            method=measurement_input.method,
            instrument_id=measurement_input.instrument_id,
            inspector_id=measurement_input.inspector_id,
            measured_at=now_iso,
            notes=f"Cross-dimensional mismatch: declared {decl_dim} ('{norm_decl_unit}') vs measured {meas_dim} ('{norm_meas_unit}'). Cannot compare without verified density.",
            statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
        )

    # 5. Convert to Normalized Base Units for Arithmetic
    base_decl_qty = to_base_unit(decl_qty, norm_decl_unit)
    base_meas_qty = to_base_unit(measurement_input.measured_quantity, norm_meas_unit)

    # Account for tare weight if provided in gravimetric measurement
    if measurement_input.tare_weight is not None and measurement_input.gross_weight is not None:
        norm_tare = to_base_unit(measurement_input.tare_weight, norm_meas_unit)
        norm_gross = to_base_unit(measurement_input.gross_weight, norm_meas_unit)
        base_meas_qty = norm_gross - norm_tare

    net_diff = base_meas_qty - base_decl_qty
    is_excess = (base_meas_qty >= base_decl_qty)

    if is_excess:
        deficiency = Decimal("0.0")
        pct_deficiency = Decimal("0.0")
    else:
        deficiency = base_decl_qty - base_meas_qty
        pct_deficiency = (deficiency / base_decl_qty) * Decimal("100")

    # 6. Lookup Statutory MPE
    statutory_mpe: Optional[Decimal] = None
    double_mpe: Optional[Decimal] = None
    verdict: IndividualQuantityVerdict = IndividualQuantityVerdict.NEEDS_REVIEW

    if decl_dim in ("mass", "volume"):
        statutory_mpe, _ = lookup_first_schedule_table_i_mpe(base_decl_qty)
        if statutory_mpe is not None:
            double_mpe = statutory_mpe * Decimal("2")
            if is_excess or deficiency <= statutory_mpe:
                verdict = IndividualQuantityVerdict.PASS
            else:
                verdict = IndividualQuantityVerdict.FAIL
    elif decl_dim == "length":
        # Rule 12 length tolerance: 2% for <= 10m, 1% for > 10m
        if base_decl_qty <= Decimal("10.0"):
            statutory_mpe = (base_decl_qty * Decimal("2.0")) / Decimal("100")
        else:
            statutory_mpe = (base_decl_qty * Decimal("1.0")) / Decimal("100")
        statutory_mpe = statutory_mpe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        double_mpe = statutory_mpe * Decimal("2")
        if is_excess or deficiency <= statutory_mpe:
            verdict = IndividualQuantityVerdict.PASS
        else:
            verdict = IndividualQuantityVerdict.FAIL
    else:
        # Count / Area: Mark NEEDS_REVIEW when deficient, or PASS when excess
        if is_excess:
            verdict = IndividualQuantityVerdict.PASS
        else:
            verdict = IndividualQuantityVerdict.NEEDS_REVIEW

    return QuantityMeasurement(
        declared_quantity=decl_qty,
        declared_unit=norm_decl_unit,
        measured_quantity=measurement_input.measured_quantity,
        measured_unit=norm_meas_unit,
        tare_weight=measurement_input.tare_weight,
        gross_weight=measurement_input.gross_weight,
        net_difference=net_diff,
        deficiency=deficiency,
        percentage_deficiency=pct_deficiency.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        statutory_mpe=statutory_mpe,
        double_mpe_limit=double_mpe,
        is_excess=is_excess,
        verdict=verdict,
        method=measurement_input.method,
        instrument_id=measurement_input.instrument_id,
        inspector_id=measurement_input.inspector_id,
        measured_at=now_iso,
        notes=measurement_input.notes,
        statutory_reference=STATUTORY_REF_FIRST_SCHEDULE,
    )
