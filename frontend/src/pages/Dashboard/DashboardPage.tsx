import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Layers,
  Loader2,
  PlusCircle,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  Tag,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import MetricCard from '../../components/dashboard/MetricCard'
import InspectionTrend from '../../components/dashboard/InspectionTrend'
import { getAnalytics } from '../../services/scanService'
import type { ApiErrorDetail } from '../../services/api'
import type { AnalyticsPeriod, AnalyticsResponse } from '../../types'

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate()
  const isMountedRef = useRef<boolean>(true)

  const [period, setPeriod] = useState<AnalyticsPeriod>('7d')
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchAnalyticsData = async (selectedPeriod: AnalyticsPeriod) => {
    try {
      setIsLoading(true)
      setErrorMessage(null)
      const data = await getAnalytics(selectedPeriod)

      if (!isMountedRef.current) return

      setAnalytics(data)
      setIsLoading(false)
    } catch (err) {
      if (!isMountedRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsLoading(false)
      setErrorMessage(apiErr.message || 'Failed to retrieve compliance analytics telemetry.')
    }
  }

  useEffect(() => {
    isMountedRef.current = true
    fetchAnalyticsData(period)

    return () => {
      isMountedRef.current = false
    }
  }, [period])

  const totalScans = analytics?.total_scans ?? 0
  const passCount = analytics?.pass_count ?? 0
  const failCount = analytics?.fail_count ?? 0
  const reviewCount = analytics?.review_count ?? 0
  const passRate = analytics?.pass_rate ?? 0

  const passPercentage = totalScans > 0 ? (passCount / totalScans) * 100 : 0
  const failPercentage = totalScans > 0 ? (failCount / totalScans) * 100 : 0
  const reviewPercentage = totalScans > 0 ? (reviewCount / totalScans) * 100 : 0

  const categoryEntries = Object.entries(analytics?.by_category || {})
  const topViolations = analytics?.top_violations || []

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Page Header with Period Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Compliance Analytics Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time Legal Metrology (Packaged Commodities) verification metrics and audit telemetry
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Period Filter Buttons */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 shadow-2xs">
            <button
              onClick={() => setPeriod('7d')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                period === '7d'
                  ? 'bg-brand-blue text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              Last 7 Days
            </button>
            <button
              onClick={() => setPeriod('30d')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                period === '30d'
                  ? 'bg-brand-blue text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              Last 30 Days
            </button>
            <button
              onClick={() => setPeriod('all')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                period === 'all'
                  ? 'bg-brand-blue text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              All Time
            </button>
          </div>

          <button
            onClick={() => fetchAnalyticsData(period)}
            disabled={isLoading}
            title="Refresh Analytics"
            className="p-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-2xs transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-blue' : ''}`} />
          </button>

          <Button
            onClick={() => navigate('/new-inspection')}
            icon={<PlusCircle className="w-4 h-4" />}
          >
            New Inspection
          </Button>
        </div>
      </div>

      {/* Error Alert Display */}
      {errorMessage && (
        <Card className="border-red-200 bg-red-50/70">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-red-900">Analytics Fetch Error</h4>
                <p className="text-xs text-red-700 mt-0.5">{errorMessage}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => fetchAnalyticsData(period)}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Loading Skeleton View */}
      {isLoading && !analytics && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 bg-white border border-slate-200 rounded-lg p-4 animate-pulse">
                <div className="h-4 w-24 bg-slate-200 rounded mb-2" />
                <div className="h-8 w-16 bg-slate-200 rounded mb-2" />
                <div className="h-3 w-32 bg-slate-100 rounded" />
              </div>
            ))}
          </div>
          <div className="h-80 bg-white border border-slate-200 rounded-lg flex items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-brand-blue" />
              <span className="text-xs font-semibold text-slate-600">Loading Telemetry Analytics...</span>
            </div>
          </div>
        </div>
      )}

      {/* Analytics Dashboard Content */}
      {analytics && (
        <>
          {/* 2. Four Real KPI Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Total Inspections"
              value={totalScans}
              supportingText={
                totalScans > 0
                  ? `${passRate.toFixed(1)}% statutory pass rate`
                  : 'No evaluations in period'
              }
              status="INFO"
              icon={<ScanLine className="w-5 h-5" />}
            />
            <MetricCard
              title="Compliant (PASS)"
              value={passCount}
              supportingText={
                totalScans > 0
                  ? `${passPercentage.toFixed(1)}% of evaluated packages`
                  : '0.0% compliant'
              }
              status="PASS"
              icon={<CheckCircle2 className="w-5 h-5" />}
            />
            <MetricCard
              title="Non-Compliant (FAIL)"
              value={failCount}
              supportingText={
                totalScans > 0
                  ? `${failPercentage.toFixed(1)}% statutory violations`
                  : '0.0% non-compliant'
              }
              status="FAIL"
              icon={<XCircle className="w-5 h-5" />}
            />
            <MetricCard
              title="Needs Review"
              value={reviewCount}
              supportingText={
                totalScans > 0
                  ? `${reviewPercentage.toFixed(1)}% pending verification`
                  : '0.0% needs review'
              }
              status="REVIEW"
              icon={<AlertTriangle className="w-5 h-5" />}
            />
          </div>

          {/* 3. Daily Inspection Trend Chart */}
          <div>
            <InspectionTrend
              data={analytics.daily_trend || []}
              period={period}
              totalScans={totalScans}
            />
          </div>

          {/* 4. Category Breakdown & Top Violations Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Category Breakdown Card */}
            <div className="lg:col-span-2">
              <Card
                title="Category Compliance Breakdown"
                subtitle="Legal Metrology verification rates categorized by commodity"
                padding="none"
              >
                {categoryEntries.length === 0 ? (
                  <div className="py-16 text-center text-slate-400">
                    <Tag className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    <p className="text-xs font-semibold text-slate-700">No Category Breakdown Available</p>
                    <p className="text-[11px] text-slate-400 mt-1 max-w-xs mx-auto">
                      Category statistics will populate automatically as packaged commodities are scanned.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500 font-semibold select-none">
                        <tr>
                          <th className="py-3 px-5">Product Category</th>
                          <th className="py-3 px-4 text-center">Total Scans</th>
                          <th className="py-3 px-4 text-center">Pass</th>
                          <th className="py-3 px-4 text-center">Fail</th>
                          <th className="py-3 px-4 text-center">Review</th>
                          <th className="py-3 px-5 text-right">Pass Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {categoryEntries.map(([catName, stats]) => {
                          const catPassRate = stats.total > 0 ? (stats.pass / stats.total) * 100 : 0
                          return (
                            <tr key={catName} className="hover:bg-slate-50/80 transition-colors">
                              <td className="py-3.5 px-5 font-semibold text-slate-800">
                                <span className="inline-flex items-center gap-1.5">
                                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                                  {catName}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-center font-mono font-medium text-slate-700">
                                {stats.total}
                              </td>
                              <td className="py-3.5 px-4 text-center">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">
                                  {stats.pass}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-center">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-700 border border-red-200 font-mono">
                                  {stats.fail}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-center">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 font-mono">
                                  {stats.review}
                                </span>
                              </td>
                              <td className="py-3.5 px-5 text-right font-mono font-bold text-xs">
                                <span
                                  className={
                                    catPassRate >= 80
                                      ? 'text-emerald-700'
                                      : catPassRate >= 50
                                      ? 'text-amber-700'
                                      : 'text-red-700'
                                  }
                                >
                                  {catPassRate.toFixed(1)}%
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>

            {/* Right Column: Top Violations & Quick Action Card */}
            <div className="lg:col-span-1 space-y-6">
              {/* Compliance Distribution Summary Bar */}
              <Card padding="sm" className="bg-slate-900 text-white border-slate-800">
                <div className="p-2 space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                    <span>Statutory Verdict Distribution</span>
                    <span className="text-emerald-400 font-mono">
                      {passRate.toFixed(1)}% Pass Rate
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden flex">
                    <div
                      className="bg-emerald-500 h-full transition-all duration-500"
                      style={{ width: `${passPercentage}%` }}
                      title={`Compliant: ${passCount} (${passPercentage.toFixed(1)}%)`}
                    />
                    <div
                      className="bg-red-500 h-full transition-all duration-500"
                      style={{ width: `${failPercentage}%` }}
                      title={`Non-Compliant: ${failCount} (${failPercentage.toFixed(1)}%)`}
                    />
                    <div
                      className="bg-amber-500 h-full transition-all duration-500"
                      style={{ width: `${reviewPercentage}%` }}
                      title={`Needs Review: ${reviewCount} (${reviewPercentage.toFixed(1)}%)`}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> {passCount} Pass
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> {failCount} Fail
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> {reviewCount} Review
                    </span>
                  </div>
                </div>
              </Card>

              {/* Top Statutory Violations Card */}
              <Card
                title="Top Rule Infractions"
                subtitle="Most frequent non-compliance citations"
              >
                {topViolations.length === 0 ? (
                  <div className="py-8 text-center text-slate-400">
                    <ShieldAlert className="w-7 h-7 mx-auto mb-1.5 text-slate-300" />
                    <p className="text-xs font-semibold text-slate-700">Zero Infractions Recorded</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      No statutory violations detected in this evaluation period.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {topViolations.slice(0, 5).map((viol, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-lg border border-red-100 bg-red-50/50 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-red-950 font-mono">
                            {viol.rule_code}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-200 text-red-900">
                            {viol.count} {viol.count === 1 ? 'citation' : 'citations'}
                          </span>
                        </div>
                        <p className="text-slate-700 text-[11px] leading-relaxed line-clamp-2">
                          {viol.description}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Quick Action Card */}
              <Card
                title="Start New Package Scan"
                subtitle="Verification against Legal Metrology Rules, 2011"
                className="border-slate-200"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 text-brand-blue flex items-center justify-center">
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Upload a packaged commodity label to verify mandatory declarations against the legal framework.
                  </p>
                  <Button
                    onClick={() => navigate('/new-inspection')}
                    className="w-full"
                    icon={<ArrowRight className="w-4 h-4" />}
                  >
                    Analyze Package
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default DashboardPage
