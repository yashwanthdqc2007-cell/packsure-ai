"""
PackSure AI — Phase 6B Quantity Verification & Metrology Tests.

Validates deterministic First Schedule [Rules 2(e) & 22] Table I MPE tolerance evaluation,
unit normalizations, cross-dimension safety guards, multi-piece/composition protections,
and inspection state transitions.
"""

from decimal import Decimal
import unittest

from app.schemas.compliance import ComplianceVerdict
from app.schemas.declaration import (
    DeclarationStatus,
    ExtractedDeclaration,
    PackageComposition,
    PackageItem,
    PackageType,
)
from app.schemas.inspection_state import InspectionStateStatus, PhysicalChecksStatus
from app.schemas.quantity import (
    IndividualQuantityVerdict,
    MeasurementMethod,
    QuantityMeasurementInput,
)
from app.services.inspection_service import derive_inspection_state_and_next_action
from app.services.quantity_service import (
    FIRST_SCHEDULE_TABLE_I_TIERS,
    evaluate_physical_quantity,
    lookup_first_schedule_table_i_mpe,
    normalize_unit_and_dimension,
    to_base_unit,
)
from app.services.report_service import compile_report_dict


class TestQuantityService(unittest.TestCase):
    """Unit test suite for First Schedule Table I quantity verification."""

    def test_tc01_1000g_declared_990g_measured_pass(self):
        """1000 g declared / 990 g measured -> PASS (deficiency 10g <= MPE 15g)."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("990"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))
        self.assertEqual(qm.deficiency, Decimal("10"))
        self.assertFalse(qm.is_excess)
        self.assertEqual(qm.double_mpe_limit, Decimal("30.0"))

    def test_tc02_1000g_declared_978g_measured_fail(self):
        """1000 g declared / 978 g measured -> FAIL (deficiency 22g > MPE 15g)."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("978"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.FAIL)
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))
        self.assertEqual(qm.deficiency, Decimal("22"))
        self.assertEqual(qm.percentage_deficiency, Decimal("2.20"))
        self.assertFalse(qm.is_excess)

    def test_tc03_1000g_declared_1025g_measured_excess_pass(self):
        """1000 g declared / 1025 g measured -> PASS (excess, zero deficiency)."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("1025"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.PASS)
        self.assertTrue(qm.is_excess)
        self.assertEqual(qm.deficiency, Decimal("0.0"))
        self.assertEqual(qm.net_difference, Decimal("25"))

    def test_tc04_exact_mpe_boundary_pass(self):
        """Exact MPE boundary (1000g declared, 985g measured, deficiency 15g == MPE 15g) -> PASS."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("985"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm.deficiency, Decimal("15"))
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))

    def test_tc05_just_beyond_mpe_fail(self):
        """Just beyond MPE boundary (1000g declared, 984.9g measured, deficiency 15.1g > MPE 15g) -> FAIL."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("984.9"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.FAIL)
        self.assertEqual(qm.deficiency, Decimal("15.1"))
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))

    def test_tc06_500g_tier_mpe(self):
        """500 g declared is in Tier 5 (300 to 500g: 3% -> 15.0g)."""
        inp_pass = QuantityMeasurementInput(
            declared_quantity=Decimal("500"),
            declared_unit="g",
            measured_quantity=Decimal("486"),
            measured_unit="g",
        )
        qm_pass = evaluate_physical_quantity(inp_pass)
        self.assertEqual(qm_pass.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm_pass.statutory_mpe, Decimal("15.0"))

        inp_fail = QuantityMeasurementInput(
            declared_quantity=Decimal("500"),
            declared_unit="g",
            measured_quantity=Decimal("484"),
            measured_unit="g",
        )
        qm_fail = evaluate_physical_quantity(inp_fail)
        self.assertEqual(qm_fail.verdict, IndividualQuantityVerdict.FAIL)

    def test_tc07_50g_tier_mpe(self):
        """50 g declared is in Tier 1 (up to 50g: 9% -> 4.5g)."""
        inp_pass = QuantityMeasurementInput(
            declared_quantity=Decimal("50"),
            declared_unit="g",
            measured_quantity=Decimal("46"),
            measured_unit="g",
        )
        qm_pass = evaluate_physical_quantity(inp_pass)
        self.assertEqual(qm_pass.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm_pass.statutory_mpe, Decimal("4.5"))

        inp_fail = QuantityMeasurementInput(
            declared_quantity=Decimal("50"),
            declared_unit="g",
            measured_quantity=Decimal("45"),
            measured_unit="g",
        )
        qm_fail = evaluate_physical_quantity(inp_fail)
        self.assertEqual(qm_fail.verdict, IndividualQuantityVerdict.FAIL)

    def test_tc08_100ml_tier_mpe(self):
        """100 ml declared is in Tier 2 (50 to 100ml: fixed 4.5ml)."""
        inp_pass = QuantityMeasurementInput(
            declared_quantity=Decimal("100"),
            declared_unit="ml",
            measured_quantity=Decimal("96"),
            measured_unit="ml",
        )
        qm_pass = evaluate_physical_quantity(inp_pass)
        self.assertEqual(qm_pass.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm_pass.statutory_mpe, Decimal("4.5"))

        inp_fail = QuantityMeasurementInput(
            declared_quantity=Decimal("100"),
            declared_unit="ml",
            measured_quantity=Decimal("95"),
            measured_unit="ml",
        )
        qm_fail = evaluate_physical_quantity(inp_fail)
        self.assertEqual(qm_fail.verdict, IndividualQuantityVerdict.FAIL)

    def test_tc09_1kg_normalization(self):
        """Declared '1 kg' normalized to 1000g; measured '990 g' -> PASS."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1"),
            declared_unit="kg",
            measured_quantity=Decimal("990"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(qm.deficiency, Decimal("10"))
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))

    def test_tc10_1L_normalization(self):
        """Declared '1 L' normalized to 1000ml; measured '980 ml' (deficiency 20ml > MPE 15ml) -> FAIL."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1"),
            declared_unit="L",
            measured_quantity=Decimal("980"),
            measured_unit="ml",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.FAIL)
        self.assertEqual(qm.deficiency, Decimal("20"))
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))

    def test_tc11_cross_dimension_barrier_g_vs_ml(self):
        """Cross-dimensional measurement (g vs ml) -> NEEDS_REVIEW."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("500"),
            declared_unit="ml",
            measured_quantity=Decimal("490"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)
        self.assertIn("Cross-dimensional mismatch", qm.notes or "")

    def test_tc12_unsupported_unit(self):
        """Unsupported/non-standard unit -> NEEDS_REVIEW."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("100"),
            declared_unit="widgets",
            measured_quantity=Decimal("95"),
            measured_unit="widgets",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)
        self.assertIn("Unsupported", qm.notes or "")

    def test_tc13_no_measurement_handling(self):
        """Missing declared quantity and declarations -> NEEDS_REVIEW with missing notes."""
        inp = QuantityMeasurementInput(
            measured_quantity=Decimal("500"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp, declarations=[])
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)
        self.assertIn("missing", qm.notes or "")

    def test_tc14_invalid_measurement_dimensions(self):
        """Invalid measurement unit dimension -> NEEDS_REVIEW."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("500"),
            declared_unit="g",
            measured_quantity=Decimal("500"),
            measured_unit="cm",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)

    def test_tc15_conflicting_declarations_across_views(self):
        """Evidence conflict on net_quantity -> NEEDS_REVIEW until officer confirms declared quantity."""
        inp = QuantityMeasurementInput(
            measured_quantity=Decimal("990"),
            measured_unit="g",
        )
        decls = [
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="1 kg",
                status=DeclarationStatus.detected,
            )
        ]
        qm = evaluate_physical_quantity(
            inp,
            declarations=decls,
            evidence_conflicts=["net_quantity"],
        )
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)
        self.assertIn("Conflicting net quantity", qm.notes or "")

    def test_tc16_multi_piece_ambiguous_target(self):
        """Multi-piece package with multiple units without explicit override -> NEEDS_REVIEW."""
        inp = QuantityMeasurementInput(
            measured_quantity=Decimal("500"),
            measured_unit="g",
        )
        decls = [
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="2 x 500 g",
                status=DeclarationStatus.detected,
            )
        ]
        comp = PackageComposition(
            package_type=PackageType.MULTI_PIECE,
            total_item_count=2,
            items=[
                PackageItem(item_index=1, commodity_name="Soap", unit_quantity="500 g"),
                PackageItem(item_index=2, commodity_name="Soap", unit_quantity="500 g"),
            ],
            status=DeclarationStatus.detected,
        )
        qm = evaluate_physical_quantity(
            inp,
            declarations=decls,
            composition=comp,
        )
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)
        self.assertIn("Multi-item", qm.notes or "")

    def test_tc17_composition_uncertainty(self):
        """Uncertain package composition without explicit override -> NEEDS_REVIEW."""
        inp = QuantityMeasurementInput(
            measured_quantity=Decimal("250"),
            measured_unit="g",
        )
        comp = PackageComposition(
            package_type=PackageType.UNCERTAIN,
            total_item_count=2,
            status=DeclarationStatus.uncertain,
        )
        qm = evaluate_physical_quantity(
            inp,
            composition=comp,
        )
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.NEEDS_REVIEW)

    def test_tc18_legacy_report_compatibility(self):
        """Legacy report dict without quantity_measurement serializes and functions safely."""
        rdict = compile_report_dict(
            scan_id="test-legacy-scan",
            verdict="PASS",
            compliance_score=100.0,
            quantity_measurement=None,
        )
        self.assertNotIn("quantity_measurement", rdict)
        self.assertEqual(rdict["compliance_summary"]["verdict"], "PASS")

    def test_tc19_report_serialization_with_quantity(self):
        """Report dict correctly serializes evaluated quantity_measurement."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("990"),
            measured_unit="g",
            instrument_id="SCALE-CAL-01",
        )
        qm = evaluate_physical_quantity(inp)
        rdict = compile_report_dict(
            scan_id="test-qty-scan",
            verdict="PASS",
            compliance_score=95.0,
            quantity_measurement=qm,
        )
        self.assertIn("quantity_measurement", rdict)
        self.assertEqual(rdict["quantity_measurement"]["verdict"], "PASS")
        self.assertEqual(float(rdict["quantity_measurement"]["deficiency"]), 10.0)
        self.assertEqual(rdict["quantity_measurement"]["instrument_id"], "SCALE-CAL-01")

    def test_tc20_visual_label_compliance_score_unchanged(self):
        """Adding a failing physical quantity measurement does NOT alter Visual Label Compliance Score."""
        inp_fail = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("900"),  # Severe deficiency
            measured_unit="g",
        )
        qm_fail = evaluate_physical_quantity(inp_fail)
        self.assertEqual(qm_fail.verdict, IndividualQuantityVerdict.FAIL)

        # Compile report with visual score of 100.0
        rdict = compile_report_dict(
            scan_id="test-score-guard",
            verdict="PASS",
            compliance_score=100.0,
            quantity_measurement=qm_fail,
        )
        # Visual score remains exactly 100.0
        self.assertEqual(rdict["compliance_summary"]["compliance_score"], 100.0)
        self.assertEqual(rdict["compliance_summary"]["score_name"], "Visual Label Compliance Score")

    def test_tc21_inspection_state_transitions(self):
        """InspectionState updates physical_checks_status: NOT_EVALUATED -> COMPLETED or PENDING."""
        # 1. No measurement -> NOT_EVALUATED
        st_none, _ = derive_inspection_state_and_next_action(
            declarations=[],
            violations=[],
            quantity_measurement=None,
        )
        self.assertEqual(st_none.physical_checks_status, PhysicalChecksStatus.NOT_EVALUATED)

        # 2. Valid measurement -> COMPLETED
        inp_pass = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("990"),
            measured_unit="g",
        )
        qm_pass = evaluate_physical_quantity(inp_pass)
        st_pass, _ = derive_inspection_state_and_next_action(
            declarations=[],
            violations=[],
            quantity_measurement=qm_pass,
        )
        self.assertEqual(st_pass.physical_checks_status, PhysicalChecksStatus.COMPLETED)

        # 3. Incompatible measurement -> PENDING
        inp_rev = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("990"),
            measured_unit="ml",
        )
        qm_rev = evaluate_physical_quantity(inp_rev)
        st_rev, _ = derive_inspection_state_and_next_action(
            declarations=[],
            violations=[],
            quantity_measurement=qm_rev,
        )
        self.assertEqual(st_rev.physical_checks_status, PhysicalChecksStatus.PENDING)

    def test_tc22_double_mpe_reference_calculation(self):
        """2xMPE reference is calculated as 2 * statutory_mpe without automated enforcement language."""
        inp = QuantityMeasurementInput(
            declared_quantity=Decimal("1000"),
            declared_unit="g",
            measured_quantity=Decimal("960"),
            measured_unit="g",
        )
        qm = evaluate_physical_quantity(inp)
        self.assertEqual(qm.statutory_mpe, Decimal("15.0"))
        self.assertEqual(qm.double_mpe_limit, Decimal("30.0"))
        self.assertEqual(qm.verdict, IndividualQuantityVerdict.FAIL)
        self.assertEqual(qm.statutory_reference, "Legal Metrology (Packaged Commodities) Rules, 2011 — First Schedule [Rules 2(e) & 22], Table I")


if __name__ == "__main__":
    unittest.main()
