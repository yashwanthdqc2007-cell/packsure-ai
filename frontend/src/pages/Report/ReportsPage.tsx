import React from 'react'
import Card from '../../components/common/Card'
import { FileText, Download } from 'lucide-react'
import Button from '../../components/common/Button'

export const ReportsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Compliance Reports
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Generate and export formal Legal Metrology inspection certificates
          </p>
        </div>
        <Button variant="secondary" icon={<Download className="w-4 h-4" />}>
          Export Summary CSV
        </Button>
      </div>

      <Card
        title="Report Generator & Document Repository"
        subtitle="Exportable PDF summaries and violation notices"
      >
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-700">
            Inspection Reports Center Ready
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mt-1">
            Structured PDF export and compliance documentation generation will be
            available once inspection audits are completed.
          </p>
        </div>
      </Card>
    </div>
  )
}

export default ReportsPage
