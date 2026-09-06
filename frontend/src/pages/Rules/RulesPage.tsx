import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Code2,
  Loader2,
  RefreshCw,
  Scale,
  Search,
  Tag,
  X,
  XCircle,
} from 'lucide-react'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import StatusBadge from '../../components/common/StatusBadge'
import { getRules } from '../../services/scanService'
import type { ApiErrorDetail } from '../../services/api'
import type { RuleItem, RulesQueryParams, RulesResponse } from '../../types'

const CATEGORY_FILTER_OPTIONS = [
  'All Categories',
  'Food Grains',
  'Edible Oil',
  'Packaged Food',
  'Snacks',
  'Beverages',
  'Dairy',
  'Cosmetics',
  'Pharmaceuticals',
  'Electronics',
  'Apparel',
  'General',
]

export const RulesPage: React.FC = () => {
  const isMountedRef = useRef<boolean>(true)
  const requestIdRef = useRef<number>(0)

  // API Filter States
  const [selectedCategory, setSelectedCategory] = useState<string>('All Categories')
  const [activeOnly, setActiveOnly] = useState<boolean>(true)

  // Client-Side Search
  const [searchTerm, setSearchTerm] = useState<string>('')

  // UI Interactive State
  const [expandedRuleId, setExpandedRuleId] = useState<string | null>(null)

  // Data & Request States
  const [rulesData, setRulesData] = useState<RulesResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchRulesCatalog = useCallback(async () => {
    const currentReqId = ++requestIdRef.current
    setIsLoading(true)
    setErrorMessage(null)

    const params: RulesQueryParams = {
      active_only: activeOnly,
    }

    if (selectedCategory && selectedCategory !== 'All Categories') {
      params.category = selectedCategory.toLowerCase()
    }

    try {
      const data = await getRules(params)
      if (!isMountedRef.current || currentReqId !== requestIdRef.current) return

      setRulesData(data)
      setIsLoading(false)
    } catch (err) {
      if (!isMountedRef.current || currentReqId !== requestIdRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsLoading(false)
      setErrorMessage(apiErr.message || 'Failed to retrieve Legal Metrology rule catalog.')
    }
  }, [selectedCategory, activeOnly])

  useEffect(() => {
    isMountedRef.current = true
    fetchRulesCatalog()

    return () => {
      isMountedRef.current = false
    }
  }, [fetchRulesCatalog])

  // Filter rules locally by search term
  const displayedRules: RuleItem[] = useMemo(() => {
    const rules = rulesData?.rules || []
    if (!searchTerm.trim()) return rules

    const lowerQuery = searchTerm.trim().toLowerCase()
    return rules.filter(
      (r) =>
        r.rule_code.toLowerCase().includes(lowerQuery) ||
        r.title.toLowerCase().includes(lowerQuery) ||
        r.description.toLowerCase().includes(lowerQuery) ||
        r.field_name.toLowerCase().includes(lowerQuery) ||
        r.validation_type.toLowerCase().includes(lowerQuery)
    )
  }, [rulesData, searchTerm])

  const getSeverityBadge = (severity: string) => {
    const s = severity.toLowerCase()
    if (s === 'critical') {
      return 'bg-red-100 text-red-800 border-red-200'
    }
    if (s === 'major') {
      return 'bg-orange-100 text-orange-800 border-orange-200'
    }
    if (s === 'minor') {
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    }
    return 'bg-slate-100 text-slate-700 border-slate-200'
  }

  const toggleExpand = (id: string) => {
    setExpandedRuleId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Legal Metrology Codified Rules Catalog
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Deterministic statutory verification rules codified from Legal Metrology (Packaged Commodities) Rules, 2011
          </p>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge status="PASS" label="Engine Active (v2011/2021)" />
          <button
            onClick={fetchRulesCatalog}
            disabled={isLoading}
            title="Refresh Rules"
            className="p-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-2xs transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-blue' : ''}`} />
          </button>
        </div>
      </div>

      {/* 2. Statutory Framework Banner */}
      <Card padding="sm" className="bg-slate-900 text-white border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-2">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600/30 text-blue-400 flex items-center justify-center flex-shrink-0">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                Statutory Authority: Legal Metrology (Packaged Commodities) Rules, 2011
              </h3>
              <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">
                Rules 6(1), 7, 8, and 9 govern mandatory declarations, Principal Display Panel (PDP) placement, font heights, and unit price standards.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono text-slate-300 bg-slate-800/80 px-3 py-2 rounded-lg border border-slate-700 self-start md:self-auto">
            <div>
              <span className="text-slate-400">Total Rules:</span>{' '}
              <strong className="text-emerald-400 font-bold">{rulesData?.total ?? '—'}</strong>
            </div>
            <span>•</span>
            <div>
              <span className="text-slate-400">Active Category:</span>{' '}
              <span className="text-blue-300 capitalize">{rulesData?.category || 'All'}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* 3. Filter & Search Workstation */}
      <Card padding="sm" className="border-slate-200 bg-white">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
            {/* Category Dropdown (API Param: category) */}
            <div className="w-full sm:w-48">
              <label htmlFor="category-select" className="sr-only">Category</label>
              <select
                id="category-select"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full text-xs py-2 px-3 rounded-lg border border-slate-300 bg-white text-slate-800 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
              >
                {CATEGORY_FILTER_OPTIONS.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* Active Only Switch (API Param: active_only) */}
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer select-none self-start sm:self-center">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(e.target.checked)}
                className="rounded border-slate-300 text-brand-blue focus:ring-brand-blue h-4 w-4"
              />
              <span>Active Rules Only</span>
            </label>
          </div>

          {/* Local Search Input */}
          <div className="w-full sm:w-72 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search rule title, code, or field..."
              className="w-full text-xs pl-9 pr-8 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder-slate-400 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                title="Clear Search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* 4. Error Alert */}
      {errorMessage && (
        <Card className="border-red-200 bg-red-50/70">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-red-900">Failed to Load Rules Catalog</h4>
                <p className="text-xs text-red-700 mt-0.5">{errorMessage}</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchRulesCatalog}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Retry
            </Button>
          </div>
        </Card>
      )}

      {/* 5. Rules Catalog Grid */}
      {isLoading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center space-y-3 bg-white rounded-lg border border-slate-200">
          <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
          <h4 className="text-sm font-semibold text-slate-700">Loading Legal Metrology Rule Catalog...</h4>
          <p className="text-xs text-slate-400">Querying deterministic compliance validator specifications...</p>
        </div>
      ) : displayedRules.length === 0 ? (
        <div className="py-20 text-center flex flex-col items-center justify-center space-y-3 bg-white rounded-lg border border-slate-200 max-w-md mx-auto px-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mb-1">
            <BookOpen className="w-6 h-6" />
          </div>
          <h4 className="text-base font-semibold text-slate-800">No Codified Rules Found</h4>
          <p className="text-xs text-slate-500 leading-relaxed">
            {searchTerm
              ? `No rules match your search "${searchTerm}". Try searching for another rule code, title, or field name.`
              : 'No rules are configured for the selected category or active filter state.'}
          </p>
          {(searchTerm || selectedCategory !== 'All Categories') && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setSearchTerm('')
                setSelectedCategory('All Categories')
              }}
            >
              Reset Filters
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {displayedRules.map((rule) => {
            const isExpanded = expandedRuleId === rule.id

            return (
              <div
                key={rule.id}
                className={`p-5 rounded-lg border bg-white shadow-2xs transition-all ${
                  isExpanded ? 'border-brand-blue ring-1 ring-brand-blue/20' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {rule.rule_code}
                      </span>
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${getSeverityBadge(
                          rule.severity
                        )}`}
                      >
                        {rule.severity}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">
                        v{rule.version}
                      </span>
                    </div>

                    <h4 className="text-sm font-semibold text-slate-900 mt-2">
                      {rule.title}
                    </h4>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {rule.active ? (
                      <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                        <CheckCircle2 className="w-3 h-3" />
                        Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                        <XCircle className="w-3 h-3" />
                        Inactive
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                  {rule.description}
                </p>

                <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-100 text-xs">
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 flex-wrap">
                    <span className="inline-flex items-center gap-1">
                      <Tag className="w-3 h-3 text-slate-400" />
                      Field: <code className="font-mono text-slate-700 font-semibold">{rule.field_name}</code>
                    </span>
                    <span>•</span>
                    <span className="inline-flex items-center gap-1">
                      <Code2 className="w-3 h-3 text-slate-400" />
                      Validator: <span className="font-mono text-slate-700">{rule.validation_type}</span>
                    </span>
                  </div>

                  <button
                    onClick={() => toggleExpand(rule.id)}
                    className="text-xs text-brand-blue hover:text-brand-blueHover font-medium inline-flex items-center gap-0.5"
                  >
                    <span>{isExpanded ? 'Less' : 'Details'}</span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Expanded Details Drawer */}
                {isExpanded && (
                  <div className="mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2 animate-in fade-in">
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <span className="text-slate-400">Rule Identifier: </span>
                        <code className="font-mono text-slate-800">{rule.id}</code>
                      </div>
                      <div>
                        <span className="text-slate-400">Enactment Version: </span>
                        <span className="font-mono text-slate-800">{rule.version} (LMR 2011)</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Severity Tier: </span>
                        <span className="font-semibold uppercase text-slate-800">{rule.severity}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Validation Mode: </span>
                        <span className="font-mono text-slate-800">{rule.validation_type}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default RulesPage
