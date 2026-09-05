import React from 'react'
import { ScanText, ShieldCheck, UserCheck, Info } from 'lucide-react'

export interface InspectionDetailsFormProps {
  category: string
  productName: string
  onCategoryChange: (value: string) => void
  onProductNameChange: (value: string) => void
}

export const CATEGORY_OPTIONS = [
  'Food Grains',
  'Edible Oil',
  'Packaged Water',
  'Flour',
  'Beverages',
  'Personal Care',
  'Household Products',
  'Other',
]

export const InspectionDetailsForm: React.FC<InspectionDetailsFormProps> = ({
  category,
  productName,
  onCategoryChange,
  onProductNameChange,
}) => {
  return (
    <div className="space-y-6">
      {/* Form Fields */}
      <div className="space-y-4">
        {/* Product Category */}
        <div>
          <label
            htmlFor="product-category"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5"
          >
            Product Category <span className="text-red-500 font-bold">*</span>
          </label>
          <select
            id="product-category"
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue transition-colors cursor-pointer"
          >
            <option value="" disabled>
              Select product category...
            </option>
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <p className="text-[11px] text-slate-400 mt-1">
            Determines the applicable Legal Metrology rules and threshold tolerances.
          </p>
        </div>

        {/* Product Name (Optional) */}
        <div>
          <label
            htmlFor="product-name"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5"
          >
            Product Name <span className="text-slate-400 font-normal lowercase">(optional)</span>
          </label>
          <input
            id="product-name"
            type="text"
            value={productName}
            onChange={(e) => onProductNameChange(e.target.value)}
            placeholder="Enter product name (optional)"
            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue transition-colors"
          />
          <p className="text-[11px] text-slate-400 mt-1">
            Helps index and search this inspection record in history.
          </p>
        </div>
      </div>

      {/* Information Card: How PackSure works */}
      <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-brand-blue" />
          <h5 className="text-xs font-bold uppercase tracking-wider text-slate-900">
            How PackSure works
          </h5>
        </div>

        <div className="space-y-3.5 text-xs text-slate-600">
          {/* Step 1 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-md bg-blue-100 text-brand-blue font-mono font-bold flex items-center justify-center flex-shrink-0 text-[11px]">
              01
            </div>
            <div>
              <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                <ScanText className="w-3.5 h-3.5 text-slate-500" />
                Extract
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                AI extracts visible declarations and evidence from the package image.
              </p>
            </div>
          </div>

          {/* Step 2 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-md bg-emerald-100 text-emerald-700 font-mono font-bold flex items-center justify-center flex-shrink-0 text-[11px]">
              02
            </div>
            <div>
              <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                Validate
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                Structured evidence is checked against applicable compliance rules.
              </p>
            </div>
          </div>

          {/* Step 3 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-md bg-amber-100 text-amber-700 font-mono font-bold flex items-center justify-center flex-shrink-0 text-[11px]">
              03
            </div>
            <div>
              <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5 text-amber-600" />
                Review
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                Uncertain findings are flagged for human verification.
              </p>
            </div>
          </div>
        </div>

        {/* Subtle legal metrology note */}
        <div className="pt-3 border-t border-slate-200/80 text-[11px] text-slate-500 italic leading-relaxed">
          Compliance decisions are based on extracted visual evidence and the configured rule set.
        </div>
      </div>
    </div>
  )
}

export default InspectionDetailsForm
