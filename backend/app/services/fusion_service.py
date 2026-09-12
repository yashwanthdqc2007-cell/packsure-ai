"""
PackSure AI — Multi-View Package Inspection Evidence Fusion Service.

Implements deterministic declaration fusion across multiple packaging views (e.g., Front, Back, Side).

Core Architectural Invariants:
1. Deduplication: Consistent observations of the same field across views are merged without duplicate penalty.
2. Provenance Preservation: Each fused declaration retains the originating image index, image name, and bounding box.
3. Conflict Detection: Conflicting observations across views (e.g., mismatched MRPs or Batch numbers)
   are never silently overwritten; they are marked UNCERTAIN and produce a NEEDS_REVIEW conflict condition.
4. Absence Semantics: Absence in View 1 does not mean missing from the package if present in View 2.
5. Separation of Concerns: AI extracts evidence per view; Fusion combines evidence; Deterministic RuleEngine alone determines legal compliance.
"""

from decimal import Decimal, InvalidOperation
import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.violation import Violation, ViolationSeverity, ViolationType

logger = logging.getLogger(__name__)


def _clean_str(text: Optional[str]) -> str:
    """Normalize string by lowercasing, collapsing whitespace, and stripping outer punctuation."""
    if not text:
        return ""
    # Remove redundant whitespace
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return cleaned


def _extract_numeric_amount(text: Optional[str]) -> Optional[Decimal]:
    """Extract primary numeric amount (e.g. for MRP currency values)."""
    if not text:
        return None
    match = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None


def are_declarations_consistent(
    field_name: str,
    decl1: ExtractedDeclaration,
    decl2: ExtractedDeclaration,
) -> bool:
    """Determine whether two extracted declarations for the same field are consistent or conflicting.

    Args:
        field_name: Canonical field name.
        decl1: First declaration.
        decl2: Second declaration.

    Returns:
        True if the declarations are consistent/complementary; False if they are in direct conflict.
    """
    val1 = (decl1.normalized_value or decl1.raw_value or "").strip()
    val2 = (decl2.normalized_value or decl2.raw_value or "").strip()

    # If either value is empty or uncertain, they don't form a definitive conflict
    if not val1 or not val2:
        return True

    clean1 = _clean_str(val1)
    clean2 = _clean_str(val2)

    # Exact normalized text match
    if clean1 == clean2:
        return True

    # Numeric fields: MRP
    if field_name == "mrp":
        num1 = _extract_numeric_amount(val1)
        num2 = _extract_numeric_amount(val2)
        if num1 is not None and num2 is not None:
            return num1 == num2
        return clean1 == clean2

    # Unit Sale Price
    if field_name == "unit_sale_price":
        # Check if same rate and unit
        num1 = _extract_numeric_amount(val1)
        num2 = _extract_numeric_amount(val2)
        if num1 is not None and num2 is not None and num1 != num2:
            return False
        # Remove currency symbols and whitespace
        s1 = re.sub(r"[₹rs\.inr\s]", "", clean1)
        s2 = re.sub(r"[₹rs\.inr\s]", "", clean2)
        return s1 == s2 or clean1 in clean2 or clean2 in clean1

    # Net Quantity
    if field_name == "net_quantity":
        num1 = _extract_numeric_amount(val1)
        num2 = _extract_numeric_amount(val2)
        if num1 is not None and num2 is not None and num1 != num2:
            # Different numbers: check unit conversions e.g. 1 kg vs 1000 g
            # For simplicity, if numbers differ and clean strings differ, mark conflict
            return False
        return clean1 in clean2 or clean2 in clean1

    # Text fields: Address, Manufacturer, Generic Name, Consumer Care
    if field_name in (
        "manufacturer_name_and_address",
        "generic_name",
        "consumer_care",
        "country_of_origin",
    ):
        # Substring containment (e.g. brand name on front, full address on back)
        if clean1 in clean2 or clean2 in clean1:
            return True
        # Strip common punctuation and test word overlap
        words1 = set(re.findall(r"\w+", clean1))
        words2 = set(re.findall(r"\w+", clean2))
        if words1 and words2:
            overlap = len(words1 & words2) / min(len(words1), len(words2))
            if overlap >= 0.7:
                return True

    # Date fields
    if field_name in ("manufacture_date", "expiry_date"):
        # Match YYYY-MM or YYYY
        digits1 = re.findall(r"\d+", clean1)
        digits2 = re.findall(r"\d+", clean2)
        if digits1 and digits2 and digits1 == digits2:
            return True
        return clean1 in clean2 or clean2 in clean1

    # Batch number
    if field_name == "batch_number":
        # Exact alphanumeric match ignoring spaces/hyphens
        alphanumeric1 = re.sub(r"[^a-zA-Z0-9]", "", clean1)
        alphanumeric2 = re.sub(r"[^a-zA-Z0-9]", "", clean2)
        return alphanumeric1 == alphanumeric2 or clean1 in clean2 or clean2 in clean1

    return False


