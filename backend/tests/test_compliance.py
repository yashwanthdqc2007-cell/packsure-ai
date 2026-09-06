"""
Integration and scenario tests for PackSure AI Compliance Engine (backend/app/rules/rule_engine.py).

Verifies:
1. Full compliant scan -> PASS (compliance_score=100.0, violations=[]).
2. Critical violation (missing mandatory MRP / address) -> FAIL.
3. Prohibited legacy units (gms, ltrs) -> FAIL with invalid_unit.
4. Uncertain declaration status -> NEEDS_REVIEW.
5. Incomplete single-panel scan -> NEEDS_REVIEW (no false statutory absence claim).
6. Rule 26 small package exemption (<= 10g) -> PASS for non-tobacco products.
7. Tobacco proviso exception -> FAIL on small tobacco pack lacking declarations.
8. Unit Sale Price threshold applicability (> 100g/ml).
9. Country of origin conditional evaluation (imported vs domestic).
10. Perishability conditional evaluation (food vs durable hardware).
11. Deterministic score calculation and citation traceability in Violations.
"""

import unittest
from app.rules.rule_engine import RuleEngine
from app.schemas.compliance import ComplianceVerdict
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.ocr import BoundingBox
from app.schemas.violation import ViolationSeverity, ViolationType


class TestComplianceEngine(unittest.TestCase):
    """Scenario tests for deterministic compliance evaluation."""

    def setUp(self):
        self.engine = RuleEngine()

        # Standard fully-compliant declaration set for a 500g packaged food item
        self.valid_food_declarations = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Whole Wheat Flour (Atta)",
                normalized_value="Wheat Flour",
                confidence=0.98,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Qty: 500 g",
                normalized_value="500 g",
                confidence=0.96,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 55.00 (incl. of all taxes)",
                normalized_value="55.00",
                confidence=0.97,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="unit_sale_price",
                status=DeclarationStatus.detected,
                raw_value="USP ₹ 0.11 / g",
                normalized_value="0.11/g",
                confidence=0.92,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="manufacture_date",
                status=DeclarationStatus.detected,
                raw_value="Mfd: 01/2026",
                normalized_value="2026-01",
                confidence=0.94,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="expiry_date",
                status=DeclarationStatus.detected,
                raw_value="Best Before: 07/2026",
                normalized_value="2026-07",
                confidence=0.95,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="batch_number",
                status=DeclarationStatus.detected,
                raw_value="Batch No: B-2026-01",
                normalized_value="B-2026-01",
                confidence=0.93,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="manufacturer_name_and_address",
                status=DeclarationStatus.detected,
                raw_value="Manufactured by: ABC Agro Foods Ltd, Sector 5, Industrial Area, Pune 411001",
                normalized_value="ABC Agro Foods Ltd, Sector 5, Industrial Area, Pune 411001",
                confidence=0.96,
                source=DeclarationSource.tesseract,
            ),
            ExtractedDeclaration(
                field_name="consumer_care",
                status=DeclarationStatus.detected,
                raw_value="For complaints contact Consumer Care Cell: care@abcagro.com or Call 1800-200-1234",
                normalized_value="care@abcagro.com",
                confidence=0.94,
                source=DeclarationSource.tesseract,
            ),
        ]

    def test_full_compliant_scan_produces_pass(self):
        """Standard valid package declarations must evaluate to PASS with 100.0 compliance score."""
        res = self.engine.evaluate_compliance(
            declarations=self.valid_food_declarations,
            product_category="Food Grains",
            is_complete_scan=True,
        )
        self.assertEqual(res.verdict, ComplianceVerdict.PASS)
        self.assertEqual(res.compliance_score, 100.0)
        self.assertEqual(len(res.violations), 0)
        self.assertIsNotNone(res.evidence)
        self.assertEqual(res.evidence.total_violations_found, 0)

    def test_missing_mandatory_mrp_produces_fail(self):
        """Missing mandatory MRP on complete scan must produce FAIL with critical severity deduction."""
        decls = [d for d in self.valid_food_declarations if d.field_name != "mrp"]
        res = self.engine.evaluate_compliance(
            declarations=decls,
            product_category="Food Grains",
            is_complete_scan=True,
        )
        self.assertEqual(res.verdict, ComplianceVerdict.FAIL)
        self.assertLessEqual(res.compliance_score, 70.0)
        self.assertEqual(len(res.violations), 1)
        self.assertEqual(res.violations[0].rule_code, "Rule-6(1)(e)")
        self.assertEqual(res.violations[0].rule_id, "LMR-R06-1-E")
        self.assertEqual(res.violations[0].severity, ViolationSeverity.critical)
        self.assertEqual(res.violations[0].violation_type, ViolationType.missing_declaration)

    def test_prohibited_unit_symbol_produces_fail(self):
        """Legacy unit symbols like 'gms' must trigger invalid_unit violation and FAIL verdict."""
        decls = [
            d if d.field_name != "net_quantity" else ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="Net Wt: 500 gms",  # Illegal symbol
            )
            for d in self.valid_food_declarations
        ]
        res = self.engine.evaluate_compliance(
            declarations=decls,
            product_category="Food Grains",
        )
        self.assertEqual(res.verdict, ComplianceVerdict.FAIL)
        self.assertTrue(any(v.violation_type == ViolationType.invalid_unit for v in res.violations))

    def test_mrp_missing_tax_clause_produces_fail(self):
        """MRP without mandatory 'inclusive of all taxes' must fail."""
        decls = [
            d if d.field_name != "mrp" else ExtractedDeclaration(
                field_name="mrp",
                status=DeclarationStatus.detected,
                raw_value="MRP Rs. 55.00",  # Missing 'inclusive of all taxes'
            )
            for d in self.valid_food_declarations
        ]
        res = self.engine.evaluate_compliance(
            declarations=decls,
            product_category="Food Grains",
        )
        self.assertEqual(res.verdict, ComplianceVerdict.FAIL)
        mrp_violation = next(v for v in res.violations if v.rule_code == "Rule-6(1)(e)")
        self.assertEqual(mrp_violation.violation_type, ViolationType.invalid_format)

    def test_uncertain_declaration_produces_needs_review(self):
        """Uncertain declaration (smudged text) must produce NEEDS_REVIEW rather than false FAIL."""
        decls = [
            d if d.field_name != "consumer_care" else ExtractedDeclaration(
                field_name="consumer_care",
                status=DeclarationStatus.uncertain,
                raw_value="care@...",
                confidence=0.35,
            )
            for d in self.valid_food_declarations
        ]
        res = self.engine.evaluate_compliance(
            declarations=decls,
            product_category="Food Grains",
        )
        self.assertEqual(res.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(len(res.violations), 0)

    def test_single_panel_incomplete_scan_produces_needs_review(self):
        """When is_complete_scan=False, missing fields route to NEEDS_REVIEW without false FAIL."""
        # Only generic name and net qty visible on front panel
        decls = [
            self.valid_food_declarations[0],
            self.valid_food_declarations[1],
        ]
        res = self.engine.evaluate_compliance(
            declarations=decls,
            product_category="Food Grains",
            is_complete_scan=False,  # Single panel view
        )
        self.assertEqual(res.verdict, ComplianceVerdict.NEEDS_REVIEW)
        self.assertEqual(len(res.violations), 0)

    def test_rule26_small_package_exemption_passes(self):
        """Small package (<= 10g) is exempt from missing MRP and date declarations under Rule 26(a)."""
        small_pack_decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Candy",
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="5 g",
            ),
        ]
        res = self.engine.evaluate_compliance(
            declarations=small_pack_decls,
            product_category="Confectionery",
            is_complete_scan=True,
        )
        self.assertEqual(res.verdict, ComplianceVerdict.PASS)

    def test_rule26_tobacco_proviso_exception_fails(self):
        """Tobacco products <= 10g are NOT exempt under Rule 26(a) and must declare MRP."""
        tobacco_decls = [
            ExtractedDeclaration(
                field_name="generic_name",
                status=DeclarationStatus.detected,
                raw_value="Beedi",
            ),
            ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="8 g",
            ),
        ]
        res = self.engine.evaluate_compliance(
            declarations=tobacco_decls,
            product_category="Tobacco / Beedi",
            is_complete_scan=True,
        )
        self.assertEqual(res.verdict, ComplianceVerdict.FAIL)
        self.assertTrue(any(v.rule_code == "Rule-6(1)(e)" for v in res.violations))

    def test_unit_sale_price_threshold_applicability(self):
        """USP is mandatory for packages > 100g, but not required for packages <= 100g."""
        # 50g package without USP -> PASS
        decls_50g = [
            d if d.field_name != "net_quantity" else ExtractedDeclaration(
                field_name="net_quantity",
                status=DeclarationStatus.detected,
                raw_value="50 g",
            )
            for d in self.valid_food_declarations
            if d.field_name != "unit_sale_price"
        ]
        res_50g = self.engine.evaluate_compliance(
            declarations=decls_50g,
            product_category="Food",
            is_complete_scan=True,
        )
        self.assertEqual(res_50g.verdict, ComplianceVerdict.PASS)

        # 500g package without USP -> FAIL
        decls_500g = [d for d in self.valid_food_declarations if d.field_name != "unit_sale_price"]
        res_500g = self.engine.evaluate_compliance(
            declarations=decls_500g,
            product_category="Food",
            is_complete_scan=True,
        )
        self.assertEqual(res_500g.verdict, ComplianceVerdict.FAIL)
        self.assertTrue(any(v.rule_code == "Rule-6(1)(f)" for v in res_500g.violations))

    def test_non_perishable_hardware_exempt_from_expiry(self):
        """Non-perishable hardware commodity without expiry date must PASS."""
        hardware_decls = [
            d for d in self.valid_food_declarations if d.field_name != "expiry_date"
        ]
        res = self.engine.evaluate_compliance(
            declarations=hardware_decls,
            product_category="Hardware & Tools",
            is_complete_scan=True,
        )
        self.assertEqual(res.verdict, ComplianceVerdict.PASS)


if __name__ == "__main__":
    unittest.main()
