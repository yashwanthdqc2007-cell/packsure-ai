import React from 'react'
import Card from '../../components/common/Card'
import StatusBadge from '../../components/common/StatusBadge'
import { Scale } from 'lucide-react'

export const RulesPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Rules & Legal Metrology Act
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Deterministic reference rules derived from Legal Metrology (Packaged Commodities) Rules, 2011
        </p>
      </div>

      <Card
        title="Codified Legal Rules Engine"
        subtitle="Active validation rules for commodity packaging"
        headerAction={<StatusBadge status="PASS" label="Engine Active" />}
      >
        <div className="space-y-4">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="flex items-start gap-3">
              <Scale className="w-5 h-5 text-brand-blue flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-slate-800">
                  Legal Metrology (Packaged Commodities) Rules, 2011 — Core Declarations
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Mandatory specifications: Rule 6 (Declarations to be made on every package),
                  Rule 7 (Principal Display Panel), Rule 8 (Letter and numeral dimensions),
                  and Rule 9 (Manner of declaration).
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-lg border border-slate-200 bg-white">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Rule 6(1)(a)
              </span>
              <h5 className="text-sm font-medium text-slate-800 mt-1">
                Manufacturer / Packer Identity & Address
              </h5>
              <p className="text-xs text-slate-500 mt-1">
                Name and complete address of manufacturer, packer, or importer.
              </p>
            </div>
            <div className="p-4 rounded-lg border border-slate-200 bg-white">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Rule 6(1)(e)
              </span>
              <h5 className="text-sm font-medium text-slate-800 mt-1">
                Maximum Retail Price (MRP) & Unit Sale Price
              </h5>
              <p className="text-xs text-slate-500 mt-1">
                Inclusive of all taxes; mandatory unit sale price per g/ml/piece where applicable.
              </p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default RulesPage
