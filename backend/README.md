# PackSure AI — Backend

Python + FastAPI + OCR + Gemini + Supabase

## Quick Start

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs at: http://localhost:8000/docs

## Services (to be implemented)

- `image_service` — Image quality check, preprocessing
- `ocr_service` — Tesseract OCR extraction
- `ai_service` — Gemini Vision structured extraction
- `compliance_service` — Deterministic rules engine
- `evidence_service` — Annotated image + field mapping
- `report_service` — PDF/JSON report generation

## External Dependencies

- Tesseract OCR must be installed on the system separately.
- Google Gemini API key required.
- Supabase project required.
