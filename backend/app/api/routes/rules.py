"""
PackSure AI — Rules Route.

GET /api/v1/rules
Retrieve active Legal Metrology rules applicable to product packaging adhering to docs/api.md.
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.rules.rule_engine import Rule, rule_engine


class RuleItemResponse(BaseModel):
    """Documented rule item representation conforming to docs/api.md."""

    id: str = Field(..., description="Unique rule identifier (e.g., LMR-R06-1-A)")
    rule_code: str = Field(..., description="Statutory rule citation (e.g., Rule-6(1)(a))")
    title: str = Field(..., description="Short descriptive rule title")
    description: str = Field(..., description="Statutory requirement specification")
    field_name: str = Field(..., description="Target declaration field name")
    validation_type: str = Field(..., description="Validator type classification")
    severity: str = Field(..., description="Violation severity level (critical, major, minor)")
    version: str = Field(..., description="Statutory enactment/amendment version year")
    active: bool = Field(..., description="Whether rule is currently active")


class RulesListResponse(BaseModel):
    """Documented top-level rules list response conforming to docs/api.md."""

    category: str = Field(..., description="Category filter applied or 'all'")
    total: int = Field(..., description="Total number of rules returned")
    rules: List[RuleItemResponse] = Field(..., description="List of applicable legal metrology rules")


router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


def _map_rule_to_response(rule: Rule) -> RuleItemResponse:
    """Map internal Rule definition to public API contract format."""
    severity_val = rule.severity.value if hasattr(rule.severity, "value") else str(rule.severity)
    version_val = (
        rule.effective_from[:4]
        if rule.effective_from and len(rule.effective_from) >= 4
        else "2011"
    )
    return RuleItemResponse(
        id=rule.rule_id,
        rule_code=rule.rule_code,
        title=rule.title,
        description=rule.requirement,
        field_name=rule.field_name,
        validation_type=rule.validator_type,
        severity=severity_val,
        version=version_val,
        active=rule.active,
    )


RECOGNIZED_PERISHABLE_CATEGORIES = {
    "food",
    "food grains",
    "food & beverages",
    "edible oil",
    "snacks",
    "beverages",
    "packaged food",
    "dairy",
    "spices",
    "confectionery",
    "bakery",
    "cereals",
    "pulses",
    "meat",
    "fish",
    "cosmetics",
    "pharmaceuticals",
    "drugs",
    "personal care",
    "fruits",
    "vegetables",
    "groceries",
}

RECOGNIZED_NON_PERISHABLE_CATEGORIES = {
    "hardware",
    "electronics",
    "electrical",
    "stationery",
    "tools",
    "steel",
    "utensils",
    "apparel",
    "textile",
    "toys",
    "plastic",
    "footwear",
    "furniture",
    "automotive",
    "chemicals",
}

RECOGNIZED_SPECIAL_CATEGORIES = {
    "tobacco",
    "tobacco / cigarettes",
    "cigarettes",
    "beedi",
    "cigar",
    "general",
    "fmcg",
    "consumer goods",
    "pre-packaged commodity",
    "all",
}


@router.get("", response_model=RulesListResponse)
def get_rules(
    category: Optional[str] = Query(
        default=None,
        description="Filter rules applicable to a specific category.",
    ),
    active_only: bool = Query(
        default=True,
        description="When true, returns only active rules.",
    ),
) -> RulesListResponse:
    """Retrieve active Legal Metrology rules applicable to product packaging."""
    # Handle direct test calls where FastAPI Query default object may be passed
    cat_param = category if isinstance(category, str) else None
    active_flag = active_only if isinstance(active_only, bool) else True

    rules_pool: List[Rule] = rule_engine.rules

    if active_flag:
        rules_pool = [r for r in rules_pool if r.active]

    if cat_param is not None and cat_param.strip() != "" and cat_param.strip().lower() != "all":
        cat_clean = cat_param.strip()
        cat_lower = cat_clean.lower()
        response_category = cat_clean

        is_perishable = any(c in cat_lower for c in RECOGNIZED_PERISHABLE_CATEGORIES)
        is_non_perishable = any(c in cat_lower for c in RECOGNIZED_NON_PERISHABLE_CATEGORIES)
        is_special = any(c in cat_lower for c in RECOGNIZED_SPECIAL_CATEGORIES)

        if not (is_perishable or is_non_perishable or is_special):
            # Unknown / unsupported / empty category
            filtered_rules = []
        else:
            matched_rules: List[Rule] = []
            for r in rules_pool:
                if is_non_perishable and not is_perishable:
                    if r.validator_type == "expiry_date" or r.field_name == "expiry_date":
                        continue
                matched_rules.append(r)
            filtered_rules = matched_rules
    else:
        response_category = "all"
        filtered_rules = rules_pool

    mapped_items = [_map_rule_to_response(r) for r in filtered_rules]

    return RulesListResponse(
        category=response_category,
        total=len(mapped_items),
        rules=mapped_items,
    )
