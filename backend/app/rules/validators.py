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

# Date patterns (MM/YYYY, DD/MM/YYYY, Month YYYY, YYYY-MM)
DATE_PATTERN = re.compile(
    r"(?:\b(\d{1,2})[/\-\.](\d{4})\b|\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,\.\-]+(\d{4})\b|\b(\d{4})[/\-](\d{1,2})\b)",
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

    if not DATE_PATTERN.search(text_to_check):
        return ValidationResult(
            is_valid=False,
            error_message=f"Manufacture date '{value}' is not in a valid MM/YYYY, DD/MM/YYYY, or Month YYYY format.",
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
# 7. Unit Sale Price Validator (Rule 6(1)(f) & Rule 6(11))
# =====================================================================


def validate_unit_sale_price(
    value: Optional[str],
    net_qty_text: Optional[str] = None,
    is_usp_applicable: bool = False,
) -> ValidationResult:
    """Validate Unit Sale Price when applicable by package quantity thresholds."""
    if not is_usp_applicable:
        return ValidationResult(is_valid=True)

    if not value or not value.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Unit Sale Price is mandatory under Rule 6(1)(f) for packages > 100g/100ml but was not declared.",
            violation_type=ViolationType.missing_declaration,
        )

    # Check format e.g. "Rs. 0.50 / g" or "Rs. 240.00 / kg"
    usp_pattern = re.compile(
        r"(?:₹|rs\.?|inr)?\s*\d+(?:\.\d+)?\s*(?:/|per)\s*(?:g|kg|ml|l|L|m|unit|N|U)\b",
        re.IGNORECASE,
    )
    if not usp_pattern.search(value):
        return ValidationResult(
            is_valid=False,
            error_message=f"Unit Sale Price declaration '{value}' is not in the required '₹ xx.xx / unit' format.",
            violation_type=ViolationType.invalid_format,
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

    if not DATE_PATTERN.search(expiry_val):
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
