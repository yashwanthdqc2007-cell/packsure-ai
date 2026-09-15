import React, { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Calendar,
  Camera,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Compass,
  Crosshair,
  Edit3,
  ExternalLink,
  Eye,
  FileCheck,
  FileText,
  Image as ImageIcon,
  Layers,
  Loader2,
  Package as PackageIcon,
  QrCode,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Tag,
  Undo2,
  UserCheck,
  X,
  XCircle,
} from 'lucide-react'
import Card from '../../components/common/Card'
import StatusBadge from '../../components/common/StatusBadge'
import Button from '../../components/common/Button'
import { getScan, reviewScan } from '../../services/scanService'
import { resolveArtifactUrl, type ApiErrorDetail } from '../../services/api'
import type {
  CorrectedDeclaration,
  DeclarationStatus,
  ExtractedDeclaration,
  ScanResponse,
  ScanReviewRequest,
} from '../../types'

const MAX_POLL_ATTEMPTS = 40 // 40 attempts * 1.5s = 60s max timeout

export const InspectionDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const isMountedRef = useRef<boolean>(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollAttemptRef = useRef<number>(0)

  // Scan Data & Navigation States
  const [scan, setScan] = useState<ScanResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'declarations' | 'violations' | 'evidence' | 'review'>('overview')
  const [selectedFieldName, setSelectedFieldName] = useState<string | null>(null)
  const [selectedViewIndex, setSelectedViewIndex] = useState<number>(0)
  const [imageError, setImageError] = useState<boolean>(false)

  // Top Workstation UI states (Phase 5B)
  const [showGuidanceDetails, setShowGuidanceDetails] = useState<boolean>(false)
  const [showUnverifiedDetails, setShowUnverifiedDetails] = useState<boolean>(true)

  // Human Review Workflow States
  const [reviewerNotes, setReviewerNotes] = useState<string>('')
  const [corrections, setCorrections] = useState<Record<string, CorrectedDeclaration>>({})
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editRawValue, setEditRawValue] = useState<string>('')
  const [editNormalizedValue, setEditNormalizedValue] = useState<string>('')
  const [editStatus, setEditStatus] = useState<DeclarationStatus>('detected')
  const [isSubmittingReview, setIsSubmittingReview] = useState<boolean>(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null)

  const fetchScanDetails = async (scanId: string, isPollingAttempt: boolean = false) => {
    try {
      if (!isPollingAttempt) {
        setIsLoading(true)
      }
      setErrorMessage(null)
      const data = await getScan(scanId)

      if (!isMountedRef.current) return

      setScan(data)
      setIsLoading(false)

      // If scan is still pending or processing, poll periodically until finalized
      if (data.status === 'pending' || data.status === 'processing') {
        if (pollAttemptRef.current >= MAX_POLL_ATTEMPTS) {
          setErrorMessage('Inspection processing timed out after 60 seconds. Please refresh or retry.')
          return
        }

        pollAttemptRef.current += 1
        pollTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            fetchScanDetails(scanId, true)
          }
        }, 1500)
      }
    } catch (err) {
      if (!isMountedRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsLoading(false)
      setErrorMessage(apiErr.message || `Failed to fetch inspection record #${scanId}`)
    }
  }

  useEffect(() => {
    isMountedRef.current = true
    pollAttemptRef.current = 0

    if (id) {
      fetchScanDetails(id)
    } else {
      setIsLoading(false)
      setErrorMessage('No scan ID provided in route.')
    }

    return () => {
      isMountedRef.current = false
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
    }
  }, [id])

  // Open correction editor for a declaration
  const startEditingDeclaration = (decl: ExtractedDeclaration) => {
    const existingCorrection = corrections[decl.field_name]
    setEditingField(decl.field_name)
    setEditRawValue(existingCorrection?.raw_value ?? decl.raw_value ?? '')
    setEditNormalizedValue(existingCorrection?.normalized_value ?? decl.normalized_value ?? '')
    setEditStatus(existingCorrection?.status ?? decl.status ?? 'detected')
    setReviewError(null)
  }

  // Save manual correction for a declaration field
  const saveDeclarationCorrection = (fieldName: string) => {
    setCorrections((prev) => ({
      ...prev,
      [fieldName]: {
        field_name: fieldName,
        raw_value: editRawValue.trim() || undefined,
        normalized_value: editNormalizedValue.trim() || undefined,
        status: editStatus,
      },
    }))
    setEditingField(null)
  }

  // Remove a manual correction override
  const removeCorrection = (fieldName: string) => {
    setCorrections((prev) => {
      const copy = { ...prev }
      delete copy[fieldName]
      return copy
    })
    if (editingField === fieldName) {
      setEditingField(null)
    }
  }

  // Submit human review resolution (PATCH /api/v1/scans/{id}/review)
  const handleSubmitReview = async (targetVerdict: 'PASS' | 'FAIL') => {
    if (!scan) return

    if (!reviewerNotes.trim()) {
      setReviewError('Please provide inspector reviewer notes before finalizing the verdict.')
      return
    }

    try {
      setIsSubmittingReview(true)
      setReviewError(null)
      setReviewSuccessMsg(null)

      const correctedList = Object.values(corrections)
      const payload: ScanReviewRequest = {
        verdict: targetVerdict,
        reviewer_notes: reviewerNotes.trim(),
        corrected_declarations: correctedList.length > 0 ? correctedList : undefined,
      }

      const updatedScan = await reviewScan(scan.scan_id, payload)
      if (!isMountedRef.current) return

      setScan(updatedScan)
      setCorrections({})
      setEditingField(null)
      setIsSubmittingReview(false)
      setReviewSuccessMsg(
        `Inspector review submitted successfully! Final verdict recorded as ${targetVerdict}.`
      )
      setActiveTab('overview')
    } catch (err) {
      if (!isMountedRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsSubmittingReview(false)
      setReviewError(apiErr.message || 'Failed to submit inspector review resolution.')
    }
  }

  // 1. Initial Loading Skeleton State
  if (isLoading && !scan) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-3">
          <Link to="/history">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
              Back
            </Button>
          </Link>
          <div className="h-6 w-48 bg-slate-200 animate-pulse rounded" />
        </div>
        <Card>
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-blue mb-3" />
            <h3 className="text-sm font-semibold text-slate-700">Loading Inspection Record...</h3>
            <p className="text-xs text-slate-400 mt-1">Retrieving compliance audit records for ID: {id}</p>
          </div>
        </Card>
      </div>
    )
  }

  // 2. Fetch / Network Error State
  if (errorMessage && !scan) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-3">
          <Link to="/history">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
              Back to History
            </Button>
          </Link>
        </div>
        <Card title="Inspection Lookup Failed">
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mb-3">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-800">Could Not Load Inspection</h3>
            <p className="text-xs text-red-600 max-w-md mt-1 mb-4">{errorMessage}</p>
            <div className="flex gap-3">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  pollAttemptRef.current = 0
                  if (id) fetchScanDetails(id)
                }}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry
              </Button>
              <Link to="/new-inspection">
                <Button size="sm">Start New Scan</Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  // 3. Scan Processing State
  const isPending = scan?.status === 'pending' || scan?.status === 'processing'
  if (isPending) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/history">
              <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Processing Package Inspection
              </h1>
              <p className="text-xs text-slate-500 font-mono">Scan ID: {scan?.scan_id}</p>
            </div>
          </div>
          <StatusBadge status={scan?.status || 'PROCESSING'} />
        </div>

        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-center max-w-lg mx-auto">
            <div className="w-14 h-14 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mb-4">
              <Loader2 className="w-7 h-7 animate-spin" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">
              Audit Pipeline Running
            </h3>
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              PackSure AI is actively analyzing your package label across OpenCV image quality checks, Tesseract OCR token extraction, Gemini 3.6 Flash structured parsing, and Legal Metrology 2011 rule verification.
            </p>

            <div className="w-full bg-slate-100 rounded-full h-2 mt-6 mb-3 overflow-hidden">
              <div className="bg-brand-blue h-full w-full animate-pulse" />
            </div>

            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Checking server status every 1.5s (Attempt {pollAttemptRef.current}/{MAX_POLL_ATTEMPTS})</span>
            </div>

            <div className="mt-6 flex gap-3">
              <Link to="/new-inspection">
                <Button size="sm" variant="outline">
                  Cancel & New Scan
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  // 4. Scan Failed State
  if (scan?.status === 'failed') {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/history">
              <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Inspection Failed
              </h1>
              <p className="text-xs text-slate-500 font-mono">Scan ID: {scan?.scan_id}</p>
            </div>
          </div>
          <StatusBadge status="FAILED" />
        </div>

        <Card title="Inspection Processing Failure">
          <div className="flex flex-col items-center justify-center py-12 text-center max-w-md mx-auto">
            <div className="w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mb-3">
              <XCircle className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-800">Pipeline Failed to Complete Scan</h3>
            <p className="text-xs text-slate-500 mt-2 mb-4 leading-relaxed">
              The inspection pipeline encountered an unrecoverable failure while analyzing the uploaded image. This can happen if the image is corrupted, lacks packaging text, or the OCR engine failed.
            </p>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs w-full text-left font-mono space-y-1 mb-6 text-slate-600">
              <div><span className="font-semibold text-slate-800">Scan ID:</span> {scan.scan_id}</div>
              <div><span className="font-semibold text-slate-800">Category:</span> {scan.product_category || 'General'}</div>
              <div><span className="font-semibold text-slate-800">Submitted:</span> {new Date(scan.created_at).toLocaleString()}</div>
            </div>
            <div className="flex gap-3">
              <Link to="/new-inspection">
                <Button size="sm">Start New Inspection</Button>
              </Link>
              <Link to="/history">
                <Button size="sm" variant="outline">View Scan History</Button>
              </Link>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  // 5. Complete State Data Normalization
  const verdict = scan?.verdict || 'NEEDS_REVIEW'
  const isNeedsReview = verdict === 'NEEDS_REVIEW' && scan?.status === 'complete'
  const score = scan?.compliance_score !== null && scan?.compliance_score !== undefined ? scan.compliance_score : null
  const declarations = scan?.declarations || []
  const violations = scan?.violations || []

  // Cleanly distinguish statutory/legal violations from image capture / quality inspection issues
  const statutoryViolations = violations.filter(
    (v) => v.rule_code !== 'QUALITY-REJECT' && !v.rule_code.endsWith('-FAILURE')
  )
  const qualityIssues = violations.filter(
    (v) => v.rule_code === 'QUALITY-REJECT' || v.rule_code.endsWith('-FAILURE')
  )

  // Count declaration statuses
  const detectedCount = declarations.filter((d) => d.status === 'detected').length
  const uncertainCount = declarations.filter((d) => d.status === 'uncertain').length
  const missingCount = declarations.filter((d) => d.status === 'missing').length

  // Count statutory violation severities
  const criticalViolations = statutoryViolations.filter((v) => v.severity === 'critical')
  const majorViolations = statutoryViolations.filter((v) => v.severity === 'major')
  const minorViolations = statutoryViolations.filter((v) => v.severity === 'minor')

  // Resolve visual evidence image URLs (support multi-view)
  const evidenceImageUrls: string[] =
    scan?.evidence_image_urls && scan.evidence_image_urls.length > 0
      ? scan.evidence_image_urls
      : scan?.evidence_image_url
      ? [scan.evidence_image_url]
      : scan?.image_urls && scan.image_urls.length > 0
      ? scan.image_urls
      : scan?.image_url
      ? [scan.image_url]
      : []

  const activeEvidenceRaw = evidenceImageUrls[selectedViewIndex] || scan?.evidence_image_url || scan?.image_url
  const evidenceUrl = resolveArtifactUrl(activeEvidenceRaw)

  // Extract human-friendly product title
  const genericNameDecl = declarations.find((d) => ['generic_name', 'product_name'].includes(d.field_name))
  const productName =
    genericNameDecl?.normalized_value ||
    genericNameDecl?.raw_value ||
    scan?.product_category ||
    'Packaged Commodity'

  const correctedFieldsCount = Object.keys(corrections).length

  // Deep-linking navigation helper to scroll to specific cards/sections
  const navigateToSection = (
    tab: 'overview' | 'declarations' | 'violations' | 'evidence' | 'review',
    elementId?: string,
    fieldName?: string
  ) => {
    setActiveTab(tab)
    if (fieldName) {
      setSelectedFieldName(fieldName)
    }
    if (elementId) {
      setTimeout(() => {
        const el = document.getElementById(elementId)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 120)
    }
  }

  // Diagnostic reason string for Copilot "Why?" callout
  const copilotWhyReason = (() => {
    if (scan?.inspection_state?.quality_blockers && scan.inspection_state.quality_blockers.length > 0) {
      return `Image quality defect (${scan.inspection_state.quality_blockers[0]}) degrades reliable optical text extraction.`
    }
    if (scan?.inspection_state?.evidence_conflicts && scan.inspection_state.evidence_conflicts.length > 0) {
      return `Contradictory values detected across package views for ${scan.inspection_state.evidence_conflicts.join(', ')}.`
    }
    if (scan?.guidance?.needs_recapture && !scan?.is_complete_scan) {
      return `Single view captured (${scan?.inspection_state?.views_captured || 1} view). Additional panels needed for full statutory coverage.`
    }
    if (scan?.composition && (scan.composition.package_type === 'UNCERTAIN' || scan.composition.status === 'uncertain')) {
      return 'Package indicates multiple constituent commodities or bundled items; breakdown requires confirmation.'
    }
    if (scan?.qr_evidence && scan.qr_evidence.applicable_product === 'APPLICABLE' && scan.qr_evidence.status === 'uncertain') {
      return 'Packaged electronic product with unverified QR declaration or missing consumer scan instruction.'
    }
    if (uncertainCount > 0) {
      return `${uncertainCount} mandatory declaration(s) have uncertain OCR confidence requiring officer review.`
    }
    if (scan?.inspection_state?.status === 'READY_TO_FINALIZE') {
      return 'All mandatory visual declarations verified without blockers. Ready for officer sign-off.'
    }
    if (scan?.inspection_state?.status === 'READY_TO_REVIEW') {
      return 'Visual evidence captured and verified. Pending human inspector sign-off.'
    }
    return scan?.inspection_state?.summary || 'Standard visual inspection workflow active.'
  })()

  // Handle Copilot primary action button click
  const handleCopilotPrimaryAction = () => {
    const nextAction = scan?.next_best_action
    if (!nextAction) {
      navigateToSection('overview')
      return
    }

    switch (nextAction.action_code) {
      case 'review_conflicting_evidence':
        navigateToSection('review', 'inspector-review-workstation')
        break
      case 'review_package_composition':
        navigateToSection('overview', 'package-composition-card')
        break
      case 'review_qr_evidence':
        navigateToSection('overview', 'qr-compliance-card')
        break
      case 'review_findings':
        navigateToSection('review', 'inspector-review-workstation')
        break
      case 'finalize_inspection':
        if (isNeedsReview) {
          navigateToSection('review', 'inspector-review-workstation')
        } else {
          navigateToSection('overview', 'compliance-verdict-summary-card')
        }
        break
      default:
        if (nextAction.target_tab) {
          navigateToSection(nextAction.target_tab as any)
        } else {
          navigateToSection('overview')
        }
        break
    }
  }

  // Construct list of unverified workflow items
  const unverifiedItems = (() => {
    const items: Array<{
      icon: React.ReactNode
      title: string
      badge: string
      reason: string
      type: 'actionable' | 'not_evaluated'
      actionButton?: React.ReactNode
    }> = []

    // 1. Cross-View Evidence Conflicts
    if (scan?.inspection_state?.evidence_conflicts && scan.inspection_state.evidence_conflicts.length > 0) {
      scan.inspection_state.evidence_conflicts.forEach((field) => {
        items.push({
          icon: <AlertTriangle className="w-4 h-4 text-amber-600" />,
          title: `Conflicting Evidence: ${field}`,
          badge: 'Needs Review',
          reason: `Contradictory values detected across package views for ${field}. Manual review required to confirm printed text.`,
          type: 'actionable',
          actionButton: (
            <Button
              size="sm"
              variant="outline"
              onClick={() => navigateToSection('review', 'inspector-review-workstation')}
            >
              Review
            </Button>
          ),
        })
      })
    }

    // 2. Image Quality Blockers
    if (scan?.inspection_state?.quality_blockers && scan.inspection_state.quality_blockers.length > 0) {
      scan.inspection_state.quality_blockers.forEach((blocker) => {
        items.push({
          icon: <Camera className="w-4 h-4 text-red-600" />,
          title: 'Image Quality Blocker',
          badge: 'Incomplete',
          reason: blocker,
          type: 'actionable',
          actionButton: (
            <Link to={`/new-inspection?category=${encodeURIComponent(scan?.product_category || '')}`}>
              <Button size="sm" variant="outline" icon={<Camera className="w-3.5 h-3.5" />}>
                Retake
              </Button>
            </Link>
          ),
        })
      })
    }

    // 3. Uncertain Declarations
    const conflictFieldSet = new Set(scan?.inspection_state?.evidence_conflicts || [])
    declarations
      .filter((d) => d.status === 'uncertain' && !conflictFieldSet.has(d.field_name))
      .forEach((d) => {
        items.push({
          icon: <AlertCircle className="w-4 h-4 text-amber-600" />,
          title: `Uncertain Declaration: ${d.field_name}`,
          badge: 'Needs Review',
          reason: `Optical character recognition or model parsing confidence is below baseline threshold (${d.raw_value ? `Raw: "${d.raw_value}"` : 'Unreadable'}).`,
          type: 'actionable',
          actionButton: (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                isNeedsReview
                  ? navigateToSection('review', 'inspector-review-workstation')
                  : navigateToSection('declarations', 'declaration-audit-table', d.field_name)
              }
            >
              Review
            </Button>
          ),
        })
      })

    // 4. Package Composition
    if (scan?.composition && (scan.composition.package_type === 'UNCERTAIN' || scan.composition.status === 'uncertain')) {
      items.push({
        icon: <PackageIcon className="w-4 h-4 text-amber-600" />,
        title: 'Package Composition Classification',
        badge: 'Needs Review',
        reason: 'Package text indicates multiple commodities or bundled items; constituent items requires officer confirmation.',
        type: 'actionable',
        actionButton: (
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigateToSection('overview', 'package-composition-card')}
          >
            Review
          </Button>
        ),
      })
    }

    // 5. QR Code Evidence
    if (
      scan?.qr_evidence &&
      scan.qr_evidence.applicable_product === 'APPLICABLE' &&
      (scan.qr_evidence.status === 'uncertain' || !scan.qr_evidence.instruction_detected)
    ) {
      items.push({
        icon: <QrCode className="w-4 h-4 text-amber-600" />,
        title: 'QR & Electronic Declarations',
        badge: 'Needs Review',
        reason: 'Packaged electronic commodity requires verification of consumer scan instruction and decoded payload under Rule 6 / G.S.R. 456(E).',
        type: 'actionable',
        actionButton: (
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigateToSection('overview', 'qr-compliance-card')}
          >
            Review
          </Button>
        ),
      })
    }

    // 6. Physical Metrology Check (Always present as Not Evaluated)
    items.push({
      icon: <Scale className="w-4 h-4 text-slate-400" />,
      title: 'Physical Metrology (Net Quantity & Font Height mm)',
      badge: 'Not Evaluated',
      reason: 'Not evaluated — requires physical weighing balance and gauge measurement (LMR Rules 14–18, Rule 8).',
      type: 'not_evaluated',
    })

    // 7. External Regulatory Check (Always present as Not Evaluated)
    items.push({
      icon: <ShieldCheck className="w-4 h-4 text-slate-400" />,
      title: 'External Regulatory Verification (Rule 27 / FSSAI / EPR)',
      badge: 'Not Evaluated',
      reason: 'Not evaluated — requires verification against DCA Director registration or external regulatory databases.',
      type: 'not_evaluated',
    })

    return items
  })()

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* 1. Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link to="/history">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
              Back
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {productName}
              </h1>
              <StatusBadge status={verdict} />
              {evidenceImageUrls.length > 1 && (
                <span className="text-xs font-semibold text-brand-blue bg-blue-50 px-2 py-0.5 rounded border border-blue-200 flex items-center gap-1">
                  <Layers className="w-3 h-3 text-brand-blue" />
                  {evidenceImageUrls.length} Views Captured
                </span>
              )}
              {scan?.is_complete_scan && (
                <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                  <Check className="w-3 h-3 text-emerald-600" />
                  Complete Scan
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
              <span>Scan ID: <code className="font-mono text-slate-700">{scan?.scan_id}</code></span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Tag className="w-3 h-3 text-slate-400" />
                {scan?.product_category || 'General Package'}
              </span>
              {scan?.completed_at && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-400" />
                    {new Date(scan.completed_at).toLocaleString()}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isNeedsReview && activeTab !== 'review' && (
            <Button
              onClick={() => setActiveTab('review')}
              icon={<UserCheck className="w-4 h-4" />}
            >
              Start Inspector Review
            </Button>
          )}
          <Link to="/new-inspection">
            <Button variant="outline" size="sm">New Inspection</Button>
          </Link>
        </div>
      </div>

      {/* 2. Success Alert after Review */}
      {reviewSuccessMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-lg flex items-center justify-between text-xs text-emerald-900 animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-semibold">{reviewSuccessMsg}</span>
          </div>
          <button onClick={() => setReviewSuccessMsg(null)} className="text-emerald-700 hover:text-emerald-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 3. Prominent NEEDS_REVIEW Notice Banner */}
      {isNeedsReview && (
        <div className="p-4 bg-amber-50 border border-amber-300 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-900 shadow-2xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="font-bold text-sm text-amber-950">
                Human Inspector Verification Required
              </div>
              <p className="leading-relaxed text-amber-800">
                One or more mandatory declarations returned an <span className="font-semibold underline">uncertain</span> status or low OCR confidence. A certified Legal Metrology inspector must verify the packaging label and submit a final resolution.
              </p>
            </div>
          </div>
          {activeTab !== 'review' && (
            <Button
              size="sm"
              onClick={() => setActiveTab('review')}
              className="self-start sm:self-auto flex-shrink-0"
              icon={<UserCheck className="w-4 h-4" />}
            >
              Review Scan
            </Button>
          )}
        </div>
      )}

      {/* Phase 5B: Top Workstation — Inspection Status + Inspection Copilot */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card A: Inspection Status */}
        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-brand-blue" />
              Inspection Status
            </span>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border ${
                scan?.inspection_state?.status === 'READY_TO_FINALIZE'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : scan?.inspection_state?.status === 'READY_TO_REVIEW'
                  ? 'bg-blue-50 text-blue-800 border-blue-200'
                  : scan?.inspection_state?.status === 'NEEDS_REVIEW'
                  ? 'bg-amber-50 text-amber-800 border-amber-200'
                  : 'bg-slate-100 text-slate-700 border-slate-200'
              }`}
            >
              {scan?.inspection_state?.status?.replace('_', ' ') || 'EVALUATING'}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-600">Visual label checks</span>
              <span className="font-semibold flex items-center gap-1 text-slate-800">
                {scan?.inspection_state?.visual_checks_complete ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Complete</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span className="text-amber-700">Incomplete</span>
                  </>
                )}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-600">Package view coverage</span>
              <span className="font-semibold text-slate-800 flex items-center gap-1">
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span>
                  {scan?.inspection_state?.views_captured || (scan?.image_urls ? scan.image_urls.length : 1)} view
                  {(scan?.inspection_state?.views_captured || (scan?.image_urls ? scan.image_urls.length : 1)) > 1 ? 's' : ''}
                  {scan?.is_complete_scan ? ' (complete)' : ''}
                </span>
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-slate-50">
              <span className="text-slate-600">Evidence review</span>
              <span className="font-semibold flex items-center gap-1">
                {scan?.reviewer_notes ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Reviewed</span>
                  </>
                ) : scan?.inspection_state?.unresolved_count && scan.inspection_state.unresolved_count > 0 ? (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span className="text-amber-700">{scan.inspection_state.unresolved_count} pending</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Verified</span>
                  </>
                )}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-slate-50 text-slate-500">
              <span>Physical verification</span>
              <span className="font-medium flex items-center gap-1">
                <span className="text-slate-400">○</span>
                <span>Not evaluated</span>
              </span>
            </div>

            <div className="flex items-center justify-between py-1 text-slate-500">
              <span>External verification</span>
              <span className="font-medium flex items-center gap-1">
                <span className="text-slate-400">○</span>
                <span>Not evaluated</span>
              </span>
            </div>
          </div>
        </div>

        {/* Card B: Inspection Copilot */}
        <div className="p-4 bg-gradient-to-br from-blue-50/90 to-indigo-50/70 rounded-xl border border-blue-200/80 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-900 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-brand-blue" />
                Inspection Copilot
              </span>
              <span className="text-[10px] font-semibold text-blue-700 bg-white/80 px-2 py-0.5 rounded border border-blue-200">
                Next Best Action
              </span>
            </div>

            {/* Diagnostic Why? Callout */}
            <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100 text-xs space-y-1">
              <span className="text-[10px] font-bold text-blue-900 uppercase tracking-wider block">
                Why?
              </span>
              <p className="text-slate-700 leading-relaxed font-medium text-[11px]">
                {copilotWhyReason}
              </p>
            </div>

            <div className="space-y-0.5 pt-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Recommended Action:
              </span>
              <h4 className="text-sm font-bold text-slate-900">
                {scan?.next_best_action?.title || 'Review Inspection Results'}
              </h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                {scan?.next_best_action?.description ||
                  'All visible mandatory label declarations have been processed. Review evidence details or submit inspector notes.'}
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-blue-200/60 flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              {/* Expand Guidance Toggle */}
              {scan?.guidance &&
              (scan.guidance.needs_recapture ||
                scan.guidance.issues.length > 0 ||
                scan.guidance.actionable_steps.length > 0) ? (
                <button
                  type="button"
                  onClick={() => setShowGuidanceDetails(!showGuidanceDetails)}
                  className="text-xs font-semibold text-blue-700 hover:text-blue-900 inline-flex items-center gap-1"
                >
                  {showGuidanceDetails ? (
                    <>
                      <ChevronUp className="w-3.5 h-3.5" />
                      <span>Hide Guidance</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3.5 h-3.5" />
                      <span>View Guidance Steps</span>
                    </>
                  )}
                </button>
              ) : (
                <span className="text-[11px] text-blue-800 font-medium">
                  {scan?.inspection_state?.summary || 'Follow copilot recommendation to proceed.'}
                </span>
              )}

              {/* Primary Action Button */}
              {scan?.next_best_action?.action_code === 'image_recapture_quality' ||
              scan?.next_best_action?.action_code === 'capture_additional_view' ||
              scan?.next_best_action?.action_code === 'capture_back_panel' ? (
                <Link to={`/new-inspection?category=${encodeURIComponent(scan?.product_category || '')}`}>
                  <Button size="sm" icon={<Camera className="w-3.5 h-3.5" />} className="flex-shrink-0">
                    {scan.next_best_action.suggested_button_text || 'Capture View'}
                  </Button>
                </Link>
              ) : (
                <Button
                  size="sm"
                  onClick={handleCopilotPrimaryAction}
                  icon={<ArrowRight className="w-3.5 h-3.5" />}
                  className="flex-shrink-0"
                >
                  {scan?.next_best_action?.suggested_button_text || 'Review Evidence'}
                </Button>
              )}
            </div>

            {/* Embedded Expandable Detailed Guidance Drawer */}
            {showGuidanceDetails && scan?.guidance && (
              <div className="p-3 bg-white rounded-lg border border-blue-200/80 space-y-2 mt-1 animate-in fade-in text-xs">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-bold text-slate-800 text-[11px] flex items-center gap-1.5">
                    <Camera className="w-3.5 h-3.5 text-brand-blue" />
                    {scan.guidance.headline || 'Field Recapture Plan'}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                        scan.guidance.priority === 'critical'
                          ? 'bg-red-100 text-red-800 border-red-200'
                          : scan.guidance.priority === 'high'
                          ? 'bg-amber-100 text-amber-800 border-amber-200'
                          : 'bg-blue-100 text-blue-800 border-blue-200'
                      }`}
                    >
                      {scan.guidance.priority} Priority
                    </span>
                    {scan.guidance.coverage_estimate_pct !== undefined && scan.guidance.coverage_estimate_pct !== null && (
                      <span className="text-[10px] font-medium text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                        ~{scan.guidance.coverage_estimate_pct}% Coverage
                      </span>
                    )}
                  </div>
                </div>

                {/* Target Panels */}
                {scan.guidance.target_panels && scan.guidance.target_panels.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-slate-500 font-medium">Target Panels:</span>
                    {scan.guidance.target_panels.map((p) => (
                      <span
                        key={p}
                        className="text-[10px] font-semibold bg-blue-50 px-2 py-0.5 rounded border border-blue-200 text-blue-800 capitalize flex items-center gap-1"
                      >
                        <Layers className="w-3 h-3 text-brand-blue" />
                        {p.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                )}

                {/* Actionable Steps */}
                {scan.guidance.actionable_steps && scan.guidance.actionable_steps.length > 0 && (
                  <div className="space-y-1 bg-slate-50 rounded p-2 border border-slate-200/80">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                      Recommended Action Steps:
                    </span>
                    <ul className="space-y-1 text-[11px] text-slate-700">
                      {scan.guidance.actionable_steps.map((step, sIdx) => (
                        <li key={sIdx} className="flex items-start gap-1.5">
                          <span className="w-3.5 h-3.5 rounded-full bg-brand-blue/10 text-brand-blue font-bold text-[9px] flex items-center justify-center flex-shrink-0 mt-0.5">
                            {sIdx + 1}
                          </span>
                          <span className="leading-tight">{step}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Unverified Workflow Items Section */}
      {unverifiedItems.length > 0 && (
        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Unverified Workflow Items
              </span>
              <span className="text-[11px] font-bold px-2 py-0.2 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                {unverifiedItems.length}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowUnverifiedDetails(!showUnverifiedDetails)}
              className="text-xs text-slate-500 hover:text-slate-800 font-medium inline-flex items-center gap-1"
            >
              {showUnverifiedDetails ? (
                <>
                  <ChevronUp className="w-3.5 h-3.5" />
                  <span>Collapse</span>
                </>
              ) : (
                <>
                  <ChevronDown className="w-3.5 h-3.5" />
                  <span>Expand</span>
                </>
              )}
            </button>
          </div>

          {showUnverifiedDetails && (
            <div className="space-y-2">
              {unverifiedItems.map((item, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all ${
                    item.type === 'actionable'
                      ? 'bg-amber-50/50 border-amber-200'
                      : 'bg-slate-50 border-slate-200 text-slate-600'
                  }`}
                >
                  <div className="flex items-start gap-2.5 flex-1">
                    <div className="mt-0.5 flex-shrink-0">{item.icon}</div>
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900">{item.title}</span>
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.2 rounded uppercase ${
                            item.type === 'actionable'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-200 text-slate-700'
                          }`}
                        >
                          {item.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 leading-snug">{item.reason}</p>
                    </div>
                  </div>

                  {item.actionButton && (
                    <div className="self-end sm:self-center flex-shrink-0">{item.actionButton}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. Top Metrics Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Visual Label Compliance Score */}
        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Visual Label Compliance Score</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {score !== null ? `${score.toFixed(1)}%` : '—'}
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                {verdict === 'PASS'
                  ? 'All mandatory visual label rules satisfied'
                  : verdict === 'FAIL'
                  ? `${statutoryViolations.length} statutory violation(s)`
                  : qualityIssues.length > 0
                  ? 'Halted on image quality inspection'
                  : 'Requires officer verification'}
              </p>
            </div>
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center ${
                score !== null && score >= 90
                  ? 'bg-emerald-50 text-emerald-600'
                  : score !== null && score >= 60
                  ? 'bg-amber-50 text-amber-600'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              <Scale className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Declarations Verified */}
        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Declarations Verified</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {declarations.length}
              </h3>
              <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-1">
                <span className="text-emerald-600 font-medium">{detectedCount} detected</span>
                <span>•</span>
                <span className="text-amber-600 font-medium">{uncertainCount} uncertain</span>
                {missingCount > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-red-600 font-medium">{missingCount} missing</span>
                  </>
                )}
              </div>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center">
              <FileCheck className="w-5 h-5" />
            </div>
          </div>
        </Card>

        {/* Statutory Violations & Quality Issues */}
        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Statutory Violations</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {statutoryViolations.length}
              </h3>
              <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-1 flex-wrap">
                {criticalViolations.length > 0 && (
                  <span className="text-red-600 font-bold">{criticalViolations.length} Critical</span>
                )}
                {majorViolations.length > 0 && (
                  <span className="text-orange-600 font-medium">{majorViolations.length} Major</span>
                )}
                {minorViolations.length > 0 && (
                  <span className="text-yellow-600 font-medium">{minorViolations.length} Minor</span>
                )}
                {statutoryViolations.length === 0 && (
                  <span className="text-emerald-600 font-medium">Zero non-compliance citations</span>
                )}
                {qualityIssues.length > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-amber-800 font-semibold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                      {qualityIssues.length} Quality Issue{qualityIssues.length > 1 ? 's' : ''}
                    </span>
                  </>
                )}
              </div>
            </div>
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center ${
                statutoryViolations.length === 0
                  ? qualityIssues.length > 0
                    ? 'bg-amber-50 text-amber-600'
                    : 'bg-emerald-50 text-emerald-600'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              {statutoryViolations.length === 0 && qualityIssues.length > 0 ? (
                <AlertTriangle className="w-5 h-5" />
              ) : statutoryViolations.length === 0 ? (
                <ShieldCheck className="w-5 h-5" />
              ) : (
                <ShieldAlert className="w-5 h-5" />
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* 5. Tab Navigation */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-6 -mb-px flex-wrap">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'overview'
                ? 'border-brand-blue text-brand-blue font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>Overview & Evidence</span>
          </button>

          <button
            onClick={() => setActiveTab('declarations')}
            className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'declarations'
                ? 'border-brand-blue text-brand-blue font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>Extracted Declarations</span>
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600">
              {declarations.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('violations')}
            className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'violations'
                ? 'border-brand-blue text-brand-blue font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <span>Violations & Quality Issues</span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full ${
                statutoryViolations.length > 0
                  ? 'bg-red-100 text-red-700 font-bold'
                  : qualityIssues.length > 0
                  ? 'bg-amber-100 text-amber-800 font-semibold'
                  : 'bg-slate-100 text-slate-600'
              }`}
            >
              {violations.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('evidence')}
            className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'evidence'
                ? 'border-brand-blue text-brand-blue font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>Full Evidence View</span>
          </button>

          {isNeedsReview && (
            <button
              onClick={() => setActiveTab('review')}
              className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'review'
                  ? 'border-amber-600 text-amber-700 font-bold'
                  : 'border-transparent text-amber-600 hover:text-amber-800'
              }`}
            >
              <UserCheck className="w-4 h-4" />
              <span>Inspector Review</span>
              {correctedFieldsCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-amber-200 text-amber-900 font-bold">
                  {correctedFieldsCount} edited
                </span>
              )}
            </button>
          )}
        </nav>
      </div>

      {/* 6. Tab Content Area */}

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Visual Evidence Card */}
          <div id="visual-evidence-card">
            <Card
              title="Visual Evidence Overlay"
              subtitle="Color-coded annotations from Legal Metrology rules engine"
            >
              {/* Multi-View Switcher */}
              {evidenceImageUrls.length > 1 && (
                <div className="flex items-center gap-1.5 mb-3 overflow-x-auto pb-1">
                  <span className="text-xs font-semibold text-slate-500 mr-1 flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-brand-blue" /> View:
                  </span>
                  {evidenceImageUrls.map((_, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedViewIndex(idx)}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                        selectedViewIndex === idx
                          ? 'bg-brand-blue text-white shadow-2xs'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      View {idx + 1}
                    </button>
                  ))}
                </div>
              )}

              {evidenceUrl && !imageError ? (
                <div className="rounded-lg overflow-hidden border border-slate-200 bg-slate-900 flex flex-col items-center justify-center min-h-[320px] relative group">
                  <img
                    src={evidenceUrl}
                    alt={`Inspection Evidence View ${selectedViewIndex + 1}`}
                    onError={() => setImageError(true)}
                    className="max-h-[460px] w-auto object-contain transition-all"
                  />
                  <div className="absolute bottom-2 right-2 bg-slate-900/80 text-white text-[11px] px-2.5 py-1 rounded backdrop-blur-xs flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5" />
                    <span>Rule Engine Overlay {evidenceImageUrls.length > 1 ? `(View ${selectedViewIndex + 1})` : ''}</span>
                  </div>
                </div>
              ) : (
                <div className="py-16 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                  <ImageIcon className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                  <p className="text-xs font-medium text-slate-600">No Visual Evidence Artifact Available</p>
                  <p className="text-[11px] text-slate-400 mt-1 max-w-xs mx-auto">
                    {imageError
                      ? 'The evidence image artifact could not be loaded over HTTP. Verify backend storage mounting.'
                      : 'This scan did not generate or persist a visual evidence overlay image.'}
                  </p>
                </div>
              )}
            </Card>
          </div>

          {/* Quick Summary & Audit Notes */}
          <div className="space-y-6">
            <div id="compliance-verdict-summary-card">
              <Card title="Compliance Verdict Summary" subtitle="Codified Legal Metrology validation outcome">
                <div className="space-y-3">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                    <span className="text-xs text-slate-600 font-medium">Verdict Determination</span>
                    <StatusBadge status={verdict} />
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                    <span className="text-xs text-slate-600 font-medium">Statutory Framework</span>
                    <span className="text-xs font-semibold text-slate-800">LMR (Packaged Commodities) Rules, 2011</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                    <span className="text-xs text-slate-600 font-medium">Evaluated Rule Catalog</span>
                    <span className="text-xs font-mono text-slate-700">LMR Rule 6(1) Declarations</span>
                  </div>
                  {scan?.reviewer_notes && (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs space-y-1">
                      <span className="font-semibold text-blue-950 flex items-center gap-1.5">
                        <UserCheck className="w-3.5 h-3.5 text-brand-blue" />
                        Inspector Reviewer Notes:
                      </span>
                      <p className="text-blue-900 leading-relaxed font-normal">{scan.reviewer_notes}</p>
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Inspection Scope & Statutory Boundary */}
            <div id="inspection-scope-card">
              <Card
                title="Inspection Scope"
                subtitle="Statutory verification tiers and operational boundaries"
              >
                <div className="space-y-2.5">
                  {/* 1. Image Label Checks */}
                  <div className="p-2.5 bg-emerald-50/60 border border-emerald-200 rounded-lg flex items-start gap-2.5 text-xs">
                    <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs">
                      🟢
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-emerald-950">Image Label Checks</span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded uppercase">
                          Evaluated
                        </span>
                      </div>
                      <p className="text-emerald-900 text-[11px] mt-0.5">
                        {scan?.scope_coverage?.image_verifiable_rules_checked?.length || 11} statutory visual declaration rules audited
                      </p>
                    </div>
                  </div>

                  {/* 2. Package Views */}
                  <div className="p-2.5 bg-emerald-50/60 border border-emerald-200 rounded-lg flex items-start gap-2.5 text-xs">
                    <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs">
                      🟢
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-emerald-950">Package Views</span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded uppercase">
                          {evidenceImageUrls.length > 0 ? evidenceImageUrls.length : 1} view{evidenceImageUrls.length > 1 ? 's' : ''} captured
                        </span>
                      </div>
                      <p className="text-emerald-900 text-[11px] mt-0.5">
                        {scan?.is_complete_scan
                          ? 'Complete multi-view panel coverage'
                          : 'Partial view capture — unobserved panels not cited as violations'}
                      </p>
                    </div>
                  </div>

                  {/* 3. Physical Metrology */}
                  <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-start gap-2.5 text-xs">
                    <div className="w-5 h-5 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs">
                      ⚪
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800">Physical Metrology</span>
                        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-200 text-slate-700 rounded">
                          Not Evaluated
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        Requires calibrated weighing/measurement (Net weight MPE Rules 14–18, Font mm Rule 8)
                      </p>
                    </div>
                  </div>

                  {/* 4. External Regulatory Verification */}
                  <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-start gap-2.5 text-xs">
                    <div className="w-5 h-5 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs">
                      ⚪
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800">External Regulatory Verification</span>
                        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-slate-200 text-slate-700 rounded">
                          Not Evaluated
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        Requires external registry/data source (DCA Director Rule 27 registration, FSSAI / EPR)
                      </p>
                    </div>
                  </div>

                  {/* Disclaimer note */}
                  <div className="pt-1 text-[10px] text-slate-400 italic leading-relaxed">
                    Notice: Automated visual inspection evaluates visible declarations on captured images. It does not verify physical weight or external registrations and does not constitute statutory legal certification.
                  </div>
                </div>
              </Card>
            </div>

            {/* QR & Electronic Declarations Evidence (Phase 4B - Rule 6 / G.S.R. 456(E)) */}
            <div id="qr-compliance-card">
              <Card
                title="QR & Electronic Declarations"
                subtitle="Statutory evaluation under Rule 6 / G.S.R. 456(E) for packaged electronic products"
              >
                <div className="space-y-3 text-xs">
                  {/* Status Badges Grid */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">QR Detection</span>
                      <div className="flex items-center gap-1.5 mt-1">
                        <QrCode className="w-3.5 h-3.5 text-brand-blue" />
                        <span className="font-semibold text-slate-800 capitalize">
                          {scan?.qr_evidence?.status || (scan?.qr_evidence?.detected ? 'Detected' : 'Not Detected')}
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Applicability</span>
                      <span
                        className={`font-semibold inline-block mt-1 px-1.5 py-0.5 rounded text-[11px] ${
                          scan?.qr_evidence?.applicable_product === 'APPLICABLE'
                            ? 'bg-blue-50 text-blue-800 border border-blue-200'
                            : scan?.qr_evidence?.applicable_product === 'NOT_APPLICABLE'
                            ? 'bg-slate-100 text-slate-700 border border-slate-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {scan?.qr_evidence?.applicable_product || 'UNCERTAIN'}
                      </span>
                    </div>
                  </div>

                  {/* Scan Instruction Status */}
                  <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-slate-700">Consumer Scan Instruction:</span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                          scan?.qr_evidence?.instruction_detected
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {scan?.qr_evidence?.instruction_detected ? 'Detected' : 'Not Detected'}
                      </span>
                    </div>
                    {scan?.qr_evidence?.instruction_text && (
                      <p className="text-[11px] text-slate-600 italic bg-white p-1.5 rounded border border-slate-200 mt-1">
                        "{scan.qr_evidence.instruction_text}"
                      </p>
                    )}
                  </div>

                  {/* Decoded Payload (if available) */}
                  {scan?.qr_evidence?.decoded_payload && (
                    <div className="p-2.5 bg-blue-50/70 border border-blue-200 rounded-lg space-y-1">
                      <span className="text-[10px] font-bold text-blue-900 uppercase tracking-wider block">Decoded QR Payload</span>
                      <code className="text-[11px] font-mono text-blue-950 break-all bg-white/80 p-1.5 rounded block border border-blue-100">
                        {scan.qr_evidence.decoded_payload}
                      </code>
                      <p className="text-[10px] text-blue-800 mt-0.5">
                        ⚠️ Note: External URL payload recorded as audit evidence; external destination content is not automatically browsed or statutory-verified.
                      </p>
                    </div>
                  )}

                  {/* Bounding Box (if available) */}
                  {scan?.qr_evidence?.bounding_box && (
                    <div className="text-[10px] text-slate-500 flex items-center gap-1 font-mono">
                      <span>Coordinates: [x: {scan.qr_evidence.bounding_box.x}, y: {scan.qr_evidence.bounding_box.y}, w: {scan.qr_evidence.bounding_box.width}, h: {scan.qr_evidence.bounding_box.height}]</span>
                    </div>
                  )}

                  {/* Statutory Note & Legal Guardrail */}
                  <div className="pt-1 text-[10px] text-slate-400 italic leading-relaxed border-t border-slate-100">
                    {scan?.qr_evidence?.statutory_note ||
                      'Under Rule 6 as amended by G.S.R. 456(E), electronic products may provide select declarations via QR code provided an explicit consumer scan instruction is present on the package.'}
                  </div>
                </div>
              </Card>
            </div>

            {/* Package Composition Card (Phase 4C - Multi-Commodity & Package Structure) */}
            {scan?.composition && (scan.composition.package_type !== 'SINGLE' || scan.composition.items.length > 1) && (
              <div id="package-composition-card">
                <Card
                  title="Package Composition"
                  subtitle="Constituent commodity classification and itemized package structure"
                >
                  <div className="space-y-3 text-xs">
                    {/* Composition Classification Header */}
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Package Type</span>
                        <div className="flex items-center gap-1.5 mt-1">
                          <PackageIcon className="w-3.5 h-3.5 text-brand-blue" />
                          <span className="font-semibold text-slate-800 capitalize">
                            {scan.composition.package_type.replace('_', ' ')}
                          </span>
                        </div>
                      </div>

                      <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Items & Status</span>
                        <div className="flex items-center justify-between mt-1">
                          <span className="font-semibold text-slate-800">
                            {scan.composition.total_item_count} Item{scan.composition.total_item_count > 1 ? 's' : ''}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                              scan.composition.status === 'detected'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                                : 'bg-amber-100 text-amber-800 border border-amber-200'
                            }`}
                          >
                            {scan.composition.status === 'detected' ? 'CONFIRMED' : 'UNCERTAIN'}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Constituent Items List */}
                    {scan.composition.items && scan.composition.items.length > 0 && (
                      <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <table className="min-w-full divide-y divide-slate-200 text-[11px]">
                          <thead className="bg-slate-50 font-semibold text-slate-600">
                            <tr>
                              <th className="px-3 py-2 text-left">#</th>
                              <th className="px-3 py-2 text-left">Constituent Commodity</th>
                              <th className="px-3 py-2 text-left">Unit Qty / Count</th>
                              <th className="px-3 py-2 text-right">Evidence</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {scan.composition.items.map((item, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/50">
                                <td className="px-3 py-2 font-mono text-slate-500 font-bold">{item.item_index || idx + 1}</td>
                                <td className="px-3 py-2 font-medium text-slate-900">{item.commodity_name}</td>
                                <td className="px-3 py-2 font-mono text-slate-700">
                                  {item.unit_quantity || (item.item_count ? `${item.item_count} N` : '—')}
                                </td>
                                <td className="px-3 py-2 text-right text-slate-500">
                                  View {(item.source_image_index || 0) + 1}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Statutory Note */}
                    {scan.composition.statutory_note && (
                      <div className="pt-1 text-[10px] text-slate-400 italic leading-relaxed border-t border-slate-100">
                        {scan.composition.statutory_note}
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            )}

            {/* Inspection Quality Issues (e.g. QUALITY-REJECT) */}
            {qualityIssues.length > 0 && (
              <div id="quality-issues-card">
                <Card
                  title="Inspection Quality Issues"
                  subtitle="Evidence capture and image quality deficiencies preventing automated legal inspection"
                >
                  <div className="space-y-3">
                    {qualityIssues.map((issue, idx) => (
                      <div
                        key={issue.id || idx}
                        className="p-3 border rounded-lg text-xs space-y-1 bg-amber-50/70 border-amber-200"
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-amber-950 font-bold">{issue.rule_code}</span>
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase">
                              Image Capture Deficiency
                            </span>
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase bg-amber-200 text-amber-900">
                            {issue.severity}
                          </span>
                        </div>
                        <p className="text-slate-800 leading-relaxed">{issue.description}</p>
                        <div className="text-[11px] text-amber-900 pt-1 font-medium flex items-center gap-1">
                          <Camera className="w-3.5 h-3.5 text-amber-700" />
                          <span>Recommendation: Retake photo in well-lit conditions with minimum 600×600 resolution and steady camera focus.</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            )}

            {/* Primary Statutory Violations */}
            <div id="statutory-violations-card">
              {statutoryViolations.length > 0 ? (
                <Card
                  title="Primary Statutory Violations"
                  subtitle="Immediate non-compliance citations under Legal Metrology Rules"
                >
                  <div className="space-y-3">
                    {statutoryViolations.slice(0, 4).map((viol, idx) => (
                      <div
                        key={viol.id || idx}
                        className={`p-3 border rounded-lg text-xs space-y-1 transition-colors ${
                          viol.severity === 'critical'
                            ? 'bg-red-50/70 border-red-200'
                            : viol.severity === 'major'
                            ? 'bg-orange-50/70 border-orange-200'
                            : 'bg-yellow-50/70 border-yellow-200'
                        }`}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-slate-900">{viol.rule_code}</span>
                            {viol.field_name && (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/80 text-slate-700 border border-slate-200">
                                {viol.field_name}
                              </span>
                            )}
                          </div>
                          <span
                            className={`uppercase text-[10px] px-2 py-0.5 rounded font-bold ${
                              viol.severity === 'critical'
                                ? 'bg-red-200 text-red-900'
                                : viol.severity === 'major'
                                ? 'bg-orange-200 text-orange-900'
                                : 'bg-yellow-200 text-yellow-900'
                            }`}
                          >
                            {viol.severity}
                          </span>
                        </div>
                        <p className="text-slate-800 leading-relaxed">{viol.description}</p>
                      </div>
                    ))}
                    {statutoryViolations.length > 4 && (
                      <button
                        onClick={() => setActiveTab('violations')}
                        className="text-xs text-brand-blue font-semibold hover:underline flex items-center gap-1 pt-1"
                      >
                        View all {statutoryViolations.length} statutory violations in detail $\rightarrow$
                      </button>
                    )}
                  </div>
                </Card>
              ) : (
                <Card>
                  <div className="py-8 text-center">
                    <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-2">
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                    <h4 className="text-sm font-semibold text-slate-800">
                      {qualityIssues.length > 0 ? 'No Statutory Violations Recorded' : 'Fully Compliant Package'}
                    </h4>
                    <p className="text-xs text-slate-400 mt-1">
                      {qualityIssues.length > 0
                        ? 'No statutory violations were cited against this package; automated inspection was halted due to image quality.'
                        : 'No statutory violations detected across all verified packaging rules.'}
                    </p>
                  </div>
                </Card>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: DECLARATIONS */}
      {activeTab === 'declarations' && (
        <div id="declaration-audit-table">
          <Card
            title="Mandatory Declaration Audit Table"
            subtitle="Extracted packaging labels, normalized values, confidence scores, and spatial coordinates"
          >
          {declarations.length === 0 ? (
            <div className="py-12 text-center text-slate-400">
              <FileText className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              <p className="text-xs">No declarations extracted for this scan.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 uppercase tracking-wider text-[11px] bg-slate-50">
                      <th className="py-2.5 px-3">Field Name</th>
                      <th className="py-2.5 px-3">Extracted Raw Text</th>
                      <th className="py-2.5 px-3">Normalized Value</th>
                      <th className="py-2.5 px-3">Detection Status</th>
                      <th className="py-2.5 px-3">Confidence</th>
                      <th className="py-2.5 px-3">Source</th>
                      <th className="py-2.5 px-3">Bounding Box</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {declarations.map((decl, idx) => {
                      const isSelected = selectedFieldName === decl.field_name
                      const hasLinkedViolations = violations.some((v) => v.field_name === decl.field_name)

                      return (
                        <tr
                          key={decl.id || idx}
                          onClick={() => {
                            const nextField = isSelected ? null : decl.field_name
                            setSelectedFieldName(nextField)
                            if (
                              decl.image_index !== null &&
                              decl.image_index !== undefined &&
                              decl.image_index < evidenceImageUrls.length
                            ) {
                              setSelectedViewIndex(decl.image_index)
                            }
                          }}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-blue-50/80 font-medium'
                              : 'hover:bg-slate-50/80'
                          }`}
                        >
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-semibold text-slate-800 font-mono">
                                {decl.field_name}
                              </span>
                              {hasLinkedViolations && (
                                <span className="w-2 h-2 rounded-full bg-red-500" title="Has linked violation" />
                              )}
                              {decl.image_index !== null && decl.image_index !== undefined && evidenceImageUrls.length > 1 && (
                                <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1 py-0.5 rounded border border-blue-200">
                                  View {decl.image_index + 1}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-slate-600 max-w-xs break-words">
                            {decl.raw_value ? (
                              <span>{decl.raw_value}</span>
                            ) : (
                              <span className="text-slate-400 italic">None</span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-slate-900 font-medium max-w-xs break-words">
                            {decl.normalized_value || (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                          <td className="py-3 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                decl.status === 'detected'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : decl.status === 'uncertain'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {decl.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono text-slate-600">
                            {decl.confidence !== null && decl.confidence !== undefined
                              ? `${(decl.confidence * 100).toFixed(1)}%`
                              : '—'}
                          </td>
                          <td className="py-3 px-3 text-slate-500 capitalize">
                            {decl.source === 'manual' ? (
                              <span className="text-blue-700 font-semibold">manual (Inspector)</span>
                            ) : (
                              decl.source || 'gemini'
                            )}
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                            {decl.bounding_box ? (
                              <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">
                                [{decl.bounding_box.x}, {decl.bounding_box.y}, {decl.bounding_box.width}×{decl.bounding_box.height}]
                              </span>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Selected Declaration Details Drawer */}
              {selectedFieldName && (
                <div className="p-4 bg-blue-50/60 border border-blue-200 rounded-lg text-xs space-y-2 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-blue-950 font-mono text-sm">
                      Field Context: {selectedFieldName}
                    </span>
                    <button
                      onClick={() => setSelectedFieldName(null)}
                      className="text-blue-600 hover:text-blue-800 text-xs font-semibold"
                    >
                      Close
                    </button>
                  </div>
                  {(() => {
                    const linkedViols = violations.filter((v) => v.field_name === selectedFieldName)
                    if (linkedViols.length === 0) {
                      return (
                        <p className="text-blue-800">
                          This declaration satisfied all statutory validation checks.
                        </p>
                      )
                    }
                    return (
                      <div className="space-y-1.5 pt-1">
                        <span className="font-semibold text-red-900">
                          Linked Violations for {selectedFieldName}:
                        </span>
                        {linkedViols.map((v, i) => (
                          <div key={i} className="p-2 bg-white rounded border border-red-200 text-red-900">
                            <span className="font-bold font-mono">{v.rule_code}</span>: {v.description}
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                </div>
              )}
            </div>
          )}
        </Card>
        </div>
      )}

      {/* TAB 3: VIOLATIONS & QUALITY ISSUES */}
      {activeTab === 'violations' && (
        <div className="space-y-6">
          {/* Inspection Quality Issues (e.g. QUALITY-REJECT) */}
          {qualityIssues.length > 0 && (
            <Card
              title="Inspection Quality Issues"
              subtitle="Evidence capture and image quality deficiencies preventing automated legal inspection"
            >
              <div className="space-y-4">
                {qualityIssues.map((issue, idx) => (
                  <div
                    key={issue.id || idx}
                    className="p-4 border rounded-lg space-y-3 bg-amber-50/50 border-amber-200"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                        <span className="font-bold text-sm text-amber-950 font-mono">
                          {issue.rule_code}
                        </span>
                        <span className="text-[11px] text-amber-800 uppercase px-2 py-0.5 rounded bg-amber-100 border border-amber-200 font-semibold">
                          Image Capture Deficiency
                        </span>
                      </div>
                      <span className="text-xs font-bold uppercase px-2.5 py-0.5 rounded-full bg-amber-200 text-amber-900 self-start sm:self-auto">
                        {issue.severity}
                      </span>
                    </div>

                    <p className="text-xs text-slate-800 leading-relaxed font-normal">
                      {issue.description}
                    </p>

                    <div className="p-3 bg-white rounded border border-amber-200 text-xs text-amber-950 space-y-1">
                      <span className="font-semibold flex items-center gap-1.5 text-amber-900">
                        <Camera className="w-3.5 h-3.5 text-amber-700" />
                        Inspector Recapture Guidelines:
                      </span>
                      <p className="text-[11px] text-slate-600 leading-relaxed">
                        Ensure the product packaging is flat, evenly illuminated, fills at least 70% of the camera frame, and is captured at &ge; 600&times;600 resolution with sharp text focus.
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Statutory Rule Violations */}
          <Card
            title="Statutory Rule Violations"
            subtitle="Comprehensive Legal Metrology non-compliance citations with linked declaration evidence"
          >
            {statutoryViolations.length === 0 ? (
              <div className="py-12 text-center">
                <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-semibold text-slate-800">No Statutory Violations Detected</h4>
                <p className="text-xs text-slate-400 mt-1">
                  {qualityIssues.length > 0
                    ? 'No statutory rule violations were cited against this packaged commodity.'
                    : 'This packaged commodity complies with all evaluated Legal Metrology rules.'}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {statutoryViolations.map((viol, idx) => {
                  const linkedDecl = viol.field_name
                    ? declarations.find((d) => d.field_name === viol.field_name)
                    : null

                  return (
                    <div
                      key={viol.id || idx}
                      className={`p-4 border rounded-lg space-y-3 transition-all ${
                        viol.severity === 'critical'
                          ? 'border-red-200 bg-red-50/40'
                          : viol.severity === 'major'
                          ? 'border-orange-200 bg-orange-50/40'
                          : 'border-yellow-200 bg-yellow-50/40'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <ShieldAlert
                            className={`w-4 h-4 ${
                              viol.severity === 'critical'
                                ? 'text-red-600'
                                : viol.severity === 'major'
                                ? 'text-orange-600'
                                : 'text-yellow-600'
                            }`}
                          />
                          <span className="font-bold text-sm text-slate-900 font-mono">
                            {viol.rule_code}
                          </span>
                          {viol.field_name && (
                            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200">
                              {viol.field_name}
                            </span>
                          )}
                          <span className="text-[11px] text-slate-500 uppercase">
                            ({viol.violation_type})
                          </span>
                        </div>
                        <span
                          className={`text-xs font-bold uppercase px-2.5 py-0.5 rounded-full self-start sm:self-auto ${
                            viol.severity === 'critical'
                              ? 'bg-red-200 text-red-900'
                              : viol.severity === 'major'
                              ? 'bg-orange-200 text-orange-900'
                              : 'bg-yellow-200 text-yellow-900'
                          }`}
                        >
                          {viol.severity}
                        </span>
                      </div>

                      <p className="text-xs text-slate-800 leading-relaxed font-normal">
                        {viol.description}
                      </p>

                      {linkedDecl && (
                        <div className="p-3 bg-white/90 rounded border border-slate-200 text-xs space-y-1">
                          <div className="flex items-center justify-between text-slate-700">
                            <span className="font-semibold flex items-center gap-1.5">
                              <Crosshair className="w-3.5 h-3.5 text-brand-blue" />
                              Linked Declaration Evidence:
                            </span>
                            <span
                              className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold ${
                                linkedDecl.status === 'detected'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : linkedDecl.status === 'uncertain'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              Status: {linkedDecl.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-[11px]">
                            <div>
                              <span className="text-slate-400">Extracted Raw Text: </span>
                              <span className="text-slate-900 font-medium">
                                {linkedDecl.raw_value || 'None detected'}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-400">Confidence: </span>
                              <span className="font-mono text-slate-800">
                                {linkedDecl.confidence !== null && linkedDecl.confidence !== undefined
                                  ? `${(linkedDecl.confidence * 100).toFixed(1)}%`
                                  : '—'}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB 4: FULL EVIDENCE VIEW */}
      {activeTab === 'evidence' && (
        <div className="space-y-6">
          <Card
            title="Inspection Visual Artifact Viewer"
            subtitle="Full-resolution bounding-box overlay and spatial coordinates"
          >
            {/* Multi-View Switcher */}
            {evidenceImageUrls.length > 1 && (
              <div className="flex items-center gap-1.5 mb-4 overflow-x-auto pb-1">
                <span className="text-xs font-semibold text-slate-500 mr-1 flex items-center gap-1">
                  <Layers className="w-3.5 h-3.5 text-brand-blue" /> Package View:
                </span>
                {evidenceImageUrls.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedViewIndex(idx)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                      selectedViewIndex === idx
                        ? 'bg-brand-blue text-white shadow-2xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    View {idx + 1}
                  </button>
                ))}
              </div>
            )}

            {evidenceUrl && !imageError ? (
              <div className="space-y-4">
                <div className="rounded-lg overflow-hidden border border-slate-300 bg-slate-950 flex items-center justify-center p-2">
                  <img
                    src={evidenceUrl}
                    alt={`Full Visual Evidence View ${selectedViewIndex + 1}`}
                    onError={() => setImageError(true)}
                    className="max-h-[600px] w-auto object-contain"
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Artifact URL: <code className="font-mono text-slate-700">{activeEvidenceRaw}</code></span>
                  <a
                    href={evidenceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-brand-blue font-semibold hover:underline"
                  >
                    <span>Open Full Image</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            ) : (
              <div className="py-20 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                <ImageIcon className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                <p className="text-sm font-medium text-slate-700">Visual Evidence Unavailable</p>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  {imageError
                    ? 'Failed to fetch the evidence image from storage over HTTP.'
                    : 'The backend did not produce a visual evidence image overlay for this inspection.'}
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB 5: HUMAN INSPECTOR REVIEW WORKFLOW (NEEDS_REVIEW ONLY) */}
      {activeTab === 'review' && isNeedsReview && (
        <div className="space-y-6" id="inspector-review-workstation">
          {/* Review Instructions Card */}
          <Card
            title="Human Inspector Review & Resolution Workstation"
            subtitle="Verify uncertain packaging declarations and record final statutory determination"
          >
            <div className="space-y-6">
              {reviewError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3 text-xs text-red-800">
                  <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Review Error:</span> {reviewError}
                  </div>
                </div>
              )}

              {/* Step 1: Declarations Verification & Overrides */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900">
                    1. Audit & Correct Packaging Declarations
                  </h3>
                  <span className="text-xs text-slate-500">
                    Click <strong>Edit</strong> on any declaration to apply a manual correction.
                  </span>
                </div>

                <div className="space-y-2">
                  {declarations.map((decl) => {
                    const isEditing = editingField === decl.field_name
                    const correction = corrections[decl.field_name]

                    return (
                      <div
                        key={decl.field_name}
                        className={`p-3.5 rounded-lg border text-xs transition-all ${
                          correction
                            ? 'bg-blue-50/70 border-blue-300'
                            : decl.status === 'uncertain'
                            ? 'bg-amber-50/60 border-amber-200'
                            : 'bg-slate-50 border-slate-200'
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-slate-800">
                              {decl.field_name}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                (correction?.status || decl.status) === 'detected'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : (correction?.status || decl.status) === 'uncertain'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {correction?.status || decl.status}
                            </span>
                            {correction && (
                              <span className="text-[10px] bg-brand-blue text-white px-2 py-0.5 rounded font-semibold">
                                Inspector Corrected
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {!isEditing && (
                              <button
                                onClick={() => startEditingDeclaration(decl)}
                                className="text-xs text-brand-blue hover:text-brand-blueHover font-medium inline-flex items-center gap-1 bg-white px-2.5 py-1 rounded border border-slate-200 shadow-2xs"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                                <span>{correction ? 'Modify Override' : 'Correct Value'}</span>
                              </button>
                            )}
                            {correction && !isEditing && (
                              <button
                                onClick={() => removeCorrection(decl.field_name)}
                                className="text-xs text-red-600 hover:text-red-700 font-medium inline-flex items-center gap-1 bg-white px-2 py-1 rounded border border-red-200 shadow-2xs"
                              >
                                <Undo2 className="w-3.5 h-3.5" />
                                <span>Revert</span>
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Value Comparison */}
                        {!isEditing ? (
                          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1 border-t border-slate-200/60">
                            <div>
                              <span className="text-slate-400">Original AI Value: </span>
                              <span className="text-slate-800 font-medium">
                                {decl.raw_value || 'None detected'}
                              </span>
                            </div>
                            {correction && (
                              <div>
                                <span className="text-blue-600 font-semibold">Inspector Value: </span>
                                <span className="text-blue-950 font-bold">
                                  {correction.raw_value || correction.normalized_value || 'Marked as valid'}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : (
                          /* Inline Correction Editor Form */
                          <div className="mt-3 p-3 bg-white rounded-lg border border-brand-blue/30 space-y-3 animate-in fade-in">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                                  Corrected Raw Text
                                </label>
                                <input
                                  type="text"
                                  value={editRawValue}
                                  onChange={(e) => setEditRawValue(e.target.value)}
                                  placeholder="e.g. ₹150.00 (incl. of all taxes)"
                                  className="w-full text-xs p-2 rounded border border-slate-300 focus:border-brand-blue focus:outline-none"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                                  Normalized Value
                                </label>
                                <input
                                  type="text"
                                  value={editNormalizedValue}
                                  onChange={(e) => setEditNormalizedValue(e.target.value)}
                                  placeholder="e.g. 150.00"
                                  className="w-full text-xs p-2 rounded border border-slate-300 focus:border-brand-blue focus:outline-none"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                                  Verification Status
                                </label>
                                <select
                                  value={editStatus}
                                  onChange={(e) => setEditStatus(e.target.value as DeclarationStatus)}
                                  className="w-full text-xs p-2 rounded border border-slate-300 bg-white focus:border-brand-blue focus:outline-none"
                                >
                                  <option value="detected">Detected (Valid)</option>
                                  <option value="missing">Missing (Non-Compliant)</option>
                                  <option value="uncertain">Uncertain</option>
                                </select>
                              </div>
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setEditingField(null)}
                              >
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => saveDeclarationCorrection(decl.field_name)}
                                icon={<Check className="w-3.5 h-3.5" />}
                              >
                                Apply Correction
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Step 2: Reviewer Audit Observations Notes */}
              <div className="space-y-2 pt-3 border-t border-slate-200">
                <label htmlFor="reviewer-notes" className="block text-sm font-bold text-slate-900">
                  2. Inspector Reviewer Observations & Statutory Justification <span className="text-red-600">*</span>
                </label>
                <textarea
                  id="reviewer-notes"
                  rows={3}
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  placeholder="Record your legal metrology audit findings (e.g., Mandatory declarations verified against Rule 6(1); Principal Display Panel placement confirmed compliant under Rule 7)."
                  className="w-full text-xs p-3 rounded-lg border border-slate-300 bg-white text-slate-900 placeholder-slate-400 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue leading-relaxed"
                />
              </div>

              {/* Step 3: Final Resolution Action Bar */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  <h4 className="text-xs font-bold text-slate-800">
                    3. Submit Final Compliance Resolution
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Submitting will finalize this inspection record and regenerate the official audit report.
                  </p>
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <Button
                    variant="outline"
                    onClick={() => handleSubmitReview('FAIL')}
                    disabled={isSubmittingReview || !reviewerNotes.trim()}
                    className="border-red-300 text-red-700 hover:bg-red-50 flex-1 sm:flex-initial"
                    icon={isSubmittingReview ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5 text-red-600" />}
                  >
                    Resolve as FAIL
                  </Button>

                  <Button
                    onClick={() => handleSubmitReview('PASS')}
                    disabled={isSubmittingReview || !reviewerNotes.trim()}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white flex-1 sm:flex-initial"
                    icon={isSubmittingReview ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Resolve as PASS
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

export default InspectionDetailsPage
