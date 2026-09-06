# PackSure AI — Canonical API Contract

Base URL: `http://localhost:8000/api/v1`
Interactive OpenAPI Docs: `http://localhost:8000/docs`

> **Status:** Frozen Canonical Contract. All frontend services, backend routes, Pydantic schemas, and database mappings MUST adhere to this specification.

> [!IMPORTANT]
> **Illustrative Regulatory Examples:**
> All rule codes (e.g., `Rule-6(1)(a)`, `Rule-6(1)(e)`), declaration field names, violation descriptions, and payload values in this API documentation are **illustrative example data only**. Authoritative legal requirements, mandatory declaration lists, validation constraints, and penalty severities come dynamically from the versioned Legal Metrology rule repository, not from example response text in this document.

---

## 1. Global Conventions & Standards

### Field Naming
- All JSON payload keys, request parameters, and response attributes strictly use **`snake_case`**.

### Canonical Enums
- **`ScanStatus`**: `"pending"` | `"processing"` | `"complete"` | `"failed"`
- **`Verdict`**: `"PASS"` | `"FAIL"` | `"NEEDS_REVIEW"`
- **`Severity`**: `"critical"` | `"major"` | `"minor"`
- **`DeclarationSource`**: `"tesseract"` | `"gemini"` | `"manual"` | `"hybrid"`
- **`DeclarationStatus`**: `"detected"` | `"missing"` | `"uncertain"`

### Declaration Status vs Overall Compliance Verdict
- `declarations[].status` (`detected`, `missing`, `uncertain`) represents the extraction and presence state of an individual package declaration field.
- Scan-level `verdict` (`PASS`, `FAIL`, `NEEDS_REVIEW`) represents the aggregate compliance decision computed exclusively by the deterministic rules engine across all applicable Legal Metrology rules.

### Confidence Representation
- Confidence scores across OCR and AI extractions are expressed as a normalized float from **`0.0` to `1.0`** (e.g. `0.945` representing 94.5%).

### Bounding Box Coordinate System
- Bounding boxes are defined as `{ "x": float, "y": float, "width": float, "height": float }`.
- Coordinates are non-negative **pixel values relative to the original image dimensions**, where `(0.0, 0.0)` is the top-left origin of the unscaled image.

### Scan Status Lifecycle
```
[POST /scans] ──► pending ──► processing ──► complete (Verdict: PASS / FAIL / NEEDS_REVIEW)
                                         └──► failed   (Pipeline / image failure)
```

### Standard Error Structure
FastAPI standard RFC-compliant error structure:
```json
{
  "detail": "Error description string or validation error array"
}
```

---

## 2. Endpoints

### 1. `POST /api/v1/scans`

Upload a package image to initiate compliance inspection.

This endpoint creates the scan record and queues asynchronous background processing (image quality verification, OpenCV preprocessing, OCR/AI extraction, and deterministic rules evaluation). It returns `202 Accepted` immediately with the created scan metadata. The frontend retrieves processing updates and final inspection results by querying `GET /api/v1/scans/{id}`.

- **Method:** `POST`
- **Path:** `/api/v1/scans`
- **Content-Type:** `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `image` | `binary` (file) | **Yes** | Image file (`image/jpeg`, `image/png`, `image/webp`). Max size: 10MB. |
| `product_category` | `string` | No | Optional category hint (e.g., `"Food Grains"`, `"Edible Oil"`). |

#### Response (`202 Accepted`)
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "created_at": "2026-09-06T09:30:00Z"
}
```

#### Error Responses
- **`400 Bad Request`**: Unsupported image format, image file unreadable, or file size exceeds 10MB limit.
- **`422 Unprocessable Entity`**: Missing mandatory `image` field.

---

### 2. `GET /api/v1/scans/{id}`

Retrieve the scan status and full compliance inspection results.

- **Method:** `GET`
- **Path:** `/api/v1/scans/{id}`

#### Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `id` | `string` (UUID) | **Yes** | Unique scan identifier. |

