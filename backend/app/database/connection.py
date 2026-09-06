"""
PackSure AI — Database Connection & Repository Layer.

Provides data persistence abstractions for scans, extracted declarations, violations,
AI analysis, and reports according to database/schema.sql.

Architecture:
- BaseScanRepository: Abstract repository interface.
- SupabaseScanRepository: Production repository connecting to Supabase / PostgreSQL.
  Raises a configuration error if database environment variables are missing (never silently falls back).
- InMemoryScanRepository: Explicit test-only in-memory repository for deterministic testing.
"""

from abc import ABC, abstractmethod
from collections import Counter
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, List, Optional
import requests

from app.core.config import settings
from app.schemas.declaration import (
    DeclarationSource,
    DeclarationStatus,
    ExtractedDeclaration,
)
from app.schemas.ocr import BoundingBox
from app.schemas.violation import Violation, ViolationSeverity, ViolationType

logger = logging.getLogger(__name__)


def _parse_iso_datetime(val: Any) -> Optional[datetime]:
    """Parse ISO8601 string or date into UTC datetime object."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if not isinstance(val, str):
        return None
    try:
        clean_str = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(val[:10], "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None


class BaseScanRepository(ABC):
    """Abstract interface for PackSure AI persistence operations."""

    @abstractmethod
    def create_scan(
        self,
        scan_id: str,
        product_category: Optional[str] = None,
        user_id: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new scan record with status='pending'."""
        pass

    @abstractmethod
    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve scan record by unique scan UUID."""
        pass

    @abstractmethod
    def update_scan(self, scan_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update fields of an existing scan record."""
        pass

    @abstractmethod
    def save_declarations(self, scan_id: str, declarations: List[ExtractedDeclaration]) -> None:
        """Persist extracted declaration records associated with a scan."""
        pass

    @abstractmethod
    def get_declarations(self, scan_id: str) -> List[ExtractedDeclaration]:
        """Fetch all extracted declarations for a scan."""
        pass

    @abstractmethod
    def save_violations(self, scan_id: str, violations: List[Violation]) -> None:
        """Persist rule violation records associated with a scan."""
        pass

    @abstractmethod
    def get_violations(self, scan_id: str) -> List[Violation]:
        """Fetch all rule violations for a scan."""
        pass

    @abstractmethod
    def save_ai_analysis(
        self,
        scan_id: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        raw_response: Optional[Any] = None,
    ) -> None:
        """Persist raw Gemini API extraction response audit trail."""
        pass

    @abstractmethod
    def save_report(self, scan_id: str, report_url: str, format_type: str = "json") -> None:
        """Persist generated compliance report metadata."""
        pass

    @abstractmethod
    def delete_child_records(self, scan_id: str) -> None:
        """Idempotently purge child declarations, violations, AI analysis, and reports on scan rerun."""
        pass

    @abstractmethod
    def query_history(
        self,
        page: int = 1,
        limit: int = 20,
        verdict: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query paginated historical scans with optional filters."""
        pass

    @abstractmethod
    def query_analytics(
        self,
        period: str = "7d",
    ) -> Dict[str, Any]:
        """Retrieve aggregated compliance metrics, pass rates, category distributions, and daily activity trends."""
        pass


class InMemoryScanRepository(BaseScanRepository):
    """Explicit in-memory test fake for deterministic offline testing."""

    def __init__(self):
        self.scans: Dict[str, Dict[str, Any]] = {}
        self.declarations: Dict[str, List[ExtractedDeclaration]] = {}
        self.violations: Dict[str, List[Violation]] = {}
        self.ai_analysis: Dict[str, List[Dict[str, Any]]] = {}
        self.reports: Dict[str, List[Dict[str, Any]]] = {}

    def create_scan(
        self,
        scan_id: str,
        product_category: Optional[str] = None,
        user_id: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        record = {
            "id": scan_id,
            "user_id": user_id,
            "status": "pending",
            "verdict": None,
            "compliance_score": None,
            "image_url": image_url,
            "processed_image_url": None,
            "evidence_image_url": None,
            "product_category": product_category,
            "reviewer_notes": None,
            "created_at": now_iso,
            "completed_at": None,
        }
        self.scans[scan_id] = record
        return record

    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        return self.scans.get(scan_id)

    def update_scan(self, scan_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if scan_id not in self.scans:
            return None
        self.scans[scan_id].update(update_data)
        return self.scans[scan_id]

    def save_declarations(self, scan_id: str, declarations: List[ExtractedDeclaration]) -> None:
        if scan_id not in self.declarations:
            self.declarations[scan_id] = []
        self.declarations[scan_id].extend(declarations)

    def get_declarations(self, scan_id: str) -> List[ExtractedDeclaration]:
        return self.declarations.get(scan_id, [])

    def save_violations(self, scan_id: str, violations: List[Violation]) -> None:
        if scan_id not in self.violations:
            self.violations[scan_id] = []
        self.violations[scan_id].extend(violations)

    def get_violations(self, scan_id: str) -> List[Violation]:
        return self.violations.get(scan_id, [])

    def save_ai_analysis(
        self,
        scan_id: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        raw_response: Optional[Any] = None,
    ) -> None:
        if scan_id not in self.ai_analysis:
            self.ai_analysis[scan_id] = []
        self.ai_analysis[scan_id].append(
            {
                "scan_id": scan_id,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens,
                "raw_response": raw_response,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def save_report(self, scan_id: str, report_url: str, format_type: str = "json") -> None:
        if scan_id not in self.reports:
            self.reports[scan_id] = []
        self.reports[scan_id].append(
            {
                "scan_id": scan_id,
                "report_url": report_url,
                "format": format_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def delete_child_records(self, scan_id: str) -> None:
        self.declarations.pop(scan_id, None)
        self.violations.pop(scan_id, None)
        self.ai_analysis.pop(scan_id, None)
        self.reports.pop(scan_id, None)

    def query_history(
        self,
        page: int = 1,
        limit: int = 20,
        verdict: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query paginated historical scans with optional filters."""
        page = max(1, page)
        limit = max(1, min(100, limit))

        filtered: List[Dict[str, Any]] = []

        from_dt = _parse_iso_datetime(from_date) if from_date else None
        to_dt = _parse_iso_datetime(to_date) if to_date else None
        if to_dt and to_date and len(to_date.strip()) <= 10:
            to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

        for scan_id, scan in self.scans.items():
            # Resolve product name from extracted generic_name declaration
            decls = self.declarations.get(scan_id, [])
            product_name = None
            for d in decls:
                if d.field_name == "generic_name":
                    product_name = d.normalized_value or d.raw_value
                    if product_name:
                        break

            # Verdict filter
            if verdict:
                scan_verdict = scan.get("verdict")
                if not scan_verdict or scan_verdict.upper() != verdict.strip().upper():
                    continue

            # Category filter
            if category:
                cat_filter = category.strip().lower()
                scan_cat = (scan.get("product_category") or "").lower()
                if cat_filter not in scan_cat:
                    continue

            # Date boundaries
            scan_dt = _parse_iso_datetime(scan.get("created_at"))
            if from_dt and scan_dt and scan_dt < from_dt:
                continue
            if to_dt and scan_dt and scan_dt > to_dt:
                continue

            # Search filter (across scan ID, category, product name)
            if search:
                s_query = search.strip().lower()
                id_match = s_query in scan["id"].lower()
                cat_match = bool(scan.get("product_category") and s_query in scan["product_category"].lower())
                name_match = bool(product_name and s_query in product_name.lower())
                if not (id_match or cat_match or name_match):
                    continue

            filtered.append(
                {
                    "id": scan["id"],
                    "product_name": product_name,
                    "category": scan.get("product_category"),
                    "scanned_at": scan.get("created_at"),
                    "verdict": scan.get("verdict"),
                    "compliance_score": scan.get("compliance_score"),
                    "status": scan.get("status", "complete"),
                    "_sort_dt": scan_dt or datetime.min.replace(tzinfo=timezone.utc),
                }
            )

        # Sort chronological descending (newest first)
        filtered.sort(key=lambda item: item["_sort_dt"], reverse=True)

        total = len(filtered)
        total_pages = math.ceil(total / limit) if total > 0 else 0
        start = (page - 1) * limit
        end = start + limit
        paginated_items = filtered[start:end]

        for item in paginated_items:
            item.pop("_sort_dt", None)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "results": paginated_items,
        }

    def query_analytics(
        self,
        period: str = "7d",
    ) -> Dict[str, Any]:
        """Compute aggregated compliance statistics, daily trends, top violations, and category breakdown."""
        now = datetime.now(timezone.utc)
        cutoff_dt: Optional[datetime] = None

        clean_period = period.strip().lower() if period else "7d"
        if clean_period == "7d":
            cutoff_dt = now - timedelta(days=7)
        elif clean_period == "30d":
            cutoff_dt = now - timedelta(days=30)
        elif clean_period == "all":
            cutoff_dt = None
        else:
            cutoff_dt = now - timedelta(days=7)

        period_scans: List[Dict[str, Any]] = []
        for scan in self.scans.values():
            scan_dt = _parse_iso_datetime(scan.get("created_at"))
            if cutoff_dt and scan_dt and scan_dt < cutoff_dt:
                continue
            period_scans.append(scan)

        total_scans = len(period_scans)
        pass_count = sum(1 for s in period_scans if s.get("verdict") == "PASS")
        fail_count = sum(1 for s in period_scans if s.get("verdict") == "FAIL")
        review_count = sum(1 for s in period_scans if s.get("verdict") == "NEEDS_REVIEW")
        pass_rate = round((pass_count / total_scans) * 100.0, 1) if total_scans > 0 else 0.0

        # Daily trend aggregation
        daily_groups: Dict[str, Dict[str, Any]] = {}
        for s in period_scans:
            s_dt = _parse_iso_datetime(s.get("created_at"))
            date_key = s_dt.strftime("%Y-%m-%d") if s_dt else now.strftime("%Y-%m-%d")
            day_name = s_dt.strftime("%a") if s_dt else now.strftime("%a")

            if date_key not in daily_groups:
                daily_groups[date_key] = {
                    "day": day_name,
                    "date": date_key,
                    "scans": 0,
                    "compliant": 0,
                    "non_compliant": 0,
                    "needs_review": 0,
                }
            daily_groups[date_key]["scans"] += 1
            verdict = s.get("verdict")
            if verdict == "PASS":
                daily_groups[date_key]["compliant"] += 1
            elif verdict == "FAIL":
                daily_groups[date_key]["non_compliant"] += 1
            elif verdict == "NEEDS_REVIEW":
                daily_groups[date_key]["needs_review"] += 1

        daily_trend = [daily_groups[k] for k in sorted(daily_groups.keys())]

        # Top violations aggregation
        violation_counts: Counter = Counter()
        violation_descriptions: Dict[str, str] = {}
        period_scan_ids = {s["id"] for s in period_scans}

        for s_id in period_scan_ids:
            for v in self.violations.get(s_id, []):
                r_code = v.rule_code or "Unknown Rule"
                violation_counts[r_code] += 1
                if r_code not in violation_descriptions and v.description:
                    violation_descriptions[r_code] = v.description

        top_violations: List[Dict[str, Any]] = []
        for r_code, count in violation_counts.most_common():
            top_violations.append(
                {
                    "rule_code": r_code,
                    "description": violation_descriptions.get(r_code, r_code),
                    "count": count,
                }
            )

        # By category aggregation
        category_stats: Dict[str, Dict[str, Any]] = {}
        for s in period_scans:
            cat = s.get("product_category")
            if not cat:
                continue
            if cat not in category_stats:
                category_stats[cat] = {
                    "total": 0,
                    "pass": 0,
                    "fail": 0,
                    "review": 0,
                }
            category_stats[cat]["total"] += 1
            verdict = s.get("verdict")
            if verdict == "PASS":
                category_stats[cat]["pass"] += 1
            elif verdict == "FAIL":
                category_stats[cat]["fail"] += 1
            elif verdict == "NEEDS_REVIEW":
                category_stats[cat]["review"] += 1

        return {
            "total_scans": total_scans,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "review_count": review_count,
            "pass_rate": pass_rate,
            "daily_trend": daily_trend,
            "top_violations": top_violations,
            "by_category": category_stats,
        }


