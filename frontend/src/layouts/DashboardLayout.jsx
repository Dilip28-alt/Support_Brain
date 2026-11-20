import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import {
  LayoutDashboard, Brain, MessageSquare, HelpCircle,
  Mail, BookOpen, BarChart2, Settings, LogOut, Zap
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/dashboard',               label: 'Overview',      Icon: LayoutDashboard, end: true },
  { to: '/dashboard/knowledge',     label: 'Knowledge Brain', Icon: Brain },
  { to: '/dashboard/conversations', label: 'Conversations', Icon: MessageSquare },
  { to: '/dashboard/pending',       label: 'Pending',       Icon: HelpCircle },
  { to: '/dashboard/email',         label: 'Email',         Icon: Mail },
  { to: '/dashboard/lessons',       label: 'Lessons',       Icon: BookOpen },
  { to: '/dashboard/analytics',     label: 'Analytics',     Icon: BarChart2 },
  { to: '/dashboard/settings',      label: 'Settings',      Icon: Settings },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-100 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-gray-900 text-lg">Support Brain</span>
          </div>
          {user?.full_name && (
            <p className="text-xs text-gray-500 mt-2 truncate">{user.full_name}</p>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto">
          {navItems.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium mb-1 transition-colors',
                isActive
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
