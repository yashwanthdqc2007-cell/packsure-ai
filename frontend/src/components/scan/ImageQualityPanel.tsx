import React from 'react'
import { CheckCircle2, Clock, Sparkles } from 'lucide-react'

export interface ImageQualityPanelProps {
  hasImage: boolean
}

export const ImageQualityPanel: React.FC<ImageQualityPanelProps> = ({ hasImage }) => {
  const qualityMetrics = [
    { label: 'Sharpness', status: hasImage ? 'Good' : 'Pending' },
    { label: 'Lighting', status: hasImage ? 'Good' : 'Pending' },
    { label: 'Coverage', status: hasImage ? 'Good' : 'Pending' },
    { label: 'Orientation', status: hasImage ? 'Good' : 'Pending' },
  ]

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-800">
            Image Quality Verification
          </span>
        </div>
        {!hasImage ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
            <Clock className="w-3 h-3" />
            Waiting for image
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
            <CheckCircle2 className="w-3 h-3" />
            Passed Quality Checks
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3">
        {qualityMetrics.map((metric) => (
          <div
            key={metric.label}
            className={`p-2.5 rounded-lg border text-center transition-colors ${
              hasImage
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-800'
                : 'bg-slate-50 border-slate-200 text-slate-500'
            }`}
          >
            <p className="text-[11px] font-medium text-slate-500">
              {metric.label}
            </p>
            <div className="flex items-center justify-center gap-1 mt-1">
              {hasImage ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span className="text-xs font-bold text-emerald-700">Good</span>
                </>
              ) : (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                  <span className="text-xs font-medium text-slate-400">—</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ImageQualityPanel
