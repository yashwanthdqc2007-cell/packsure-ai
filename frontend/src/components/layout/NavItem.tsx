import React from 'react'
import { NavLink } from 'react-router-dom'

export interface NavItemProps {
  to: string
  label: string
  icon: React.ReactNode
  badge?: string
}

export const NavItem: React.FC<NavItemProps> = ({ to, label, icon, badge }) => {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
          isActive
            ? 'bg-brand-blue text-white shadow-sm'
            : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
        }`
      }
    >
      <div className="flex items-center gap-3 truncate">
        <span className="flex-shrink-0 text-slate-300">{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      {badge && (
        <span className="ml-2 px-1.5 py-0.5 text-[11px] font-semibold bg-slate-800 text-slate-300 rounded border border-slate-700">
          {badge}
        </span>
      )}
    </NavLink>
  )
}

export default NavItem
