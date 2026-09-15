/**
 * PackSure AI — Canonical Frontend API Type Definitions.
 *
 * Strict TypeScript interfaces exactly mirroring backend schemas (backend/app/schemas/*.py)
 * and the frozen API contract (docs/api.md).
 */

// ============================================================
// 1. Core Canonical Enums & Domain Unions
// ============================================================

/** Lifecycle status of a package compliance scan. */
export type ScanStatus = 'pending' | 'processing' | 'complete' | 'failed'

/** Deterministic compliance verdict computed across all applicable Legal Metrology rules. */
export type ComplianceVerdict = 'PASS' | 'FAIL' | 'NEEDS_REVIEW'
export type Verdict = ComplianceVerdict

/** Severity tier rating for compliance violations. */
export type ViolationSeverity = 'critical' | 'major' | 'minor'
export type Severity = ViolationSeverity

/** Categorization of rule violation according to Legal Metrology validation rules. */
export type ViolationType =
  | 'missing_declaration'
  | 'invalid_format'
  | 'invalid_unit'
  | 'out_of_range'
  | 'illegible'
  | 'misleading'
  | 'pdp_violation'
  | 'font_size_violation'
  | 'other'

/** Source modality or engine for extracted declarations. */
export type DeclarationSource = 'tesseract' | 'gemini' | 'manual' | 'hybrid'

/** Presence and detection status of an individual declaration field. */
export type DeclarationStatus = 'detected' | 'missing' | 'uncertain'

/** Codified mandatory Legal Metrology declaration field identifiers. */
export type MandatoryFieldType =
  | 'manufacturer_name_and_address'
  | 'net_quantity'
  | 'mrp'
  | 'unit_sale_price'
  | 'manufacture_date'
  | 'expiry_date'
  | 'batch_number'
  | 'consumer_care'
  | 'country_of_origin'
  | 'generic_name'

/** Time aggregation period filter for analytics queries. */
export type AnalyticsPeriod = '7d' | '30d' | 'all'


// ============================================================
// 2. Spatial & Declaration Models
// ============================================================

/** Non-negative pixel bounding box relative to original unscaled image dimensions. */
export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

/** Extracted declaration field with OCR/AI metadata, normalized values, bounding box, and view provenance. */
export interface ExtractedDeclaration {
  id?: string | null
  scan_id?: string | null
  field_name: string
  status: DeclarationStatus
  raw_value?: string | null
  normalized_value?: string | null
  confidence?: number | null
  bounding_box?: BoundingBox | null
  source?: DeclarationSource | null
  image_index?: number | null
  image_name?: string | null
  created_at?: string | null
}

/** Schema for manual reviewer overrides submitted via PATCH review endpoint. */
export interface CorrectedDeclaration {
  field_name: string
  raw_value?: string | null
  normalized_value?: string | null
  status?: DeclarationStatus | null
}


// ============================================================
// 3. Violation & Evidence Models
// ============================================================

/** Detailed violation record linking statutory rule citation, affected field, and description. */
export interface Violation {
  id?: string | null
  scan_id?: string | null
  rule_id?: string | null
  rule_code: string
  field_name?: string | null
  violation_type: ViolationType
  severity: ViolationSeverity
  description: string
  created_at?: string | null
}

/** Metadata container for generated visual evidence artifacts and audit trails. */
export interface EvidenceMetadata {
  evidence_image_url?: string | null
  annotated_image_path?: string | null
  timestamp?: string | null
  rule_version?: string | null
  total_declarations_checked: number
  total_violations_found: number
}

/** Structured manifest declaring the exact statutory scope, automated visual coverage, and physical/external exclusions. */
export interface ScopeCoverageManifest {
  score_name?: string
  score_meaning?: string
  image_verifiable_rules_checked: string[]
  views_captured_count: number
  multi_view_status: string
  is_complete_scan: boolean
  physical_checks_excluded: string[]
  external_data_checks_excluded: string[]
  disclaimer: string
}

/** Detection and decoding status for on-package QR codes. */
export type QREvidenceStatus = 'detected' | 'decoded' | 'undecodable' | 'missing' | 'uncertain'

