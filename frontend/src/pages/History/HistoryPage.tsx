import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  History,
  Loader2,
  PlusCircle,
  RefreshCw,
  RotateCcw,
  Search,
  Tag,
  X,
} from 'lucide-react'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import StatusBadge from '../../components/common/StatusBadge'
import { getHistory } from '../../services/scanService'
import type { ApiErrorDetail } from '../../services/api'
import type {
  ComplianceVerdict,
  HistoryQueryParams,
  ScanHistoryItem,
  ScanHistoryResponse,
} from '../../types'

const CATEGORY_OPTIONS = [
  'Food Grains',
  'Edible Oil',
  'Packaged Food',
  'Snacks',
  'Beverages',
  'Dairy',
  'Cosmetics',
  'Pharmaceuticals',
  'General Commodity',
]

const PAGE_SIZE = 10

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate()
  const isMountedRef = useRef<boolean>(true)
  const requestIdRef = useRef<number>(0)

  // Filter States
  const [searchInput, setSearchInput] = useState<string>('')
  const [debouncedSearch, setDebouncedSearch] = useState<string>('')
  const [selectedVerdict, setSelectedVerdict] = useState<ComplianceVerdict | ''>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [fromDate, setFromDate] = useState<string>('')
  const [toDate, setToDate] = useState<string>('')
  const [currentPage, setCurrentPage] = useState<number>(1)

  // Data & Request States
  const [historyData, setHistoryData] = useState<ScanHistoryResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Debounce search input by 350ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
      setCurrentPage(1)
    }, 350)
    return () => clearTimeout(handler)
  }, [searchInput])

  const fetchHistory = useCallback(async () => {
    const currentReqId = ++requestIdRef.current
    setIsLoading(true)
    setErrorMessage(null)

    const params: HistoryQueryParams = {
      page: currentPage,
      limit: PAGE_SIZE,
    }

    if (debouncedSearch) {
      params.search = debouncedSearch
    }
    if (selectedVerdict) {
      params.verdict = selectedVerdict
    }
    if (selectedCategory) {
      params.category = selectedCategory
    }
    if (fromDate) {
      params.from_date = fromDate
    }
    if (toDate) {
      params.to_date = toDate
    }

    try {
      const data = await getHistory(params)
      if (!isMountedRef.current || currentReqId !== requestIdRef.current) return

      setHistoryData(data)
      setIsLoading(false)
    } catch (err) {
      if (!isMountedRef.current || currentReqId !== requestIdRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsLoading(false)
      setErrorMessage(apiErr.message || 'Failed to fetch inspection history records.')
    }
  }, [currentPage, debouncedSearch, selectedVerdict, selectedCategory, fromDate, toDate])

  useEffect(() => {
    isMountedRef.current = true
    fetchHistory()

    return () => {
      isMountedRef.current = false
    }
  }, [fetchHistory])

  const resetFilters = () => {
    setSearchInput('')
    setDebouncedSearch('')
    setSelectedVerdict('')
    setSelectedCategory('')
    setFromDate('')
    setToDate('')
    setCurrentPage(1)
  }

  const hasActiveFilters =
    Boolean(debouncedSearch) ||
    Boolean(selectedVerdict) ||
    Boolean(selectedCategory) ||
    Boolean(fromDate) ||
    Boolean(toDate)

  const results: ScanHistoryItem[] = historyData?.results || []
  const total = historyData?.total ?? 0
  const totalPages = historyData?.total_pages ?? 1
  const startItem = total > 0 ? (currentPage - 1) * PAGE_SIZE + 1 : 0
  const endItem = total > 0 ? Math.min(currentPage * PAGE_SIZE, total) : 0

  const getScoreBadgeClass = (verdict?: ComplianceVerdict | null, score?: number | null) => {
    if (verdict === 'PASS' || (score !== null && score !== undefined && score >= 90)) {
      return 'text-emerald-700 bg-emerald-50 border-emerald-200'
    }
    if (verdict === 'FAIL' || (score !== null && score !== undefined && score < 60)) {
      return 'text-red-700 bg-red-50 border-red-200'
    }
    return 'text-amber-700 bg-amber-50 border-amber-200'
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Inspection History & Audit Archive
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Search, filter, and review historical Legal Metrology package compliance evaluations
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => navigate('/new-inspection')}
            icon={<PlusCircle className="w-4 h-4" />}
          >
            New Inspection
          </Button>
        </div>
      </div>

      {/* 2. Search & Filter Bar Card */}
      <Card padding="sm" className="border-slate-200 bg-white">
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3">
            {/* Search Input */}
            <div className="lg:col-span-4 relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by package name or scan ID..."
                className="w-full text-xs pl-9 pr-8 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder-slate-400 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
              />
              {searchInput && (
                <button
                  onClick={() => setSearchInput('')}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Verdict Filter */}
            <div className="lg:col-span-2">
              <select
                value={selectedVerdict}
                onChange={(e) => {
                  setSelectedVerdict(e.target.value as ComplianceVerdict | '')
                  setCurrentPage(1)
                }}
                className="w-full text-xs py-2 px-2.5 rounded-lg border border-slate-300 bg-white text-slate-800 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
              >
                <option value="">All Verdicts</option>
                <option value="PASS">PASS (Compliant)</option>
                <option value="FAIL">FAIL (Non-Compliant)</option>
                <option value="NEEDS_REVIEW">NEEDS_REVIEW (Officer Review)</option>
              </select>
            </div>

            {/* Category Filter */}
            <div className="lg:col-span-2">
              <select
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value)
                  setCurrentPage(1)
                }}
                className="w-full text-xs py-2 px-2.5 rounded-lg border border-slate-300 bg-white text-slate-800 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
              >
                <option value="">All Categories</option>
                {CATEGORY_OPTIONS.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* From Date */}
            <div className="lg:col-span-2">
              <div className="relative">
                <input
                  type="date"
                  value={fromDate}
                  onChange={(e) => {
                    setFromDate(e.target.value)
                    setCurrentPage(1)
                  }}
                  title="From Date"
                  className="w-full text-xs py-2 px-2.5 rounded-lg border border-slate-300 bg-white text-slate-700 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
              </div>
            </div>

            {/* To Date & Reset Actions */}
            <div className="lg:col-span-2 flex items-center gap-2">
              <input
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value)
                  setCurrentPage(1)
                }}
                title="To Date"
                className="w-full text-xs py-2 px-2.5 rounded-lg border border-slate-300 bg-white text-slate-700 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
              />
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  title="Clear all filters"
                  className="p-2 text-slate-500 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50 flex-shrink-0 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Active Filter Chips Bar */}
          {hasActiveFilters && (
            <div className="flex items-center gap-2 pt-2 border-t border-slate-100 text-xs text-slate-500 flex-wrap">
              <span className="font-semibold text-slate-600">Active Filters:</span>
              {debouncedSearch && (
                <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                  Keyword: "{debouncedSearch}"
                  <button onClick={() => setSearchInput('')} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedVerdict && (
                <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                  Verdict: {selectedVerdict}
                  <button onClick={() => setSelectedVerdict('')} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedCategory && (
                <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                  Category: {selectedCategory}
                  <button onClick={() => setSelectedCategory('')} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {fromDate && (
                <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                  From: {fromDate}
                  <button onClick={() => setFromDate('')} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {toDate && (
                <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                  To: {toDate}
                  <button onClick={() => setToDate('')} className="hover:text-red-600">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              <button
                onClick={resetFilters}
                className="text-xs text-brand-blue font-semibold hover:underline ml-auto"
              >
                Reset all filters
              </button>
            </div>
          )}
        </div>
      </Card>

      {/* 3. Error Alert */}
      {errorMessage && (
        <Card className="border-red-200 bg-red-50/70">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-red-900">Failed to Load History</h4>
                <p className="text-xs text-red-700 mt-0.5">{errorMessage}</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchHistory}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Retry
            </Button>
          </div>
        </Card>
      )}

      {/* 4. History Table Card */}
      <Card padding="none" className="overflow-hidden border-slate-200">
        {/* Table Content */}
        {isLoading ? (
          <div className="py-20 text-center flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
            <h4 className="text-sm font-semibold text-slate-700">Loading Inspection Archive...</h4>
            <p className="text-xs text-slate-400">Fetching audit records from PackSure backend...</p>
          </div>
        ) : results.length === 0 ? (
          <div className="py-20 text-center flex flex-col items-center justify-center space-y-3 max-w-md mx-auto px-4">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mb-1">
              <History className="w-6 h-6" />
            </div>
            <h4 className="text-base font-semibold text-slate-800">
              {hasActiveFilters ? 'No Matching Inspection Records' : 'No Scan History Available'}
            </h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              {hasActiveFilters
                ? 'No past inspections match your specified keyword or filter criteria. Try adjusting or clearing your filters.'
                : 'Your inspection log is currently empty. Run your first package scan to generate compliance audit records.'}
            </p>
            <div className="pt-2 flex gap-3">
              {hasActiveFilters ? (
                <Button size="sm" variant="outline" onClick={resetFilters}>
                  Clear Active Filters
                </Button>
              ) : (
                <Button size="sm" onClick={() => navigate('/new-inspection')}>
                  Start First Inspection
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500 font-semibold select-none">
                <tr>
                  <th scope="col" className="py-3 px-5">Package / Commodity</th>
                  <th scope="col" className="py-3 px-4">Category</th>
                  <th scope="col" className="py-3 px-4">Date & Time</th>
                  <th scope="col" className="py-3 px-4">Verdict</th>
                  <th scope="col" className="py-3 px-4 text-center">Compliance Score</th>
                  <th scope="col" className="py-3 px-4 text-center">Pipeline Status</th>
                  <th scope="col" className="py-3 px-5 text-right"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {results.map((item) => {
                  const displayVerdict = item.verdict || (item.status === 'complete' ? 'PASS' : 'NEEDS_REVIEW')
                  const score = item.compliance_score !== null && item.compliance_score !== undefined ? item.compliance_score : null
                  const displayTitle = item.product_name || item.category || 'Packaged Commodity'

                  return (
                    <tr
                      key={item.id}
                      onClick={() => navigate(`/inspection/${item.id}`)}
                      className="hover:bg-slate-50/90 cursor-pointer transition-colors group"
                    >
                      {/* Product Name & Scan ID */}
                      <td className="py-3.5 px-5">
                        <div className="font-semibold text-slate-900 group-hover:text-brand-blue transition-colors text-sm">
                          {displayTitle}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          ID: <span className="text-slate-600">{item.id}</span>
                        </div>
                      </td>

                      {/* Commodity Category */}
                      <td className="py-3.5 px-4 text-slate-700">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-100 font-medium text-[11px]">
                          <Tag className="w-3 h-3 text-slate-400" />
                          {item.category || 'General Package'}
                        </span>
                      </td>

                      {/* Scanned Timestamp */}
                      <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-xs text-slate-700">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{new Date(item.scanned_at).toLocaleDateString()}</span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {new Date(item.scanned_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>

                      {/* Verdict Status Badge */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <StatusBadge status={displayVerdict} size="sm" />
                      </td>

                      {/* Compliance Score */}
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <span
                          className={`inline-flex items-center justify-center font-mono font-bold text-xs px-2.5 py-0.5 rounded border ${getScoreBadgeClass(
                            item.verdict,
                            score
                          )}`}
                        >
                          {score !== null ? `${score.toFixed(1)}%` : '—'}
                        </span>
                      </td>

                      {/* Lifecycle Status */}
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                            item.status === 'complete'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : item.status === 'processing' || item.status === 'pending'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                              : 'bg-red-50 text-red-700 border border-red-200'
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>

                      {/* Action Arrow */}
                      <td className="py-3.5 px-5 text-right whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-blue group-hover:underline">
                          <span>View Audit</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* 5. Pagination Controls Footer */}
        {!isLoading && results.length > 0 && (
          <div className="px-5 py-3.5 border-t border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-600 select-none">
            <div>
              Showing <strong className="font-semibold text-slate-900">{startItem}</strong> to{' '}
              <strong className="font-semibold text-slate-900">{endItem}</strong> of{' '}
              <strong className="font-semibold text-slate-900">{total}</strong> inspection records
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1 || isLoading}
                icon={<ChevronLeft className="w-3.5 h-3.5" />}
              >
                Previous
              </Button>

              <span className="text-xs text-slate-500 font-mono px-2">
                Page {currentPage} of {totalPages}
              </span>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages || isLoading}
                icon={<ChevronRight className="w-3.5 h-3.5" />}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

export default HistoryPage
