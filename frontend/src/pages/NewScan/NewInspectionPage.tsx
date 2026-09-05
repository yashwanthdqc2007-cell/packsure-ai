import React from 'react'
import Card from '../../components/common/Card'
import { ScanLine, UploadCloud } from 'lucide-react'

export const NewInspectionPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          New Inspection
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload or capture packaged commodity images for compliance verification
        </p>
      </div>

      <Card
        title="Package Upload Workstation"
        subtitle="Supported formats: JPEG, PNG, WebP"
      >
        <div className="flex flex-col items-center justify-center py-16 border-2 border-dashed border-slate-200 rounded-lg bg-slate-50/50 hover:bg-slate-50 transition-colors">
          <div className="w-12 h-12 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mb-3">
            <UploadCloud className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-700">
            Package Ingestion Area
          </h3>
          <p className="text-xs text-slate-400 max-w-sm text-center mt-1">
            Drag and drop package images or use camera capture. OCR extraction and
            rule evaluation will process automatically.
          </p>
          <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
            <ScanLine className="w-4 h-4" />
            <span>Inspection flow ready for Milestone 2</span>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default NewInspectionPage