def _select_best_declaration(
    declarations: List[ExtractedDeclaration],
) -> ExtractedDeclaration:
    """Select the most authoritative declaration from a set of consistent observations."""
    if not declarations:
        raise ValueError("Cannot select from empty declarations list.")

    if len(declarations) == 1:
        return declarations[0]

    # Preference ranking:
    # 1. Detected status over uncertain/missing
    # 2. Confidence score (higher is better)
    # 3. Completeness of raw_value (longer is usually more detailed)
    # 4. Presence of bounding box

    def sort_key(d: ExtractedDeclaration):
        status_score = 2 if d.status == DeclarationStatus.detected else (1 if d.status == DeclarationStatus.uncertain else 0)
        conf = d.confidence if d.confidence is not None else 0.0
        val_len = len(d.raw_value or "")
        has_box = 1 if d.bounding_box is not None else 0
        return (status_score, conf, has_box, val_len)

    sorted_decls = sorted(declarations, key=sort_key, reverse=True)
    return sorted_decls[0]


def fuse_declarations(
    views_declarations: Sequence[Sequence[ExtractedDeclaration]],
) -> Tuple[List[ExtractedDeclaration], List[Violation]]:
    """Fuse declaration observations from multiple package views into a unified declaration set.

    Args:
        views_declarations: Sequence of ExtractedDeclaration lists, one list per package view.

    Returns:
        Tuple of:
        - fused_declarations: Combined, deduplicated list of ExtractedDeclaration domain models.
        - conflict_violations: Any identified cross-view conflict violations requiring manual review.
    """
    # Group observations by field_name across all views
    grouped: Dict[str, List[ExtractedDeclaration]] = {}
    for view_idx, view_list in enumerate(views_declarations):
        for decl in view_list:
            if not decl.field_name:
                continue
            # Ensure provenance is attached if missing
            if decl.image_index is None:
                decl = decl.model_copy(update={"image_index": view_idx})
            grouped.setdefault(decl.field_name, []).append(decl)

    fused: List[ExtractedDeclaration] = []
    conflict_violations: List[Violation] = []

    for field_name, decls in grouped.items():
        # Filter only observations that have content or detected status
        active_decls = [d for d in decls if d.status != DeclarationStatus.missing and (d.raw_value or d.normalized_value)]

        if not active_decls:
            # All observations were missing/empty
            best = _select_best_declaration(decls)
            fused.append(best)
            continue

        if len(active_decls) == 1:
            # Single view observation: retain cleanly with original provenance
            fused.append(active_decls[0])
            continue

        # Multiple views observed this field: check pairwise consistency
        has_conflict = False
        conflicting_pair = None
        for i in range(len(active_decls)):
            for j in range(i + 1, len(active_decls)):
                d1 = active_decls[i]
                d2 = active_decls[j]
                if not are_declarations_consistent(field_name, d1, d2):
                    has_conflict = True
                    conflicting_pair = (d1, d2)
                    break
            if has_conflict:
                break

        if not has_conflict:
            # All observations are consistent: deduplicate to the best one
            best_decl = _select_best_declaration(active_decls)
            fused.append(best_decl)
        else:
            # Cross-view conflict detected!
            d1, d2 = conflicting_pair
            v1_idx = d1.image_index if d1.image_index is not None else 0
            v2_idx = d2.image_index if d2.image_index is not None else 1
            val1 = d1.normalized_value or d1.raw_value
            val2 = d2.normalized_value or d2.raw_value

            conflict_desc = (
                f"Conflicting values detected for '{field_name}' across package views: "
                f"View {v1_idx} declared '{val1}' vs View {v2_idx} declared '{val2}'. "
                "Requires manual inspector resolution."
            )
            logger.warning(f"Evidence fusion conflict: {conflict_desc}")

            # Mark the fused declaration as UNCERTAIN so compliance fails safe to NEEDS_REVIEW
            conflict_decl = ExtractedDeclaration(
                field_name=field_name,
                status=DeclarationStatus.uncertain,
                raw_value=f"Conflict between View {v1_idx} ('{val1}') and View {v2_idx} ('{val2}')",
                normalized_value=None,
                confidence=min(d1.confidence or 0.5, d2.confidence or 0.5),
                bounding_box=d1.bounding_box or d2.bounding_box,
                source=DeclarationSource.hybrid,
                image_index=d1.image_index,
                image_name=d1.image_name,
            )
            fused.append(conflict_decl)

            conflict_violations.append(
                Violation(
                    rule_code="CONFLICT-NEEDS-REVIEW",
                    field_name=field_name,
                    violation_type=ViolationType.other,
                    severity=ViolationSeverity.major,
                    description=conflict_desc,
                )
            )

    return fused, conflict_violations
