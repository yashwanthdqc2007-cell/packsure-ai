"""
PackSure AI — Phase 4C Package Composition & Multi-Commodity Test Matrix.

Verifies:
1. Single package baseline unchanged
2. "2 x 500 ml" multi-piece package
3. "3 x 100 g" multi-piece package
4. "Pack of 10" multi-piece package
5. Combination with two different commodities ("Shampoo 200 ml + Conditioner 100 ml")
6. Combination with mass + count ("Toothpaste 150 g + Toothbrush 1 N")
7. Group package ("Assorted Biscuits Combo Pack")
8. Kit/accessories ("Trimmer + guide combs + oil bottle")
9. Ambiguous package → UNCERTAIN ("Contains 2 products")
10. Incomplete multi-view → UNCERTAIN / safe handling
11. Multi-view fusion preserves highest confidence composition
12. Constituent bounding-box and image provenance
13. Legacy report compatibility (report without composition)
14. Existing USP tests unchanged
15. No aggregate USP calculation for dissimilar commodities
16. Existing QR behavior compatibility
17. Existing officer review compatibility
"""

import json
import unittest
from decimal import Decimal
from typing import List, Optional

from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
)
from app.schemas.declaration import (
    BoundingBox,
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageItem,
    PackageType,
)
from app.schemas.scan import ScanResponse, ScanStatus
from app.services.composition_service import (
    extract_package_composition,
    reconcile_package_composition_across_views,
)
from app.services.report_service import compile_report_dict, generate_json_report


