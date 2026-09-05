import React from 'react'

export type StatusType = 'PASS' | 'FAIL' | 'REVIEW' | 'INFO' | 'PENDING'

export interface StatusBadgeProps {
  status: StatusType | string
  label?: string
  size?: 'sm' | 'md'
  showDot?: boolean
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = 'md',
  showDot = true,
}) => {
  const normalizedStatus = status.toUpperCase()

  const config: Record<
    string,
    { bg: string; text: string; border: string; dot: string; defaultLabel: string }
  > = {
    PASS: {
      bg: 'bg-verdict-passBg',
      text: 'text-emerald-700',
      border: 'border-verdict-passBorder',
      dot: 'bg-verdict-pass',
      defaultLabel: 'PASS',
    },
    FAIL: {
      bg: 'bg-verdict-failBg',
      text: 'text-red-700',
      border: 'border-verdict-failBorder',
      dot: 'bg-verdict-fail',
      defaultLabel: 'FAIL',
    },
    REVIEW: {
      bg: 'bg-verdict-reviewBg',
      text: 'text-amber-700',
      border: 'border-verdict-reviewBorder',
      dot: 'bg-verdict-review',
      defaultLabel: 'NEEDS REVIEW',
    },
    PENDING: {
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-200',
      dot: 'bg-blue-500 animate-pulse',
      defaultLabel: 'PROCESSING',
    },
    INFO: {
      bg: 'bg-slate-100',
      text: 'text-slate-700',
      border: 'border-slate-200',
      dot: 'bg-slate-400',
      defaultLabel: 'INFO',
    },
  }

  const current = config[normalizedStatus] || config['INFO']
  const displayLabel = label || current.defaultLabel

  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5 gap-1.5 font-medium',
    md: 'text-xs px-2.5 py-1 gap-2 font-semibold tracking-wide',
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border ${current.bg} ${current.text} ${current.border} ${sizeStyles[size]}`}
    >
      {showDot && (
        <span
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${current.dot}`}
          aria-hidden="true"
        />
      )}
      <span>{displayLabel}</span>
    </span>
  )
}

export default StatusBadge
