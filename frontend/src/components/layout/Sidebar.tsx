import React from 'react'
import {
  LayoutDashboard,
  ScanLine,
  History,
  FileText,
  Scale,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import NavItem from './NavItem'

export const Sidebar: React.FC = () => {
  const navItems = [
    {
      to: '/dashboard',
      label: 'Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      to: '/new-inspection',
      label: 'New Inspection',
      icon: <ScanLine className="w-4 h-4" />,
    },
    {
      to: '/history',
      label: 'Inspection History',
      icon: <History className="w-4 h-4" />,
    },
    {
      to: '/reports',
      label: 'Reports',
      icon: <FileText className="w-4 h-4" />,
    },
    {
      to: '/rules',
      label: 'Rules & Act',
      icon: <Scale className="w-4 h-4" />,
    },
    {
      to: '/settings',
      label: 'Settings',
      icon: <Settings className="w-4 h-4" />,
    },
  ]

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-screen select-none flex-shrink-0">
      {/* Brand Header */}
      <div className="px-5 py-5 border-b border-slate-800/80 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-brand-blue flex items-center justify-center text-white shadow-md flex-shrink-0">
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
            PackSure <span className="text-blue-400 font-semibold">AI</span>
          </h1>
          <p className="text-[11px] text-slate-400 truncate">
            AI-assisted inspection
          </p>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
          Workspace
        </div>
        {navItems.map((item) => (
          <NavItem
            key={item.to}
            to={item.to}
            label={item.label}
            icon={item.icon}
          />
        ))}
      </nav>

      {/* Core Principle Card */}
      <div className="p-3">
        <div className="rounded-lg bg-slate-800/90 border border-slate-700/70 p-3 text-slate-300">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-blue-400 mb-1.5">
            Core Principle
          </div>
          <p className="text-xs text-slate-300 leading-relaxed font-normal space-y-1">
            <span className="block text-slate-200 font-medium">
              • AI extracts the evidence.
            </span>
            <span className="block text-slate-200 font-medium">
              • Rules determine compliance.
            </span>
            <span className="block text-slate-200 font-medium">
              • Humans review uncertainty.
            </span>
          </p>
        </div>
      </div>

      {/* Version Footer */}
      <div className="px-5 py-3 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
        <span>PackSure AI v0.1.0</span>
        <span className="text-slate-400 font-medium">SIH26034</span>
      </div>
    </aside>
  )
}

export default Sidebar
