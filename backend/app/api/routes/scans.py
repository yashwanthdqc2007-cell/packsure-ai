"""
Scan routes — POST /api/v1/scans, GET /api/v1/scans/{id}, POST /api/v1/scans/{id}/ocr

TODO (Backend Dev):
- POST /api/v1/scans — Accept image upload, create scan record, trigger pipeline
- POST /api/v1/scans/{id}/ocr — Trigger OCR on uploaded image
- GET /api/v1/scans/{id} — Return scan result including compliance verdict
"""

from fastapi import APIRouter

router = APIRouter(prefix="/scans", tags=["scans"])


# TODO: Implement scan endpoints
