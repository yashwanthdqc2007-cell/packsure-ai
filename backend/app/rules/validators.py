"""
PackSure AI — Pure Deterministic Declaration Validators.

Implements pure functional validation logic for Legal Metrology (Packaged Commodities) Rules:
1. validate_address: Name & complete geographic address.
2. validate_country_of_origin: Country of origin for imported goods.
3. validate_generic_name: Common or generic commodity name.
4. validate_net_quantity: Standard SI metric units vs. prohibited legacy symbols.
5. validate_manufacture_date: Month/year structure.
6. validate_mrp: Decimal price + mandatory 'inclusive of all taxes' clause.
7. validate_unit_sale_price: Base unit ratio & threshold applicability.
8. validate_batch_number: Traceability lot/batch code.
9. validate_expiry_date: Date syntax & chronological validity against manufacture date.
10. validate_consumer_care: Telephone, email, or physical grievance contact.
11. check_rule26_exemption: Small package exemption (<= 10g/ml, non-tobacco).

Invariants:
- Pure deterministic functions (no database calls, no network I/O, no LLMs).
- Output is structured tuple: (is_valid, error_message, violation_type).
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import NamedTuple, Optional, Tuple
from app.schemas.violation import ViolationType

# Prohibited non-standard unit symbols per Rule 13 / Third Schedule
PROHIBITED_UNIT_PATTERN = re.compile(
    r"\b(gms?|grms?|kilos?|ltrs?|litres?|liters?|pcs|pieces?|pkts?|packets?)\b",
    re.IGNORECASE,
)

# Allowed standard SI metric units per Rule 13 / Third Schedule
VALID_METRIC_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|g|kg|ml|l|L|m|cm|mm|sq\s*m|m2|m²|N|U)\b",
)

# Mandatory tax inclusion phrase per Rule 6(1)(e)
TAX_INCLUSION_PATTERN = re.compile(
    r"(incl(?:usive)?\.?\s*of\s*all\s*taxes|incl\.?\s*taxes)",
    re.IGNORECASE,
)

# Currency pattern
CURRENCY_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr|mrp)\s*(\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Date patterns supporting 2-digit and 4-digit years per Legal Metrology Rule 6(1)(d) & FSSAI Reg 5(3)/5(10)
# Matches:
# - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD/MM/YY, DD-MM-YY, DD.MM.YY
# - MM/YYYY, MM-YYYY, MM.YYYY, MM/YY, MM-YY, MM.YY
# - Month YYYY, Month YY (e.g. 'Jan 2026', 'Sep 26', 'September 2026')
# - YYYY-MM, YYYY/MM, YYYY-MM-DD
DATE_PATTERN = re.compile(
    r"(?:"
    r"\b([0-3]?\d)[/\-\.]([0-1]?\d)[/\-\.](\d{4}|\d{2})\b"  # 3-part: DD/MM/YY or DD/MM/YYYY
    r"|"
    r"\b([0-1]?\d)[/\-\.](\d{4}|\d{2})\b"                  # 2-part: MM/YYYY or MM/YY
    r"|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,\.\-]+(\d{4}|\d{2})\b"  # Month YYYY/YY
    r"|"
    r"\b(\d{4})[/\-]([0-1]?\d)(?:[/\-]([0-3]?\d))?\b"     # ISO: YYYY-MM or YYYY-MM-DD
    r")",
    re.IGNORECASE,
)

# Email and Phone patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"(?:\+?91[\-\s]?)?[0-9]{3,5}[\-\s]?[0-9]{5,8}|\b1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b")


class ValidationResult(NamedTuple):
    is_valid: bool
    error_message: Optional[str] = None
    violation_type: Optional[ViolationType] = None


# =====================================================================
# 1. Address Validator (Rule 6(1)(a))
# =====================================================================


def validate_address(value: Optional[str]) -> ValidationResult:
    """Validate manufacturer / packer / importer address declaration."""
    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Manufacturer, packer, or importer name and address is missing.",
            violation_type=ViolationType.missing_declaration,
        )

    clean_val = value.strip()
    if len(clean_val) < 8:
        return ValidationResult(
            is_valid=False,
            error_message=f"Declared address '{clean_val}' is suspiciously short or incomplete.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 2. Country of Origin Validator (Rule 6(1)(aa))
# =====================================================================


def validate_country_of_origin(
    value: Optional[str],
    is_imported: bool = False,
) -> ValidationResult:
    """Validate country of origin for imported commodities."""
    if not is_imported:
        # Not statutory requirement for domestic product under Rule 6(1)(aa)
        return ValidationResult(is_valid=True)

    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Country of origin is mandatory for imported products under Rule 6(1)(aa).",
            violation_type=ViolationType.missing_declaration,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 3. Generic Commodity Name Validator (Rule 6(1)(b))
# =====================================================================


def validate_generic_name(value: Optional[str]) -> ValidationResult:
    """Validate common or generic commodity name declaration."""
    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Common or generic commodity name is missing under Rule 6(1)(b).",
            violation_type=ViolationType.missing_declaration,
        )

    clean_val = value.strip()
    if len(clean_val) < 2:
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid generic name '{clean_val}'.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 4. Net Quantity & Metric SI Units Validator (Rule 6(1)(c) & Rule 13)
# =====================================================================


def validate_net_quantity(
    value: Optional[str],
    normalized_value: Optional[str] = None,
) -> ValidationResult:
    """Validate net quantity and strictly enforce standard SI metric symbols."""
    text_to_check = (value or "") + " " + (normalized_value or "")
    if not text_to_check.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Net quantity declaration is missing under Rule 6(1)(c).",
            violation_type=ViolationType.missing_declaration,
        )

    # Check for prohibited legacy unit symbols
    prohibited_match = PROHIBITED_UNIT_PATTERN.search(text_to_check)
    if prohibited_match:
        illegal_unit = prohibited_match.group(1)
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Prohibited non-standard unit symbol '{illegal_unit}' used. "
                "Rule 13 and Third Schedule mandate standard SI symbols (e.g. 'g', 'kg', 'ml', 'l', 'N', 'U')."
            ),
            violation_type=ViolationType.invalid_unit,
        )

    # Check for valid numerical quantity + standard SI symbol
    if not VALID_METRIC_UNIT_PATTERN.search(text_to_check):
        # Also check if it's sold by number e.g. "10 units", "1 N"
        if not re.search(r"\b\d+\s*(?:units?|pieces?|N|U)\b", text_to_check, re.IGNORECASE):
            return ValidationResult(
                is_valid=False,
                error_message=f"Net quantity '{value}' lacks standard numerical quantity or valid SI metric unit.",
                violation_type=ViolationType.invalid_format,
            )

    return ValidationResult(is_valid=True)


def normalize_2digit_year(yy: int) -> int:
    """Normalize 2-digit year to 4-digit century (00-99 -> 2000-2099)."""
    return 2000 + yy if yy < 100 else yy


def _is_valid_date_format(text: str) -> bool:
    """Validate whether text contains a legitimate, real calendar date expression per FSSAI / Legal Metrology rules.

    Performs:
    1. Syntactic extraction matching authorized date-marking structures:
       - 3-part: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD/MM/YY, DD-MM-YY, DD.MM.YY
       - 2-part: MM/YYYY, MM-YYYY, MM.YYYY, MM/YY, MM-YY, MM.YY
       - Month name: Month YYYY, Month YY (e.g. 'Jan 2026', 'Sep 26', 'September 2026')
       - ISO format: YYYY-MM, YYYY-MM-DD, YYYY/MM/DD
    2. True calendar date validation using datetime.date:
       - Rejects impossible calendar dates (e.g. 31/02/26, 31/04/26, 29/02/25).
       - Validates leap years (e.g. 29/02/24 passes, 29/02/25 fails).
    """
    if not text or not text.strip():
        return False

    for match in DATE_PATTERN.finditer(text):
        groups = match.groups()
        # Group 1, 2, 3: 3-part (d, m, y)
        d_str, m_str, y_str = groups[0], groups[1], groups[2]
        if d_str is not None and m_str is not None and y_str is not None:
            try:
                d = int(d_str)
                m = int(m_str)
                raw_y = int(y_str)
                y = normalize_2digit_year(raw_y) if len(y_str) == 2 else raw_y
                if 1900 <= y <= 2099:
                    date(y, m, d)  # Validates actual calendar existence (leap years, month days)
                    return True
            except (ValueError, TypeError):
                pass

        # Group 4, 5: 2-part (m, y)
        m2_str, y2_str = groups[3], groups[4]
        if m2_str is not None and y2_str is not None:
            try:
                m2 = int(m2_str)
                raw_y2 = int(y2_str)
                y2 = normalize_2digit_year(raw_y2) if len(y2_str) == 2 else raw_y2
                if 1 <= m2 <= 12 and 1900 <= y2 <= 2099:
                    date(y2, m2, 1)
                    return True
            except (ValueError, TypeError):
                pass

        # Group 6: Named month year
        y3_str = groups[5]
        if y3_str is not None:
            try:
                raw_y3 = int(y3_str)
                y3 = normalize_2digit_year(raw_y3) if len(y3_str) == 2 else raw_y3
                if 1900 <= y3 <= 2099:
                    return True
            except (ValueError, TypeError):
                pass

        # Group 7, 8, 9: ISO (y, m, optional d)
        y4_str, m4_str, d4_str = groups[6], groups[7], groups[8]
        if y4_str is not None and m4_str is not None:
            try:
                y4 = int(y4_str)
                m4 = int(m4_str)
                if 1900 <= y4 <= 2099:
                    if d4_str is not None:
                        d4 = int(d4_str)
                        date(y4, m4, d4)
                        return True
                    else:
                        date(y4, m4, 1)
                        return True
            except (ValueError, TypeError):
                pass

    return False


# =====================================================================
# 5. Manufacture / Packing Date Validator (Rule 6(1)(d))
# =====================================================================


def validate_manufacture_date(
    value: Optional[str],
    normalized_value: Optional[str] = None,
) -> ValidationResult:
    """Validate month and year of manufacture, packing, or import."""
    text_to_check = (value or "") + " " + (normalized_value or "")
    if not text_to_check.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Month and year of manufacture/packing/import is missing under Rule 6(1)(d).",
            violation_type=ViolationType.missing_declaration,
        )

    if not _is_valid_date_format(text_to_check):
        return ValidationResult(
            is_valid=False,
            error_message=f"Manufacture date '{value}' is not in a valid MM/YYYY, DD/MM/YYYY, MM/YY, DD/MM/YY, or Month YYYY format.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 6. Maximum Retail Price (MRP) Validator (Rule 6(1)(e))
# =====================================================================


def validate_mrp(
    value: Optional[str],
    normalized_value: Optional[str] = None,
) -> ValidationResult:
    """Validate MRP format and mandatory 'inclusive of all taxes' statement."""
    text_to_check = (value or "") + " " + (normalized_value or "")
    if not text_to_check.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Maximum Retail Price (MRP) declaration is missing under Rule 6(1)(e).",
            violation_type=ViolationType.missing_declaration,
        )

    # Check for presence of price amount
    has_amount = re.search(r"\d+(?:\.\d{1,2})?", text_to_check)
    if not has_amount:
        return ValidationResult(
            is_valid=False,
            error_message=f"MRP declaration '{value}' contains no legible numerical price amount.",
            violation_type=ViolationType.invalid_format,
        )

    # Check mandatory tax clause: "inclusive of all taxes" or "incl. of all taxes"
    if not TAX_INCLUSION_PATTERN.search(text_to_check):
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"MRP declaration '{value}' is missing the mandatory phrase "
                "'inclusive of all taxes' or 'incl. of all taxes' mandated by Rule 6(1)(e)."
            ),
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 7. Unit Sale Price Validator (Rule 6(11))
# =====================================================================

MASS_GRAM_UNITS = {"g", "gm", "gms", "gram", "grams"}
MASS_KG_UNITS = {"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"}
MASS_MG_UNITS = {"mg", "milligram", "milligrams"}

VOL_ML_UNITS = {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}
VOL_L_UNITS = {"l", "lt", "ltr", "ltrs", "litre", "litres", "liter", "liters"}

LEN_CM_UNITS = {"cm", "centimetre", "centimetres", "centimeter", "centimeters"}
LEN_M_UNITS = {"m", "metre", "meter", "metres", "meters"}
LEN_MM_UNITS = {"mm", "millimetre", "millimeter", "millimetres", "millimeters"}

COUNT_UNITS = {
    "n", "u", "unit", "units", "piece", "pieces", "item", "items",
    "no", "nos", "pkt", "pkts", "pack", "packs", "sachet", "sachets",
    "wipe", "wipes", "tablet", "tablets", "capsule", "capsules",
}


def _parse_net_quantity_spec(text: Optional[str]) -> Optional[Tuple[Decimal, str, str]]:
    """Parse net quantity text into (normalized_magnitude, dimension_type, raw_unit).

    Dimensions:
    - 'mass': normalized to grams (Decimal)
    - 'volume': normalized to millilitres (Decimal)
    - 'length': normalized to centimetres (Decimal)
    - 'count': normalized to count (Decimal)
    """
    if not text or not text.strip():
        return None

    # Strip prefixes like 'Net Qty:', 'Net Wt:', 'Net Weight:', 'Quantity:'
    cleaned = re.sub(
        r"^(?:net\s*(?:qty|quantity|wt|weight|contents?)|qty|wt)\s*[:\-]?\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )

    # Match numeric value and following unit symbol
    match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z²³]+)", cleaned)
    if not match:
        return None

    try:
        val_dec = Decimal(match.group(1))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if val_dec <= Decimal("0"):
        return None

    raw_unit = match.group(2).lower()

    # Classify dimension and normalize to base unit
    if raw_unit in MASS_GRAM_UNITS:
        return val_dec, "mass", raw_unit
    elif raw_unit in MASS_KG_UNITS:
        return val_dec * Decimal("1000"), "mass", raw_unit
    elif raw_unit in MASS_MG_UNITS:
        return val_dec / Decimal("1000"), "mass", raw_unit
    elif raw_unit in VOL_ML_UNITS:
        return val_dec, "volume", raw_unit
    elif raw_unit in VOL_L_UNITS:
        return val_dec * Decimal("1000"), "volume", raw_unit
    elif raw_unit in LEN_CM_UNITS:
        return val_dec, "length", raw_unit
    elif raw_unit in LEN_M_UNITS:
        return val_dec * Decimal("100"), "length", raw_unit
    elif raw_unit in LEN_MM_UNITS:
        return val_dec / Decimal("10"), "length", raw_unit
    elif raw_unit in COUNT_UNITS:
        return val_dec, "count", raw_unit

    return None


def _parse_mrp_amount(text: Optional[str]) -> Optional[Decimal]:
    """Extract numeric MRP decimal value from MRP text."""
    if not text or not text.strip():
        return None

    # Search for currency pattern or decimal number
    match = re.search(r"(?:₹|rs\.?|inr|mrp)?\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if not match:
        return None

    raw_num = match.group(1).replace(",", "")
    try:
        val = Decimal(raw_num)
        return val if val > Decimal("0") else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_declared_usp(text: Optional[str]) -> Optional[Tuple[Decimal, str]]:
    """Parse declared Unit Sale Price into (rate_decimal, denominator_unit_str)."""
    if not text or not text.strip():
        return None

    cleaned = text.strip()
    # Match strings like '₹ 0.10 / g', 'Rs. 55.00 / kg', '0.50/g', '₹ 1.25 per N', 'Rs. 25 per piece'
    pattern = re.compile(
        r"(?:usp\s*[:\-]?)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:/|per|/-)\s*(?:1\s*)?([a-zA-Z²³]+)",
        re.IGNORECASE,
    )
    match = pattern.search(cleaned)
    if not match:
        return None

    raw_num = match.group(1).replace(",", "")
    unit_str = match.group(2).lower()
    try:
        rate = Decimal(raw_num)
        return rate, unit_str
    except (InvalidOperation, TypeError, ValueError):
        return None


def validate_unit_sale_price(
    value: Optional[str],
    net_qty_text: Optional[str] = None,
    mrp_text: Optional[str] = None,
    is_usp_applicable: bool = False,
) -> ValidationResult:
    """Validate Unit Sale Price under Rule 6(11).

    Checks:
    1. Statutory applicability (exempt packages pass cleanly).
    2. Presence of USP declaration when mandatory.
    3. Syntax & format validation.
    4. Statutory denominator validation (<1kg -> /g, >1kg -> /kg, <1L -> /ml, >1L -> /L, <1m -> /cm, >1m -> /m, count>1 -> /N or /unit).
    5. Mathematical cross-verification (declared rate vs expected rate = MRP / BaseQty with 2-decimal half-up rounding).
    """
    if not is_usp_applicable:
        return ValidationResult(is_valid=True)

    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Unit Sale Price is mandatory under Rule 6(11) for this package quantity but was not declared.",
            violation_type=ViolationType.missing_declaration,
        )

    parsed_usp = _parse_declared_usp(value)
    if not parsed_usp:
        return ValidationResult(
            is_valid=False,
            error_message=f"Unit Sale Price declaration '{value}' is not in the required '₹ xx.xx / unit' format.",
            violation_type=ViolationType.invalid_format,
        )

    declared_rate, declared_unit = parsed_usp

    # If Net Quantity text is available, perform denominator and calculation checks
    if net_qty_text and net_qty_text.strip():
        parsed_qty = _parse_net_quantity_spec(net_qty_text)
        if parsed_qty:
            norm_val, dim_type, _ = parsed_qty

            # 1. Denominator Compliance Check
            legal_unit_desc = ""
            divisor = Decimal("0")

            if dim_type == "mass":
                if norm_val < Decimal("1000"):
                    legal_unit_desc = "g"
                    divisor = norm_val
                    if declared_unit in MASS_KG_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per g' for net quantity < 1 kg (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in MASS_GRAM_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per g' for net quantity < 1 kg (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                elif norm_val > Decimal("1000"):
                    legal_unit_desc = "kg"
                    divisor = norm_val / Decimal("1000")
                    if declared_unit in (MASS_GRAM_UNITS | MASS_MG_UNITS):
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per kg' for net quantity > 1 kg (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in MASS_KG_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per kg' for net quantity > 1 kg (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                else:
                    # Exactly 1 kg (boundary exemption)
                    divisor = Decimal("1") if declared_unit in MASS_KG_UNITS else norm_val

            elif dim_type == "volume":
                if norm_val < Decimal("1000"):
                    legal_unit_desc = "ml"
                    divisor = norm_val
                    if declared_unit in VOL_L_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per ml' for net quantity < 1 L (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in VOL_ML_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per ml' for net quantity < 1 L (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                elif norm_val > Decimal("1000"):
                    legal_unit_desc = "L"
                    divisor = norm_val / Decimal("1000")
                    if declared_unit in VOL_ML_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per L' for net quantity > 1 L (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in VOL_L_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per L' for net quantity > 1 L (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                else:
                    # Exactly 1 L (boundary exemption)
                    divisor = Decimal("1") if declared_unit in VOL_L_UNITS else norm_val

            elif dim_type == "length":
                if norm_val < Decimal("100"):
                    legal_unit_desc = "cm"
                    divisor = norm_val
                    if declared_unit in LEN_M_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per cm' for net quantity < 1 m (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in LEN_CM_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per cm' for net quantity < 1 m (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                elif norm_val > Decimal("100"):
                    legal_unit_desc = "m"
                    divisor = norm_val / Decimal("100")
                    if declared_unit in (LEN_CM_UNITS | LEN_MM_UNITS):
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per m' for net quantity > 1 m (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                    elif declared_unit not in LEN_M_UNITS:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                                f"Mandatory denominator is 'per m' for net quantity > 1 m (declared: '{net_qty_text}')."
                            ),
                            violation_type=ViolationType.invalid_unit,
                        )
                else:
                    # Exactly 1 m (boundary exemption)
                    divisor = Decimal("1") if declared_unit in LEN_M_UNITS else norm_val

            elif dim_type == "count":
                legal_unit_desc = "number/unit"
                divisor = norm_val
                if declared_unit not in COUNT_UNITS:
                    return ValidationResult(
                        is_valid=False,
                        error_message=(
                            f"Declared Unit Sale Price denominator '{declared_unit}' violates Rule 6(11). "
                            f"Mandatory denominator is 'per number/unit/piece' for count commodity (declared: '{net_qty_text}')."
                        ),
                        violation_type=ViolationType.invalid_unit,
                    )

            # 2. Mathematical Cross-Verification Check
            if mrp_text and mrp_text.strip() and divisor > Decimal("0"):
                mrp_val = _parse_mrp_amount(mrp_text)
                if mrp_val and mrp_val > Decimal("0"):
                    expected_rate = (mrp_val / divisor).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    declared_rate_rounded = declared_rate.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    if declared_rate_rounded != expected_rate:
                        return ValidationResult(
                            is_valid=False,
                            error_message=(
                                f"Unit Sale Price '₹ {declared_rate}' does not match expected statutory rate "
                                f"'₹ {expected_rate:.2f}' calculated from MRP (₹ {mrp_val:.2f}) and Net Quantity "
                                f"({net_qty_text}) under Rule 6(11)."
                            ),
                            violation_type=ViolationType.misleading,
                        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 8. Batch / Lot Number Validator (Rule 6(1)(g))
# =====================================================================


def validate_batch_number(value: Optional[str]) -> ValidationResult:
    """Validate batch number or lot number declaration."""
    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Batch number, lot number, or code number is missing under Rule 6(1)(g).",
            violation_type=ViolationType.missing_declaration,
        )

    clean_val = value.strip()
    if len(clean_val) < 2:
        return ValidationResult(
            is_valid=False,
            error_message=f"Batch number '{clean_val}' is invalid or too short.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 9. Expiry Date Validator (Rule 6(1)(m))
# =====================================================================


def validate_expiry_date(
    expiry_val: Optional[str],
    mfd_val: Optional[str] = None,
    is_perishable: bool = True,
) -> ValidationResult:
    """Validate expiry / best before date for perishable commodities."""
    if not is_perishable:
        return ValidationResult(is_valid=True)

    if not expiry_val or not expiry_val.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Best before or expiry date is mandatory for perishable goods under Rule 6(1)(m).",
            violation_type=ViolationType.missing_declaration,
        )

    if not _is_valid_date_format(expiry_val):
        return ValidationResult(
            is_valid=False,
            error_message=f"Expiry date '{expiry_val}' is not in a valid date format.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 10. Consumer Care Details Validator (Rule 6(1)(n))
# =====================================================================


def validate_consumer_care(value: Optional[str]) -> ValidationResult:
    """Validate consumer care contact details (phone, email, or contact cell)."""
    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Consumer care contact details are missing under Rule 6(1)(n).",
            violation_type=ViolationType.missing_declaration,
        )

    text = value.strip()
    has_phone = bool(PHONE_PATTERN.search(text))
    has_email = bool(EMAIL_PATTERN.search(text))
    has_address = len(text) >= 12

    if not (has_phone or has_email or has_address):
        return ValidationResult(
            is_valid=False,
            error_message=f"Consumer care declaration '{value}' lacks telephone number, email, or contact address.",
            violation_type=ViolationType.invalid_format,
        )

    return ValidationResult(is_valid=True)


# =====================================================================
# 11. Rule 26 Small Package Exemption Helper
# =====================================================================


def check_rule26_exemption(
    net_quantity_text: Optional[str],
    category: Optional[str] = None,
) -> bool:
    """Check if package qualifies for Rule 26(a) exemption (<= 10g or <= 10ml, non-tobacco)."""
    if not net_quantity_text:
        return False

    # Proviso exception: Tobacco products are NEVER exempt under Rule 26(a)
    cat_lower = (category or "").lower()
    if any(tobacco_term in cat_lower for tobacco_term in ("tobacco", "cigarette", "beedi", "bidi", "cigar")):
        return False

    # Extract numerical weight/volume
    match = re.search(r"(\d+(?:\.\d+)?)\s*(g|gm|gms|ml|grm)\b", net_quantity_text, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        if val <= 10.0:
            return True

    return False
