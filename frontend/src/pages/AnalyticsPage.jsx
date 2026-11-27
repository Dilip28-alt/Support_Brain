import { useEffect, useState } from 'react'
import api from '../services/api.js'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { TrendingUp, TrendingDown, MessageSquare, BookOpen, HelpCircle, Brain, UserCheck } from 'lucide-react'

function StatCard({ label, value, Icon, colorClass }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm text-gray-500">{label}</p>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorClass}`}>
          <Icon size={18} className="text-white" />
        </div>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value ?? 0}</p>
    </div>
  )
}

export default function AnalyticsPage() {
  const [data, setData]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/analytics/summary').then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400 text-sm">Loading analytics…</div>
  if (!data) return <div className="p-8 text-red-500 text-sm">Failed to load analytics.</div>

  const weekly = data.weekly_trends || []

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Analytics</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Questions"   value={data.total_questions}      Icon={MessageSquare} colorClass="bg-blue-500" />
        <StatCard label="AI Answers"        value={data.total_ai_answers}     Icon={Brain}         colorClass="bg-brand-600" />
        <StatCard label="Owner Answers"     value={data.total_owner_answers}  Icon={UserCheck}     colorClass="bg-indigo-600" />
        <StatCard label="Good Answers"      value={data.good_answers}         Icon={TrendingUp}    colorClass="bg-green-500" />
        <StatCard label="Bad Answers"       value={data.bad_answers}          Icon={TrendingDown}  colorClass="bg-red-500" />
        <StatCard label="Pending Questions" value={data.pending_questions}    Icon={HelpCircle}    colorClass="bg-yellow-500" />
        <StatCard label="Lessons Created"   value={data.lessons_created}      Icon={BookOpen}      colorClass="bg-purple-500" />
        <StatCard label="Lessons Used"      value={data.lessons_used}         Icon={BookOpen}      colorClass="bg-indigo-500" />
        <StatCard
          label="Answer Quality"
          value={data.total_ai_answers > 0
            ? `${Math.round((data.good_answers / Math.max(data.good_answers + data.bad_answers, 1)) * 100)}%`
            : '—'}
          Icon={TrendingUp}
          colorClass="bg-teal-500"
        />
      </div>

      {/* Weekly Q&A trend */}
      <div className="card mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Weekly Questions & Answers</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={weekly} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week_start" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Legend />
            <Bar dataKey="total_questions" name="Questions" fill="#3b82f6" radius={[4,4,0,0]} />
            <Bar dataKey="ai_answered"     name="AI Answered" fill="#8b5cf6" radius={[4,4,0,0]} />
            <Bar dataKey="owner_answered"  name="Owner Answered" fill="#6366f1" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Answer quality trend */}
      <div className="card mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Answer Quality Trend</h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={weekly} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week_start" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="good_answers" name="Good" stroke="#22c55e" strokeWidth={2} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="bad_answers"  name="Bad"  stroke="#ef4444" strokeWidth={2} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="pending"      name="Pending" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Lesson usage trend */}
      <div className="card">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Lesson Usage Over Time</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={weekly} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week_start" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Legend />
            <Bar dataKey="lessons_created" name="Created" fill="#8b5cf6" radius={[4,4,0,0]} />
            <Bar dataKey="lessons_used"    name="Used"    fill="#6366f1" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
