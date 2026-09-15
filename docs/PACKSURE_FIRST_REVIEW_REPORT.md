# PACKSURE AI — FIELD INSPECTION COPILOT FOR LEGAL METROLOGY
## Comprehensive Project Report for First Academic & Technical Review

---

**Project Title:** PackSure AI — Field Inspection Copilot for Legal Metrology  
**Problem Statement Reference:** Smart India Hackathon (SIH) Problem Statement SIH26034  
**Target Domain:** Regulatory Technology (RegTech), Legal Metrology Enforcement, Packaged Commodities Compliance  
**Active Development Branch:** `backend`  
**System Classification:** AI-Assisted Field Inspection Workstation & Copilot (Working Prototype)  
**Review Milestone:** First Technical & Project Review Milestone  

---

## 1. Title

**PackSure AI: An Explainable, Evidence-Linked Field Inspection Copilot for Legal Metrology (Packaged Commodities) Compliance Verification.**

---

## 2. Executive Summary

PackSure AI is a software workstation engineered to assist field enforcement officers in checking the statutory compliance of packaged commodities under the **Legal Metrology (Packaged Commodities) Rules, 2011** (as amended). 

In field operations, inspectors examine retail packages to verify mandatory visual declarations (manufacturer information, generic name, net quantity format, dates, MRP with inclusive tax wording, Unit Sale Price, batch numbers, and consumer care) and physically measure package contents against the **First Schedule [Rules 2(e) & 22], Table I Maximum Permissible Error (MPE)** tolerances.

### The Architectural Axiom
$$\text{AI/OCR Extracts Evidence} \longrightarrow \text{Deterministic Rules Evaluate Law} \longrightarrow \text{Inspector Resolves Uncertainty}$$

PackSure AI enforces a strict architectural boundary:
1. **Perception Layer (AI & OCR):** Computer vision (OpenCV), Tesseract OCR, and Multimodal Vision AI (Google Gemini) process multi-view packaging images to detect text tokens, locate spatial bounding boxes, and assess image quality.
2. **Deterministic Compliance Layer:** Pure, codified software validators evaluate extracted declarations against specific Gazette provisions and mathematical constraints with **zero LLM hallucination**.
3. **Field Copilot & Human Resolution:** The system acts as a field copilot. It determines what has been visually proven, surfaces evidence conflicts, guides the inspector to the single **Next Best Action**, evaluates individual physical scale measurements against Table I MPE, and records certified officer review decisions.

> **Statutory Disclaimer:** PackSure AI is an inspector-assistive working prototype. It does not possess autonomous legal authority, does not perform legal certification, does not execute automated seizure or prosecution, and does not replace the statutory judgment of a designated Legal Metrology Officer.

---

## 3. Introduction

Pre-packaged commodities represent a vital component of commerce in India. To protect consumer rights and ensure fair trade, the Department of Consumer Affairs (Ministry of Consumer Affairs, Food and Public Distribution) enforces the Legal Metrology Act, 2009 and the Legal Metrology (Packaged Commodities) Rules, 2011.

These rules mandate that all pre-packaged commodities sold in retail must carry conspicuous, legible, and standardized declarations. PackSure AI introduces a systematic, digital workflow to assist inspectors in evaluating packaging declarations and physical package quantities with traceable, evidence-backed findings.

---

## 4. Problem Statement

Manual inspection of packaged commodities in retail and distribution environments faces substantial operational challenges:

1. **Information Distribution Across Surfaces:** Mandatory declarations are rarely consolidated on a single panel. They are distributed across the Principal Display Panel (PDP), back panels, side gussets, and bottom flaps.
2. **Format Ambiguities & Prohibited Units:** Manufacturers frequently use prohibited non-standard unit abbreviations (e.g., `gms`, `kilos`, `ltrs`, `pcs` instead of statutory SI metric symbols `g`, `kg`, `ml`, `L`, `U`), omit mandatory tax declarations on MRP, or calculate Unit Sale Price (USP) incorrectly.
3. **Variable Field Image Quality:** Smartphone captures in retail environments often exhibit motion blur, severe glare, perspective distortion, and low lighting. Unchecked OCR on degraded images produces false alarms or undetected violations.
4. **Complex Package Compositions:** Products are packaged as multi-piece units, combination packs with dissimilar goods, kits, and group packages. Naive single-scalar parsers fail when handling multi-unit statements (e.g., `"2N x 500g"`).
5. **Electronic / QR Code Ambiguity:** Recent statutory amendments (e.g., G.S.R. 456(E)) allow certain electronic products to declare specific information via QR codes under strict conditions. Officers must verify whether a QR code is legally applicable, accompanied by on-pack instructions, and not improperly offloading non-exempt declarations.
6. **Physical Quantity Verification Bottlenecks:** Label compliance alone does not guarantee net quantity accuracy. Field officers must physically weigh packages and determine compliance against statutory Maximum Permissible Error (MPE) thresholds.
7. **Traceability Deficits:** Field inspections require an auditable trail connecting every recorded violation to exact visual evidence, bounding coordinates, and specific Gazette citations.

