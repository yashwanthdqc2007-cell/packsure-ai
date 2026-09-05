import React from 'react'
import { useParams, Link } from 'react-router-dom'
import Card from '../../components/common/Card'
import StatusBadge from '../../components/common/StatusBadge'
import Button from '../../components/common/Button'
import { ArrowLeft, CheckCircle2 } from 'lucide-react'

export const InspectionDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/history">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
              Back
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Inspection #{id || 'SCAN-DEMO'}
              </h1>
              <StatusBadge status="PASS" />
            </div>
            <p className="text-sm text-slate-500 mt-0.5">
              Legal Metrology (Packaged Commodities) Rules, 2011 compliance breakdown
            </p>
          </div>
        </div>
      </div>

      <Card
        title="Audit Findings & Evidence Mapping"
        subtitle="Mandatory declaration extraction and rules verification"
      >
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-700">
            Inspection Audit View
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mt-1">
            Visual bounding boxes, OCR declaration table, and rule-by-rule citations
            will display for record ID: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-600">{id}</code>.
          </p>
        </div>
      </Card>
    </div>
  )
}

export default InspectionDetailsPage
