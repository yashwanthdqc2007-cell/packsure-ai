# PackSure AI

> **Hackathon MVP** — Smart India Hackathon 2026  
> Problem Statement: **SIH26034**

**Tagline:** *From Package Image to Inspection-Ready Evidence.*

---

## What is PackSure AI?

PackSure AI is a software system designed to help Legal Metrology inspectors and enforcement officers verify compliance of packaged commodities against the **Legal Metrology (Packaged Commodities) Rules, 2011** (India).

Inspectors photograph a product package. PackSure AI extracts the mandatory declarations from the image using OCR and AI vision, checks them against the applicable legal rules using a deterministic compliance engine, and produces structured, inspection-ready evidence.

> **Disclaimer:** This is a hackathon MVP. It has not been approved, certified, or endorsed by any government authority. It is not ready for production or legal enforcement use.

---

## Problem Statement — SIH26034

**Title:** Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011.

**Problem:** Manual inspection of packaged commodities is time-consuming, inconsistent, and difficult to scale. Inspectors must manually check whether every mandatory declaration (name, address, weight, MRP, date, batch, etc.) is present, legible, and formatted correctly — across thousands of different products and categories.

**Impact:** Non-compliant packages mislead consumers, cause revenue loss, and undermine fair trade. Enforcement is under-resourced.

---

## Core Solution

1. Inspector uploads or photographs a product package.
2. **OpenCV** preprocesses the image for OCR quality.
3. **Tesseract OCR + Gemini Vision** extracts text and structured declarations.
4. A **deterministic rules engine** checks extracted data against the applicable Legal Metrology rules.
5. The system produces a **PASS / FAIL / NEEDS REVIEW** verdict with:
   - Field-by-field compliance breakdown
   - Specific violations cited against rule numbers
   - Annotated evidence image
   - Exportable inspection report

> **Architectural principle:** AI extracts information. The deterministic rules engine makes the compliance decision. AI does not directly determine legal compliance.

---

## Architecture Overview

```
Package Image
    ↓
Image Quality Check
    ↓
OpenCV Preprocessing
    ↓
OCR / Vision (Tesseract + Gemini)
    ↓
Structured Declaration Extraction
    ↓
Product Category Detection
    ↓
Applicable Rules Selection
    ↓
Deterministic Compliance Engine
    ↓
PASS / FAIL / NEEDS REVIEW
    ↓
Evidence Mapping
    ↓
Compliance Report
    ↓
Dashboard / History
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI |
| **OCR** | Tesseract OCR, OpenCV |
| **AI Vision** | Google Gemini API |
| **Database** | Supabase (PostgreSQL) |
| **Validation** | Pydantic |
| **CI** | GitHub Actions |

---

## Repository Structure

```
packsure-ai/
├── frontend/          # React + Vite + TypeScript UI
├── backend/           # FastAPI + OCR + AI + Rules engine
├── database/          # SQL schema, migrations, seeds
├── sample-images/     # Test package images (compliant / non-compliant / unclear)
├── research/          # Legal Metrology rules research
├── docs/              # Architecture, API, database, pipeline docs
├── tests/             # Integration and E2E tests
├── .github/           # GitHub Actions CI workflows
├── .gitignore
├── .env.example
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

---

## Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/packsure-ai.git
cd packsure-ai
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in your values (never commit .env)
```

---

## Running the Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

## Running the Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs at: http://localhost:8000/docs

---

## Environment Variables

| Variable | Used By | Description |
|---|---|---|
| `FRONTEND_URL` | Backend | Allowed CORS origin |
| `BACKEND_URL` | Frontend | API base URL |
| `GEMINI_API_KEY` | Backend | Google Gemini API key |
| `SUPABASE_URL` | Backend | Supabase project URL |
| `SUPABASE_ANON_KEY` | Backend | Supabase anon/public key |
| `DATABASE_URL` | Backend | PostgreSQL connection string |
| `VITE_API_BASE_URL` | Frontend | Vite-exposed API URL |

See [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example).

---

## Team Development Workflow

```bash
# Developer 1 — Frontend
git checkout frontend-dev
git pull origin frontend-dev
# work ... commit ... push

# Developer 2 — Backend
git checkout backend-dev
git pull origin backend-dev
# work ... commit ... push

# Merge to main when stable
git checkout main && git merge frontend-dev
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow.

---

## Current MVP Status

| Area | Status |
|---|---|
| Project structure | ✅ Complete |
| Frontend UI | 🔲 In Progress |
| Backend API skeleton | 🔲 In Progress |
| OCR pipeline | 🔲 In Progress |
| Rules engine | 🔲 In Progress |
| Gemini integration | 🔲 In Progress |
| Database schema | 🔲 In Progress |
| Demo flow | 🔲 Planned |

---

*Built for Smart India Hackathon 2026 — Hackathon MVP only.*
