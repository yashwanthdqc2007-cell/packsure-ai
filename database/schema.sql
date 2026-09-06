-- PackSure AI — Database Schema
-- Legal Metrology (Packaged Commodities) Rules, 2011 Compliance System
-- Engine: PostgreSQL (via Supabase)

-- Enable UUID extension if not already available
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- users
-- Inspector / user accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'inspector',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- product_categories
-- Categorization for applicable rule selection
-- ============================================================
CREATE TABLE IF NOT EXISTS product_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    applicable_rule_ids TEXT[],  -- rule IDs that apply to this category
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- rules
-- Versioned Legal Metrology rules
-- ============================================================
CREATE TABLE IF NOT EXISTS rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code TEXT NOT NULL,     -- e.g. "Rule-6(1)(a)"
    title TEXT NOT NULL,
    description TEXT,
    field_name TEXT,             -- declaration field this rule validates
    validation_type TEXT,        -- presence | format | range | conditional
    severity TEXT DEFAULT 'critical',  -- critical | major | minor
    version TEXT DEFAULT '2011',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- scans
-- Each scan represents one package compliance check
-- ============================================================
CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',  -- pending | processing | complete | failed
    verdict TEXT,                    -- PASS | FAIL | NEEDS_REVIEW
    compliance_score NUMERIC(5,2),
    product_category TEXT,           -- textual category name (e.g. "Food Grains", "Edible Oil")
    image_url TEXT,
    processed_image_url TEXT,
    evidence_image_url TEXT,         -- annotated visual evidence image path
    reviewer_notes TEXT,             -- human inspector notes on manual review
    product_category_id UUID REFERENCES product_categories(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============================================================
-- extracted_declarations
-- OCR + AI extracted mandatory declaration fields
-- ============================================================
CREATE TABLE IF NOT EXISTS extracted_declarations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES scans(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_value TEXT,
    confidence NUMERIC(5,4),
    bounding_box JSONB,           -- {x, y, width, height}
    source TEXT,                  -- 'tesseract' | 'gemini' | 'manual' | 'hybrid'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- violations
-- Individual rule violations found in a scan
-- ============================================================
CREATE TABLE IF NOT EXISTS violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES scans(id) ON DELETE CASCADE,
    rule_id TEXT,                 -- codified rule identifier string e.g. "LMR-R06-1-E"
    rule_code TEXT,               -- statutory rule citation code e.g. "Rule-6(1)(e)"
    field_name TEXT,
    violation_type TEXT,
    description TEXT,
    severity TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ai_analysis
-- Raw Gemini API responses for audit and debugging
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES scans(id) ON DELETE CASCADE,
    model TEXT,
    prompt_tokens INTEGER,
    response_tokens INTEGER,
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- reports
-- Generated compliance reports
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES scans(id) ON DELETE CASCADE,
    report_url TEXT,
    format TEXT DEFAULT 'json',   -- json | pdf
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes for query optimization (History & Analytics)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_verdict ON scans (verdict);
CREATE INDEX IF NOT EXISTS idx_scans_product_category ON scans (product_category);
CREATE INDEX IF NOT EXISTS idx_scans_user_id ON scans (user_id);
CREATE INDEX IF NOT EXISTS idx_extracted_declarations_scan_id ON extracted_declarations (scan_id);
CREATE INDEX IF NOT EXISTS idx_violations_scan_id ON violations (scan_id);
CREATE INDEX IF NOT EXISTS idx_violations_rule_code ON violations (rule_code);
CREATE INDEX IF NOT EXISTS idx_violations_created_at ON violations (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_scan_id ON ai_analysis (scan_id);
CREATE INDEX IF NOT EXISTS idx_reports_scan_id ON reports (scan_id);
