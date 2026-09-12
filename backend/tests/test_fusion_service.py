"""
Unit tests for PackSure AI Multi-View Evidence Fusion Service (backend/app/services/fusion_service.py).

Verifies:
1. Complementary declarations across views merge into a complete declaration set.
2. Duplicate declarations across views deduplicate to the best observation without duplicate penalty.
3. Provenance (image_index, image_name, bounding_box) is preserved on fused declarations.
4. Conflicting declarations across views produce an UNCERTAIN declaration and CONFLICT-NEEDS-REVIEW violation.
5. Absence in View 1 does not result in missing declaration when present in View 2.
6. Number and unit comparisons for MRP, Net Quantity, and Unit Sale Price.
"""

import unittest
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.ocr import BoundingBox
from app.schemas.violation import ViolationSeverity, ViolationType
from app.services.fusion_service import are_declarations_consistent, fuse_declarations


class TestEvidenceFusionService(unittest.TestCase):
    """Test suite for deterministic evidence fusion across multiple views."""

    def test_complementary_views_merge_cleanly(self):
        """View 0 (Front) and View 1 (Back) with non-overlapping fields merge into full set."""
        view0_decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Whole Wheat Flour",
                normalized_value="Wheat Flour",
                confidence=0.98,
                bounding_box=BoundingBox(x=10, y=20, width=100, height=30),
                image_index=0,
                image_name="front.jpg",
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Qty: 1 kg",
                normalized_value="1 kg",
                confidence=0.96,
                bounding_box=BoundingBox(x=10, y=60, width=80, height=20),
                image_index=0,
                image_name="front.jpg",
            ),
        ]

        view1_decls = [
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 60.00 (incl. of all taxes)",
                normalized_value="60.00",
                confidence=0.95,
                bounding_box=BoundingBox(x=15, y=30, width=120, height=25),
                image_index=1,
                image_name="back.jpg",
            ),
            ExtractedDeclaration(
                field_name="manufacturer_name_and_address",
                status=DeclarationStatus.detected,
                raw_value="PackSure Foods Ltd, Sector 18, Gurugram 122015",
                normalized_value="PackSure Foods Ltd, Sector 18, Gurugram 122015",
                confidence=0.94,
                bounding_box=BoundingBox(x=15, y=70, width=250, height=40),
                image_index=1,
                image_name="back.jpg",
            ),
        ]

        fused, conflicts = fuse_declarations([view0_decls, view1_decls])

        self.assertEqual(len(conflicts), 0)
        self.assertEqual(len(fused), 4)

        fused_map = {d.field_name: d for d in fused}
        self.assertIn("generic_name", fused_map)
        self.assertIn("net_quantity", fused_map)
        self.assertIn("mrp", fused_map)
        self.assertIn("manufacturer_name_and_address", fused_map)

        # Verify provenance preservation
        self.assertEqual(fused_map["generic_name"].image_index, 0)
        self.assertEqual(fused_map["generic_name"].image_name, "front.jpg")
        self.assertEqual(fused_map["mrp"].image_index, 1)
        self.assertEqual(fused_map["mrp"].image_name, "back.jpg")

    def test_duplicate_consistent_declarations_deduplicate(self):
        """Same field present in both views with consistent values deduplicates to best confidence."""
        view0_decls = [
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="500 g",
                normalized_value="500 g",
                confidence=0.85,
                bounding_box=BoundingBox(x=50, y=50, width=60, height=20),
                image_index=0,
                image_name="front.jpg",
            )
        ]

        view1_decls = [
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Weight: 500 g",
                normalized_value="500 g",
                confidence=0.98,
                bounding_box=BoundingBox(x=30, y=40, width=100, height=25),
                image_index=1,
                image_name="back.jpg",
            )
        ]

        fused, conflicts = fuse_declarations([view0_decls, view1_decls])

        self.assertEqual(len(conflicts), 0)
        self.assertEqual(len(fused), 1)

        fused_net_qty = fused[0]
        self.assertEqual(fused_net_qty.normalized_value, "500 g")
        # Chose higher confidence (0.98) from View 1
        self.assertEqual(fused_net_qty.confidence, 0.98)
        self.assertEqual(fused_net_qty.image_index, 1)
        self.assertEqual(fused_net_qty.image_name, "back.jpg")

    def test_conflicting_mrp_declarations_flag_uncertain_and_conflict(self):
        """Conflicting MRPs (e.g. 150 vs 200) across views flag UNCERTAIN and produce violation."""
        view0_decls = [
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 150.00",
                normalized_value="150.00",
                confidence=0.95,
                image_index=0,
                image_name="front.jpg",
            )
        ]

        view1_decls = [
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 200.00",
                normalized_value="200.00",
                confidence=0.96,
                image_index=1,
                image_name="back.jpg",
            )
        ]

        fused, conflicts = fuse_declarations([view0_decls, view1_decls])

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0].field_name, "mrp")
        self.assertEqual(fused[0].status, DeclarationStatus.uncertain)
        self.assertIn("Conflict", fused[0].raw_value)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].rule_code, "CONFLICT-NEEDS-REVIEW")
        self.assertEqual(conflicts[0].field_name, "mrp")
        self.assertEqual(conflicts[0].severity, ViolationSeverity.major)
        self.assertIn("150.00", conflicts[0].description)
        self.assertIn("200.00", conflicts[0].description)

    def test_conflicting_batch_numbers_flag_uncertain(self):
        """Conflicting batch numbers (B-101 vs B-202) across views flag conflict."""
        view0_decls = [
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch: B-101",
                normalized_value="B-101",
                confidence=0.92,
                image_index=0,
            )
        ]

        view1_decls = [
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch: B-202",
                normalized_value="B-202",
                confidence=0.94,
                image_index=1,
            )
        ]

        fused, conflicts = fuse_declarations([view0_decls, view1_decls])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(fused[0].status, DeclarationStatus.uncertain)

    def test_consistent_address_containment(self):
        """Brand name on front and full address on back are considered consistent."""
        d1 = ExtractedDeclaration(
            field_name="manufacturer_name_and_address",
            status=DeclarationStatus.detected,
            raw_value="PackSure Foods Ltd",
            normalized_value="PackSure Foods Ltd",
        )
        d2 = ExtractedDeclaration(
            field_name="manufacturer_name_and_address",
            status=DeclarationStatus.detected,
            raw_value="Manufactured by: PackSure Foods Ltd, Plot 12, Sector 18, Gurugram 122015",
            normalized_value="PackSure Foods Ltd, Plot 12, Sector 18, Gurugram 122015",
        )
        self.assertTrue(are_declarations_consistent("manufacturer_name_and_address", d1, d2))


if __name__ == "__main__":
    unittest.main()
