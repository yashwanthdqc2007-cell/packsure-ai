"""
PackSure AI — Legal Metrology Compliance Rule Engine.

Implements Phase 5 rule evaluation pipeline:
1. Rule loading from rules.json with schema validation.
2. Dynamic applicability & exemption filtering (Rule 26, USP threshold, Country of Origin, Perishability).
3. Deterministic execution of pure field validators.
4. Robust verdict state machine (PASS / FAIL / NEEDS_REVIEW).
5. Explainable scoring & violation traceability.
"""

import json
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.rules.validators import (
    _parse_net_quantity_spec,
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
from app.schemas.compliance import (
    ComplianceResult,
    ComplianceVerdict,
    EvidenceMetadata,
)
from app.schemas.declaration import (
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.violation import (
    Violation,
    ViolationSeverity,
    ViolationType,
)

DEFAULT_RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


class Rule(BaseModel):
    """Codified Legal Metrology rule specification model."""

    rule_id: str
    rule_code: str
    title: str
    field_name: str
    requirement: str
    applies_when: str
    does_not_apply_when: str
    effective_from: str
    effective_to: Optional[str] = None
    amended_by: str
    official_source: str
    evidence_required: str
    validator_type: str
    severity: ViolationSeverity = ViolationSeverity.critical
    active: bool = True


class RuleEngine:
    """Deterministic Legal Metrology Rule Engine."""

    def __init__(self, rules_file_path: Optional[str] = None):
        self.rules_file_path = rules_file_path or DEFAULT_RULES_PATH
        self.rules_version: str = "unknown"
        self.rules_source: str = "unknown"
        self.rules: List[Rule] = self.load_rules()

    def load_rules(self) -> List[Rule]:
        """Load and validate rules from the JSON rules file."""
        if not os.path.exists(self.rules_file_path):
            raise FileNotFoundError(f"Rules configuration file not found at: {self.rules_file_path}")

        try:
            with open(self.rules_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise RuntimeError(f"Failed to read or parse rules JSON: {exc}") from exc

        self.rules_version = data.get("_version", "unknown")
        self.rules_source = data.get("_source", "Legal Metrology Rules")

        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raise ValueError("Rules configuration missing 'rules' list.")

        parsed_rules: List[Rule] = []
        for item in raw_rules:
            try:
                rule_obj = Rule(**item)
                parsed_rules.append(rule_obj)
            except Exception as exc:
                raise ValueError(f"Malformed rule entry in rules.json: {exc} | Item: {item}") from exc

        return parsed_rules

    def get_active_rules(self, category: Optional[str] = None) -> List[Rule]:
        """Return all currently active rules, optionally filtered by category."""
        return [r for r in self.rules if r.active]

    def _is_perishable_category(self, category: Optional[str]) -> bool:
        """Infer if category requires mandatory expiry date (Rule 6(1)(m))."""
        if not category:
            return True  # Default to conservative compliance check
        cat_lower = category.lower()
        non_perishable_terms = (
            "hardware", "electronics", "electrical", "stationery", "tools",
            "steel", "utensils", "apparel", "textile", "toys", "plastic"
        )
        if any(term in cat_lower for term in non_perishable_terms):
            return False
        return True

    def _is_imported_product(self, category: Optional[str], decl_map: Dict[str, ExtractedDeclaration]) -> bool:
        """Determine if product has imported status requiring Rule 6(1)(aa)."""
        if category and "import" in category.lower():
            return True

        # Check if address contains 'imported by' or foreign country indicator
        addr_decl = decl_map.get("manufacturer_name_and_address")
        if addr_decl and addr_decl.raw_value:
            txt = addr_decl.raw_value.lower()
            if any(term in txt for term in ("imported by", "importer:", "imp by", "mfg in", "made in")):
                return True

        country_decl = decl_map.get("country_of_origin")
        if country_decl and country_decl.raw_value:
            country_txt = country_decl.raw_value.strip().lower()
            if country_txt and country_txt != "india":
                return True

        return False

    def _is_usp_applicable(self, net_qty_decl: Optional[ExtractedDeclaration]) -> bool:
        """Check if Unit Sale Price is mandatory under Rule 6(11).

        Statutory exemptions under Rule 6(11) & Rule 26(a):
        - Net quantity is exactly 1 kg, 1 L, 1 m, or 1 number/unit/piece.
        - Small packages (<= 10g or <= 10ml) exempt under Rule 26(a).
        - Insufficient / malformed quantity data does not trigger a false USP mandate.
        """
        if not net_qty_decl:
            return False
        text = (net_qty_decl.normalized_value or net_qty_decl.raw_value or "").strip()
        if not text:
            return False

        parsed_qty = _parse_net_quantity_spec(text)
        if not parsed_qty:
            return False

        norm_val, dim_type, _ = parsed_qty

        # Small package exemption (<= 10g / <= 10ml / <= 10cm) under Rule 26(a)
        if dim_type in ("mass", "volume", "length") and norm_val <= Decimal("10"):
            return False

        # Exact 1-unit statutory exemptions under Rule 6(11)
        if dim_type == "mass" and norm_val == Decimal("1000"):  # exact 1 kg (1000 g)
            return False
        if dim_type == "volume" and norm_val == Decimal("1000"):  # exact 1 L (1000 ml)
            return False
        if dim_type == "length" and norm_val == Decimal("100"):  # exact 1 m (100 cm)
            return False
        if dim_type == "count" and norm_val == Decimal("1"):  # exact 1 number / piece / unit
            return False

        return True

    def evaluate_compliance(
        self,
        declarations: List[ExtractedDeclaration],
        product_category: Optional[str] = None,
        is_imported: Optional[bool] = None,
        is_perishable: Optional[bool] = None,
        is_complete_scan: bool = True,
    ) -> ComplianceResult:
        """Evaluate extracted declarations against versioned Legal Metrology rules.

        Args:
            declarations: List of ExtractedDeclaration objects from Phase 4.
            product_category: Optional category string (e.g. 'Food & Beverages', 'Electronics').
            is_imported: Optional flag indicating import status. If None, inferred from context.
            is_perishable: Optional flag indicating perishability. If None, inferred from category.
            is_complete_scan: Flag indicating whether all packaging panels were captured.

        Returns:
            ComplianceResult with verdict, compliance_score, violations, and metadata.
        """
        decl_map: Dict[str, ExtractedDeclaration] = {d.field_name: d for d in declarations}
        active_rules = self.get_active_rules(product_category)

        # Infer context parameters
        imported_context = is_imported if is_imported is not None else self._is_imported_product(product_category, decl_map)
        perishable_context = is_perishable if is_perishable is not None else self._is_perishable_category(product_category)

        # Check Rule 26 Small Package Exemption
        net_qty_decl = decl_map.get("net_quantity")
        net_qty_text = (net_qty_decl.normalized_value or net_qty_decl.raw_value or "") if net_qty_decl else ""
        is_rule26_exempt = check_rule26_exemption(net_qty_text, product_category)

        # Check USP Applicability
        usp_applicable = self._is_usp_applicable(net_qty_decl)

        violations: List[Violation] = []
        has_uncertainty = False
        declarations_checked_count = 0

        for rule in active_rules:
            # Skip Rule 26 entry itself from execution
            if rule.rule_id == "LMR-R26-A":
                continue

            # Country of Origin Rule 6(1)(aa) applicability check
            if rule.rule_id == "LMR-R06-1-AA" and not imported_context:
                # Not applicable for purely domestic commodities
                continue

            # Expiry Date Rule 6(1)(m) applicability check
            if rule.rule_id == "LMR-R06-1-M" and not perishable_context:
                # Non-perishable goods are exempt from mandatory expiry date
                continue

            # Unit Sale Price Rule 6(11) applicability check (supporting backward-compat LMR-R06-1-F)
            if (rule.rule_id in ("LMR-R06-11", "LMR-R06-1-F") or rule.validator_type == "unit_sale_price") and not usp_applicable:
                # Packages <= 10g/ml or exact 1kg/1L/1m/1N are exempt
                continue

            declarations_checked_count += 1
            decl = decl_map.get(rule.field_name)

            # Case 1: Declaration was extracted with status == uncertain
            if decl and decl.status == DeclarationStatus.uncertain:
                has_uncertainty = True
                continue

            # Case 2: Declaration was not extracted / omitted
            if not decl:
                if is_rule26_exempt:
                    # Small packages <= 10g or <= 10ml exempt from missing declarations under Rule 26(a)
                    continue

                if is_complete_scan:
                    # Confirmed complete scan -> genuine missing mandatory declaration violation
                    violations.append(
                        Violation(
                            rule_code=rule.rule_code,
                            rule_id=rule.rule_id,
                            field_name=rule.field_name,
                            violation_type=ViolationType.missing_declaration,
                            severity=rule.severity,
                            description=(
                                f"Mandatory declaration '{rule.title}' is missing. "
                                f"Requirement: {rule.requirement} (Ref: {rule.official_source})."
                            ),
                        )
                    )
                else:
                    # Incomplete / single-panel scan -> route to uncertainty rather than false FAIL
                    has_uncertainty = True
                continue

            # Case 3: Declaration detected -> execute pure deterministic validator
            val_result = None
            raw_v = decl.raw_value
            norm_v = decl.normalized_value

            if rule.validator_type == "address":
                val_result = validate_address(raw_v)
            elif rule.validator_type == "country_of_origin":
                val_result = validate_country_of_origin(raw_v, is_imported=imported_context)
            elif rule.validator_type == "generic_name":
                val_result = validate_generic_name(raw_v)
            elif rule.validator_type == "net_quantity":
                val_result = validate_net_quantity(raw_v, norm_v)
            elif rule.validator_type == "manufacture_date":
                val_result = validate_manufacture_date(raw_v, norm_v)
            elif rule.validator_type == "mrp":
                val_result = validate_mrp(raw_v, norm_v)
            elif rule.validator_type == "unit_sale_price":
                mrp_decl = decl_map.get("mrp")
                mrp_text = (mrp_decl.normalized_value or mrp_decl.raw_value) if mrp_decl else None
                val_result = validate_unit_sale_price(
                    raw_v or norm_v,
                    net_qty_text=net_qty_text,
                    mrp_text=mrp_text,
                    is_usp_applicable=usp_applicable,
                )
            elif rule.validator_type == "batch_number":
                val_result = validate_batch_number(raw_v)
            elif rule.validator_type == "expiry_date":
                mfd_text = decl_map.get("manufacture_date", ExtractedDeclaration(field_name="manufacture_date")).raw_value
                val_result = validate_expiry_date(raw_v, mfd_text, is_perishable=perishable_context)
            elif rule.validator_type == "consumer_care":
                val_result = validate_consumer_care(raw_v)

            if val_result and not val_result.is_valid:
                # Evidence Coverage Semantics for Incomplete Scans:
                # If the scan is incomplete (is_complete_scan=False) and MRP has a valid price amount
                # but the mandatory tax wording ('inclusive of all taxes') was not observed on the captured panel,
                # do NOT issue an immediate statutory FAIL. Instead route to NEEDS_REVIEW / uncertainty guidance.
                if (
                    not is_complete_scan
                    and rule.validator_type == "mrp"
                    and "inclusive of all taxes" in (val_result.error_message or "").lower()
                ):
                    has_uncertainty = True
                    continue

                violations.append(
                    Violation(
                        rule_code=rule.rule_code,
                        rule_id=rule.rule_id,
                        field_name=rule.field_name,
                        violation_type=val_result.violation_type or ViolationType.invalid_format,
                        severity=rule.severity,
                        description=(
                            f"{val_result.error_message} "
                            f"(Ref: {rule.rule_code}, {rule.official_source})."
                        ),
                    )
                )

        # Deterministic Scoring & Verdict Calculation
        # Base score 100.0 with calibrated deductions per violation severity:
        # Critical = -30.0, Major = -15.0, Minor = -5.0
        score = 100.0
        for v in violations:
            if v.severity == ViolationSeverity.critical:
                score -= 30.0
            elif v.severity == ViolationSeverity.major:
                score -= 15.0
            elif v.severity == ViolationSeverity.minor:
                score -= 5.0

        compliance_score = max(0.0, min(100.0, round(score, 2)))

        # Verdict State Machine
        has_critical = any(v.severity == ViolationSeverity.critical for v in violations)
        has_major = any(v.severity == ViolationSeverity.major for v in violations)

        if has_critical or has_major:
            verdict = ComplianceVerdict.FAIL
        elif has_uncertainty:
            verdict = ComplianceVerdict.NEEDS_REVIEW
        elif any(v.severity == ViolationSeverity.minor for v in violations):
            verdict = ComplianceVerdict.NEEDS_REVIEW
        else:
            verdict = ComplianceVerdict.PASS

        evidence_meta = EvidenceMetadata(
            rule_version=self.rules_version,
            total_declarations_checked=declarations_checked_count,
            total_violations_found=len(violations),
        )

        return ComplianceResult(
            verdict=verdict,
            compliance_score=compliance_score,
            declarations=declarations,
            violations=violations,
            evidence=evidence_meta,
        )


# Global singleton rule engine instance
rule_engine = RuleEngine()
