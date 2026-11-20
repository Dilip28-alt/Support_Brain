import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth.jsx'
import DashboardLayout from './layouts/DashboardLayout.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import KnowledgePage from './pages/KnowledgePage.jsx'
import ConversationsPage from './pages/ConversationsPage.jsx'
import PendingPage from './pages/PendingPage.jsx'
import EmailPage from './pages/EmailPage.jsx'
import LessonsPage from './pages/LessonsPage.jsx'
import AnalyticsPage from './pages/AnalyticsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import ChatWidgetPage from './pages/ChatWidgetPage.jsx'

function ProtectedRoute({ children }) {
  const { token, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-gray-400">Loading…</div>
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/chat/:slug" element={<ChatWidgetPage />} />

        {/* Protected dashboard */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }>
          <Route index element={<DashboardPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="pending" element={<PendingPage />} />
          <Route path="email" element={<EmailPage />} />
          <Route path="lessons" element={<LessonsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  )
}
