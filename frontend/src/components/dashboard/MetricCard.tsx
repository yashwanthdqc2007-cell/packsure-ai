import React from 'react'
import Card from '../common/Card'

export interface MetricCardProps {
  title: string
  value: number | string
  supportingText: string
  status?: 'PASS' | 'FAIL' | 'REVIEW' | 'INFO'
  icon: React.ReactNode
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  supportingText,
  status = 'INFO',
  icon,
}) => {
  const statusStyles = {
    PASS: {
      accent: 'border-l-4 border-l-verdict-pass',
      valueColor: 'text-emerald-700',
      iconBg: 'bg-emerald-50 text-emerald-600',
      badgeBg: 'text-emerald-700 bg-emerald-50',
    },
    FAIL: {
      accent: 'border-l-4 border-l-verdict-fail',
      valueColor: 'text-red-700',
      iconBg: 'bg-red-50 text-red-600',
      badgeBg: 'text-red-700 bg-red-50',
    },
    REVIEW: {
      accent: 'border-l-4 border-l-verdict-review',
      valueColor: 'text-amber-700',
      iconBg: 'bg-amber-50 text-amber-600',
      badgeBg: 'text-amber-700 bg-amber-50',
    },
    INFO: {
      accent: 'border-l-4 border-l-brand-blue',
      valueColor: 'text-slate-900',
      iconBg: 'bg-blue-50 text-brand-blue',
      badgeBg: 'text-slate-600 bg-slate-100',
    },
  }

  const current = statusStyles[status]

  return (
    <Card padding="sm" className={`h-full ${current.accent}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {title}
          </p>
          <div className={`text-2xl font-bold mt-1 tracking-tight ${current.valueColor}`}>
            {value}
          </div>
          <p className="text-xs text-slate-500 mt-1 font-medium">
            {supportingText}
          </p>
        </div>
        <div className={`p-2.5 rounded-lg flex-shrink-0 ${current.iconBg}`}>
          {icon}
        </div>
      </div>
    </Card>
  )
}

export default MetricCard
