"""
PackSure AI — Structured Inspection Report Service.

Compiles deterministic Legal Metrology inspection reports into machine-readable
JSON documents compliant with the Legal Metrology (Packaged Commodities) Rules, 2011.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from app.schemas.compliance import ComplianceResult, ComplianceVerdict
from app.schemas.declaration import ExtractedDeclaration
from app.schemas.violation import Violation

logger = logging.getLogger(__name__)

REPORT_FORMAT_VERSION = "1.0.0"
SYSTEM_NAME = "PackSure AI"
SYSTEM_VERSION = "0.1.0"
REGULATORY_FRAMEWORK = "Legal Metrology (Packaged Commodities) Rules, 2011"
REGULATORY_JURISDICTION = "India"


def _extract_product_name(declarations: List[ExtractedDeclaration]) -> Optional[str]:
    """Derive product/commodity name from generic_name declaration if present."""
    for decl in declarations:
        if decl.field_name in ("generic_name", "product_name", "commodity_name"):
            return decl.normalized_value or decl.raw_value
    return None


def compile_report_dict(
    scan_id: str,
    verdict: Optional[Union[str, ComplianceVerdict]] = None,
    compliance_score: Optional[float] = None,
    product_category: Optional[str] = None,
    declarations: Optional[List[ExtractedDeclaration]] = None,
    violations: Optional[List[Violation]] = None,
    image_path: Optional[str] = None,
    evidence_path: Optional[str] = None,
    created_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    status: str = "complete",
    reviewer_notes: Optional[str] = None,
    compliance_result: Optional[ComplianceResult] = None,
) -> Dict[str, Any]:
    """Compile structured inspection report dictionary from scan domain models.

    Args:
        scan_id: Unique UUID of the scan.
        verdict: Overall compliance verdict (PASS, FAIL, NEEDS_REVIEW).
        compliance_score: Score between 0.0 and 100.0.
        product_category: Commodity category name.
        declarations: List of extracted declarations.
        violations: List of rule violations.
        image_path: Local or remote path to original image.
        evidence_path: Local or remote path to annotated evidence image.
        created_at: ISO8601 creation timestamp.
        completed_at: ISO8601 completion timestamp.
        status: Scan lifecycle status string.
        reviewer_notes: Human reviewer notes if reviewed.
        compliance_result: Optional ComplianceResult object to populate fields.

    Returns:
        Structured dictionary matching the canonical inspection report schema.
    """
    # Unpack from compliance_result if provided and direct args were not passed
    if compliance_result is not None:
        if verdict is None:
            verdict = compliance_result.verdict
        if compliance_score is None:
            compliance_score = compliance_result.compliance_score
        if declarations is None:
            declarations = compliance_result.declarations
        if violations is None:
            violations = compliance_result.violations
        if evidence_path is None and compliance_result.evidence:
            evidence_path = (
                compliance_result.evidence.annotated_image_path
                or compliance_result.evidence.evidence_image_url
            )

    decls_list: List[ExtractedDeclaration] = declarations or []
    viols_list: List[Violation] = violations or []

    # Format verdict string
    verdict_str: Optional[str] = None
    if verdict is not None:
        verdict_str = verdict.value if isinstance(verdict, ComplianceVerdict) else str(verdict)

    now_iso = datetime.now(timezone.utc).isoformat()
    if completed_at is None and status == "complete":
        completed_at = now_iso
    if created_at is None:
        created_at = now_iso

    # Serialize declarations
    serialized_declarations: List[Dict[str, Any]] = []
    for d in decls_list:
        status_val = d.status.value if hasattr(d.status, "value") else str(d.status)
        source_val = d.source.value if d.source and hasattr(d.source, "value") else (str(d.source) if d.source else None)
        bbox_dict = None
        if d.bounding_box is not None:
            bbox_dict = {
                "x": round(float(d.bounding_box.x), 2),
                "y": round(float(d.bounding_box.y), 2),
                "width": round(float(d.bounding_box.width), 2),
                "height": round(float(d.bounding_box.height), 2),
            }

        serialized_declarations.append(
            {
                "field_name": d.field_name,
                "status": status_val,
                "raw_value": d.raw_value,
                "normalized_value": d.normalized_value,
                "confidence": round(float(d.confidence), 4) if d.confidence is not None else 0.0,
                "source": source_val,
                "bounding_box": bbox_dict,
            }
        )

    # Serialize violations
    serialized_violations: List[Dict[str, Any]] = []
    for v in viols_list:
        v_type = v.violation_type.value if hasattr(v.violation_type, "value") else str(v.violation_type)
        v_sev = v.severity.value if hasattr(v.severity, "value") else str(v.severity)
        serialized_violations.append(
            {
                "id": v.id,
                "rule_id": v.rule_id,
                "rule_code": v.rule_code,
                "field_name": v.field_name,
                "violation_type": v_type,
                "severity": v_sev,
                "description": v.description,
            }
        )

    product_name = _extract_product_name(decls_list)

    report_dict: Dict[str, Any] = {
        "report_metadata": {
            "report_format": "json",
            "report_version": REPORT_FORMAT_VERSION,
            "generated_at": now_iso,
            "system_name": SYSTEM_NAME,
            "system_version": SYSTEM_VERSION,
        },
        "regulatory_reference": {
            "framework": REGULATORY_FRAMEWORK,
            "jurisdiction": REGULATORY_JURISDICTION,
        },
        "scan_metadata": {
            "scan_id": scan_id,
            "status": status,
            "created_at": created_at,
            "completed_at": completed_at,
        },
        "product_information": {
            "product_category": product_category,
            "product_name": product_name,
        },
        "compliance_summary": {
            "verdict": verdict_str,
            "compliance_score": round(float(compliance_score), 2) if compliance_score is not None else None,
            "total_declarations_evaluated": len(decls_list),
            "total_violations_found": len(viols_list),
        },
        "declarations": serialized_declarations,
        "violations": serialized_violations,
        "evidence_artifacts": {
            "original_image_path": image_path,
            "evidence_image_path": evidence_path,
        },
        "reviewer_audit": {
            "is_reviewed": reviewer_notes is not None,
            "reviewer_notes": reviewer_notes,
        },
    }

    return report_dict


def generate_json_report(
    scan_id: str,
    verdict: Optional[Union[str, ComplianceVerdict]] = None,
    compliance_score: Optional[float] = None,
    product_category: Optional[str] = None,
    declarations: Optional[List[ExtractedDeclaration]] = None,
    violations: Optional[List[Violation]] = None,
    image_path: Optional[str] = None,
    evidence_path: Optional[str] = None,
    output_path: Optional[str] = None,
    created_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    status: str = "complete",
    reviewer_notes: Optional[str] = None,
    compliance_result: Optional[ComplianceResult] = None,
) -> str:
    """Generate and serialize a structured JSON inspection report to disk.

    Args:
        scan_id: Unique UUID of the scan.
        verdict: Overall compliance verdict.
        compliance_score: Compliance score (0-100).
        product_category: Category name.
        declarations: Extracted declarations.
        violations: Rule violations.
        image_path: Original image path.
        evidence_path: Annotated evidence image path.
        output_path: Destination file path (defaults to storage/scans/{scan_id}/report.json).
        created_at: ISO8601 creation timestamp.
        completed_at: ISO8601 completion timestamp.
        status: Lifecycle status.
        reviewer_notes: Human reviewer notes.
        compliance_result: Optional ComplianceResult object.

    Returns:
        The file path where the report JSON was written.
    """
    report_dict = compile_report_dict(
        scan_id=scan_id,
        verdict=verdict,
        compliance_score=compliance_score,
        product_category=product_category,
        declarations=declarations,
        violations=violations,
        image_path=image_path,
        evidence_path=evidence_path,
        created_at=created_at,
        completed_at=completed_at,
        status=status,
        reviewer_notes=reviewer_notes,
        compliance_result=compliance_result,
    )

    if not output_path:
        output_path = os.path.join("storage", "scans", scan_id, "report.json")

    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info(f"Generated JSON inspection report for scan {scan_id} at {output_path}")
    return output_path
