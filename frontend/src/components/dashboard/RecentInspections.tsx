import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Card from '../common/Card'
import StatusBadge from '../common/StatusBadge'
import { RecentInspection } from '../../mock'
import { ChevronRight, ArrowUpRight } from 'lucide-react'

export interface RecentInspectionsProps {
  inspections: RecentInspection[]
}

export const RecentInspections: React.FC<RecentInspectionsProps> = ({
  inspections,
}) => {
  const navigate = useNavigate()

  const getScoreColor = (result: string) => {
    if (result === 'PASS') return 'text-emerald-700 bg-emerald-50 border-emerald-200'
    if (result === 'FAIL') return 'text-red-700 bg-red-50 border-red-200'
    return 'text-amber-700 bg-amber-50 border-amber-200'
  }

  return (
    <Card
      title="Recent Inspections"
      subtitle="Latest packaged commodity compliance evaluations"
      padding="none"
      headerAction={
        <Link
          to="/history"
          className="inline-flex items-center gap-1 text-xs font-medium text-brand-blue hover:text-brand-blueHover hover:underline"
        >
          <span>View all history</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </Link>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500 font-semibold select-none">
            <tr>
              <th scope="col" className="py-3 px-6">Product</th>
              <th scope="col" className="py-3 px-4">Category</th>
              <th scope="col" className="py-3 px-4">Scanned</th>
              <th scope="col" className="py-3 px-4">Result</th>
              <th scope="col" className="py-3 px-4 text-center">Score</th>
              <th scope="col" className="py-3 px-4 text-right"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {inspections.map((item) => (
              <tr
                key={item.id}
                onClick={() => navigate(`/results/${item.id}`)}
                className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
              >
                <td className="py-3.5 px-6 font-medium text-slate-900 group-hover:text-brand-blue transition-colors">
                  <div className="font-semibold">{item.product}</div>
                  <div className="text-[11px] text-slate-400 font-mono">ID: {item.id.toUpperCase()}</div>
                </td>
                <td className="py-3.5 px-4 text-slate-600 text-xs">
                  <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                    {item.category}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-slate-500 text-xs whitespace-nowrap">
                  {item.scannedAt}
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <StatusBadge status={item.result} size="sm" />
                </td>
                <td className="py-3.5 px-4 text-center whitespace-nowrap">
                  <span
                    className={`inline-flex items-center justify-center font-mono font-bold text-xs px-2 py-0.5 rounded border ${getScoreColor(
                      item.result
                    )}`}
                  >
                    {item.score}
                    <span className="text-[10px] font-normal text-slate-400 ml-0.5">/100</span>
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right whitespace-nowrap">
                  <span className="inline-flex items-center text-slate-400 group-hover:text-brand-blue transition-colors">
                    <ChevronRight className="w-4 h-4" />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default RecentInspections
