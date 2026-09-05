# PackSure AI — API Contract

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs`

> **Status:** These are planned contracts/placeholders. Implementation is in progress.

---

## POST /api/v1/scans

Upload a new package image for compliance checking.

**Request:** `multipart/form-data`
- `image` — package image file (JPEG/PNG)
- `product_category` — optional category hint

**Response:**
```json
{
  "scan_id": "uuid",
  "status": "pending",
  "created_at": "ISO8601"
}
```

---

## POST /api/v1/scans/{id}/ocr

Trigger OCR processing on an uploaded scan.

**Response:**
```json
{
  "scan_id": "uuid",
  "status": "processing"
}
```

---

## GET /api/v1/scans/{id}

Get the full result of a scan including compliance verdict.

**Response:**
```json
{
  "scan_id": "uuid",
  "status": "complete",
  "verdict": "FAIL",
  "compliance_score": 72.5,
  "declarations": [...],
  "violations": [...],
  "evidence_image_url": "..."
}
```

---

## GET /api/v1/history

Get paginated scan history.

**Query params:** `page`, `limit`, `verdict`, `from_date`, `to_date`

**Response:**
```json
{
  "total": 142,
  "page": 1,
  "results": [...]
}
```

---

## GET /api/v1/analytics

Get compliance statistics.

**Response:**
```json
{
  "total_scans": 142,
  "pass_rate": 61.3,
  "top_violations": [...],
  "by_category": {...}
}
```

---

## GET /api/v1/rules

Get the applicable rules for a product category.

**Query params:** `category`

**Response:**
```json
{
  "category": "food",
  "rules": [...]
}
```
