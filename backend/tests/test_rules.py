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
    """Tests for Rule 6(11) Unit Sale Price validator."""

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

    def test_250g_rs25_010_per_g_valid(self):
        """250 g / ₹25 / ₹0.10 per g -> valid."""
        res = validate_unit_sale_price(
            "₹ 0.10 / g",
            net_qty_text="250 g",
            mrp_text="MRP Rs. 25.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_250g_rs25_050_per_g_mismatch(self):
        """250 g / ₹25 / ₹0.50 per g -> mathematical mismatch (expected ₹0.10)."""
        res = validate_unit_sale_price(
            "₹ 0.50 / g",
            net_qty_text="250 g",
            mrp_text="MRP Rs. 25.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.misleading)
        self.assertIn("0.10", res.error_message)

    def test_58g_rs20_correct_rounded_per_g(self):
        """58 g / ₹20 -> 20 / 58 = 0.3448... rounded half-up to ₹ 0.34 / g."""
        res = validate_unit_sale_price(
            "₹ 0.34 / g",
            net_qty_text="58 g",
            mrp_text="MRP Rs. 20.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_5kg_rs275_55_per_kg_valid(self):
        """5 kg / ₹275 / ₹55 per kg -> valid."""
        res = validate_unit_sale_price(
            "₹ 55.00 / kg",
            net_qty_text="5 kg",
            mrp_text="MRP Rs. 275.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_sub_1kg_wrong_denominator_kg_rejected(self):
        """Sub-1kg package declared in /kg must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 100.00 / kg",
            net_qty_text="250 g",
            mrp_text="MRP Rs. 25.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per g'", res.error_message)

    def test_gt_1kg_wrong_denominator_g_rejected(self):
        """Package > 1kg declared in /g must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 0.055 / g",
            net_qty_text="5 kg",
            mrp_text="MRP Rs. 275.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per kg'", res.error_message)

    def test_volume_sub_1L_conversion(self):
        """500 ml / ₹50 / ₹0.10 per ml -> valid."""
        res = validate_unit_sale_price(
            "₹ 0.10 / ml",
            net_qty_text="500 ml",
            mrp_text="MRP Rs. 50.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_volume_sub_1L_wrong_denominator_L_rejected(self):
        """500 ml declared in /L must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 100.00 / L",
            net_qty_text="500 ml",
            mrp_text="MRP Rs. 50.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per ml'", res.error_message)

    def test_volume_gt_1L_conversion(self):
        """2 L / ₹120 / ₹60 per L -> valid."""
        res = validate_unit_sale_price(
            "₹ 60.00 / L",
            net_qty_text="2 L",
            mrp_text="MRP Rs. 120.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_volume_gt_1L_wrong_denominator_ml_rejected(self):
        """2 L declared in /ml must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 0.06 / ml",
            net_qty_text="2 L",
            mrp_text="MRP Rs. 120.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per L'", res.error_message)

    def test_length_sub_1m_conversion(self):
        """50 cm / ₹10 / ₹0.20 per cm -> valid."""
        res = validate_unit_sale_price(
            "₹ 0.20 / cm",
            net_qty_text="50 cm",
            mrp_text="MRP Rs. 10.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_length_sub_1m_wrong_denominator_m_rejected(self):
        """50 cm declared in /m must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 20.00 / m",
            net_qty_text="50 cm",
            mrp_text="MRP Rs. 10.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per cm'", res.error_message)

    def test_length_gt_1m_conversion(self):
        """5 m / ₹100 / ₹20 per m -> valid."""
        res = validate_unit_sale_price(
            "₹ 20.00 / m",
            net_qty_text="5 m",
            mrp_text="MRP Rs. 100.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_length_gt_1m_wrong_denominator_cm_rejected(self):
        """5 m declared in /cm must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 0.20 / cm",
            net_qty_text="5 m",
            mrp_text="MRP Rs. 100.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per m'", res.error_message)

    def test_count_based_commodity(self):
        """10 units / ₹25 / ₹2.50 per piece -> valid."""
        res = validate_unit_sale_price(
            "₹ 2.50 / piece",
            net_qty_text="10 units",
            mrp_text="MRP Rs. 25.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_count_wrong_denominator(self):
        """10 units declared with mass denominator /kg must fail with invalid_unit."""
        res = validate_unit_sale_price(
            "₹ 2.50 / kg",
            net_qty_text="10 units",
            mrp_text="MRP Rs. 25.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_unit)
        self.assertIn("Mandatory denominator is 'per number/unit/piece'", res.error_message)

    def test_equivalent_internal_unit_normalization_2000g(self):
        """2000 g package (> 1 kg) normalized internally to 2 kg with ₹60/kg rate."""
        res = validate_unit_sale_price(
            "₹ 60.00 / kg",
            net_qty_text="2000 g",
            mrp_text="MRP Rs. 120.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_malformed_usp_syntax(self):
        """Unparseable USP syntax triggers invalid_format."""
        res = validate_unit_sale_price("not a valid price", is_usp_applicable=True)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_format)

    def test_malformed_quantity_safe_fallback(self):
        """Unparseable net quantity falls back safely without false legal violation."""
        res = validate_unit_sale_price(
            "₹ 0.50 / g",
            net_qty_text="invalid qty text",
            mrp_text="MRP Rs. 50.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_malformed_mrp_safe_fallback(self):
        """Unparseable MRP falls back safely without false legal violation."""
        res = validate_unit_sale_price(
            "₹ 0.50 / g",
            net_qty_text="100 g",
            mrp_text="MRP unreadable",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_zero_quantity_safe_handling(self):
        """Zero quantity handled gracefully."""
        res = validate_unit_sale_price(
            "₹ 0.50 / g",
            net_qty_text="0 g",
            mrp_text="MRP Rs. 50.00 (incl. of all taxes)",
            is_usp_applicable=True,
        )
        self.assertTrue(res.is_valid)

    def test_exact_1kg_boundary_exemption_handling(self):
        """1 kg exact package is exempt under Rule 6(11)."""
        res = validate_unit_sale_price(
            "₹ 50.00 / kg",
            net_qty_text="1 kg",
            mrp_text="MRP Rs. 50.00 (incl. of all taxes)",
            is_usp_applicable=False,
        )
        self.assertTrue(res.is_valid)


class TestDatesAndExpiryValidator(unittest.TestCase):
    """Tests for Rule 6(1)(d) manufacture date and Rule 6(1)(m) expiry date."""

    def test_valid_manufacture_dates(self):
        # Existing 4-digit formats
        self.assertTrue(validate_manufacture_date("01/2026").is_valid)
        self.assertTrue(validate_manufacture_date("15/02/2026").is_valid)
        self.assertTrue(validate_manufacture_date("15-02-2026").is_valid)
        self.assertTrue(validate_manufacture_date("15.02.2026").is_valid)
        self.assertTrue(validate_manufacture_date("Jan 2026").is_valid)
        self.assertTrue(validate_manufacture_date("September 2026").is_valid)

        # 2-digit year formats per FSSAI / Legal Metrology
        self.assertTrue(validate_manufacture_date("08/09/26").is_valid)
        self.assertTrue(validate_manufacture_date("08-09-26").is_valid)
        self.assertTrue(validate_manufacture_date("08.09.26").is_valid)
        self.assertTrue(validate_manufacture_date("09/26").is_valid)
        self.assertTrue(validate_manufacture_date("09-26").is_valid)
        self.assertTrue(validate_manufacture_date("09.26").is_valid)
        self.assertTrue(validate_manufacture_date("Sep 26").is_valid)
        self.assertTrue(validate_manufacture_date("MFD: 08/09/26").is_valid)

    def test_valid_expiry_dates_2digit_and_4digit(self):
        # 2-digit year formats for UBD / Expiry
        self.assertTrue(validate_expiry_date("08/09/26", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("08-09-26", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("08.09.26", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("09/26", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("UBD: 08/09/26", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("Best Before 08/09/26", is_perishable=True).is_valid)

        # 4-digit year formats
        self.assertTrue(validate_expiry_date("08/09/2026", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("08-09-2026", is_perishable=True).is_valid)
        self.assertTrue(validate_expiry_date("08.09.2026", is_perishable=True).is_valid)

    def test_calendar_validity_and_leap_years(self):
        """Calendar date validation rejects impossible dates and enforces leap-year rules."""
        # Valid leap year date
        self.assertTrue(validate_manufacture_date("29/02/24").is_valid)
        self.assertTrue(validate_manufacture_date("29/02/2024").is_valid)
        self.assertTrue(validate_expiry_date("29/02/24", is_perishable=True).is_valid)

        # Invalid non-leap year date (Feb 29 on non-leap year)
        self.assertFalse(validate_manufacture_date("29/02/25").is_valid)
        self.assertFalse(validate_manufacture_date("29/02/2025").is_valid)
        self.assertFalse(validate_expiry_date("29/02/25", is_perishable=True).is_valid)

        # Impossible calendar dates (Feb 31, April 31)
        self.assertFalse(validate_manufacture_date("31/02/26").is_valid)
        self.assertFalse(validate_manufacture_date("31/02/2026").is_valid)
        self.assertFalse(validate_manufacture_date("31/04/26").is_valid)
        self.assertFalse(validate_manufacture_date("31/04/2026").is_valid)
        self.assertFalse(validate_expiry_date("31/02/26", is_perishable=True).is_valid)
        self.assertFalse(validate_expiry_date("31/04/26", is_perishable=True).is_valid)

    def test_invalid_manufacture_date(self):
        # Malformed / unparseable
        res = validate_manufacture_date("Not a date")
        self.assertFalse(res.is_valid)
        self.assertEqual(res.violation_type, ViolationType.invalid_format)

        # Out-of-bounds dates
        self.assertFalse(validate_manufacture_date("99/99/99").is_valid)
        self.assertFalse(validate_manufacture_date("00/00/00").is_valid)
        self.assertFalse(validate_manufacture_date("32/01/26").is_valid)
        self.assertFalse(validate_manufacture_date("15/13/26").is_valid)
        self.assertFalse(validate_manufacture_date("08/13/2026").is_valid)
        self.assertFalse(validate_manufacture_date("123/45/6789").is_valid)

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


class TestRulesEndpointContract(unittest.TestCase):
    """Tests for GET /api/v1/rules response schema conforming to docs/api.md."""

    def test_no_category_filter_returns_all_active_rules(self):
        """When no category filter is passed, category is 'all' and returns active rules."""
        from app.api.routes.rules import get_rules, RulesListResponse

        res: RulesListResponse = get_rules()
        data = res.model_dump()

        self.assertEqual(data["category"], "all")
        self.assertGreater(data["total"], 0)
        self.assertEqual(len(data["rules"]), data["total"])

    def test_category_filter_returns_category_and_matching_rules(self):
        """When category filter is applied, category is preserved and matching rules returned."""
        from app.api.routes.rules import get_rules, RulesListResponse

        res: RulesListResponse = get_rules(category="Food Grains")
        data = res.model_dump()

        self.assertEqual(data["category"], "Food Grains")
        self.assertGreater(data["total"], 0)
        self.assertEqual(len(data["rules"]), data["total"])

    def test_exact_top_level_response_keys(self):
        """Top-level response must strictly contain only 'category', 'total', and 'rules'."""
        from app.api.routes.rules import get_rules, RulesListResponse

        res: RulesListResponse = get_rules()
        data = res.model_dump()

        expected_keys = {"category", "total", "rules"}
        self.assertEqual(set(data.keys()), expected_keys)

    def test_exact_rule_item_field_names(self):
        """Every rule item must strictly contain the 9 documented field names."""
        from app.api.routes.rules import get_rules, RulesListResponse

        res: RulesListResponse = get_rules()
        data = res.model_dump()

        expected_rule_keys = {
            "id",
            "rule_code",
            "title",
            "description",
            "field_name",
            "validation_type",
            "severity",
            "version",
            "active",
        }

        self.assertGreater(len(data["rules"]), 0)
        for rule_item in data["rules"]:
            self.assertEqual(set(rule_item.keys()), expected_rule_keys)
            self.assertIsInstance(rule_item["id"], str)
            self.assertIsInstance(rule_item["rule_code"], str)
            self.assertIsInstance(rule_item["title"], str)
            self.assertIsInstance(rule_item["description"], str)
            self.assertIsInstance(rule_item["field_name"], str)
            self.assertIsInstance(rule_item["validation_type"], str)
            self.assertIn(rule_item["severity"], ("critical", "major", "minor"))
            self.assertIsInstance(rule_item["version"], str)
            self.assertIsInstance(rule_item["active"], bool)

    def test_empty_category_result(self):
        """Querying an unknown or non-existent category returns total=0 and empty rules list."""
        from app.api.routes.rules import get_rules, RulesListResponse

        res: RulesListResponse = get_rules(category="nonexistent_category_xyz")
        data = res.model_dump()

        self.assertEqual(data["category"], "nonexistent_category_xyz")
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["rules"], [])

    def test_non_perishable_category_filters_expiry_date_rule(self):
        """Non-perishable categories (e.g., Electronics) exclude perishable expiry date rules."""
        from app.api.routes.rules import get_rules, RulesListResponse

        all_res: RulesListResponse = get_rules()
        elec_res: RulesListResponse = get_rules(category="Electronics")

        all_fields = [r.field_name for r in all_res.rules]
        elec_fields = [r.field_name for r in elec_res.rules]

        self.assertIn("expiry_date", all_fields)
        self.assertNotIn("expiry_date", elec_fields)
        self.assertEqual(elec_res.total, len(elec_res.rules))


if __name__ == "__main__":
    unittest.main()
