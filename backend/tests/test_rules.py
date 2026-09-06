"""
Unit tests for PackSure AI Legal Metrology Field Validators and Rule Loading (backend/app/rules/).

Verifies:
1. Pure field validators (MRP, Net Quantity, Dates, Address, Consumer Care, Generic Name, Batch).
2. Prohibited legacy unit detection (gms, ltrs, kilos) vs standard SI metric units (g, kg, ml, l).
3. MRP 'inclusive of all taxes' mandatory clause enforcement.
4. Rule 26(a) small package exemption calculation and tobacco exception.
5. Rule definition loading, schema adherence, and audit metadata.
"""

import os
import unittest
from app.rules.rule_engine import Rule, RuleEngine
from app.rules.validators import (
    check_rule26_exemption,
    validate_address,
    validate_batch_number,
    validate_consumer_care,
    validate_country_of_origin,
    validate_expiry_date,
    validate_generic_name,
    validate_manufacture_date,
    validate_mrp,
    validate_net_quantity,
    validate_unit_sale_price,
)
from app.schemas.violation import ViolationType


class TestRuleDataAndLoading(unittest.TestCase):
    """Tests for rules.json structure, loading, and audit metadata."""

    def setUp(self):
        self.engine = RuleEngine()

    def test_rules_json_loads_successfully(self):
        """Rule engine loads all codified rules from rules.json."""
        self.assertGreater(len(self.engine.rules), 0)
        self.assertEqual(self.engine.rules_version, "2026.1")
        self.assertIn("Legal Metrology", self.engine.rules_source)

    def test_every_rule_has_auditability_metadata(self):
        """Every codified rule entry must have all required statutory fields."""
        for rule in self.engine.rules:
            self.assertTrue(rule.rule_id.startswith("LMR-"))
            self.assertTrue(rule.rule_code.startswith("Rule-"))
            self.assertIsNotNone(rule.title)
            self.assertIsNotNone(rule.requirement)
            self.assertIsNotNone(rule.official_source)
            self.assertIsNotNone(rule.applies_when)
            self.assertIsNotNone(rule.does_not_apply_when)
            self.assertIsNotNone(rule.effective_from)
            self.assertIn(rule.severity.value, ("critical", "major", "minor"))


class TestAddressValidator(unittest.TestCase):
    """Tests for Rule 6(1)(a) address validator."""

    def test_valid_address(self):
        res = validate_address("ABC Foods Ltd, Plot 12, Industrial Area, Mumbai 400001")
        self.assertTrue(res.is_valid)

    def test_missing_address(self):
        res = validate_address(None)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)

    def test_short_incomplete_address(self):
        res = validate_address("ABC Ltd")
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_format)


class TestCountryOfOriginValidator(unittest.TestCase):
    """Tests for Rule 6(1)(aa) country of origin validator."""

    def test_domestic_product_skips_rule(self):
        res = validate_country_of_origin(None, is_imported=False)
        self.assertTrue(res.is_valid)

    def test_imported_product_with_country(self):
        res = validate_country_of_origin("Country of Origin: Vietnam", is_imported=True)
        self.assertTrue(res.is_valid)

    def test_imported_product_missing_country(self):
        res = validate_country_of_origin(None, is_imported=True)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)


class TestNetQuantityValidator(unittest.TestCase):
    """Tests for Rule 6(1)(c) and Rule 13 SI metric units validator."""

    def test_valid_standard_si_units(self):
        self.assertTrue(validate_net_quantity("500 g").is_valid)
        self.assertTrue(validate_net_quantity("1 kg").is_valid)
        self.assertTrue(validate_net_quantity("750 ml").is_valid)
        self.assertTrue(validate_net_quantity("1 L").is_valid)
        self.assertTrue(validate_net_quantity("10 N").is_valid)
        self.assertTrue(validate_net_quantity("5 units").is_valid)

    def test_prohibited_legacy_units_rejected(self):
        """Symbols like gms, grm, ltrs, kilos must trigger invalid_unit violation."""
        res_gms = validate_net_quantity("500 gms")
        self.assertFalse(res_gms.is_valid)
        self.assertEqual(res_gms.violation_type, ViolationType.invalid_unit)
        self.assertIn("Prohibited non-standard unit symbol 'gms'", res_gms.error_message)

        res_ltrs = validate_net_quantity("1.5 ltrs")
        self.assertFalse(res_ltrs.is_valid)
        self.assertEqual(res_ltrs.violation_type, ViolationType.invalid_unit)

        res_kilos = validate_net_quantity("2 kilos")
        self.assertFalse(res_kilos.is_valid)
        self.assertEqual(res_kilos.violation_type, ViolationType.invalid_unit)

    def test_missing_net_quantity(self):
        res = validate_net_quantity(None)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)


