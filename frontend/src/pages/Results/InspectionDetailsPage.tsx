import React, { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  FileCheck,
  FileText,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Scale,
  ShieldAlert,
  Tag,
} from 'lucide-react'
import Card from '../../components/common/Card'
import StatusBadge from '../../components/common/StatusBadge'
import Button from '../../components/common/Button'
import { getScan } from '../../services/scanService'
import type { ApiErrorDetail } from '../../services/api'
import type { ScanResponse } from '../../types'

export const InspectionDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const isMountedRef = useRef<boolean>(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [scan, setScan] = useState<ScanResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'declarations' | 'violations' | 'evidence'>('overview')

  const fetchScanDetails = async (scanId: string) => {
    try {
      setIsLoading(true)
      setErrorMessage(null)
      const data = await getScan(scanId)

      if (!isMountedRef.current) return

      setScan(data)
      setIsLoading(false)

      // If scan is still pending or processing, poll periodically until finalized
      if (data.status === 'pending' || data.status === 'processing') {
        pollTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            fetchScanDetails(scanId)
          }
        }, 2000)
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
            <h3 className="text-sm font-semibold text-slate-700">Loading Inspection Results...</h3>
            <p className="text-xs text-slate-400 mt-1">Retrieving compliance audit records for ID: {id}</p>
          </div>
        </Card>
      </div>
    )
  }

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
              <Button size="sm" variant="outline" onClick={() => id && fetchScanDetails(id)} icon={<RefreshCw className="w-3.5 h-3.5" />}>
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

  const isPending = scan?.status === 'pending' || scan?.status === 'processing'
  const verdict = scan?.verdict || (isPending ? 'PENDING' : 'NEEDS_REVIEW')
  const score = scan?.compliance_score !== null && scan?.compliance_score !== undefined ? scan.compliance_score : null
  const declarations = scan?.declarations || []
  const violations = scan?.violations || []

  // Resolve image artifact path (using /storage mount)
  const evidenceUrl = scan?.evidence_image_url
    ? scan.evidence_image_url.startsWith('http')
      ? scan.evidence_image_url
      : `/${scan.evidence_image_url.replace(/\\/g, '/')}`
    : scan?.image_url
    ? scan.image_url.startsWith('http')
      ? scan.image_url
      : `/${scan.image_url.replace(/\\/g, '/')}`
    : null

  const genericNameDecl = declarations.find((d) => ['generic_name', 'product_name'].includes(d.field_name))
  const productName = genericNameDecl?.normalized_value || genericNameDecl?.raw_value || 'Packaged Commodity'

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
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {productName}
              </h1>
              <StatusBadge status={verdict} />
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
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
          <Link to="/new-inspection">
            <Button size="sm">New Inspection</Button>
          </Link>
        </div>
      </div>

      {/* 2. Processing Banner if still running */}
      {isPending && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between animate-pulse">
          <div className="flex items-center gap-3 text-sm text-blue-900 font-medium">
            <Loader2 className="w-5 h-5 animate-spin text-brand-blue" />
            <span>Inspection is currently processing. Results will update automatically.</span>
          </div>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded font-semibold uppercase">
            {scan?.status}
          </span>
        </div>
      )}

      {/* 3. Top Metrics Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Compliance Score</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {score !== null ? `${score.toFixed(1)}%` : '—'}
              </h3>
            </div>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              score && score >= 90 ? 'bg-emerald-50 text-emerald-600' : score && score >= 60 ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'
            }`}>
              <Scale className="w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Declarations Verified</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {declarations.length}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center">
              <FileCheck className="w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card className="border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Violations Detected</p>
              <h3 className="text-2xl font-bold text-slate-900 mt-1">
                {violations.length}
              </h3>
            </div>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              violations.length === 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'
            }`}>
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      {/* 4. Tab Navigation */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-6 -mb-px">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-brand-blue text-brand-blue font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Overview & Evidence
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
            <span>Violations & Citations</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
              violations.length > 0 ? 'bg-red-100 text-red-700 font-bold' : 'bg-slate-100 text-slate-600'
            }`}>
              {violations.length}
            </span>
          </button>
        </nav>
      </div>

      {/* 5. Tab Content Area */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Visual Evidence Card */}
          <Card title="Visual Evidence Overlay" subtitle="Color-coded annotations from Legal Metrology rules engine">
            {evidenceUrl ? (
              <div className="rounded-lg overflow-hidden border border-slate-200 bg-slate-900 flex items-center justify-center min-h-[300px]">
                <img
                  src={evidenceUrl}
                  alt="Inspection Evidence"
                  className="max-h-[450px] w-auto object-contain"
                />
              </div>
            ) : (
              <div className="py-16 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                <ImageIcon className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="text-xs">No visual evidence artifact available for this scan.</p>
              </div>
            )}
          </Card>

          {/* Quick Summary & Audit Notes */}
          <div className="space-y-6">
            <Card title="Compliance Verdict Summary" subtitle="Codified Legal Metrology validation verdict">
              <div className="space-y-4">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <span className="text-xs text-slate-600 font-medium">Verdict Determination</span>
                  <StatusBadge status={verdict} />
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <span className="text-xs text-slate-600 font-medium">Statutory Framework</span>
                  <span className="text-xs font-semibold text-slate-800">LMR (Packaged Commodities) Rules, 2011</span>
                </div>
                {scan?.reviewer_notes && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-1">
                    <span className="font-semibold text-amber-900">Inspector Reviewer Notes:</span>
                    <p className="text-amber-800">{scan.reviewer_notes}</p>
                  </div>
                )}
              </div>
            </Card>

            {violations.length > 0 && (
              <Card title="Primary Statutory Violations" subtitle="Immediate legal non-compliance items">
                <div className="space-y-3">
                  {violations.map((viol, idx) => (
                    <div key={viol.id || idx} className="p-3 bg-red-50/70 border border-red-200 rounded-lg text-xs space-y-1">
                      <div className="flex items-center justify-between font-semibold text-red-900">
                        <span>{viol.rule_code}</span>
                        <span className="uppercase text-[10px] px-2 py-0.5 bg-red-200 text-red-800 rounded font-bold">
                          {viol.severity}
                        </span>
                      </div>
                      <p className="text-red-800 leading-relaxed">{viol.description}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {activeTab === 'declarations' && (
        <Card title="Mandatory Declaration Audit Table" subtitle="Extracted packaging labels and confidence scores">
          {declarations.length === 0 ? (
            <div className="py-12 text-center text-slate-400">
              <FileText className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              <p className="text-xs">No declarations extracted for this scan.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 uppercase tracking-wider text-[11px] bg-slate-50">
                    <th className="py-2.5 px-3">Field Name</th>
                    <th className="py-2.5 px-3">Extracted Raw Text</th>
                    <th className="py-2.5 px-3">Normalized Value</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Confidence</th>
                    <th className="py-2.5 px-3">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {declarations.map((decl, idx) => (
                    <tr key={decl.id || idx} className="hover:bg-slate-50/80">
                      <td className="py-3 px-3 font-semibold text-slate-800 font-mono">
                        {decl.field_name}
                      </td>
                      <td className="py-3 px-3 text-slate-600 max-w-xs break-words">
                        {decl.raw_value || '—'}
                      </td>
                      <td className="py-3 px-3 text-slate-900 font-medium max-w-xs break-words">
                        {decl.normalized_value || '—'}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                          decl.status === 'detected' ? 'bg-emerald-100 text-emerald-800' : decl.status === 'uncertain' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {decl.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-600">
                        {decl.confidence !== null && decl.confidence !== undefined
                          ? `${(decl.confidence * 100).toFixed(1)}%`
                          : '—'}
                      </td>
                      <td className="py-3 px-3 text-slate-500 capitalize">
                        {decl.source || 'gemini'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'violations' && (
        <Card title="Statutory Rule Violations" subtitle="Rule-by-rule non-compliance citations">
          {violations.length === 0 ? (
            <div className="py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-800">No Rule Violations Detected</h4>
              <p className="text-xs text-slate-400 mt-1">This packaged commodity complies with all evaluated Legal Metrology rules.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {violations.map((viol, idx) => (
                <div key={viol.id || idx} className="p-4 border border-red-200 bg-red-50/50 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-red-600" />
                      <span className="font-bold text-sm text-red-950 font-mono">{viol.rule_code}</span>
                      {viol.field_name && (
                        <span className="text-xs text-red-700 bg-red-100 px-2 py-0.5 rounded font-mono">
                          {viol.field_name}
                        </span>
                      )}
                    </div>
                    <span className="text-xs font-bold uppercase px-2.5 py-0.5 bg-red-200 text-red-900 rounded-full">
                      {viol.severity}
                    </span>
                  </div>
                  <p className="text-xs text-red-900 leading-relaxed">{viol.description}</p>
                  <div className="text-[11px] text-red-700/80 pt-1">
                    Classification: <span className="font-semibold uppercase">{viol.violation_type}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

export default InspectionDetailsPage
