"""
PackSure AI — Phase 6B Quantity API Integration Tests.

Validates the POST /api/v1/scans/{id}/quantity endpoint,
MPE evaluation, report.json artifact persistence, and InspectionState response.
"""

from decimal import Decimal
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.api.routes.scans import record_physical_quantity
from app.database.connection import InMemoryScanRepository
from app.schemas.compliance import ComplianceVerdict
from app.schemas.declaration import DeclarationStatus, ExtractedDeclaration
from app.schemas.inspection_state import PhysicalChecksStatus
from app.schemas.quantity import IndividualQuantityVerdict, QuantityMeasurementInput


class TestQuantityAPI(unittest.TestCase):
    """Integration test suite for quantity verification API endpoints."""

    def setUp(self):
        self.test_scan_id = "test-scan-qty-101"
        self.temp_storage = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_storage, ignore_errors=True)

    def test_record_quantity_pass(self):
        """record_physical_quantity returns evaluated PASS result and updates inspection state."""
        # Setup mock scan directory & report.json
        scan_dir = os.path.join(self.temp_storage, self.test_scan_id)
        os.makedirs(scan_dir, exist_ok=True)
        report_json_path = os.path.join(scan_dir, "report.json")
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump({
                "scan_metadata": {"scan_id": self.test_scan_id, "status": "complete"},
                "compliance_summary": {"verdict": "PASS", "compliance_score": 100.0},
            }, f)

        mock_repo = MagicMock()
        mock_repo.get_scan.return_value = {
            "id": self.test_scan_id,
            "status": "complete",
            "verdict": "PASS",
            "compliance_score": 100.0,
            "product_category": "Food",
            "image_url": "storage/scans/test.jpg",
        }
        mock_repo.get_declarations.return_value = [
            ExtractedDeclaration(
                field_name="net_quantity",
                raw_value="1 kg",
                normalized_value="1 kg",
                status=DeclarationStatus.detected,
            )
        ]
        mock_repo.get_violations.return_value = []

        with patch("app.api.routes.scans.LOCAL_STORAGE_BASE", self.temp_storage):
            req = QuantityMeasurementInput(
                measured_quantity=Decimal("990"),
                measured_unit="g",
                method="MANUAL_SCALE",
                instrument_id="SCALE-001",
            )
            response = record_physical_quantity(
                id=self.test_scan_id,
                measurement_input=req,
                repo=mock_repo,
            )

        self.assertIsNotNone(response.quantity_measurement)
        self.assertEqual(response.quantity_measurement.verdict, IndividualQuantityVerdict.PASS)
        self.assertEqual(response.quantity_measurement.declared_quantity, Decimal("1"))
        self.assertEqual(response.quantity_measurement.declared_unit, "kg")
        self.assertEqual(response.quantity_measurement.measured_quantity, Decimal("990"))
        self.assertEqual(response.quantity_measurement.statutory_mpe, Decimal("15.0"))
        self.assertFalse(response.quantity_measurement.is_excess)

        # Verify inspection state was updated to COMPLETED
        self.assertIsNotNone(response.inspection_state)
        self.assertEqual(response.inspection_state.physical_checks_status, PhysicalChecksStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