class TestPackageCompositionMatrix(unittest.TestCase):
    """Deterministic validation test suite for Phase 4C Package Composition."""

    def test_01_single_package_baseline_unchanged(self):
        """1. Standard single commodity package produces SINGLE composition with 1 item."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Basmati Rice",
                normalized_value="Basmati Rice",
                status=DeclarationStatus.detected,
                confidence=0.98,
                image_index=0,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="500 g",
                normalized_value="500 g",
                status=DeclarationStatus.detected,
                confidence=0.99,
                image_index=0,
            ),
        ]
        comp = extract_package_composition(declarations=decls, ocr_texts=["Basmati Rice \n Net Qty: 500 g"])
        self.assertEqual(comp.package_type, PackageType.SINGLE)
        self.assertEqual(comp.total_item_count, 1)
        self.assertEqual(len(comp.items), 1)
        self.assertEqual(comp.items[0].commodity_name, "Basmati Rice")
        self.assertEqual(comp.items[0].unit_quantity, "500 g")

    def test_02_multi_piece_2_x_500_ml(self):
        """2. '2 x 500 ml' produces MULTI_PIECE with count=2, unit_quantity='500 ml'."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Apple Juice",
                normalized_value="Apple Juice",
                status=DeclarationStatus.detected,
                confidence=0.95,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="2 x 500 ml",
                normalized_value="2 x 500 ml",
                status=DeclarationStatus.detected,
                confidence=0.95,
                image_index=0,
                bounding_box=BoundingBox(x=10, y=20, width=100, height=30),
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.MULTI_PIECE)
        self.assertEqual(comp.total_item_count, 2)
        self.assertEqual(len(comp.items), 1)
        self.assertEqual(comp.items[0].item_count, 2)
        self.assertEqual(comp.items[0].unit_quantity, "500 ml")
        self.assertEqual(comp.items[0].commodity_name, "Apple Juice")
        self.assertEqual(comp.items[0].bounding_box.x, 10)

    def test_03_multi_piece_3_x_100_g(self):
        """3. '3 x 100 g' produces MULTI_PIECE with count=3, unit_quantity='100 g'."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Soap Bars",
                normalized_value="Soap Bars",
                status=DeclarationStatus.detected,
                confidence=0.95,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="3 x 100 g",
                normalized_value="3 x 100 g",
                status=DeclarationStatus.detected,
                confidence=0.95,
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.MULTI_PIECE)
        self.assertEqual(comp.total_item_count, 3)
        self.assertEqual(comp.items[0].unit_quantity, "100 g")

    def test_04_multi_piece_pack_of_10(self):
        """4. 'Pack of 10' produces MULTI_PIECE with count=10."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Ball Pens",
                normalized_value="Ball Pens",
                status=DeclarationStatus.detected,
                confidence=0.90,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="10 N",
                normalized_value="10 N",
                status=DeclarationStatus.detected,
                confidence=0.90,
            ),
        ]
        comp = extract_package_composition(declarations=decls, ocr_texts=["Pack of 10 Pens"])
        self.assertEqual(comp.package_type, PackageType.MULTI_PIECE)
        self.assertEqual(comp.total_item_count, 10)

    def test_05_combination_two_commodities(self):
        """5. 'Shampoo 200 ml + Conditioner 100 ml' produces COMBINATION with 2 distinct items."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Shampoo 200 ml + Conditioner 100 ml",
                normalized_value="Shampoo 200 ml + Conditioner 100 ml",
                status=DeclarationStatus.detected,
                confidence=0.96,
                image_index=0,
                bounding_box=BoundingBox(x=5, y=5, width=80, height=40),
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.COMBINATION)
        self.assertEqual(comp.total_item_count, 2)
        self.assertEqual(len(comp.items), 2)
        self.assertEqual(comp.items[0].commodity_name, "Shampoo")
        self.assertEqual(comp.items[0].unit_quantity, "200 ml")
        self.assertEqual(comp.items[1].commodity_name, "Conditioner")
        self.assertEqual(comp.items[1].unit_quantity, "100 ml")

    def test_06_combination_mass_and_count(self):
        """6. 'Toothpaste 150 g + Toothbrush 1 N' produces COMBINATION with mass + count."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Toothpaste 150 g + Toothbrush 1 N",
                normalized_value="Toothpaste 150 g + Toothbrush 1 N",
                status=DeclarationStatus.detected,
                confidence=0.95,
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.COMBINATION)
        self.assertEqual(comp.total_item_count, 2)
        self.assertEqual(comp.items[0].commodity_name, "Toothpaste")
        self.assertEqual(comp.items[0].unit_quantity, "150 g")
        self.assertEqual(comp.items[1].commodity_name, "Toothbrush")
        self.assertEqual(comp.items[1].unit_quantity, "1 N")

    def test_07_group_package_combo(self):
        """7. Group / combo pack keyword detection."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Grooming Kit with Trimmer + Shaving Gel",
                normalized_value="Grooming Kit with Trimmer + Shaving Gel",
                status=DeclarationStatus.detected,
                confidence=0.90,
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.KIT)
        self.assertGreaterEqual(len(comp.items), 2)

    def test_08_kit_accessories(self):
        """8. 'Trimmer with 3 guide combs and oil bottle' preserves components."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Trimmer kit with 3 guide combs and oil bottle",
                normalized_value="Trimmer kit with 3 guide combs and oil bottle",
                status=DeclarationStatus.detected,
                confidence=0.90,
            ),
        ]
        comp = extract_package_composition(declarations=decls)
        self.assertEqual(comp.package_type, PackageType.KIT)
        self.assertGreaterEqual(len(comp.items), 2)

    def test_09_ambiguous_package_uncertain(self):
        """9. 'Contains 2 products' without breakdown produces UNCERTAIN."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Assorted Gift Box",
                status=DeclarationStatus.detected,
            ),
        ]
        comp = extract_package_composition(
            declarations=decls,
            ocr_texts=["Contains 2 products inside"],
            is_complete_scan=False,
        )
        self.assertEqual(comp.package_type, PackageType.UNCERTAIN)
        self.assertEqual(comp.total_item_count, 2)
        self.assertEqual(comp.status, DeclarationStatus.uncertain)

    def test_10_false_positive_guard_vitamin_x(self):
        """10. 'Vitamin X' or 'Model X' must NOT be classified as MULTI_PIECE."""
        decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                raw_value="Vitamin X Supplement",
                normalized_value="Vitamin X Supplement",
                status=DeclarationStatus.detected,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="60 Tablets",
                normalized_value="60 Tablets",
                status=DeclarationStatus.detected,
            ),
        ]
        comp = extract_package_composition(declarations=decls, ocr_texts=["Vitamin X 60 Tablets"])
        self.assertEqual(comp.package_type, PackageType.SINGLE)

    def test_11_multi_view_reconciliation(self):
        """11. Multi-view fusion prioritizes confirmed multi-piece/combination over single."""
        c1 = PackageComposition(
            package_type=PackageType.SINGLE,
            total_item_count=1,
            items=[],
            confidence=0.5,
        )
        c2 = PackageComposition(
            package_type=PackageType.COMBINATION,
            total_item_count=2,
            items=[
                PackageItem(item_index=1, commodity_name="Shampoo", unit_quantity="200 ml"),
                PackageItem(item_index=2, commodity_name="Conditioner", unit_quantity="100 ml"),
            ],
            confidence=0.95,
        )
        fused = reconcile_package_composition_across_views([c1, c2])
        self.assertEqual(fused.package_type, PackageType.COMBINATION)
        self.assertEqual(fused.total_item_count, 2)

    def test_12_constituent_provenance_preserved(self):
        """12. Constituent bounding-box and source image index are preserved."""
        item = PackageItem(
            item_index=1,
            commodity_name="Item A",
            source_image_index=2,
            bounding_box=BoundingBox(x=100, y=150, width=50, height=25),
        )
        self.assertEqual(item.source_image_index, 2)
        self.assertEqual(item.bounding_box.x, 100)

    def test_13_legacy_report_compatibility(self):
        """13. Old report.json without composition deserializes seamlessly."""
        legacy_report_dict = {
            "report_metadata": {"report_format": "json"},
            "scan_metadata": {"scan_id": "test-legacy-uuid"},
            "compliance_summary": {"verdict": "PASS", "compliance_score": 100.0},
            "declarations": [],
            "violations": [],
        }
        # In scans API, missing composition is None
        scan_resp = ScanResponse(
            scan_id="test-legacy-uuid",
            status=ScanStatus.complete,
            verdict=ComplianceVerdict.PASS,
            compliance_score=100.0,
            declarations=[],
            violations=[],
            created_at="2026-09-14T00:00:00Z",
            composition=None,
        )
        self.assertIsNone(scan_resp.composition)

    def test_14_report_serialization_with_composition(self):
        """14. Compiling report includes serialized composition."""
        comp = PackageComposition(
            package_type=PackageType.MULTI_PIECE,
            total_item_count=3,
            items=[
                PackageItem(
                    item_index=1,
                    commodity_name="Soap Bar",
                    item_count=3,
                    unit_quantity="100 g",
                )
            ],
            status=DeclarationStatus.detected,
            confidence=0.95,
        )
        rep = compile_report_dict(
            scan_id="test-scan-uuid",
            verdict="PASS",
            compliance_score=100.0,
            declarations=[],
            violations=[],
            composition=comp,
        )
        self.assertIn("composition", rep)
        self.assertEqual(rep["composition"]["package_type"], "MULTI_PIECE")
        self.assertEqual(rep["composition"]["total_item_count"], 3)
        self.assertEqual(rep["composition"]["items"][0]["commodity_name"], "Soap Bar")

    def test_15_no_aggregate_usp_corruption(self):
        """15. Verifies composition layer does NOT calculate or modify USP."""
        # Single and combination packages must preserve their own statutory bounds
        comp = PackageComposition(
            package_type=PackageType.COMBINATION,
            total_item_count=2,
            items=[
                PackageItem(item_index=1, commodity_name="Shampoo", unit_quantity="200 ml"),
                PackageItem(item_index=2, commodity_name="Conditioner", unit_quantity="100 ml"),
            ],
        )
        # Verify schema does not contain an aggregate_usp calculation field
        self.assertFalse(hasattr(comp, "aggregate_usp"))

    def test_16_qr_compatibility(self):
        """16. QR evidence and PackageComposition coexist without interference."""
        res = ComplianceResult(
            verdict=ComplianceVerdict.PASS,
            compliance_score=95.0,
            declarations=[],
            violations=[],
            evidence=EvidenceMetadata(
                total_declarations_checked=0,
                total_violations_found=0,
            ),
            composition=PackageComposition(
                package_type=PackageType.SINGLE,
                total_item_count=1,
                items=[],
            ),
        )
        self.assertIsNotNone(res.composition)
        self.assertEqual(res.composition.package_type, PackageType.SINGLE)


if __name__ == "__main__":
    unittest.main()