/** Statutory applicability of Rule 6 electronic product QR offloading. */
export type ElectronicApplicability = 'APPLICABLE' | 'NOT_APPLICABLE' | 'UNCERTAIN'

/** Typed evidence container for on-package QR codes under Rule 6 / G.S.R. 456(E). */
export interface QREvidence {
  detected: boolean
  status: QREvidenceStatus
  confidence: number
  bounding_box?: BoundingBox | null
  decoded_payload?: string | null
  payload_valid?: boolean | null
  source_image_index?: number | null
  instruction_detected: boolean
  instruction_text?: string | null
  applicable_product: ElectronicApplicability
  statutory_note?: string | null
}

/** Package composition classification types. */
export type PackageType = 'SINGLE' | 'MULTI_PIECE' | 'COMBINATION' | 'GROUP' | 'KIT' | 'UNCERTAIN'

/** Constituent item declaration within a packaged commodity. */
export interface PackageItem {
  item_index: number
  commodity_name: string
  item_count?: number | null
  unit_quantity?: string | null
  status?: DeclarationStatus | null
  confidence?: number | null
  source_image_index?: number | null
  bounding_box?: BoundingBox | null
}

/** Structured container representing package composition and constituent items. */
export interface PackageComposition {
  package_type: PackageType
  total_item_count: number
  items: PackageItem[]
  status?: DeclarationStatus | null
  confidence?: number | null
  statutory_note?: string | null
}

/** Consolidated outcome of the deterministic rules engine evaluation. */
export interface ComplianceResult {
  verdict: ComplianceVerdict
  compliance_score: number
  declarations: ExtractedDeclaration[]
  violations: Violation[]
  evidence_image_url?: string | null
  evidence?: EvidenceMetadata | null
  guidance?: InspectionGuidance | null
  scope_coverage?: ScopeCoverageManifest | null
  qr_evidence?: QREvidence | null
  composition?: PackageComposition | null
  inspection_state?: InspectionState | null
  next_best_action?: NextBestAction | null
}


// ============================================================
// 4. Inspection Guidance & Operational State Models
// ============================================================

export type GuidancePriority = 'none' | 'low' | 'medium' | 'high' | 'critical'
export type GuidanceIssueCategory = 'quality' | 'conflict' | 'missing_evidence' | 'uncertain_evidence'
export type GuidanceTargetPanel = 'front' | 'back' | 'side' | 'top' | 'bottom' | 'mrp_panel' | 'nutrition_table' | 'generic'

export interface GuidanceIssue {
  code: string
  category: GuidanceIssueCategory
  title: string
  description: string
  suggested_action: string
  target_panel?: GuidanceTargetPanel | null
  affected_view_index?: number | null
  affected_fields: string[]
}

export interface InspectionGuidance {
  needs_recapture: boolean
  priority: GuidancePriority
  headline: string
  target_panels: string[]
  issues: GuidanceIssue[]
  actionable_steps: string[]
  coverage_estimate_pct?: number | null
}

export type InspectionStateStatus = 'INCOMPLETE' | 'NEEDS_REVIEW' | 'READY_TO_REVIEW' | 'READY_TO_FINALIZE'
export type OfficerReviewStatus = 'NOT_REQUIRED' | 'PENDING' | 'COMPLETED'
export type PhysicalChecksStatus = 'NOT_EVALUATED' | 'PENDING' | 'COMPLETED'
export type ExternalChecksStatus = 'NOT_EVALUATED' | 'PENDING' | 'COMPLETED'

export interface NextBestAction {
  action_code: string
  title: string
  description: string
  priority: string
  target_tab?: string | null
  target_panel?: string | null
  suggested_button_text?: string | null
}

export interface InspectionState {
  status: InspectionStateStatus
  visual_checks_complete: boolean
  views_captured: number
  unresolved_count: number
  quality_blockers: string[]
  evidence_conflicts: string[]
  officer_review_status: OfficerReviewStatus
  physical_checks_status: PhysicalChecksStatus
  external_checks_status: ExternalChecksStatus
  ready_to_finalize: boolean
  summary?: string | null
}


