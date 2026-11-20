import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import {
  LayoutDashboard, Brain, MessageSquare, HelpCircle,
  Mail, BookOpen, BarChart2, Settings, LogOut, Zap,
  Building2, ExternalLink, ChevronLeft, ChevronRight, Menu
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/dashboard',               label: 'Overview',        Icon: LayoutDashboard, end: true },
  { to: '/dashboard/knowledge',     label: 'Knowledge Brain', Icon: Brain },
  { to: '/dashboard/conversations', label: 'Conversations',   Icon: MessageSquare },
  { to: '/dashboard/pending',       label: 'Pending',         Icon: HelpCircle },
  { to: '/dashboard/email',         label: 'Email Inbox',     Icon: Mail },
  { to: '/dashboard/lessons',       label: 'Lessons',         Icon: BookOpen },
  { to: '/dashboard/analytics',     label: 'Analytics',       Icon: BarChart2 },
  { to: '/dashboard/settings',      label: 'Settings',        Icon: Settings },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const businessName = user?.business_name || (user?.business_slug ? user.business_slug.replace(/-/g, ' ').toUpperCase() : 'My Business')

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800">
      {/* Sidebar */}
      <aside className={clsx(
        "bg-white border-r border-slate-200 flex flex-col transition-all duration-200 z-20 select-none",
        collapsed ? "w-20" : "w-64"
      )}>
        {/* App Branding & Collapse Toggle */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-9 h-9 bg-indigo-600 rounded-xl flex items-center justify-center shrink-0 shadow-sm shadow-indigo-200">
              <Zap size={18} className="text-white fill-white" />
            </div>
            {!collapsed && (
              <div className="truncate">
                <span className="font-bold text-slate-900 tracking-tight text-base block">Support Brain</span>
                <span className="text-[10px] uppercase font-semibold text-indigo-600 tracking-wider">SaaS Workspace</span>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Business Tenant Identity Banner */}
        {!collapsed ? (
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/70">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Building2 size={14} className="text-indigo-600 shrink-0" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Business Workspace</span>
            </div>
            <div className="font-semibold text-slate-900 text-sm truncate" title={businessName}>
              {businessName}
            </div>
            {user?.business_slug && (
              <a
                href={`/chat/${user.business_slug}`}
                target="_blank"
                rel="noreferrer"
                className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Public Chat Link <ExternalLink size={10} />
              </a>
            )}
          </div>
        ) : (
          <div className="py-3 flex justify-center border-b border-slate-100" title={businessName}>
            <Building2 size={18} className="text-indigo-600" />
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto space-y-1">
          {navItems.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                isActive
                  ? 'bg-indigo-50 text-indigo-600 font-semibold shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                collapsed && 'justify-center px-0'
              )}
            >
              <Icon size={19} className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Owner Profile & Logout */}
        <div className="p-3 border-t border-slate-100 bg-white">
          {!collapsed && (
            <div className="mb-2 px-2 py-1.5 bg-slate-50 rounded-lg">
              <div className="text-xs font-semibold text-slate-800 truncate">{user?.full_name || 'Owner'}</div>
              <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
            </div>
          )}
          <button
            onClick={handleLogout}
            title={collapsed ? "Sign Out" : undefined}
            className={clsx(
              "flex items-center gap-3 px-3 py-2 w-full rounded-xl text-sm font-medium text-slate-600 hover:bg-rose-50 hover:text-rose-600 transition-colors",
              collapsed && "justify-center px-0"
            )}
          >
            <LogOut size={18} className="shrink-0" />
            {!collapsed && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto flex flex-col min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
