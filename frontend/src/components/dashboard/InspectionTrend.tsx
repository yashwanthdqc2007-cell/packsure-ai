import React from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import Card from '../common/Card'
import { ActivityDay } from '../../mock'

export interface InspectionTrendProps {
  data: ActivityDay[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{
    value: number
    name: string
    payload: ActivityDay
  }>
  label?: string
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    return (
      <div className="bg-slate-900 text-white p-3 rounded-lg shadow-lg border border-slate-700 text-xs space-y-1">
        <p className="font-semibold text-slate-300 pb-1 border-b border-slate-700">
          {label} — {data.scans} Scans Total
        </p>
        <div className="flex items-center justify-between gap-4 pt-0.5 text-emerald-400">
          <span>Compliant:</span>
          <span className="font-mono font-medium">{data.compliant}</span>
        </div>
        <div className="flex items-center justify-between gap-4 text-red-400">
          <span>Non-Compliant:</span>
          <span className="font-mono font-medium">{data.nonCompliant}</span>
        </div>
        <div className="flex items-center justify-between gap-4 text-amber-400">
          <span>Needs Review:</span>
          <span className="font-mono font-medium">{data.needsReview}</span>
        </div>
      </div>
    )
  }
  return null
}

export const InspectionTrend: React.FC<InspectionTrendProps> = ({ data }) => {
  return (
    <Card
      title="Inspection Activity"
      subtitle="Scans processed over the last 7 days"
      padding="none"
      className="h-full flex flex-col"
    >
      <div className="p-6 pt-4 flex-1 min-h-[260px]">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 10, right: 15, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorScans" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#E2E8F0"
              />
              <XAxis
                dataKey="day"
                tickLine={false}
                axisLine={{ stroke: '#E2E8F0' }}
                tick={{ fill: '#64748B', fontSize: 12 }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#64748B', fontSize: 12 }}
                domain={[0, 'dataMax + 5']}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="scans"
                name="Total Scans"
                stroke="#2563EB"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#colorScans)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
        <span>Weekly throughput: 128 items evaluated</span>
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-brand-blue" /> Total Activity
          </span>
        </span>
      </div>
    </Card>
  )
}

export default InspectionTrend