---

## 5. Motivation / Need

- **Consistency & Objectivity:** Eliminates subjective manual oversights and ensures uniform statutory interpretation across inspection teams.
- **Explainability:** Replaces opaque "black-box" AI decisions with deterministic rule evaluations directly linked to Gazette citations.
- **Operational Efficiency:** Reduces the time required to cross-verify mandatory fields across multi-panel packaging.
- **Evidence Integrity:** Maintains an immutable record of original captures, bounding boxes, physical scale inputs, and reviewer decisions.

---

## 6. Target Users

1. **Legal Metrology Field Officers & Inspectors:** Primary end-users conducting retail, market, and warehouse inspections.
2. **Enforcement Supervisors & Controllers:** Administrative users reviewing inspection logs, compliance trends, and field activity.
3. **Brand Compliance & Quality Assurance Teams:** Pre-market packaging review teams checking labeling compliance prior to commercial distribution.

---

## 7. Objectives

### A. Implemented & Verified Objectives (First Review Milestone)
- [x] **Multi-View Image Ingestion:** Ingest single-panel or multi-view package captures up to 20MB per view.
- [x] **Image Quality & Preprocessing:** Evaluate blur (Laplacian variance), glare, contrast, and perspective skew via OpenCV.
- [x] **Hybrid OCR & Multimodal Extraction:** Extract spatial text tokens via Tesseract and structured declaration fields via Gemini Vision with deterministic fallback parsing.
- [x] **Multi-View Evidence Fusion:** Reconcile declarations across multiple panels and automatically flag conflicting values for human review.
- [x] **Deterministic Legal Rule Engine:** Execute pure codified validators for 11 specific rule specifications in `rules.json`.
- [x] **Visual Evidence Overlay Generation:** Generate high-resolution evidence artifacts with spatial bounding box overlays.
- [x] **Conditional QR & Electronic Commodity Handling:** Evaluate electronic product applicability under G.S.R. 456(E), verify mandatory on-pack instructions, and restrict offloading without blind network fetching.
- [x] **Package Composition Classification:** Categorize packages into `SINGLE`, `MULTI_PIECE`, `COMBINATION`, `GROUP`, `KIT`, or `UNCERTAIN` to protect Unit Sale Price logic.
- [x] **Scope & Coverage Transparency:** Distinguish evaluated visual declarations from unperformed physical and external registry checks.
- [x] **Inspection Completeness & Next Best Action:** Derive operational workflow states (`INCOMPLETE`, `NEEDS_REVIEW`, `READY_TO_REVIEW`, `READY_TO_FINALIZE`) and recommend exactly one prioritized action.
- [x] **Individual Physical Quantity Verification:** Evaluate scale measurements against **First Schedule Table I MPE** using `Decimal` arithmetic, unit normalization, cross-dimension safety, and Double-MPE reference limits.
- [x] **Inspector Copilot Workstation Interface:** React/TypeScript interface with live MPE computation, visual evidence viewers, unverified checklists, and review workflows.
- [x] **Persistence & Historical Analytics:** Store structured reports in JSON artifacts and PostgreSQL/Supabase tables with filtering, pagination, and telemetry.

### B. Future Objectives (Post-First Review Roadmap)
- [ ] Calibrated optical font-height measurement (Rule 7 font size validation).
- [ ] Fifth Schedule statistical lot-sampling and lot acceptance/rejection algorithms.
- [ ] Direct integration with external regulatory registries (DCA Rule 27 Manufacturer Database, FSSAI, EPR).
- [ ] Fully offline Edge-AI deployment for remote rural field inspections.
- [ ] Cryptographically signed, tamper-evident PDF inspection certificates.

