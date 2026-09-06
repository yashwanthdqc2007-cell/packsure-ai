import React, { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import StatusBadge from '../../components/common/StatusBadge'
import {
  mockInspectionResult,
  ComplianceFinding,
  ComplianceStatus,
} from '../../mock/results'
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCcw,
  LayoutDashboard,
  Eye,
  ShieldAlert,
  Info,
  Layers,
} from 'lucide-react'

// TODO: Replace with GET /api/v1/inspections/:id/results response from backend
// TODO: Persist human verification review to backend audit log

export const InspectionDetailsPage: React.FC = () => {
  const { id = 'demo-1' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  // Route state if image or details were passed from previous steps
  const routeState = location.state as
    | {
        imagePreviewUrl?: string
        productName?: string
        category?: string
      }
    | undefined

  // Local state for findings and human-in-the-loop actions
  const [findings, setFindings] = useState<ComplianceFinding[]>(
    mockInspectionResult.findings
  )
  const [activeFindingId, setActiveFindingId] = useState<string>(
    mockInspectionResult.findings[0]?.id || 'f-1'
  )
  const [reviewModalFinding, setReviewModalFinding] =
    useState<ComplianceFinding | null>(null)

  // Package image source (route state fallback to SVG demo evidence)
  const imageSrc = routeState?.imagePreviewUrl || '/demo-package.svg'
  const productName = routeState?.productName || mockInspectionResult.product
  const categoryName = routeState?.category || mockInspectionResult.category
  const formattedId =
    id.toLowerCase() === 'demo-1' ? 'DEMO-001' : id.toUpperCase()

  // Dynamic counts based on local findings state
  const passCount = findings.filter((f) => f.status === 'PASS').length
  const failCount = findings.filter((f) => f.status === 'FAIL').length
  const reviewCount = findings.filter((f) => f.status === 'REVIEW').length
  const totalEvaluated = findings.length

  // Overall status calculation
  const overallStatus: 'NON-COMPLIANT' | 'NEEDS REVIEW' | 'COMPLIANT' =
    failCount > 0
      ? 'NON-COMPLIANT'
      : reviewCount > 0
      ? 'NEEDS REVIEW'
      : 'COMPLIANT'

  // Dynamic score calculation:
  // PASS gives 20 pts (5 checks * 20 = 100 max)
  // REVIEW gives 8 pts (partial score; not confirmed violation)
  // Initial demo: 3 PASS (60) + 1 REVIEW (8) + 1 FAIL (0) = 68 / 100!
  const complianceScore = passCount * 20 + reviewCount * 8

  // Findings requiring attention
  const attentionCount = failCount + reviewCount

  // Human-in-the-loop review actions
  const handleMarkVerified = (findingId: string) => {
    // TODO: Send inspector verification audit log to backend
    setFindings((prev) =>
      prev.map((f) =>
        f.id === findingId
          ? {
              ...f,
              status: 'PASS' as ComplianceStatus,
              explanation:
                'Inspector verified: Manufacturer and packer address confirmed readable and complete.',
            }
          : f
      )
    )
    setReviewModalFinding(null)
  }

  const handleMarkViolation = (findingId: string) => {
    // TODO: Send inspector violation audit log to backend
    setFindings((prev) =>
      prev.map((f) =>
        f.id === findingId
          ? {
              ...f,
              status: 'FAIL' as ComplianceStatus,
              explanation:
                'Inspector confirmed violation: Manufacturer declaration incomplete or illegible.',
            }
          : f
      )
    )
    setReviewModalFinding(null)
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* ================================================== */}
      {/* 2. RESULT HEADER */}
      {/* ================================================== */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                Inspection Result
              </span>
              <span className="text-xs font-mono font-bold text-slate-700 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                {formattedId}
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs text-slate-500 font-medium">
                {categoryName}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                {productName}
              </h1>

              {/* Overall status badge */}
              {overallStatus === 'NON-COMPLIANT' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide bg-red-100 text-red-800 border border-red-200">
                  <XCircle className="w-4 h-4 text-red-600" />
                  NON-COMPLIANT
                </span>
              )}
              {overallStatus === 'NEEDS REVIEW' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide bg-amber-100 text-amber-800 border border-amber-200">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  NEEDS REVIEW
                </span>
              )}
              {overallStatus === 'COMPLIANT' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  COMPLIANT
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
              <span className="flex items-center gap-1 font-medium text-slate-700">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Evidence reviewed
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-slate-600">
                Rule set: <strong className="text-slate-800">Applicable Legal Metrology requirements</strong>
              </span>
              <span className="text-slate-300">•</span>
              <span className={attentionCount > 0 ? 'text-amber-700 font-semibold' : 'text-emerald-700 font-medium'}>
                {attentionCount > 0
                  ? `${attentionCount} finding${attentionCount > 1 ? 's require' : ' requires'} attention`
                  : 'All mandatory declarations satisfied'}
              </span>
            </div>
          </div>

          {/* Quick Score Capsule */}
          <div className="flex items-center gap-4 bg-slate-50 border border-slate-200 rounded-xl p-4 self-start lg:self-center">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Compliance Score
              </div>
              <div className="flex items-baseline gap-1 mt-0.5">
                <span
                  className={`text-3xl font-extrabold tracking-tight ${
                    complianceScore >= 80
                      ? 'text-emerald-700'
                      : complianceScore >= 60
                      ? 'text-amber-600'
                      : 'text-red-600'
                  }`}
                >
                  {complianceScore}
                </span>
                <span className="text-sm font-semibold text-slate-400">/ 100</span>
              </div>
            </div>

            <div className="h-10 w-[1px] bg-slate-200" />

            <div className="text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-slate-600 font-medium">Pass: {passCount}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-slate-600 font-medium">Fail: {failCount}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="text-slate-600 font-medium">Review: {reviewCount}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ================================================== */}
      {/* 4. MAIN EVIDENCE-FIRST TWO-COLUMN WORKSPACE */}
      {/* ================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* -------------------------------------------------- */}
        {/* LEFT COLUMN: PACKAGE EVIDENCE VIEWER (5 cols) */}
        {/* -------------------------------------------------- */}
        <div className="lg:col-span-5 space-y-4">
          <Card
            title="Package Evidence"
            subtitle="Visual record with deterministic evidence bounding regions"
            padding="none"
          >
            {/* Header tags */}
            <div className="px-4 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-[11px] font-mono">
              <span className="text-blue-400 font-semibold flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5" />
                PACKAGE EVIDENCE
              </span>
              <div className="flex items-center gap-2 text-slate-400">
                <span>Captured image</span>
                <span>•</span>
                <span>Evidence frame</span>
              </div>
            </div>

            {/* Interactive Image Frame */}
            <div className="relative bg-slate-950 p-4 flex items-center justify-center overflow-hidden min-h-[460px]">
              {/* Image Container with relative positioning for bounding boxes */}
              <div className="relative w-full max-w-[420px] rounded border border-slate-800 overflow-hidden shadow-2xl">
                <img
                  src={imageSrc}
                  alt="Packaged commodity evidence preview"
                  className="w-full h-auto object-contain select-none block"
                />

                {/* Overlaid Visual Evidence Markers */}
                {findings.map((f) => {
                  const isActive = f.id === activeFindingId
                  const coords = f.regionCoords

                  // Bounding box colors based on 3-State Model:
                  // PASS -> green, FAIL -> red, REVIEW -> amber
                  const boxStyles = {
                    PASS: isActive
                      ? 'border-emerald-500 bg-emerald-500/25 ring-2 ring-emerald-400 shadow-md'
                      : 'border-emerald-500/80 bg-emerald-500/15 hover:bg-emerald-500/25',
                    FAIL: isActive
                      ? 'border-red-500 bg-red-500/25 ring-2 ring-red-400 shadow-md'
                      : 'border-red-500/80 bg-red-500/15 hover:bg-red-500/25',
                    REVIEW: isActive
                      ? 'border-amber-500 bg-amber-500/25 ring-2 ring-amber-400 shadow-md'
                      : 'border-amber-500/80 bg-amber-500/15 hover:bg-amber-500/25',
                  }

                  const tagStyles = {
                    PASS: 'bg-emerald-600 text-white',
                    FAIL: 'bg-red-600 text-white',
                    REVIEW: 'bg-amber-600 text-white',
                  }

                  return (
                    <div
                      key={f.id}
                      onClick={() => setActiveFindingId(f.id)}
                      title={`Click to review ${f.field}`}
                      className={`absolute cursor-pointer rounded transition-all duration-150 border-2 ${
                        boxStyles[f.status]
                      }`}
                      style={{
                        top: `${coords.top}%`,
                        left: `${coords.left}%`,
                        width: `${coords.width}%`,
                        height: `${coords.height}%`,
                      }}
                    >
                      {/* Attached label pill */}
                      <span
                        className={`absolute -top-3 left-1.5 text-[9px] font-mono font-bold px-1.5 py-0.2 rounded tracking-tight shadow-sm flex items-center gap-1 ${
                          tagStyles[f.status]
                        }`}
                      >
                        {coords.label}
                        {isActive && <span className="w-1 h-1 rounded-full bg-white animate-ping" />}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Evidence Legend */}
            <div className="p-4 bg-slate-50 border-t border-slate-200">
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Evidence Legend
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="flex items-center gap-2 p-1.5 rounded bg-white border border-slate-200">
                  <span className="w-3 h-3 rounded border-2 border-emerald-500 bg-emerald-100 flex-shrink-0" />
                  <span className="font-medium text-slate-700 truncate">Verified</span>
                </div>
                <div className="flex items-center gap-2 p-1.5 rounded bg-white border border-slate-200">
                  <span className="w-3 h-3 rounded border-2 border-red-500 bg-red-100 flex-shrink-0" />
                  <span className="font-medium text-slate-700 truncate">Violation</span>
                </div>
                <div className="flex items-center gap-2 p-1.5 rounded bg-white border border-slate-200">
                  <span className="w-3 h-3 rounded border-2 border-amber-500 bg-amber-100 flex-shrink-0" />
                  <span className="font-medium text-slate-700 truncate">Review</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 mt-2">
                Select any finding or box to focus evidence details.
              </p>
            </div>
          </Card>

          {/* 9. ASSESSMENT SUMMARY CARD */}
          <Card
            title="Assessment Summary"
            subtitle="Deterministic verification breakdown"
            padding="sm"
          >
            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <span className="text-slate-500 font-medium">Evaluated Checks:</span>
                <span className="font-semibold text-slate-800">{totalEvaluated} evaluated</span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2.5 rounded-lg bg-emerald-50/70 border border-emerald-200">
                  <div className="text-[11px] font-bold text-emerald-800">PASS</div>
                  <div className="text-lg font-extrabold text-emerald-700">{passCount}</div>
                  <div className="text-[10px] text-emerald-600 mt-0.5">Satisfied</div>
                </div>
                <div className="p-2.5 rounded-lg bg-red-50/70 border border-red-200">
                  <div className="text-[11px] font-bold text-red-800">FAIL</div>
                  <div className="text-lg font-extrabold text-red-700">{failCount}</div>
                  <div className="text-[10px] text-red-600 mt-0.5">Violation</div>
                </div>
                <div className="p-2.5 rounded-lg bg-amber-50/70 border border-amber-200">
                  <div className="text-[11px] font-bold text-amber-800">REVIEW</div>
                  <div className="text-lg font-extrabold text-amber-700">{reviewCount}</div>
                  <div className="text-[10px] text-amber-600 mt-0.5">Uncertain</div>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-slate-600 flex items-start gap-2 text-[11px] leading-relaxed">
                <Info className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                <span>
                  Score summarizes evaluated requirements. REVIEW findings are not treated as confirmed violations.
                </span>
              </div>
            </div>
          </Card>
        </div>

        {/* -------------------------------------------------- */}
        {/* RIGHT COLUMN: COMPLIANCE FINDINGS (7 cols) */}
        {/* -------------------------------------------------- */}
        <div className="lg:col-span-7 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <Layers className="w-5 h-5 text-brand-blue" />
                Compliance Findings
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic rule checks mapped to detected evidence declarations
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-slate-100 px-2 py-1 rounded">
              {findings.length} Mandatory Declarations
            </span>
          </div>

          {/* 7. FINDING CARDS LIST */}
          <div className="space-y-4">
            {findings.map((finding) => {
              const isSelected = finding.id === activeFindingId

              return (
                <div
                  key={finding.id}
                  onClick={() => setActiveFindingId(finding.id)}
                  className={`rounded-xl border transition-all duration-150 p-5 cursor-pointer bg-white ${
                    isSelected
                      ? 'border-brand-blue ring-1 ring-blue-300 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 hover:shadow-xs'
                  }`}
                >
                  {/* Finding Header */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
                    <div className="flex items-center gap-2.5">
                      {/* Status indicator */}
                      <StatusBadge status={finding.status} />
                      <h3 className="text-base font-bold text-slate-900">
                        {finding.field}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-slate-400 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                        {finding.evidenceRegion}
                      </span>
                      {isSelected && (
                        <span className="text-[10px] font-semibold text-brand-blue bg-blue-50 px-2 py-0.5 rounded">
                          Active
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Finding Body Details */}
                  <div className="mt-3.5 space-y-3 text-xs">
                    {/* Detected value */}
                    <div>
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                        Detected:
                      </span>
                      <div className="mt-1 p-2.5 bg-slate-50 rounded-lg border border-slate-200 font-mono text-slate-800 text-xs">
                        {finding.detectedValue}
                      </div>
                    </div>

                    {/* 8. Confidence Bar */}
                    <div className="flex items-center justify-between p-2 rounded bg-slate-50 border border-slate-100">
                      <span className="text-slate-600 font-medium">
                        Evidence confidence:
                      </span>
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-slate-200 h-1.5 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              finding.confidence >= 90
                                ? 'bg-emerald-600'
                                : finding.confidence >= 75
                                ? 'bg-blue-600'
                                : 'bg-amber-500'
                            }`}
                            style={{ width: `${finding.confidence}%` }}
                          />
                        </div>
                        <span className="font-mono font-bold text-slate-800">
                          {finding.confidence}%
                        </span>
                      </div>
                    </div>

                    {/* Requirement & Rule */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600">
                      <div className="p-2 bg-slate-50/60 rounded border border-slate-100">
                        <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                          Requirement
                        </span>
                        <span className="font-medium text-slate-700 leading-snug block mt-0.5">
                          {finding.requirement}
                        </span>
                      </div>

                      <div className="p-2 bg-slate-50/60 rounded border border-slate-100">
                        <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                          Rule Logic
                        </span>
                        <span className="font-medium text-slate-700 leading-snug block mt-0.5">
                          {finding.rule}
                        </span>
                      </div>
                    </div>

                    {/* Why / Explanation */}
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
                      <span className="text-[10px] font-bold uppercase text-slate-500 block mb-0.5">
                        Why:
                      </span>
                      <p className="text-slate-700 leading-relaxed">
                        {finding.explanation}
                      </p>
                    </div>

                    {/* 10. REVIEW / HUMAN-IN-THE-LOOP ACTION */}
                    {finding.status === 'REVIEW' && (
                      <div className="pt-2 flex items-center justify-between bg-amber-50 border border-amber-200 rounded-lg p-3">
                        <div className="flex items-center gap-2">
                          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
                          <span className="font-semibold text-amber-900 text-xs">
                            Needs human verification
                          </span>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation()
                            setReviewModalFinding(finding)
                          }}
                          className="bg-white hover:bg-amber-100 text-amber-900 border-amber-300 font-semibold"
                        >
                          Verify Evidence
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* ================================================== */}
          {/* 11. ACTION BAR */}
          {/* ================================================== */}
          <div className="pt-6 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <Button
                type="button"
                variant="secondary"
                onClick={() => navigate('/dashboard')}
                icon={<LayoutDashboard className="w-4 h-4" />}
                className="w-full sm:w-auto"
              >
                Back to Dashboard
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/new-inspection')}
                icon={<RotateCcw className="w-4 h-4" />}
                className="w-full sm:w-auto"
              >
                New Inspection
              </Button>
            </div>

            <Button
              type="button"
              onClick={() => navigate(`/reports/${id || 'demo-1'}`)}
              icon={<ArrowRight className="w-4 h-4" />}
              className="w-full sm:w-auto font-semibold px-6 shadow-sm"
            >
              Generate Inspection Report
            </Button>
          </div>
        </div>
      </div>

      {/* ================================================== */}
      {/* 10. HUMAN-IN-THE-LOOP VERIFICATION MODAL */}
      {/* ================================================== */}
      {reviewModalFinding && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="review-modal-title"
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl max-w-lg w-full overflow-hidden animate-fadeIn">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-amber-600" />
                <h3
                  id="review-modal-title"
                  className="text-base font-bold text-slate-900"
                >
                  Human verification required
                </h3>
              </div>
              <span className="text-xs font-mono font-semibold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                REVIEW
              </span>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4 text-xs">
              <p className="text-slate-600 text-sm leading-relaxed">
                Confirm whether the visible manufacturer/packer declaration is complete and readable.
              </p>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Declaration:</span>
                  <span className="font-bold text-slate-900">
                    {reviewModalFinding.field}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Detected Text:</span>
                  <span className="font-mono text-slate-800 font-semibold">
                    {reviewModalFinding.detectedValue}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Evidence Confidence:</span>
                  <span className="font-mono text-amber-700 font-bold">
                    {reviewModalFinding.confidence}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Location:</span>
                  <span className="font-mono text-slate-600">
                    {reviewModalFinding.evidenceRegion}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-blue-50/60 border border-blue-100 text-slate-600 text-[11px] leading-relaxed">
                <strong>Inspector Guidance:</strong> In accordance with Legal Metrology requirements,
                both manufacturer name and complete address must be verifiable on the packaged commodity label.
              </div>
            </div>

            {/* Modal Actions */}
            <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setReviewModalFinding(null)}
              >
                Cancel
              </Button>

              <Button
                type="button"
                variant="danger"
                size="sm"
                icon={<XCircle className="w-3.5 h-3.5" />}
                onClick={() => handleMarkViolation(reviewModalFinding.id)}
              >
                Mark Violation
              </Button>

              <Button
                type="button"
                size="sm"
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={() => handleMarkVerified(reviewModalFinding.id)}
              >
                Mark Verified
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default InspectionDetailsPage
