# PackSure AI — Architecture Decision Records

This document records key technical decisions made during development.

## ADR-001: AI extracts, rules engine decides

**Decision:** Gemini Vision is used only for information extraction. The compliance verdict is always produced by the deterministic rules engine.

**Rationale:** Legal compliance decisions must be auditable, traceable to specific rule references, and stable across AI model updates.

## ADR-002: Supabase for database

**Decision:** Use Supabase (hosted PostgreSQL) for the MVP.

**Rationale:** Fast setup, no infrastructure management, built-in REST API and auth.

## ADR-003: Tesseract + Gemini dual extraction

**Decision:** Use Tesseract for raw text extraction, Gemini for structured field parsing.

**Rationale:** Tesseract provides low-latency baseline. Gemini improves accuracy for complex layouts and multilingual text.

## ADR-004: Vite + React + Tailwind for frontend

**Decision:** Use Vite for fast dev server, React for component model, Tailwind for utility-first styling.

**Rationale:** Fast setup, large ecosystem, well-suited for a 1-day hackathon build.