---

## 8. Proposed Solution

PackSure AI provides an end-to-end field inspection copilot that guides an officer through:
1. **Capturing Package Surfaces:** Ingesting multiple views of a package.
2. **Assessing Image Feasibility:** Flagging blur, glare, or skew that could compromise evidence.
3. **Extracting Structured Evidence:** Mapping raw OCR tokens to structured Legal Metrology fields.
4. **Evaluating Deterministic Rules:** Applying pure Python validators against codified rules.
5. **Evaluating Physical Net Quantity:** Computing statutory MPE and deficiency for an individual package.
6. **Guiding Next Steps:** Surfacing the single highest-priority operational action.
7. **Capturing Officer Resolutions:** Recording human review notes and declaration overrides into an immutable report.

---

## 9. Key Innovation & Differentiators

1. **Separation of Perception from Adjudication:** AI vision only extracts candidate text and bounding boxes; deterministic rules determine statutory compliance. AI never decides legal guilt or violation status.
2. **Uncertainty-Aware State Machine:** Ambiguous text, low OCR confidence, conflicting multi-view declarations, and unverified package compositions transition to `NEEDS_REVIEW` rather than generating false positives or false passes.
3. **Deterministic First Schedule Table I Engine:** Continuous, immutable tier lookup for weight and volume MPE calculations with explicit cross-dimension safety barriers.
4. **Scope Transparency:** Explicitly informs the officer which statutory checks were evaluated from the image versus which checks require physical measurement or external registry lookup.
5. **Intelligent Recapture Guidance:** Translates OpenCV quality defects into actionable camera instructions (e.g., *"Hold camera steady — motion blur detected"*).

---

## 10. System Architecture

```
                       +-----------------------------------+
                       |         FIELD INSPECTOR           |
                       | (Mobile / Web Workstation Client) |
                       +-----------------+-----------------+
                                         |
                                         | REST API (HTTP/JSON)
                                         v
+-----------------------------------------------------------------------------------+
|                            FASTAPI BACKEND CORE                                   |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                            API ROUTING LAYER                                |  |
|  |   /scans (POST, GET)  |  /scans/{id}/quantity  |  /review  |  /history      |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                     IMAGE & PERCEPTION PIPELINE                             |  |
|  |   1. Image Validation (MIME, Size <= 20MB)                                  |  |
|  |   2. OpenCV Quality Assessment (Laplacian Blur, Glare, Skew)                |  |
|  |   3. Tesseract OCR (Spatial Tokens & Words)                                 |  |
|  |   4. Gemini Vision AI (Structured Declaration Extraction)                   |  |
|  |   5. QR Code Detection & Decoder (OpenCV / PyZbar)                          |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                      EVIDENCE & RECONCILIATION LAYER                        |  |
|  |   1. Multi-View Evidence Fusion (Confidence Weighting & Conflict Detection) |  |
|  |   2. Package Composition Engine (Single, Multi-Piece, Combo, Kit)           |  |
|  |   3. QR Evidence Evaluator (Electronic Product G.S.R. 456(E) Checks)        |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                   DETERMINISTIC STATUTORY RULE ENGINE                       |  |
|  |   1. Applicability & Exemption Evaluator (Rule 26, Perishability, Imports)  |  |
|  |   2. Codified Pure Validators (Address, Date, MRP, USP, Net Qty, etc.)      |  |
|  |   3. Verdict State Machine (PASS / FAIL / NEEDS_REVIEW)                     |  |
|  |   4. Explainable Scoring (0-100%) & Violation Citation Mapping              |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                  OPERATIONAL COPILOT & PHYSICAL METROLOGY                   |  |
|  |   1. Scope & Coverage Manifest (Visual vs Physical/External)                |  |
|  |   2. Inspection Completeness & Next Best Action Engine                      |  |
|  |   3. Physical Quantity Verification (First Schedule Table I MPE Engine)     |  |
|  |   4. Human Reviewer Resolution & Correction Overrides                       |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                     PERSISTENCE & ARTIFACT REPOSITORY                       |  |
|  |   - PostgreSQL / Supabase Database (Scans, Declarations, Violations)        |  |
|  |   - JSON Report Artifacts (storage/scans/{id}/report.json)                  |  |
|  |   - Annotated Visual Evidence Images (storage/scans/{id}/evidence_0.jpg)    |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 11. End-to-End Workflow

```
[Start Inspection]
        │
        ▼
