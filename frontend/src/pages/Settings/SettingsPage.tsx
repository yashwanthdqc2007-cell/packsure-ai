import React from 'react'
import Card from '../../components/common/Card'
import StatusBadge from '../../components/common/StatusBadge'

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Settings
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Workstation configuration, OCR parameters, and integration endpoints
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Extraction & OCR Engine" subtitle="Vision model and OCR thresholds">
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-slate-100 text-xs">
              <span className="text-slate-600 font-medium">OCR Preprocessor</span>
              <span className="text-slate-800 font-mono">OpenCV (Adaptive Threshold)</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-slate-100 text-xs">
              <span className="text-slate-600 font-medium">Vision Extraction Engine</span>
              <span className="text-slate-800 font-mono">Tesseract + Gemini Vision</span>
            </div>
            <div className="flex items-center justify-between py-2 text-xs">
              <span className="text-slate-600 font-medium">OCR Confidence Threshold</span>
              <span className="text-slate-800 font-mono">75%</span>
            </div>
          </div>
        </Card>

        <Card title="System Connectivity" subtitle="Backend API and database status">
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-slate-100 text-xs">
              <span className="text-slate-600 font-medium">Backend API</span>
              <StatusBadge status="PASS" label="http://localhost:8000" size="sm" />
            </div>
            <div className="flex items-center justify-between py-2 border-b border-slate-100 text-xs">
              <span className="text-slate-600 font-medium">Rule Engine</span>
              <StatusBadge status="PASS" label="Deterministic v1.0" size="sm" />
            </div>
            <div className="flex items-center justify-between py-2 text-xs">
              <span className="text-slate-600 font-medium">Environment</span>
              <span className="text-slate-800 font-mono">Development (SIH26034)</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default SettingsPage
