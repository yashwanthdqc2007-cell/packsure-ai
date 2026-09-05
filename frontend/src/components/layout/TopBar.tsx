import React from 'react'
import { useLocation } from 'react-router-dom'
import { Bell, HelpCircle } from 'lucide-react'

export interface TopBarProps {
  title?: string
  description?: string
}

interface RouteMeta {
  title: string
  description: string
}

const routeMetadata: Record<string, RouteMeta> = {
  '/dashboard': {
    title: 'Inspection Dashboard',
    description: 'Overview of packaging compliance metrics and recent verification activities',
  },
  '/new-inspection': {
    title: 'New Inspection',
    description: 'Upload package photographs to extract declarations and verify legal metrology compliance',
  },
  '/inspection/new': {
    title: 'New Inspection',
    description: 'Upload package photographs to extract declarations and verify legal metrology compliance',
  },
  '/history': {
    title: 'Inspection History',
    description: 'Search, filter, and review completed and pending packaging compliance records',
  },
  '/reports': {
    title: 'Compliance Reports',
    description: 'Review and export structured legal metrology inspection summaries and certificates',
  },
  '/rules': {
    title: 'Rules & Legal Metrology Act',
    description: 'Legal Metrology (Packaged Commodities) Rules, 2011 standard reference table',
  },
  '/settings': {
    title: 'System Settings',
    description: 'Configure OCR thresholds, API endpoints, and workstation preferences',
  },
}

export const TopBar: React.FC<TopBarProps> = ({ title, description }) => {
  const location = useLocation()

  // Match dynamic routes like /inspection/:id, /results/:id, /processing/:id
  const getMeta = (): RouteMeta => {
    if (title && description) {
      return { title, description }
    }
    if (location.pathname.startsWith('/processing/')) {
      return {
        title: 'Inspection Processing',
        description: 'Executing OCR preprocessing, Gemini vision extraction, and deterministic rule evaluation',
      }
    }
    if (
      (location.pathname.startsWith('/inspection/') && location.pathname !== '/inspection/new') ||
      location.pathname.startsWith('/results/')
    ) {
      return {
        title: 'Inspection Details',
        description: 'Audit declarations, rule compliance verdicts, and visual evidence mapping',
      }
    }
    return (
      routeMetadata[location.pathname] || {
        title: title || 'PackSure AI Workstation',
        description: description || 'Legal Metrology Packaged Commodities Compliance System',
      }
    )
  }

  const meta = getMeta()

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between flex-shrink-0 z-10 shadow-xs">
      {/* Page Title & Description */}
      <div className="min-w-0 pr-4">
        <h2 className="text-lg font-bold text-slate-900 tracking-tight leading-none truncate">
          {meta.title}
        </h2>
        <p className="text-xs text-slate-500 mt-1 truncate">
          {meta.description}
        </p>
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Help button */}
        <button
          type="button"
          title="Help & Documentation"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
        >
          <HelpCircle className="w-4 h-4 text-slate-500" />
          <span>Help</span>
        </button>

        {/* Notifications */}
        <button
          type="button"
          title="Notifications"
          className="relative p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-brand-blue rounded-full ring-2 ring-white" />
        </button>

        {/* Divider */}
        <div className="h-6 w-px bg-slate-200" />

        {/* Simple User/Workspace Menu */}
        <div className="flex items-center gap-2.5 pl-1">
          <div className="w-8 h-8 rounded-full bg-slate-800 text-white text-xs font-semibold flex items-center justify-center ring-2 ring-slate-100">
            WS
          </div>
          <div className="text-left hidden sm:block">
            <div className="text-xs font-medium text-slate-900 leading-tight">
              Workstation User
            </div>
            <div className="text-[11px] text-slate-400">Standard Operator</div>
          </div>
        </div>
      </div>
    </header>
  )
}

export default TopBar