[Capture Package Views (Front, Back, Sides)]
        │
        ▼
[OpenCV Image Quality Check] ──(Fails Quality)──> [Intelligent Recapture Guidance]
        │ (Passes)
        ▼
[OCR & Multimodal Declaration Extraction]
        │
        ▼
[Multi-View Evidence Fusion & Conflict Check] ──(Conflict Detected)──> [NEEDS_REVIEW]
        │ (No Conflict)
        ▼
[Package Composition & QR Applicability Check]
        │
        ▼
[Deterministic Legal Rule Engine Evaluation]
        │
        ▼
[Visual Compliance Verdict & Score Computed]
        │
        ▼
[Copilot Recommends Next Best Action]
        │
        ▼
[Physical Quantity Verification (Scale Input)] ──> [First Schedule Table I MPE Check]
        │
        ▼
[Officer Review & Declaration Override]
        │
        ▼
[Inspection Finalized & Report Persisted]
```

---

## 12. Technology Stack

| Layer | Technologies Used | Purpose |
|---|---|---|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons, Recharts, Axios | Responsive field inspector workstation UI |
| **Backend Framework** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 | High-performance asynchronous REST API |
| **Image Processing** | OpenCV (Headless), Pillow | Blur, glare, skew detection, and image manipulation |
| **OCR & Vision** | Tesseract OCR (`pytesseract`), Google Gemini API (`google-generativeai`) | Spatial tokenization and structured multimodal extraction |
| **Database** | PostgreSQL / Supabase (`supabase-py`), JSON Artifacts | Relational metadata persistence and immutable report storage |
| **Testing** | Python `unittest`, `pytest`, `httpx` | Deterministic unit, integration, and API test suites |

---

## 13. Detailed Module Description

### Module 1: Image Processing & Quality Assessment (`image_service.py`)
- Evaluates image quality prior to OCR using Laplacian variance ($\sigma^2 < 100.0$), glare saturation ($V > 250$), grayscale standard deviation ($\sigma < 35.0$), and perspective skew via Hough lines.
- Generates actionable recapture advice and preserves original image immutability.

### Module 2: OCR & Structured Declaration Extraction (`ocr_service.py`, `ai_service.py`)
- Extracts spatial word tokens and bounding boxes via Tesseract OCR (PSM 11/6).
- Prompts Gemini Vision with image bytes and OCR hints to extract structured Legal Metrology fields into Pydantic models. Includes deterministic regex fallback parser.

### Module 3: Multi-View Evidence Fusion (`fusion_service.py`)
- Aggregates declarations across multiple package surfaces.
- Evaluates confidence scores, tracks source view provenance, and flags conflicting declarations across views (e.g., mismatched MRP) as `uncertain`, routing the scan to `NEEDS_REVIEW`.

### Module 4: Package Composition Engine (`composition_service.py`)
- Categorizes package architecture (`SINGLE`, `MULTI_PIECE`, `COMBINATION`, `GROUP`, `KIT`, `UNCERTAIN`).
- Protects Unit Sale Price (USP) logic by ensuring dissimilar commodities in combination packages are not averaged together.

### Module 5: QR Code & Electronic Product Evaluator (`qr_service.py`)
- Implements G.S.R. 456(E) rules for electronic commodities.
- Verifies physical on-pack scanning instructions, strictly restricts offloading to manufacturer address, country of origin, and manufacturing date, and prohibits blind external URL fetching.

### Module 6: Deterministic Compliance Rule Engine (`rule_engine.py`, `validators.py`)
- Pure mathematical and logical evaluation of mandatory declaration rules.
- Computes Visual Label Compliance Score ($0\text{--}100\%$) and outputs structured violations cited against Gazette rules.

### Module 7: Scope & Coverage Transparency (`compliance.py`)
- Explicitly partitions statutory requirements into evaluated visual declarations versus unperformed physical/external registry checks.

### Module 8: Inspection State & Next Best Action (`inspection_service.py`)
- Derives operational workflow state (`INCOMPLETE`, `NEEDS_REVIEW`, `READY_TO_REVIEW`, `READY_TO_FINALIZE`).
- Computes exactly one prioritized Next Best Action for the field officer.

### Module 9: Individual Physical Quantity Verification (`quantity_service.py`)
- Evaluates physical scale measurements of **one package** against First Schedule Table I MPE tolerances using `Decimal` arithmetic, unit normalization, and cross-dimension safety guards.

### Module 10: Persistence & Report Service (`report_service.py`, `connection.py`)
- Persists complete inspection payloads in `storage/scans/{id}/report.json` and PostgreSQL tables. Ensures backward compatibility for legacy scan reports.

---

## 14. Legal Metrology Rule Coverage

PackSure AI inspects declarations against **11 specifically codified rules** in `backend/app/rules/rules.json`:

| Rule Identifier | Statutory Citation | Rule Requirement & Evidence Evaluated | Decision Type | Evaluation Mode | Current Status |
|---|---|---|---|---|---|
| `LMR-R06-1-A` | Rule 6(1)(a) | Name and complete address of manufacturer, packer, or importer (entity name + geographic address). | Deterministic Format | Automated + Review | ✅ Implemented |
| `LMR-R06-1-AA` | Rule 6(1)(aa) | Country of origin for imported goods (country declaration string). | Conditional Presence | Automated (Conditional) | ✅ Implemented |
| `LMR-R06-1-B` | Rule 6(1)(b) | Common or generic name of the commodity contained in the package. | Substantive Presence | Automated | ✅ Implemented |
| `LMR-R06-1-C` | Rule 6(1)(c) | Net quantity declared in standard SI metric units (`g`, `kg`, `ml`, `L`, `U`). Non-standard units prohibited. | Strict SI Unit Format | Automated | ✅ Implemented |
| `LMR-R06-1-D` | Rule 6(1)(d) | Month and year of manufacture, packing, or import (`MM/YYYY`, `DD/MM/YYYY`, `Month YYYY`). | Date Format & Validity | Automated | ✅ Implemented |
| `LMR-R06-1-E` | Rule 6(1)(e) | Maximum Retail Price (MRP) with currency symbol and mandatory "inclusive of all taxes" clause. | Strict Text Format | Automated | ✅ Implemented |
| `LMR-R06-11` | Rule 6(11) | Unit Sale Price (USP) with correct statutory denominator (`per g/kg/ml/L/m/cm/U`) and mathematical rate. | Rate & Unit Math | Automated (Conditional) | ✅ Implemented |
| `LMR-R06-1-G` | Rule 6(1)(g) | Batch number, lot number, or code number for traceability. | Alphanumeric Presence | Automated | ✅ Implemented |
| `LMR-R06-1-M` | Rule 6(1)(m) | Best before / expiry date on perishable goods; verified that Expiry $\ge$ Manufacture Date. | Perishability Chronology | Automated (Conditional) | ✅ Implemented |
| `LMR-R06-1-N` | Rule 6(1)(n) | Consumer care cell details (name/designation, telephone digits, email address). | Contact Info Format | Automated | ✅ Implemented |
| `LMR-R26-A` | Rule 26(a) | Small package exemption ($\le 10\text{g}$ or $\le 10\text{ml}$ exempt from net qty, MRP, date; non-tobacco). | Statutory Exemption | Automated Filter | ✅ Implemented |

---

## 15. AI + OCR Architecture

The perception pipeline extracts candidate information without deciding compliance:
1. **Raw OCR (Tesseract):** Tokenizes all visible text with confidence levels and coordinates.
2. **Multimodal Vision (Gemini):** Interprets complex packaging layouts, multi-lingual texts, and non-linear declaration boxes.
3. **Structured Mapping:** Translates extracted data into typed Pydantic models.
4. **Deterministic Gate:** The rule engine receives extracted text and bounding boxes, evaluating statutory validity purely through deterministic Python validators.

---

## 16. Evidence Fusion

For multi-panel scans:
- Normalizes extracted values across views ($0, 1, \dots, N$).
- Tracks view provenance for every declaration.
- If declarations conflict (e.g., View 0 declares `MRP = ₹100` while View 1 declares `MRP = ₹150`), the system marks the field as `uncertain` with `conflict = True`, escalating the scan to `NEEDS_REVIEW`.

---

## 17. QR Code & Electronic Declaration Support

Under **G.S.R. 456(E)** (applicable to electronic products):
- **Conditional Applicability:** Evaluates if the product category represents an electronic commodity.
- **Physical Package Instruction:** Verifies presence of a physical on-pack instruction directing consumers to scan the QR code.
- **Restricted Offloading:** Only three fields may be electronically offloaded: (1) Manufacturer address, (2) Country of Origin, and (3) Month/Year of Manufacture.
- **Mandatory Physical Presence:** Net quantity, MRP, and consumer care must remain physically printed on the package.
- **Security Barrier:** The backend decodes and validates QR payloads without making outbound network requests.

---

## 18. Package Composition

Categorizes package structure to prevent erroneous rule execution:
- `SINGLE`: Individual retail container.
- `MULTI_PIECE`: Multiple identical individual items packaged together.
- `COMBINATION`: Dissimilar commodities bundled together.
- `GROUP`: Multiple identical pre-packaged units.
- `KIT`: Specialized composite articles with accessories.
- `UNCERTAIN`: Ambiguous structure requiring officer clarification.

**USP Protection:** Combination packs with dissimilar commodities are barred from calculating an invalid aggregate Unit Sale Price.

---

## 19. Inspector Copilot

The Inspector Copilot acts as an interactive field assistant:
- Displays overall inspection status (`PASS`, `FAIL`, `NEEDS_REVIEW`).
- Explains the rationale behind the current status (*"Why?"*).
- Recommends the single highest-priority **Next Best Action** with direct UI navigation.
- Maintains an interactive checklist of unverified workflow items.

---

## 20. Inspection Completeness

Synthesizes visual coverage, quality barriers, and physical verification into operational readiness states:
- `INCOMPLETE`: Critical data missing or image quality blocker detected.
- `NEEDS_REVIEW`: Conflicting evidence, unverified QR offload, or ambiguous composition present.
- `READY_TO_REVIEW`: Visual analysis completed; awaiting officer verification.
- `READY_TO_FINALIZE`: All visual, physical, and review steps resolved.

---

## 21. Individual Physical Quantity Verification

Field officers can verify the physical net quantity of **one individual package** against the **First Schedule [Rules 2(e) & 22], Table I Maximum Permissible Error (MPE)**:

### Table I Continuous Tier Registry (Weight & Volume)

| Declared Net Quantity ($q$) | Maximum Permissible Error (MPE) | Error Nature | Statutory Authority |
|---|---|---|---|
| $q \le 50\text{ g/ml}$ | $9.0\%$ of declared quantity | Percentage | First Schedule Table I |
| $50 < q \le 100\text{ g/ml}$ | $4.5\text{ g/ml}$ | Fixed | First Schedule Table I |
| $100 < q \le 200\text{ g/ml}$ | $4.5\%$ of declared quantity | Percentage | First Schedule Table I |
| $200 < q \le 300\text{ g/ml}$ | $9.0\text{ g/ml}$ | Fixed | First Schedule Table I |
| $300 < q \le 500\text{ g/ml}$ | $3.0\%$ of declared quantity | Percentage | First Schedule Table I |
| $500 < q \le 1000\text{ g/ml}$ | $15.0\text{ g/ml}$ | Fixed | First Schedule Table I |
| $1000 < q \le 10000\text{ g/ml}$ | $1.5\%$ of declared quantity | Percentage | First Schedule Table I |
| $10000 < q \le 15000\text{ g/ml}$ | $150.0\text{ g/ml}$ | Fixed | First Schedule Table I |
| $q > 15000\text{ g/ml}$ | $1.0\%$ of declared quantity | Percentage | First Schedule Table I |

### Metrological Invariants
- **Decimal Arithmetic:** Exact Python `Decimal` computations rounded to 4 decimal places.
- **Unit Normalization:** Normalizes canonical units ($1\text{ kg} = 1000\text{ g}$, $1\text{ L} = 1000\text{ ml}$).
- **Cross-Dimension Barrier:** Conversions between mass (`g`, `kg`) and volume (`ml`, `L`) are blocked and return `NEEDS_REVIEW`.
- **Double-MPE ($2\times\text{MPE}$):** Evaluated and displayed as a supplementary reference limit; does not initiate automated prosecution.
- **Decoupled Workflow State:** Updates `physical_checks_status` independently without altering the 0–100% Visual Label Compliance Score.

---

## 22. API Architecture

The FastAPI backend exposes structured REST endpoints adhering to `docs/api.md`:

| Method | Endpoint | Purpose | Request Body | Response Model |
|---|---|---|---|---|
| `POST` | `/api/v1/scans` | Ingest package images & dispatch scan worker | `multipart/form-data` | `ScanInitResponse` (202 Accepted) |
| `GET` | `/api/v1/scans/{id}` | Fetch full inspection record, evidence, & copilot | None (Path ID) | `ScanResponse` |
| `PATCH` | `/api/v1/scans/{id}/review` | Human reviewer declaration overrides & notes | `ScanReviewRequest` | `ScanResponse` |
| `POST` | `/api/v1/scans/{id}/quantity` | Submit physical scale measurement & Table I MPE | `QuantityMeasurementInput` | `ScanResponse` |
| `GET` | `/api/v1/history` | Paginated query of historical inspection records | Query params | `ScanHistoryResponse` |
| `GET` | `/api/v1/analytics` | Aggregated compliance metrics & trends | Query params | `AnalyticsResponse` |
| `GET` | `/api/v1/rules` | Retrieve codified rules & statutory descriptions | Query params | `RulesListResponse` |

---

## 23. Database & Persistence Architecture

- **PostgreSQL / Supabase:** Persists core entities (`scans`, `extracted_declarations`, `violations`, `product_categories`, `users`).
- **File & JSON Artifact Repository:** Stores raw images, annotated bounding box images, and complete `report.json` documents in `storage/scans/{id}/`.
- **Backward Compatibility:** Legacy scan reports lacking new physical quantity or composition fields deserialize gracefully without schema errors.

---

## 24. Frontend Workstation Experience

- **New Inspection Studio (`/new-inspection`):** Drag-and-drop / camera upload supporting multi-panel captures with real-time format validation.
- **Inspection Details Workstation (`/inspection/:id`):** Status header, Inspector Copilot, Physical Quantity card, side-by-side Evidence viewer, Declarations table, Rule Violations table, and Human Review modal.
- **Inspection History (`/history`):** Searchable, filterable data grid with pagination.
- **Analytics Dashboard (`/dashboard`):** Real-time pass rates, violation distributions, and daily inspection trends.
- **Rules Explorer (`/rules`):** Searchable reference catalog of all codified Legal Metrology rules.

---

## 25. Testing and Validation

- **Backend Automated Tests:** **361 test cases** across **26 test suites** in `backend/tests/`.
- **Offline Test Execution:** 360/360 deterministic offline tests pass (`OK`). (1 optional live Gemini API test is quota-dependent).
- **Frontend Build Validation:** Production build (`tsc -b && vite build`) completed successfully with **0 TypeScript compilation errors and no build-blocking errors**; Vite emitted a non-blocking bundle-size warning.

---

## 26. Current Results

- **Verified Declaration Parsing:** Successfully extracts and normalizes mandatory declarations across food, personal care, and packaged commodities.
- **Accurate Statutory Evaluation:** Deterministically flags missing MRP clauses, non-standard units (e.g., `gms`), and incorrect USP rates.
- **Deterministic Physical Net Quantity Evaluation:** Correctly evaluates scale inputs against First Schedule Table I MPE tiers and boundaries.
- **Robust Error Handling:** Rejects corrupted images, identifies blur/glare defects, and handles multi-view conflicts safely.

---

## 27. Known Limitations

1. **Individual Package Verification Only:** Evaluates **one package at a time**. Does not perform Fifth Schedule statistical lot sampling or batch clearance.
2. **Optical Font Height Limitation:** Physical font height in millimeters (Rule 7) cannot be certified from uncalibrated 2D mobile images without a physical calibration target.
3. **No Blind URL Fetching:** Decodes QR codes without fetching external endpoints to protect hardware security.
4. **No Autonomous Legal Authority:** Produces inspection findings, not automated judicial summonses or seizure orders.

---

## 28. Current Scope vs Future Scope

| Feature / Capability | Current Status | Technical Explanation |
|---|---|---|
| Multi-View Packaging Ingestion | ✅ Implemented | Ingests front, back, and side captures up to 20MB per view. |
| OpenCV Image Quality Pipeline | ✅ Implemented | Detects blur, glare, contrast, and skew before OCR. |
| OCR & AI Declaration Extraction | ✅ Implemented | Spatial Tesseract tokenization + Gemini multimodal extraction. |
| Deterministic Legal Rule Engine | ✅ Implemented | Pure Python validators for 11 codified rules in `rules.json`. |
| Multi-View Evidence Fusion | ✅ Implemented | Reconciles declarations across views; flags conflicts for review. |
| Package Composition Awareness | ✅ Implemented | Classifies Single/Multi-Piece/Combo/Kit to protect USP logic. |
| Conditional QR Code Verification | ✅ Implemented | Evaluates G.S.R. 456(E) electronic offloading rules safely. |
| Individual Physical Quantity Verification | ✅ Implemented | Computes First Schedule Table I MPE for one package at a time. |
| Inspector Copilot & Next Best Action | ✅ Implemented | Derives operational state and prioritized action guidance. |
| Human Review & Override Workflow | ✅ Implemented | Officer declaration correction and report finalization. |
| Calibrated Optical Font Height (Rule 7) | 🟡 Manual / Physical | Requires uncalibrated visual estimation or physical tool. |
| Fifth Schedule Statistical Lot Sampling | ⏳ Future | Lot-size sample selection, standard deviation, and batch clearance. |
| External DCA Registry (Rule 27) Lookup | ⏳ Future | Real-time verification against central government databases. |
| Offline Edge-AI Processing | ⏳ Future | On-device lightweight OCR and models for remote field use. |
| Cryptographic PDF Inspection Certificates | ⏳ Future | SHA-256 tamper-evident signed inspection certificates. |

---

## 29. Future Roadmap

- **Phase 7 (Review 2):** Cryptographic evidence hashing (SHA-256) & tamper-evident audit trails.
- **Phase 8 (Review 2):** Multi-officer review workflows, supervisory sign-offs, and appeals handling.
- **Phase 9 (Review 2/3):** Calibrated optical font-height validation (Rule 7) and commodity-specific packing schedules.
- **Phase 10 (Review 3):** Fifth Schedule statistical lot-sampling algorithms and batch clearance.
- **Phase 11 (Review 3):** Integration with DCA Rule 27 Manufacturer Database and FSSAI registries.
- **Phase 12 (Final Demo):** Offline Edge-AI field deployment for low-connectivity environments.

---

## 30. Demonstration Flow for Mentor Review (5–10 Minutes)

1. **Dashboard (`/dashboard`):** Show live compliance metrics, pass rates, and violation trends.
2. **Initiate Scan (`/new-inspection`):** Upload package front and back captures.
3. **Perception & Quality Check (`/inspection/:id`):** Demonstrate OpenCV blur/glare filters and raw OCR tokens.
4. **Structured Evidence & Bounding Boxes:** Inspect extracted declarations with visual overlays.
5. **Deterministic Rule Evaluation:** Show field-by-field compliance checking against Gazette citations.
6. **Inspector Copilot & Scope:** Review operational state and the recommended Next Best Action (*"Record Physical Net Quantity"*).
7. **Physical Quantity Verification:** Enter measured scale weight (e.g., `990g` for `1000g` pack); verify Table I MPE lookup ($15\text{g}$), deficiency ($10\text{g}$), and **PASS** verdict.
8. **Officer Review & Finalization:** Record reviewer notes and finalize the certified inspection record.
9. **History & Report Export (`/history`):** Show persisted JSON report artifact with timestamps and evidence.

---

## 31. Conclusion

PackSure AI demonstrates that regulatory compliance technology can be both **automated and legally defensible**. By strictly separating **AI perception** from **deterministic statutory evaluation**, the system provides transparent, explainable, and auditable field assistance for Legal Metrology officers. 

With 361 automated test cases, complete First Schedule Table I physical quantity verification, multi-view evidence fusion, and an interactive Inspector Copilot, PackSure AI establishes a solid, verified foundation for modern field inspection operations.