// ============================================================
// 5. Scan API Request & Response Models
// ============================================================

/** Ingestion parameters for POST /api/v1/scans multipart upload. Supports single or multi-view images. */
export interface ScanCreateParams {
  image?: File | Blob
  images?: (File | Blob)[]
  is_complete_scan?: boolean
  product_category?: string | null
  user_id?: string | null
}

/** Initial response returned upon image ingestion (POST /api/v1/scans — 202 Accepted). */
export interface ScanInitResponse {
  scan_id: string
  status: ScanStatus
  created_at: string
}

/** Comprehensive inspection report payload returned by GET /api/v1/scans/{id}. */
export interface ScanResponse {
  scan_id: string
  status: ScanStatus
  verdict?: ComplianceVerdict | null
  compliance_score?: number | null
  product_category?: string | null
  image_url?: string | null
  image_urls?: string[] | null
  processed_image_url?: string | null
  evidence_image_url?: string | null
  evidence_image_urls?: string[] | null
  is_complete_scan?: boolean
  declarations: ExtractedDeclaration[]
  violations: Violation[]
  reviewer_notes?: string | null
  guidance?: InspectionGuidance | null
  scope_coverage?: ScopeCoverageManifest | null
  qr_evidence?: QREvidence | null
  composition?: PackageComposition | null
  inspection_state?: InspectionState | null
  next_best_action?: NextBestAction | null
  created_at: string
  completed_at?: string | null
}

/** Payload submitted by inspector to resolve NEEDS_REVIEW scan (PATCH /api/v1/scans/{id}/review). */
export interface ScanReviewRequest {
  verdict: 'PASS' | 'FAIL'
  reviewer_notes: string
  corrected_declarations?: CorrectedDeclaration[] | null
}


// ============================================================
// 5. History API Models
// ============================================================

/** Summary item representing a historical scan in paginated list (GET /api/v1/history). */
export interface ScanHistoryItem {
  id: string
  product_name?: string | null
  category?: string | null
  scanned_at: string
  verdict?: ComplianceVerdict | null
  compliance_score?: number | null
  status: ScanStatus
}

/** Paginated scan history response (GET /api/v1/history). */
export interface ScanHistoryResponse {
  total: number
  page: number
  limit: number
  total_pages: number
  results: ScanHistoryItem[]
}

/** Query parameters supported by GET /api/v1/history. */
export interface HistoryQueryParams {
  page?: number
  limit?: number
  verdict?: ComplianceVerdict
  category?: string
  search?: string
  from_date?: string
  to_date?: string
}


// ============================================================
// 6. Analytics API Models
// ============================================================

/** Daily activity volume and compliance breakdown trend item (GET /api/v1/analytics). */
export interface DailyTrendItem {
  day: string
  date: string
  scans: number
  compliant: number
  non_compliant: number
  needs_review: number
}

/** Aggregated occurrence frequency for a statutory rule violation. */
export interface TopViolationItem {
  rule_code: string
  description: string
  count: number
}

/** Per-category compliance breakdown statistics. */
export interface CategoryStats {
  total: number
  pass: number
  fail: number
  review: number
}

/** Aggregated telemetry and metrics payload (GET /api/v1/analytics). */
export interface AnalyticsResponse {
  total_scans: number
  pass_count: number
  fail_count: number
  review_count: number
  pass_rate: number
  daily_trend: DailyTrendItem[]
  top_violations: TopViolationItem[]
  by_category: Record<string, CategoryStats>
}


// ============================================================
// 7. Rules API Models
// ============================================================

/** Documented representation of an individual Legal Metrology rule item (GET /api/v1/rules). */
export interface RuleItem {
  id: string
  rule_code: string
  title: string
  description: string
  field_name: string
  validation_type: string
  severity: string
  version: string
  active: boolean
}

/** Canonical response from GET /api/v1/rules. */
export interface RulesResponse {
  category: string
  total: number
  rules: RuleItem[]
}

/** Query parameters supported by GET /api/v1/rules. */
export interface RulesQueryParams {
  category?: string
  active_only?: boolean
}
