"""
PackSure AI — Rules Route.

GET /api/v1/rules
Returns list of active, versioned Legal Metrology compliance rules with official source citations.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query

from app.rules.rule_engine import rule_engine

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=Dict[str, Any])
def get_rules(category: Optional[str] = Query(default=None, description="Filter rules by product category")) -> Dict[str, Any]:
    """Return active Legal Metrology rules, version metadata, and citations."""
    active_rules = rule_engine.get_active_rules(category=category)
    return {
        "version": rule_engine.rules_version,
        "source": rule_engine.rules_source,
        "total_rules": len(active_rules),
        "rules": [rule.model_dump() for rule in active_rules],
    }