class SupabaseScanRepository(BaseScanRepository):
    """Production persistent repository integrating with Supabase PostgREST endpoints."""

    def __init__(self):
        self.supabase_url = settings.supabase_url.rstrip("/") if settings.supabase_url else ""
        self.supabase_key = settings.supabase_anon_key

    def _verify_configuration(self) -> None:
        """Ensure Supabase URL and Key are configured; never fail silently."""
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError(
                "Production database configuration missing: SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment."
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def create_scan(
        self,
        scan_id: str,
        product_category: Optional[str] = None,
        user_id: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._verify_configuration()
        payload = {
            "id": scan_id,
            "user_id": user_id,
            "status": "pending",
            "image_url": image_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        res = requests.post(
            f"{self.supabase_url}/rest/v1/scans",
            headers=self._get_headers(),
            json=payload,
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to create scan in Supabase: {res.status_code} {res.text}")
        data = res.json()
        return data[0] if isinstance(data, list) and data else payload

    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        self._verify_configuration()
        res = requests.get(
            f"{self.supabase_url}/rest/v1/scans",
            headers=self._get_headers(),
            params={"id": f"eq.{scan_id}", "select": "*"},
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to fetch scan from Supabase: {res.status_code} {res.text}")
        data = res.json()
        return data[0] if isinstance(data, list) and data else None

    def update_scan(self, scan_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._verify_configuration()
        res = requests.patch(
            f"{self.supabase_url}/rest/v1/scans",
            headers=self._get_headers(),
            params={"id": f"eq.{scan_id}"},
            json=update_data,
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to update scan in Supabase: {res.status_code} {res.text}")
        data = res.json()
        return data[0] if isinstance(data, list) and data else None

    def save_declarations(self, scan_id: str, declarations: List[ExtractedDeclaration]) -> None:
        self._verify_configuration()
        if not declarations:
            return
        payloads = []
        for d in declarations:
            payloads.append(
                {
                    "scan_id": scan_id,
                    "field_name": d.field_name,
                    "raw_value": d.raw_value,
                    "normalized_value": d.normalized_value,
                    "confidence": d.confidence,
                    "bounding_box": d.bounding_box.model_dump() if d.bounding_box else None,
                    "source": d.source.value if d.source else None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        res = requests.post(
            f"{self.supabase_url}/rest/v1/extracted_declarations",
            headers=self._get_headers(),
            json=payloads,
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to persist declarations in Supabase: {res.status_code} {res.text}")

    def get_declarations(self, scan_id: str) -> List[ExtractedDeclaration]:
        self._verify_configuration()
        res = requests.get(
            f"{self.supabase_url}/rest/v1/extracted_declarations",
            headers=self._get_headers(),
            params={"scan_id": f"eq.{scan_id}", "select": "*"},
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to fetch declarations from Supabase: {res.status_code} {res.text}")
        data = res.json()
        results = []
        for row in data:
            bbox_raw = row.get("bounding_box")
            bbox = BoundingBox(**bbox_raw) if bbox_raw and isinstance(bbox_raw, dict) else None
            results.append(
                ExtractedDeclaration(
                    id=row.get("id"),
                    scan_id=row.get("scan_id"),
                    field_name=row.get("field_name"),
                    status=DeclarationStatus.detected,
                    raw_value=row.get("raw_value"),
                    normalized_value=row.get("normalized_value"),
                    confidence=row.get("confidence"),
                    bounding_box=bbox,
                    source=DeclarationSource(row["source"]) if row.get("source") else None,
                    created_at=row.get("created_at"),
                )
            )
        return results

    def save_violations(self, scan_id: str, violations: List[Violation]) -> None:
        self._verify_configuration()
        if not violations:
            return
        payloads = []
        for v in violations:
            payloads.append(
                {
                    "scan_id": scan_id,
                    "rule_id": v.rule_id,
                    "rule_code": v.rule_code or v.rule_id,
                    "field_name": v.field_name,
                    "violation_type": v.violation_type.value,
                    "severity": v.severity.value,
                    "description": v.description,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        res = requests.post(
            f"{self.supabase_url}/rest/v1/violations",
            headers=self._get_headers(),
            json=payloads,
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to persist violations in Supabase: {res.status_code} {res.text}")

    def get_violations(self, scan_id: str) -> List[Violation]:
        self._verify_configuration()
        res = requests.get(
            f"{self.supabase_url}/rest/v1/violations",
            headers=self._get_headers(),
            params={"scan_id": f"eq.{scan_id}", "select": "*"},
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to fetch violations from Supabase: {res.status_code} {res.text}")
        data = res.json()
        results = []
        for row in data:
            rule_code_val = row.get("rule_code") or row.get("rule_id") or "LMR-RULE"
            results.append(
                Violation(
                    id=row.get("id"),
                    scan_id=row.get("scan_id"),
                    rule_id=row.get("rule_id"),
                    rule_code=rule_code_val,
                    field_name=row.get("field_name"),
                    violation_type=ViolationType(row["violation_type"]) if row.get("violation_type") else ViolationType.other,
                    severity=ViolationSeverity(row["severity"]) if row.get("severity") else ViolationSeverity.critical,
                    description=row.get("description", ""),
                    created_at=row.get("created_at"),
                )
            )
        return results

    def save_ai_analysis(
        self,
        scan_id: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        raw_response: Optional[Any] = None,
    ) -> None:
        self._verify_configuration()
        payload = {
            "scan_id": scan_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "raw_response": raw_response,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        requests.post(
            f"{self.supabase_url}/rest/v1/ai_analysis",
            headers=self._get_headers(),
            json=payload,
            timeout=10,
        )

    def save_report(self, scan_id: str, report_url: str, format_type: str = "json") -> None:
        self._verify_configuration()
        payload = {
            "scan_id": scan_id,
            "report_url": report_url,
            "format": format_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        requests.post(
            f"{self.supabase_url}/rest/v1/reports",
            headers=self._get_headers(),
            json=payload,
            timeout=10,
        )

    def delete_child_records(self, scan_id: str) -> None:
        self._verify_configuration()
        headers = self._get_headers()
        requests.delete(
            f"{self.supabase_url}/rest/v1/extracted_declarations",
            headers=headers,
            params={"scan_id": f"eq.{scan_id}"},
            timeout=10,
        )
        requests.delete(
            f"{self.supabase_url}/rest/v1/violations",
            headers=headers,
            params={"scan_id": f"eq.{scan_id}"},
            timeout=10,
        )
        requests.delete(
            f"{self.supabase_url}/rest/v1/ai_analysis",
            headers=headers,
            params={"scan_id": f"eq.{scan_id}"},
            timeout=10,
        )
        requests.delete(
            f"{self.supabase_url}/rest/v1/reports",
            headers=headers,
            params={"scan_id": f"eq.{scan_id}"},
            timeout=10,
        )

    def query_history(
        self,
        page: int = 1,
        limit: int = 20,
        verdict: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._verify_configuration()
        page = max(1, page)
        limit = max(1, min(100, limit))
        offset = (page - 1) * limit

        headers = self._get_headers()
        headers["Prefer"] = "count=exact"

        params: Dict[str, Any] = {
            "select": "*,extracted_declarations(field_name,raw_value,normalized_value)",
            "order": "created_at.desc",
            "limit": limit,
            "offset": offset,
        }

        if verdict:
            params["verdict"] = f"eq.{verdict.strip().upper()}"
        if category:
            params["product_category"] = f"ilike.%{category.strip()}%"
        if from_date:
            params["created_at"] = f"gte.{from_date.strip()}"
        if to_date:
            params["created_at"] = f"lte.{to_date.strip()}"

        res = requests.get(
            f"{self.supabase_url}/rest/v1/scans",
            headers=headers,
            params=params,
            timeout=10,
        )
        if not res.ok:
            raise RuntimeError(f"Failed to query history from Supabase: {res.status_code} {res.text}")

        total = 0
        content_range = res.headers.get("Content-Range")
        if content_range and "/" in content_range:
            try:
                total = int(content_range.split("/")[1])
            except (ValueError, IndexError):
                total = len(res.json()) if isinstance(res.json(), list) else 0

        data = res.json() if isinstance(res.json(), list) else []
        results = []
        for row in data:
            decls = row.get("extracted_declarations", [])
            product_name = None
            if isinstance(decls, list):
                for d in decls:
                    if d.get("field_name") == "generic_name":
                        product_name = d.get("normalized_value") or d.get("raw_value")
                        if product_name:
                            break

            results.append(
                {
                    "id": row.get("id"),
                    "product_name": product_name,
                    "category": row.get("product_category"),
                    "scanned_at": row.get("created_at"),
                    "verdict": row.get("verdict"),
                    "compliance_score": row.get("compliance_score"),
                    "status": row.get("status", "complete"),
                }
            )

        total_pages = math.ceil(total / limit) if total > 0 else 0

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "results": results,
        }

    def query_analytics(
        self,
        period: str = "7d",
    ) -> Dict[str, Any]:
        self._verify_configuration()
        now = datetime.now(timezone.utc)
        clean_period = period.strip().lower() if period else "7d"
        if clean_period == "7d":
            cutoff_dt = now - timedelta(days=7)
        elif clean_period == "30d":
            cutoff_dt = now - timedelta(days=30)
        elif clean_period == "all":
            cutoff_dt = None
        else:
            cutoff_dt = now - timedelta(days=7)

        params: Dict[str, Any] = {
            "select": "id,verdict,product_category,created_at",
            "order": "created_at.asc",
        }
        if cutoff_dt:
            params["created_at"] = f"gte.{cutoff_dt.isoformat()}"

        res_scans = requests.get(
            f"{self.supabase_url}/rest/v1/scans",
            headers=self._get_headers(),
            params=params,
            timeout=10,
        )
        if not res_scans.ok:
            raise RuntimeError(f"Failed to fetch analytics scans from Supabase: {res_scans.status_code} {res_scans.text}")

        scans_data = res_scans.json() if isinstance(res_scans.json(), list) else []

        total_scans = len(scans_data)
        pass_count = sum(1 for s in scans_data if s.get("verdict") == "PASS")
        fail_count = sum(1 for s in scans_data if s.get("verdict") == "FAIL")
        review_count = sum(1 for s in scans_data if s.get("verdict") == "NEEDS_REVIEW")
        pass_rate = round((pass_count / total_scans) * 100.0, 1) if total_scans > 0 else 0.0

        daily_groups: Dict[str, Dict[str, Any]] = {}
        for s in scans_data:
            s_dt = _parse_iso_datetime(s.get("created_at"))
            date_key = s_dt.strftime("%Y-%m-%d") if s_dt else now.strftime("%Y-%m-%d")
            day_name = s_dt.strftime("%a") if s_dt else now.strftime("%a")
            if date_key not in daily_groups:
                daily_groups[date_key] = {
                    "day": day_name,
                    "date": date_key,
                    "scans": 0,
                    "compliant": 0,
                    "non_compliant": 0,
                    "needs_review": 0,
                }
            daily_groups[date_key]["scans"] += 1
            verdict = s.get("verdict")
            if verdict == "PASS":
                daily_groups[date_key]["compliant"] += 1
            elif verdict == "FAIL":
                daily_groups[date_key]["non_compliant"] += 1
            elif verdict == "NEEDS_REVIEW":
                daily_groups[date_key]["needs_review"] += 1

        daily_trend = [daily_groups[k] for k in sorted(daily_groups.keys())]

        v_params: Dict[str, Any] = {"select": "rule_code,description,created_at"}
        if cutoff_dt:
            v_params["created_at"] = f"gte.{cutoff_dt.isoformat()}"

        res_v = requests.get(
            f"{self.supabase_url}/rest/v1/violations",
            headers=self._get_headers(),
            params=v_params,
            timeout=10,
        )
        violations_data = res_v.json() if res_v.ok and isinstance(res_v.json(), list) else []

        violation_counts: Counter = Counter()
        violation_descriptions: Dict[str, str] = {}
        for v in violations_data:
            r_code = v.get("rule_code") or "Unknown Rule"
            violation_counts[r_code] += 1
            if r_code not in violation_descriptions and v.get("description"):
                violation_descriptions[r_code] = v.get("description")

        top_violations = [
            {
                "rule_code": r_code,
                "description": violation_descriptions.get(r_code, r_code),
                "count": count,
            }
            for r_code, count in violation_counts.most_common()
        ]

        category_stats: Dict[str, Dict[str, Any]] = {}
        for s in scans_data:
            cat = s.get("product_category")
            if not cat:
                continue
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "pass": 0, "fail": 0, "review": 0}
            category_stats[cat]["total"] += 1
            verdict = s.get("verdict")
            if verdict == "PASS":
                category_stats[cat]["pass"] += 1
            elif verdict == "FAIL":
                category_stats[cat]["fail"] += 1
            elif verdict == "NEEDS_REVIEW":
                category_stats[cat]["review"] += 1

        return {
            "total_scans": total_scans,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "review_count": review_count,
            "pass_rate": pass_rate,
            "daily_trend": daily_trend,
            "top_violations": top_violations,
            "by_category": category_stats,
        }


def get_repository() -> BaseScanRepository:
    """Production dependency provider returning configured database repository."""
    return SupabaseScanRepository()