#### Response (`200 OK`) — Completed Scan
*(Note: Regulatory fields, rules, and values below are illustrative examples)*
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "complete",
  "verdict": "FAIL",
  "compliance_score": 72.5,
  "product_category": "Food Grains",
  "image_url": "https://storage.packsure.ai/scans/raw/3fa85f64.jpg",
  "processed_image_url": "https://storage.packsure.ai/scans/processed/3fa85f64.jpg",
  "evidence_image_url": "https://storage.packsure.ai/scans/evidence/3fa85f64.jpg",
  "declarations": [
    {
      "id": "7b1c4e92-628a-4d2a-89a1-0f81643c71a2",
      "field_name": "mrp",
      "status": "detected",
      "raw_value": "Rs. 150.00 (incl. of all taxes)",
      "normalized_value": "150.00",
      "confidence": 0.945,
      "bounding_box": {
        "x": 120.0,
        "y": 450.0,
        "width": 180.0,
        "height": 45.0
      },
      "source": "gemini"
    },
    {
      "id": "c3f81e44-129b-432d-947f-8561129b71e3",
      "field_name": "net_quantity",
      "status": "detected",
      "raw_value": "Net Wt: 1 kg",
      "normalized_value": "1 kg",
      "confidence": 0.982,
      "bounding_box": {
        "x": 120.0,
        "y": 510.0,
        "width": 140.0,
        "height": 38.0
      },
      "source": "hybrid"
    },
    {
      "id": "d5e81a99-8472-4bc3-90ef-1129b71e3456",
      "field_name": "consumer_care",
      "status": "uncertain",
      "raw_value": "care@...",
      "normalized_value": null,
      "confidence": 0.42,
      "bounding_box": {
        "x": 120.0,
        "y": 580.0,
        "width": 100.0,
        "height": 25.0
      },
      "source": "tesseract"
    }
  ],
  "violations": [
    {
      "id": "e4a29c11-739b-4b4d-91cf-229b4561129b",
      "rule_code": "Rule-6(1)(e)",
      "field_name": "unit_sale_price",
      "violation_type": "missing_declaration",
      "severity": "critical",
      "description": "Unit sale price mandatory for packages above 100g/ml is missing."
    }
  ],
  "created_at": "2026-09-06T09:30:00Z",
  "completed_at": "2026-09-06T09:30:04Z"
}
```

#### Response (`200 OK`) — In-Progress Scan
```json
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "processing",
  "verdict": null,
  "compliance_score": null,
  "product_category": "Food Grains",
  "image_url": "https://storage.packsure.ai/scans/raw/3fa85f64.jpg",
  "processed_image_url": null,
  "evidence_image_url": null,
  "declarations": [],
  "violations": [],
  "created_at": "2026-09-06T09:30:00Z",
  "completed_at": null
}
```

#### Error Responses
- **`404 Not Found`**: Scan ID does not exist.
- **`422 Unprocessable Entity`**: Invalid UUID format.

---

### 3. `GET /api/v1/history`

Query paginated historical scans with optional filters.

- **Method:** `GET`
- **Path:** `/api/v1/history`

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `page` | `integer` | No | `1` | Page number (min: 1). |
| `limit` | `integer` | No | `20` | Items per page (min: 1, max: 100). |
| `verdict` | `string` | No | — | Filter by verdict (`PASS`, `FAIL`, `NEEDS_REVIEW`). |
| `category` | `string` | No | — | Filter by category name or UUID. |
| `search` | `string` | No | — | Search term across product/brand/scan ID. |
| `from_date` | `string` (ISO8601) | No | — | Filter scans created on or after date. |
| `to_date` | `string` (ISO8601) | No | — | Filter scans created on or before date. |

#### Response (`200 OK`)
```json
{
  "total": 142,
  "page": 1,
  "limit": 20,
  "total_pages": 8,
  "results": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "product_name": "SunFresh Refined Sunflower Oil",
      "category": "Edible Oil",
      "scanned_at": "2026-09-06T10:42:00Z",
      "verdict": "PASS",
      "compliance_score": 96.0,
      "status": "complete"
    },
    {
      "id": "8dc45a12-127b-4892-938a-41f229b45611",
      "product_name": "Golden Harvest Rice",
      "category": "Food Grains",
      "scanned_at": "2026-09-06T09:18:00Z",
      "verdict": "FAIL",
      "compliance_score": 68.0,
      "status": "complete"
    }
  ]
}
```

---

### 4. `GET /api/v1/analytics`

Retrieve aggregated compliance metrics, pass rates, category distributions, and daily activity trends.

- **Method:** `GET`
- **Path:** `/api/v1/analytics`

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `period` | `string` | No | `"7d"` | Time period: `"7d"`, `"30d"`, or `"all"`. |

#### Response (`200 OK`)
```json
{
  "total_scans": 128,
  "pass_count": 76,
  "fail_count": 34,
  "review_count": 18,
  "pass_rate": 59.4,
  "daily_trend": [
    {
      "day": "Mon",
      "date": "2026-08-31",
      "scans": 14,
      "compliant": 9,
      "non_compliant": 3,
      "needs_review": 2
    },
    {
      "day": "Tue",
      "date": "2026-09-01",
      "scans": 18,
      "compliant": 11,
      "non_compliant": 5,
      "needs_review": 2
    }
  ],
  "top_violations": [
    {
      "rule_code": "Rule-6(1)(e)",
      "description": "Missing Unit Sale Price",
      "count": 21
    },
    {
      "rule_code": "Rule-6(1)(a)",
      "description": "Incomplete Manufacturer Address",
      "count": 14
    }
  ],
  "by_category": {
    "Edible Oil": { "total": 42, "pass": 30, "fail": 8, "review": 4 },
    "Food Grains": { "total": 54, "pass": 32, "fail": 16, "review": 6 }
  }
}
```

---

### 5. `GET /api/v1/rules`

Retrieve the active Legal Metrology rules applicable to product packaging.

- **Method:** `GET`
- **Path:** `/api/v1/rules`

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `category` | `string` | No | — | Filter rules applicable to a specific category. |
| `active_only` | `boolean` | No | `true` | When true, returns only active rules. |

#### Response (`200 OK`)
*(Note: Regulatory fields and descriptions below are illustrative examples)*
```json
{
  "category": "all",
  "total": 2,
  "rules": [
    {
      "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "rule_code": "Rule-6(1)(a)",
      "title": "Manufacturer / Packer Identity & Address",
      "description": "Name and complete address of the manufacturer, packer, or importer.",
      "field_name": "manufacturer_name_and_address",
      "validation_type": "presence",
      "severity": "critical",
      "version": "2011",
      "active": true
    },
    {
      "id": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
      "rule_code": "Rule-6(1)(e)",
      "title": "Maximum Retail Price (MRP) & Unit Sale Price",
      "description": "MRP inclusive of all taxes, with unit sale price where applicable.",
      "field_name": "mrp",
      "validation_type": "format",
      "severity": "critical",
      "version": "2011",
      "active": true
    }
  ]
}
```

---

### 6. `PATCH /api/v1/scans/{id}/review`

Submit human inspector review, manual findings resolution, or corrected declaration values.

> [!IMPORTANT]
> **Workflow Constraint:**
> The review workflow exclusively applies to scans whose current verdict is **`NEEDS_REVIEW`**. This endpoint is designed to resolve a pending review state to a definitive outcome (**`PASS`** or **`FAIL`**). Arbitrary `PASS` ↔ `FAIL` overrides of conclusive scans are not supported.

- **Method:** `PATCH`
- **Path:** `/api/v1/scans/{id}/review`
- **Content-Type:** `application/json`

#### Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `id` | `string` (UUID) | **Yes** | Unique scan identifier (scan verdict must currently be `NEEDS_REVIEW`). |

#### Request Body
```json
{
  "verdict": "PASS",
  "reviewer_notes": "Verified consumer care email and batch number manually from back panel.",
  "corrected_declarations": [
    {
      "field_name": "consumer_care",
      "raw_value": "care@brand.com / 1800-123-456",
      "normalized_value": "care@brand.com"
    }
  ]
}
```

#### Response (`200 OK`)
Returns the updated `ScanResponse` object (identical structure to `GET /api/v1/scans/{id}`) reflecting the updated `verdict` (`PASS` or `FAIL`), recalculated compliance score, and reviewer audit trail.

#### Error Responses
- **`400 Bad Request`**: Scan verdict is not `NEEDS_REVIEW`, or target resolution verdict is not `PASS` or `FAIL`.
- **`404 Not Found`**: Scan ID does not exist.
- **`422 Unprocessable Entity`**: Invalid payload schema.