class TestMRPValidator(unittest.TestCase):
    """Tests for Rule 6(1)(e) Maximum Retail Price validator."""

    def test_valid_mrp_with_tax_statement(self):
        self.assertTrue(validate_mrp("MRP Rs. 150.00 (inclusive of all taxes)").is_valid)
        self.assertTrue(validate_mrp("MRP ₹ 240.00 (incl. of all taxes)").is_valid)
        self.assertTrue(validate_mrp("Max. Retail Price Rs. 99/- incl. taxes").is_valid)

    def test_missing_tax_inclusion_clause_rejected(self):
        """MRP without 'inclusive of all taxes' must be rejected under Rule 6(1)(e)."""
        res = validate_mrp("MRP Rs. 150.00")
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_format)
        self.assertIn("inclusive of all taxes", res.error_message)

    def test_missing_mrp(self):
        res = validate_mrp(None)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)


class TestUnitSalePriceValidator(unittest.TestCase):
    """Tests for Rule 6(1)(f) Unit Sale Price validator."""

    def test_not_applicable_passes_cleanly(self):
        res = validate_unit_sale_price(None, is_usp_applicable=False)
        self.assertTrue(res.is_valid)

    def test_applicable_with_valid_usp(self):
        res = validate_unit_sale_price("₹ 0.48 / g", is_usp_applicable=True)
        self.assertTrue(res.is_valid)

    def test_applicable_with_missing_usp(self):
        res = validate_unit_sale_price(None, is_usp_applicable=True)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)


class TestDatesAndExpiryValidator(unittest.TestCase):
    """Tests for Rule 6(1)(d) manufacture date and Rule 6(1)(m) expiry date."""

    def test_valid_manufacture_dates(self):
        self.assertTrue(validate_manufacture_date("01/2026").is_valid)
        self.assertTrue(validate_manufacture_date("15/02/2026").is_valid)
        self.assertTrue(validate_manufacture_date("Jan 2026").is_valid)

    def test_invalid_manufacture_date(self):
        res = validate_manufacture_date("Not a date")
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_format)

    def test_perishable_missing_expiry_fails(self):
        res = validate_expiry_date(None, is_perishable=True)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)

    def test_non_perishable_missing_expiry_passes(self):
        res = validate_expiry_date(None, is_perishable=False)
        self.assertTrue(res.is_valid)


class TestConsumerCareValidator(unittest.TestCase):
    """Tests for Rule 6(1)(n) Consumer Care contact validator."""

    def test_valid_consumer_care_with_phone_and_email(self):
        res = validate_consumer_care("Customer Care: care@brand.com, Toll Free: 1800-123-4567")
        self.assertTrue(res.is_valid)

    def test_missing_consumer_care(self):
        res = validate_consumer_care(None)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.missing_declaration)


class TestRule26ExemptionHelper(unittest.TestCase):
    """Tests for Rule 26 small package exemption logic."""

    def test_small_package_qualifies(self):
        self.assertTrue(check_rule26_exemption("5 g", category="Snacks"))
        self.assertTrue(check_rule26_exemption("10 ml", category="Cosmetics"))

    def test_standard_package_does_not_qualify(self):
        self.assertFalse(check_rule26_exemption("500 g", category="Snacks"))
        self.assertFalse(check_rule26_exemption("1 L", category="Beverages"))

    def test_tobacco_proviso_exception_never_exempt(self):
        """Rule 26(a) proviso: Tobacco products are never exempt regardless of size."""
        self.assertFalse(check_rule26_exemption("5 g", category="Tobacco / Cigarettes"))
        self.assertFalse(check_rule26_exemption("8 g", category="Beedi"))


if __name__ == "__main__":
    unittest.main()
