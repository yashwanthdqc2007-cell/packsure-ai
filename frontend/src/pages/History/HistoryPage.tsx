import React from 'react'
import Card from '../../components/common/Card'
import { History, Search, Filter } from 'lucide-react'
import { Link } from 'react-router-dom'

export const HistoryPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Inspection History
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Search, filter, and audit past packaged commodity compliance records
        </p>
      </div>

      <Card
        title="Historical Scan Archive"
        subtitle="Chronological log of verified package inspections"
        headerAction={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500">
              <Search className="w-3.5 h-3.5" />
              <span>Search scans...</span>
            </div>
            <button className="p-1.5 text-slate-500 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50">
              <Filter className="w-4 h-4" />
            </button>
          </div>
        }
      >
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
            <History className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-700">
            Inspection History Table Ready
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mt-1 mb-4">
            Past scans with timestamps, package brand, category, verdict status, and
            quick links to audit reports will be tabulated here.
          </p>
          <div className="flex items-center gap-2 text-xs">
            <Link
              to="/inspection/DEMO-001"
              className="text-brand-blue hover:underline font-medium"
            >
              View sample inspection record (DEMO-001) →
            </Link>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default HistoryPage
