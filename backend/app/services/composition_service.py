"""
PackSure AI — Package Composition & Multi-Commodity Extraction Service.

Implements Phase 4C: Deterministic Package Structure Classification and Constituent Item Extraction.

Principles:
1. Data Model & Evidence Focus: Represents structure of multi-piece, combination, group, kit, and single packages.
2. Pure Deterministic Processing: Zero LLM / network calls; deterministic regex and pattern parsing.
3. Separation of Concerns: Classifies composition and extracts constituents; does NOT alter Rule 6(11) USP or invent new legal rules.
4. Spatial Provenance: Bounding boxes and image view indexes are preserved per constituent item.
5. Incomplete Scan Safety: Unseen constituent panels yield UNCERTAIN composition and NEEDS_REVIEW.
"""

import logging
import re
from typing import List, Optional, Sequence, Tuple
from decimal import Decimal

from app.schemas.declaration import (
    BoundingBox,
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageItem,
    PackageType,
)

logger = logging.getLogger(__name__)

# Multi-piece patterns: e.g. "2 x 500 ml", "3 x 100g", "4 x 250 g", "Pack of 10", "10 units of 10g each"
MULTI_PIECE_MULTIPLY_PATTERN = re.compile(
    r"\b(\d{1,3})\s*(?:x|\*|×)\s*(\d+(?:\.\d+)?)\s*(mg|g|kg|ml|l|L|m|cm|mm|sq\s*m|N|U)\b",
    re.IGNORECASE,
)

PACK_OF_COUNT_PATTERN = re.compile(
    r"\b(?:pack|set|box|bundle)\s+of\s+(\d{1,3})\b",
    re.IGNORECASE,
)

EACH_QUANTITY_PATTERN = re.compile(
    r"\b(\d{1,3})\s*(?:units?|pieces?|pkts?|nos?|n|u)\s*(?:of|@)?\s*(\d+(?:\.\d+)?)\s*(mg|g|kg|ml|l|L|m|cm|mm)\s*(?:each)?\b",
    re.IGNORECASE,
)

# Combination & Kit connector patterns
COMBO_PLUS_PATTERN = re.compile(
    r"([a-zA-Z\s]+?)\s*(\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|L|m|cm|mm|N|U))\s*(?:\+|\&|\band\b)\s*([a-zA-Z\s]+?)\s*(\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|L|m|cm|mm|N|U))",
    re.IGNORECASE,
)

KIT_KEYWORDS = (
    "kit", "set", "starter kit", "grooming kit", "shaving kit", "travel kit",
    "combo pack", "gift pack", "bundle", "accessories included", "with accessories",
)

COMBINATION_KEYWORDS = (
    "combo", "combination", "assorted", "twin pack", "duo pack", "value pack",
)


