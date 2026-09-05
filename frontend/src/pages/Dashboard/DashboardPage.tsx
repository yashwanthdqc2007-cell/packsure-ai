import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PlusCircle,
  ScanLine,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  UploadCloud,
  ArrowRight,
} from 'lucide-react'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import MetricCard from '../../components/dashboard/MetricCard'
import InspectionTrend from '../../components/dashboard/InspectionTrend'
import RecentInspections from '../../components/dashboard/RecentInspections'
import {
  mockDashboardMetrics,
  mockWeeklyActivity,
  mockRecentInspections,
} from '../../mock'

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Inspection workstation overview and recent activity
          </p>
        </div>
        <Button
          onClick={() => navigate('/new-inspection')}
          icon={<PlusCircle className="w-4 h-4" />}
        >
          New Inspection
        </Button>
      </div>

      {/* 2. Four Compact Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title={mockDashboardMetrics[0].title}
          value={mockDashboardMetrics[0].value}
          supportingText={mockDashboardMetrics[0].changeText}
          status={mockDashboardMetrics[0].status}
          icon={<ScanLine className="w-5 h-5" />}
        />
        <MetricCard
          title={mockDashboardMetrics[1].title}
          value={mockDashboardMetrics[1].value}
          supportingText={mockDashboardMetrics[1].changeText}
          status={mockDashboardMetrics[1].status}
          icon={<CheckCircle2 className="w-5 h-5" />}
        />
        <MetricCard
          title={mockDashboardMetrics[2].title}
          value={mockDashboardMetrics[2].value}
          supportingText={mockDashboardMetrics[2].changeText}
          status={mockDashboardMetrics[2].status}
          icon={<XCircle className="w-5 h-5" />}
        />
        <MetricCard
          title={mockDashboardMetrics[3].title}
          value={mockDashboardMetrics[3].value}
          supportingText={mockDashboardMetrics[3].changeText}
          status={mockDashboardMetrics[3].status}
          icon={<AlertTriangle className="w-5 h-5" />}
        />
      </div>

      {/* 3. Inspection Trend Activity */}
      <div>
        <InspectionTrend data={mockWeeklyActivity} />
      </div>

      {/* 4. Recent Inspections & 5. Quick Action */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentInspections inspections={mockRecentInspections} />
        </div>

        <div className="lg:col-span-1 space-y-6">
          {/* Quick Action Card */}
          <Card
            title="Start a new inspection"
            subtitle="Verification against Legal Metrology Rules, 2011"
            className="border-slate-200"
          >
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-lg bg-blue-50 text-brand-blue flex items-center justify-center">
                <UploadCloud className="w-5 h-5" />
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Upload a package image and check its declarations against the applicable compliance rules.
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

          {/* Inspection Breakdown Summary Card */}
          <Card padding="sm" className="bg-slate-900 text-white border-slate-800">
            <div className="p-2 space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                <span>Compliance Distribution</span>
                <span className="text-emerald-400 font-mono">59.4% Pass</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden flex">
                <div
                  className="bg-emerald-500 h-full"
                  style={{ width: '59.4%' }}
                  title="Compliant (59.4%)"
                />
                <div
                  className="bg-red-500 h-full"
                  style={{ width: '26.6%' }}
                  title="Non-Compliant (26.6%)"
                />
                <div
                  className="bg-amber-500 h-full"
                  style={{ width: '14.0%' }}
                  title="Needs Review (14.0%)"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> 76 Pass
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> 34 Fail
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> 18 Review
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
