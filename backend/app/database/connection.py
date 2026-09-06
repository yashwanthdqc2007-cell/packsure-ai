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
from datetime import datetime, timezone
import logging
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
            results.append(
                Violation(
                    id=row.get("id"),
                    scan_id=row.get("scan_id"),
                    rule_id=row.get("rule_id"),
                    rule_code=row.get("rule_code", "LMR-RULE"),
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


def get_repository() -> BaseScanRepository:
    """Production dependency provider returning configured database repository."""
    return SupabaseScanRepository()