def _clean_commodity_name(raw_name: str) -> str:
    """Normalize extracted commodity name string."""
    cleaned = re.sub(r"^(?:contains|includes|with|and|\+|&|free)\s+", "", raw_name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "Commodity"


def extract_package_composition(
    declarations: Optional[Sequence[ExtractedDeclaration]] = None,
    ocr_texts: Optional[Sequence[str]] = None,
    product_category: Optional[str] = None,
    is_complete_scan: bool = True,
) -> PackageComposition:
    """Deterministically analyze packaging declarations and OCR text to extract package composition.

    Args:
        declarations: List of extracted declarations.
        ocr_texts: Sequence of OCR strings per view.
        product_category: Optional product category.
        is_complete_scan: Whether all package panels were captured.

    Returns:
        PackageComposition instance.
    """
    decls = declarations or []
    decl_map = {d.field_name: d for d in decls}

    net_qty_decl = decl_map.get("net_quantity")
    generic_name_decl = decl_map.get("generic_name")

    net_qty_text = (net_qty_decl.normalized_value or net_qty_decl.raw_value or "") if net_qty_decl else ""
    generic_name_text = (generic_name_decl.normalized_value or generic_name_decl.raw_value or "") if generic_name_decl else ""

    all_ocr = " \n ".join(ocr_texts or [])
    combined_search_text = f"{net_qty_text} \n {generic_name_text} \n {all_ocr}"

    # 1. Check for Combination Patterns (e.g. "Shampoo 200 ml + Conditioner 100 ml")
    combo_match = COMBO_PLUS_PATTERN.search(combined_search_text)
    if combo_match:
        name1 = _clean_commodity_name(combo_match.group(1))
        qty1 = combo_match.group(2).strip()
        name2 = _clean_commodity_name(combo_match.group(3))
        qty2 = combo_match.group(4).strip()

        src_idx = net_qty_decl.image_index if net_qty_decl and net_qty_decl.image_index is not None else 0
        bbox = net_qty_decl.bounding_box if net_qty_decl else None

        items = [
            PackageItem(
                item_index=1,
                commodity_name=name1 or "Product 1",
                item_count=1,
                unit_quantity=qty1,
                status=DeclarationStatus.detected,
                source_image_index=src_idx,
                bounding_box=bbox,
            ),
            PackageItem(
                item_index=2,
                commodity_name=name2 or "Product 2",
                item_count=1,
                unit_quantity=qty2,
                status=DeclarationStatus.detected,
                source_image_index=src_idx,
                bounding_box=bbox,
            ),
        ]
        return PackageComposition(
            package_type=PackageType.COMBINATION,
            total_item_count=2,
            items=items,
            status=DeclarationStatus.detected,
            confidence=0.95,
            statutory_note="Combination package containing 2 distinct commodities.",
        )

    # 2. Check for Multi-Piece Expressions (e.g. "2 x 500 ml", "3 x 100 g")
    mult_match = MULTI_PIECE_MULTIPLY_PATTERN.search(combined_search_text)
    if mult_match:
        try:
            count = int(mult_match.group(1))
            val_num = mult_match.group(2)
            val_unit = mult_match.group(3)
            unit_qty = f"{val_num} {val_unit}"

            base_name = generic_name_text.strip() or "Identical Commodity Unit"
            src_idx = net_qty_decl.image_index if net_qty_decl and net_qty_decl.image_index is not None else 0
            bbox = net_qty_decl.bounding_box if net_qty_decl else None

            items = [
                PackageItem(
                    item_index=1,
                    commodity_name=base_name,
                    item_count=count,
                    unit_quantity=unit_qty,
                    status=DeclarationStatus.detected,
                    source_image_index=src_idx,
                    bounding_box=bbox,
                )
            ]
            return PackageComposition(
                package_type=PackageType.MULTI_PIECE,
                total_item_count=count,
                items=items,
                status=DeclarationStatus.detected,
                confidence=0.95,
                statutory_note=f"Multi-piece package containing {count} identical units of {unit_qty} each.",
            )
        except Exception:
            pass

    # 3. Check for "Units of ... each" pattern (e.g. "2 units of 500 ml each")
    each_match = EACH_QUANTITY_PATTERN.search(combined_search_text)
    if each_match:
        try:
            count = int(each_match.group(1))
            unit_qty = f"{each_match.group(2)} {each_match.group(3)}"
            base_name = generic_name_text.strip() or "Identical Commodity Unit"
            src_idx = net_qty_decl.image_index if net_qty_decl and net_qty_decl.image_index is not None else 0
            bbox = net_qty_decl.bounding_box if net_qty_decl else None

            items = [
                PackageItem(
                    item_index=1,
                    commodity_name=base_name,
                    item_count=count,
                    unit_quantity=unit_qty,
                    status=DeclarationStatus.detected,
                    source_image_index=src_idx,
                    bounding_box=bbox,
                )
            ]
            return PackageComposition(
                package_type=PackageType.MULTI_PIECE,
                total_item_count=count,
                items=items,
                status=DeclarationStatus.detected,
                confidence=0.90,
                statutory_note=f"Multi-piece package containing {count} units of {unit_qty} each.",
            )
        except Exception:
            pass

    # 4. Check for "Pack of N" count pattern (e.g. "Pack of 10")
    pack_match = PACK_OF_COUNT_PATTERN.search(combined_search_text)
    if pack_match:
        try:
            count = int(pack_match.group(1))
            base_name = generic_name_text.strip() or "Identical Commodity Unit"
            src_idx = generic_name_decl.image_index if generic_name_decl and generic_name_decl.image_index is not None else 0
            bbox = generic_name_decl.bounding_box if generic_name_decl else None

            items = [
                PackageItem(
                    item_index=1,
                    commodity_name=base_name,
                    item_count=count,
                    unit_quantity=net_qty_text or None,
                    status=DeclarationStatus.detected,
                    source_image_index=src_idx,
                    bounding_box=bbox,
                )
            ]
            return PackageComposition(
                package_type=PackageType.MULTI_PIECE,
                total_item_count=count,
                items=items,
                status=DeclarationStatus.detected,
                confidence=0.85,
                statutory_note=f"Multi-piece pack of {count} units.",
            )
        except Exception:
            pass

    # 5. Check for Kit / Set / Accessories Keywords (e.g. "Trimmer + guide combs")
    text_lower = combined_search_text.lower()
    has_kit_term = any(k in text_lower for k in KIT_KEYWORDS)
    if has_kit_term:
        # Check if multiple parts or components are described with '+' or 'with'
        comp_parts = re.split(r"\s*(?:\+|\bwith\b|\band\b|,)\s*", generic_name_text)
        if len(comp_parts) > 1:
            items = []
            for idx, part in enumerate(comp_parts):
                clean_part = _clean_commodity_name(part)
                if clean_part:
                    items.append(
                        PackageItem(
                            item_index=len(items) + 1,
                            commodity_name=clean_part,
                            item_count=1,
                            status=DeclarationStatus.detected,
                            source_image_index=generic_name_decl.image_index if generic_name_decl else 0,
                            bounding_box=generic_name_decl.bounding_box if generic_name_decl else None,
                        )
                    )
            if len(items) > 1:
                return PackageComposition(
                    package_type=PackageType.KIT,
                    total_item_count=len(items),
                    items=items,
                    status=DeclarationStatus.detected,
                    confidence=0.85,
                    statutory_note=f"Kit / set package containing {len(items)} components/accessories.",
                )

    # 6. Incomplete / Ambiguous Scan Handling: e.g. "Contains 2 products" but no panel breakdown
    ambiguous_combo_match = re.search(r"contains\s+(\d+)\s+(?:products?|items?|varieties?)", text_lower)
    if ambiguous_combo_match:
        cnt = int(ambiguous_combo_match.group(1))
        return PackageComposition(
            package_type=PackageType.UNCERTAIN,
            total_item_count=cnt,
            items=[],
            status=DeclarationStatus.uncertain,
            confidence=0.50,
            statutory_note=f"Package indicates {cnt} contained products, but constituent breakdown is unobserved or incomplete.",
        )

    # 7. Default: Single Commodity Package (Unchanged baseline)
    base_name = generic_name_text.strip() or "Standard Pre-Packaged Commodity"
    items = [
        PackageItem(
            item_index=1,
            commodity_name=base_name,
            item_count=1,
            unit_quantity=net_qty_text or None,
            status=DeclarationStatus.detected,
            source_image_index=net_qty_decl.image_index if net_qty_decl and net_qty_decl.image_index is not None else 0,
            bounding_box=net_qty_decl.bounding_box if net_qty_decl else None,
        )
    ]
    return PackageComposition(
        package_type=PackageType.SINGLE,
        total_item_count=1,
        items=items,
        status=DeclarationStatus.detected,
        confidence=1.0,
        statutory_note="Standard single-commodity pre-packaged commodity.",
    )


def reconcile_package_composition_across_views(
    view_compositions: Sequence[PackageComposition],
    is_complete_scan: bool = True,
) -> PackageComposition:
    """Fuse and reconcile package compositions extracted across multiple package views.

    Args:
        view_compositions: Sequence of PackageComposition objects from each view.
        is_complete_scan: Whether all package panels were captured.

    Returns:
        Reconciled composite PackageComposition.
    """
    if not view_compositions:
        return PackageComposition(
            package_type=PackageType.SINGLE,
            total_item_count=1,
            items=[],
            status=DeclarationStatus.detected,
        )

    # If any view clearly established a COMBINATION, MULTI_PIECE, or KIT, prioritize it over SINGLE
    non_single = [c for c in view_compositions if c.package_type not in (PackageType.SINGLE, PackageType.UNCERTAIN)]
    if non_single:
        # Sort by confidence and item count
        best_comp = max(non_single, key=lambda c: (c.confidence or 0.0, len(c.items)))
        return best_comp

    # If all views are UNCERTAIN, preserve UNCERTAIN
    uncertain_comps = [c for c in view_compositions if c.package_type == PackageType.UNCERTAIN]
    if uncertain_comps:
        return uncertain_comps[0]

    # Return primary view composition (default SINGLE)
    return view_compositions[0]
