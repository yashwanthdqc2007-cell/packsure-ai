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
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
        """Check if Unit Sale Price is mandatory (> 100g / > 100ml / > 1m)."""
        if not net_qty_decl:
            return False
        text = (net_qty_decl.normalized_value or net_qty_decl.raw_value or "").strip()
        if not text:
            return False

        # Exemption if exactly 1kg, 1L, 1m, 1N
        if re.search(r"\b1\s*(kg|l|L|m|N|U)\b", text):
            return False

        # Check if weight in grams > 100g
        match_g = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gm|gms)\b", text, re.IGNORECASE)
        if match_g and float(match_g.group(1)) > 100.0:
            return True

        # Check if weight in kg
        match_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", text, re.IGNORECASE)
        if match_kg and float(match_kg.group(1)) > 0.1:
            return True

        # Check if volume in ml > 100ml
        match_ml = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", text, re.IGNORECASE)
        if match_ml and float(match_ml.group(1)) > 100.0:
            return True

        # Check if volume in L
        match_l = re.search(r"(\d+(?:\.\d+)?)\s*(?:l|L)\b", text, re.IGNORECASE)
        if match_l and float(match_l.group(1)) > 0.1:
            return True

        return False

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

            # Unit Sale Price Rule 6(1)(f) applicability check
            if rule.rule_id == "LMR-R06-1-F" and not usp_applicable:
                # Packages <= 100g/ml or exact 1kg/1L are exempt
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
                val_result = validate_unit_sale_price(raw_v, net_qty_text, is_usp_applicable=usp_applicable)
            elif rule.validator_type == "batch_number":
                val_result = validate_batch_number(raw_v)
            elif rule.validator_type == "expiry_date":
                mfd_text = decl_map.get("manufacture_date", ExtractedDeclaration(field_name="manufacture_date")).raw_value
                val_result = validate_expiry_date(raw_v, mfd_text, is_perishable=perishable_context)
            elif rule.validator_type == "consumer_care":
                val_result = validate_consumer_care(raw_v)

            if val_result and not val_result.is_valid:
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
