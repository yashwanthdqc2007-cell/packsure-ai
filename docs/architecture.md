# PackSure AI — System Architecture

## Pipeline Overview

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
Applicable Versioned Rules Selection
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

## Critical Architectural Principle

> **AI extracts information. The deterministic rules engine makes the compliance decision.**

Gemini Vision is used to extract and structure declaration fields from the package image. It is explicitly **not** allowed to determine whether a package is compliant or non-compliant.

All compliance verdicts are produced by the `compliance_service` which applies the rules loaded from `rules.json` (sourced from the Legal Metrology (Packaged Commodities) Rules, 2011) against the extracted declarations.

This ensures:
- Compliance decisions are auditable and rule-traceable
- Compliance decisions do not change if the AI model changes
- Each violation can be cited against a specific rule reference

## Components

### 1. Image Quality Check
- Validates image is usable (resolution, blur, brightness)
- Returns quality report; rejects below-threshold images

### 2. OpenCV Preprocessing
- Deskew, denoise, binarize, resize
- Optimizes image for OCR accuracy

### 3. OCR — Tesseract
- Extracts raw text blocks with bounding boxes
- Returns confidence scores per block

### 4. AI Extraction — Gemini Vision
- Receives preprocessed image + OCR raw text
- Extracts structured declaration fields using JSON structured output
- Does NOT evaluate compliance

### 5. Product Category Detection
- Classifies the product (food, beverage, cosmetic, etc.)
- Determines which subset of rules apply

### 6. Rules Engine (Deterministic)
- Loads versioned rules for the product category
- Applies each rule against the extracted declaration
- Produces a list of violations with rule references

### 7. Verdict
- PASS: No violations
- FAIL: One or more critical violations
- NEEDS REVIEW: Low-confidence extraction or minor violations only

### 8. Evidence Mapping
- Annotates original image with bounding boxes
- Maps each field to its compliance status
- Creates timestamped evidence package

### 9. Report
- Structured JSON + exportable PDF
- Field-by-field breakdown
- Rule references for each violation

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript, Tailwind |
| Backend API | FastAPI (Python) |
| Image Processing | OpenCV |
| OCR | Tesseract |
| AI Extraction | Google Gemini Vision |
| Database | Supabase (PostgreSQL) |
| Validation | Pydantic |
