import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  mockInspectionResult,
  ComplianceFinding,
  ComplianceStatus,
} from '../../mock/results'
import Button from '../../components/common/Button'
import StatusBadge from '../../components/common/StatusBadge'
import {
  ArrowLeft,
  Printer,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ShieldAlert,
} from 'lucide-react'

// TODO: Replace mockInspectionResult with GET /api/v1/reports/:id from backend
// TODO: Persist PDF export event to backend audit log

// ---- Derived report data from single source of truth ----
function buildReportData(data: typeof mockInspectionResult) {
  const findings = data.findings
  const passCount = findings.filter((f) => f.status === 'PASS').length
  const failCount = findings.filter((f) => f.status === 'FAIL').length
  const reviewCount = findings.filter((f) => f.status === 'REVIEW').length
  // PASS: 20pts each, REVIEW: 8pts partial (not confirmed violation)
  const score = passCount * 20 + reviewCount * 8
  const overallStatus: 'NON-COMPLIANT' | 'NEEDS REVIEW' | 'COMPLIANT' =
    failCount > 0
      ? 'NON-COMPLIANT'
      : reviewCount > 0
      ? 'NEEDS REVIEW'
      : 'COMPLIANT'
  const failFindings = findings.filter((f) => f.status === 'FAIL')
  const reviewFindings = findings.filter((f) => f.status === 'REVIEW')
  const generatedAt = new Date().toLocaleString('en-IN', {
    dateStyle: 'long',
    timeStyle: 'short',
  })
  return {
    passCount,
    failCount,
    reviewCount,
    score,
    overallStatus,
    failFindings,
    reviewFindings,
    generatedAt,
  }
}

const STATUS_COLORS: Record<ComplianceStatus, string> = {
  PASS: 'text-emerald-700',
  FAIL: 'text-red-700',
  REVIEW: 'text-amber-700',
}

const STATUS_ROW_BG: Record<ComplianceStatus, string> = {
  PASS: '',
  FAIL: 'bg-red-50/60',
  REVIEW: 'bg-amber-50/40',
}

const STATUS_LABEL: Record<ComplianceStatus, string> = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  REVIEW: 'NEEDS REVIEW',
}

function ConfidenceBar({ value }: { value: number }) {
  const color =
    value >= 90 ? 'bg-emerald-600' : value >= 75 ? 'bg-blue-600' : 'bg-amber-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-slate-200 overflow-hidden flex-shrink-0">
        <div className={`h-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="font-mono text-xs font-semibold text-slate-700">{value}%</span>
    </div>
  )
}

// ---- Print CSS injected once ----
const PRINT_STYLE = `
@media print {
  /* Hide shell chrome */
  aside, nav, header, [data-no-print] { display: none !important; }
  /* Full-width report */
  main, [data-print-root] { margin: 0 !important; padding: 0 !important; max-width: 100% !important; }
  body { background: white !important; }
  .print\\:break-before-page { break-before: page; }
  /* No shadows/rings */
  * { box-shadow: none !important; }
}
`

export const ReportsPage: React.FC = () => {
  const { id = 'demo-1' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Inject print styles once
  React.useEffect(() => {
    const existing = document.getElementById('packsure-print-style')
    if (!existing) {
      const style = document.createElement('style')
      style.id = 'packsure-print-style'
      style.textContent = PRINT_STYLE
      document.head.appendChild(style)
    }
    return () => {
      // leave style tag; harmless to keep
    }
  }, [])

  // Use mock data as source of truth; in production this would come from backend
  const data = mockInspectionResult
  const {
    passCount,
    failCount,
    reviewCount,
    score,
    overallStatus,
    failFindings,
    reviewFindings,
    generatedAt,
  } = buildReportData(data)

  const formattedId =
    id.toLowerCase() === 'demo-1' ? 'DEMO-001' : id.toUpperCase()

  const handlePrint = () => {
    window.print()
  }

  const handleBackToResults = () => {
    navigate(`/results/${id || 'demo-1'}`)
  }

  const handleNewInspection = () => {
    navigate('/new-inspection')
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">

      {/* ── Top action bar (hidden on print) ── */}
      <div data-no-print className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Inspection Report
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Formal inspection summary and evidence record
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={handleBackToResults}
          >
            Back to Results
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<RotateCcw className="w-4 h-4" />}
            onClick={handleNewInspection}
          >
            New Inspection
          </Button>
          <Button
            size="sm"
            icon={<Printer className="w-4 h-4" />}
            onClick={handlePrint}
          >
            Download / Print PDF
          </Button>
        </div>
      </div>

      {/* ── MAIN REPORT CARD ── */}
      <div
        data-print-root
        className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden"
      >

        {/* ══ REPORT HEADER ══ */}
        <div className="px-8 pt-8 pb-6 border-b border-slate-200">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">

            {/* Brand & Title */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-md bg-brand-blue flex items-center justify-center flex-shrink-0">
                  <span className="text-white font-black text-xs leading-none">P</span>
                </div>
                <div>
                  <div className="text-xs font-bold uppercase tracking-widest text-brand-blue">
                    PackSure AI
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium tracking-wide">
                    SIH26034 — Evidence-based Inspection Platform
                  </div>
                </div>
              </div>

              <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
                Inspection Report
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Rule set: <strong className="text-slate-700">Applicable Legal Metrology requirements</strong>
              </p>
            </div>

            {/* Overall verdict capsule */}
            <div className="flex-shrink-0 flex flex-col items-end gap-1.5">
              {overallStatus === 'NON-COMPLIANT' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-100 text-red-800 border border-red-200 text-xs font-bold uppercase tracking-wide">
                  <XCircle className="w-4 h-4 text-red-600" />
                  NON-COMPLIANT
                </span>
              )}
              {overallStatus === 'NEEDS REVIEW' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 text-xs font-bold uppercase tracking-wide">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  NEEDS REVIEW
                </span>
              )}
              {overallStatus === 'COMPLIANT' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-bold uppercase tracking-wide">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  COMPLIANT
                </span>
              )}
              <span className="text-[11px] text-slate-400">
                Generated: {generatedAt}
              </span>
            </div>
          </div>

          {/* Inspection metadata grid */}
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            {[
              { label: 'Inspection ID', value: formattedId },
              { label: 'Product', value: data.product },
              { label: 'Category', value: data.category },
              { label: 'Analysis Mode', value: data.analysisMode },
            ].map(({ label, value }) => (
              <div key={label} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">
                  {label}
                </div>
                <div className="font-semibold text-slate-900 leading-snug">{value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ══ ASSESSMENT SUMMARY ══ */}
        <div className="px-8 py-6 border-b border-slate-200 bg-slate-50/50">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">

            {/* Score */}
            <div className="flex items-center gap-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
                  Assessment Score
                </div>
                <div className="flex items-baseline gap-1">
                  <span
                    className={`text-4xl font-extrabold tracking-tight ${
                      score >= 80
                        ? 'text-emerald-700'
                        : score >= 60
                        ? 'text-amber-600'
                        : 'text-red-600'
                    }`}
                  >
                    {score}
                  </span>
                  <span className="text-lg font-semibold text-slate-400">/ 100</span>
                </div>
              </div>

              <div className="h-14 w-[1px] bg-slate-200 hidden sm:block" />

              {/* 3-state counts */}
              <div className="flex items-center gap-3 text-xs font-semibold">
                <div className="flex flex-col items-center p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 min-w-[52px]">
                  <span className="text-[10px] font-bold text-emerald-800">PASS</span>
                  <span className="text-2xl font-extrabold text-emerald-700">{passCount}</span>
                </div>
                <div className="flex flex-col items-center p-2.5 rounded-lg bg-red-50 border border-red-200 min-w-[52px]">
                  <span className="text-[10px] font-bold text-red-800">FAIL</span>
                  <span className="text-2xl font-extrabold text-red-700">{failCount}</span>
                </div>
                <div className="flex flex-col items-center p-2.5 rounded-lg bg-amber-50 border border-amber-200 min-w-[52px]">
                  <span className="text-[10px] font-bold text-amber-800">REVIEW</span>
                  <span className="text-2xl font-extrabold text-amber-700">{reviewCount}</span>
                </div>
              </div>
            </div>

            {/* Score note */}
            <div className="flex items-start gap-2 text-[11px] text-slate-500 max-w-xs leading-relaxed bg-white border border-slate-200 rounded-lg p-3">
              <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
              <span>
                REVIEW findings are not treated as confirmed violations. Assessment score is
                not a legal compliance percentage.
              </span>
            </div>
          </div>
        </div>

        {/* ══ PACKAGE EVIDENCE IMAGE ══ */}
        <div className="px-8 py-6 border-b border-slate-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Package Evidence
          </div>
          <div className="flex flex-col sm:flex-row gap-6 items-start">
            {/* Image */}
            <div className="bg-slate-900 rounded-lg overflow-hidden border border-slate-800 flex-shrink-0 w-full sm:w-48">
              <img
                src="/demo-package.svg"
                alt="Package evidence — demo commodity label"
                className="w-full h-auto object-contain block"
              />
            </div>

            {/* Legend + note */}
            <div className="space-y-3 text-xs">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">
                  Evidence Legend
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 rounded border-2 border-emerald-500 bg-emerald-100 flex-shrink-0" />
                    <span className="font-medium text-slate-700">
                      Verified evidence — requirement satisfied
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 rounded border-2 border-red-500 bg-red-100 flex-shrink-0" />
                    <span className="font-medium text-slate-700">
                      Violation evidence — requirement not satisfied
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 rounded border-2 border-amber-500 bg-amber-100 flex-shrink-0" />
                    <span className="font-medium text-slate-700">
                      Review evidence — insufficient for deterministic decision
                    </span>
                  </div>
                </div>
              </div>

              <p className="text-slate-400 text-[11px] leading-relaxed max-w-sm">
                Evidence regions are mapped from the visual evidence captured during inspection.
                Deterministic rules are evaluated against extracted declarations only.
              </p>
            </div>
          </div>
        </div>

        {/* ══ FINDINGS TABLE ══ */}
        <div className="px-8 py-6 border-b border-slate-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">
            Declaration Findings ({data.findings.length} evaluated)
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-xs border-collapse min-w-[640px]">
              <thead>
                <tr className="bg-slate-100 text-left">
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px] w-8">#</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px]">Declaration</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px]">Status</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px]">Detected Value</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px]">Evidence Confidence</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 uppercase tracking-wider text-[10px]">Requirement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.findings.map((f: ComplianceFinding, idx: number) => (
                  <tr
                    key={f.id}
                    className={`${STATUS_ROW_BG[f.status]} hover:bg-slate-50 transition-colors`}
                  >
                    <td className="px-4 py-3 text-slate-400 font-mono">{String(idx + 1).padStart(2, '0')}</td>
                    <td className="px-4 py-3 font-semibold text-slate-900">{f.field}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={f.status} size="sm" label={STATUS_LABEL[f.status]} />
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700 max-w-[160px] truncate" title={f.detectedValue}>
                      {f.detectedValue}
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceBar value={f.confidence} />
                    </td>
                    <td className="px-4 py-3 text-slate-600 leading-snug max-w-[200px]">
                      {f.requirement}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ══ VIOLATION HIGHLIGHT ══ */}
        {failFindings.length > 0 && (
          <div className="px-8 py-6 border-b border-slate-200">
            <div className="text-xs font-semibold uppercase tracking-wider text-red-600 mb-3 flex items-center gap-2">
              <XCircle className="w-4 h-4" />
              Violation Detail{failFindings.length > 1 ? 's' : ''}
            </div>
            <div className="space-y-4">
              {failFindings.map((f) => (
                <div
                  key={f.id}
                  className="rounded-xl border border-red-200 bg-red-50/60 p-5"
                >
                  <div className="flex flex-wrap items-center gap-3 mb-3">
                    <StatusBadge status="FAIL" />
                    <h3 className="text-sm font-bold text-red-900">{f.field}</h3>
                    <span className="text-[11px] font-mono text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded">
                      {f.evidenceRegion}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Evidence</div>
                      <div className="font-mono bg-white border border-red-200 rounded p-2 text-slate-800">
                        {f.detectedValue}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Requirement</div>
                      <div className="text-slate-700 leading-snug">{f.requirement}</div>
                    </div>
                  </div>

                  <div className="mt-3 pt-3 border-t border-red-200">
                    <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Explanation</div>
                    <p className="text-slate-700 text-xs leading-relaxed">{f.explanation}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ REVIEW NOTICE ══ */}
        {reviewFindings.length > 0 && (
          <div className="px-8 py-6 border-b border-slate-200">
            <div className="text-xs font-semibold uppercase tracking-wider text-amber-600 mb-3 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4" />
              Findings Requiring Human Verification
            </div>
            <div className="space-y-4">
              {reviewFindings.map((f) => (
                <div
                  key={f.id}
                  className="rounded-xl border border-amber-200 bg-amber-50/50 p-5"
                >
                  <div className="flex flex-wrap items-center gap-3 mb-3">
                    <StatusBadge status="REVIEW" />
                    <h3 className="text-sm font-bold text-amber-900">{f.field}</h3>
                    <span className="text-[11px] font-mono text-slate-400 bg-white border border-slate-200 px-2 py-0.5 rounded">
                      {f.evidenceRegion}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs mb-3">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Detected Text</div>
                      <div className="font-mono bg-white border border-amber-200 rounded p-2 text-slate-800">
                        {f.detectedValue}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Evidence Confidence</div>
                      <ConfidenceBar value={f.confidence} />
                      <p className="text-[11px] text-amber-700 mt-1">
                        Below threshold — manual review required
                      </p>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-amber-200">
                    <div className="text-[10px] font-bold uppercase text-slate-500 mb-1">Explanation</div>
                    <p className="text-slate-700 text-xs leading-relaxed">{f.explanation}</p>
                  </div>

                  <div className="mt-3 p-3 rounded-lg bg-white border border-amber-200 text-[11px] text-amber-800 flex items-start gap-2">
                    <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-600" />
                    <span>
                      REVIEW is not a confirmed violation. A qualified inspector must verify
                      this finding before a formal compliance determination is recorded.
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ DETAILED FINDING EXPLANATIONS ══ */}
        <div className="px-8 py-6 border-b border-slate-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">
            Detailed Finding Notes
          </div>
          <div className="divide-y divide-slate-100">
            {data.findings.map((f, idx) => (
              <div key={f.id} className="py-3.5 grid grid-cols-12 gap-4 text-xs items-start">
                <div className="col-span-1 text-slate-400 font-mono pt-0.5">
                  {String(idx + 1).padStart(2, '0')}
                </div>
                <div className="col-span-3 font-semibold text-slate-800">{f.field}</div>
                <div className="col-span-2">
                  <StatusBadge status={f.status} size="sm" label={STATUS_LABEL[f.status]} />
                </div>
                <div className={`col-span-6 leading-relaxed ${STATUS_COLORS[f.status]} opacity-90`}>
                  {f.explanation}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ══ REPORT FOOTER ══ */}
        <div className="px-8 py-6 bg-slate-50 border-t border-slate-200">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <p className="text-xs text-slate-500 italic max-w-lg leading-relaxed">
              "AI extracts the evidence. Deterministic rules determine compliance. Humans review uncertainty."
            </p>
            <div className="text-right text-[11px] text-slate-400 space-y-0.5">
              <div className="font-semibold text-slate-600">PackSure AI — SIH26034</div>
              <div>Report ID: {formattedId} • {generatedAt}</div>
              <div>This report is a demonstration output. Not a legal compliance certificate.</div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom action repeat (non-print) */}
      <div data-no-print className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={handleBackToResults}
          >
            Back to Results
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<RotateCcw className="w-4 h-4" />}
            onClick={handleNewInspection}
          >
            New Inspection
          </Button>
        </div>
        <Button
          size="sm"
          icon={<Printer className="w-4 h-4" />}
          onClick={handlePrint}
        >
          Download / Print PDF
        </Button>
      </div>
    </div>
  )
}

export default ReportsPage
