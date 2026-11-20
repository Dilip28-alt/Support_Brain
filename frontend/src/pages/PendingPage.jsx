import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import {
  HelpCircle,
  CheckCircle,
  Loader2,
  MessageSquare,
  Mail,
  Brain,
  Send,
  Trash2,
  Clock,
  User,
  ShieldCheck,
  Sparkles,
  AlertCircle
} from 'lucide-react'

export default function PendingPage() {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('open')
  const [resolving, setResolving] = useState(null)
  const [form, setForm] = useState({})

  const load = (status = statusFilter) => {
    setLoading(true)
    api.get(`/pending/?status_filter=${status}`)
      .then((r) => setQuestions(Array.isArray(r.data) ? r.data : []))
      .catch(() => {
        toast.error('Failed to load pending inquiries')
        setQuestions([])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load(statusFilter)
  }, [statusFilter])

  const resolve = async (q, addToBrain = true) => {
    const answer = form[q.id]?.trim()
    if (!answer) {
      toast.error('Please enter an answer')
      return
    }
    setResolving(q.id)
    try {
      await api.post(`/pending/${q.id}/resolve`, {
        owner_answer: answer,
        add_to_brain: addToBrain,
        send_via_channel: true,
      })
      toast.success(
        addToBrain
          ? '🧠 Answer added to Knowledge Brain & saved as a verified Lesson!'
          : '✉️ Reply sent to customer and question marked resolved!'
      )
      setForm((prev) => {
        const next = { ...prev }
        delete next[q.id]
        return next
      })
      // Immediately reflect the resolution in the card state so it never vanishes abruptly
      setQuestions((prev) => {
        if (!Array.isArray(prev)) return []
        return prev.map((item) =>
          item.id === q.id
            ? { ...item, status: 'resolved', owner_answer: answer, resolved_at: new Date().toISOString() }
            : item
        )
      })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to resolve question')
    } finally {
      setResolving(null)
    }
  }

  const dismiss = async (q) => {
    if (!window.confirm('Dismiss and remove this pending question?')) return
    try {
      await api.delete(`/pending/${q.id}`)
      toast.success('Question dismissed')
      setQuestions((prev) => (Array.isArray(prev) ? prev.filter((item) => item.id !== q.id) : []))
    } catch {
      toast.error('Failed to dismiss question')
    }
  }

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <HelpCircle className="text-blue-600" size={26} />
            Pending Questions
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Questions where the AI could not answer with high confidence. Answer them to teach Support Brain.
          </p>
        </div>

        {/* Status Switcher Tabs */}
        <div className="flex bg-slate-100 p-1 rounded-xl self-start">
          <button
            onClick={() => setStatusFilter('open')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              statusFilter === 'open'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Open Questions
          </button>
          <button
            onClick={() => setStatusFilter('resolved')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              statusFilter === 'resolved'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Resolved History
          </button>
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            All Questions
          </button>
        </div>
      </div>

      {/* Questions list */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400 text-sm">
          <Loader2 size={20} className="animate-spin text-blue-600 mr-2" />
          Loading pending inquiries…
        </div>
      ) : (!Array.isArray(questions) || questions.length === 0) ? (
        <div className="bg-white rounded-2xl border border-slate-200 text-center py-16 px-4">
          <CheckCircle size={44} className="mx-auto mb-3 text-emerald-500" />
          <h3 className="text-base font-semibold text-slate-800">
            {statusFilter === 'open' ? 'All caught up!' : 'No resolved questions yet'}
          </h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
            {statusFilter === 'open'
              ? 'There are no pending customer questions requiring your attention right now.'
              : 'Resolved inquiries will appear here after you answer them.'}
          </p>
          {statusFilter === 'open' && (
            <button
              onClick={() => setStatusFilter('resolved')}
              className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors cursor-pointer"
            >
              <ShieldCheck size={14} />
              View Resolved Inquiries & Verified Lessons
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {questions.map((q) => {
            if (!q || !q.id) return null
            const isEmail = (q.source || '').toLowerCase() === 'email'
            const isResolved = q.status === 'resolved'

            return (
              <div
                key={q.id}
                className={`bg-white rounded-2xl border p-5 transition-all shadow-sm ${
                  isResolved ? 'border-slate-200 bg-slate-50/50' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                        isEmail ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                      }`}
                    >
                      {isEmail ? <Mail size={18} /> : <MessageSquare size={18} />}
                    </div>

                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                            isEmail ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-purple-50 text-purple-700 border border-purple-200'
                          }`}
                        >
                          via {q.source}
                        </span>
                        <span className="text-xs text-slate-400 flex items-center gap-1">
                          <Clock size={11} />
                          {q.created_at ? new Date(q.created_at).toLocaleString() : 'Recently'}
                        </span>
                      </div>

                      <h3 className="text-base font-semibold text-slate-900 leading-snug">
                        {q.customer_question}
                      </h3>

                      {/* Customer Info */}
                      {(q.customer_name || q.customer_email) && (
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
                          {q.customer_name && (
                            <span className="flex items-center gap-1">
                              <User size={12} className="text-slate-400" />
                              {q.customer_name}
                            </span>
                          )}
                          {q.customer_email && (
                            <span className="flex items-center gap-1 font-mono text-slate-600">
                              <Mail size={12} className="text-slate-400" />
                              {q.customer_email}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {!isResolved && (
                    <button
                      onClick={() => dismiss(q)}
                      title="Dismiss Question"
                      className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>

                {/* Resolved View */}
                {isResolved ? (
                  <div className="mt-4 p-4 rounded-xl bg-emerald-50/60 border border-emerald-200/80">
                    <div className="flex items-center justify-between text-xs text-emerald-800 font-semibold mb-1">
                      <span className="flex items-center gap-1">
                        <ShieldCheck size={14} className="text-emerald-600" />
                        Owner Answer (Saved to Brain)
                      </span>
                      <span className="text-[11px] font-normal text-emerald-700">Resolved</span>
                    </div>
                    <p className="text-sm text-slate-800 whitespace-pre-wrap">{q.owner_answer}</p>
                  </div>
                ) : (
                  /* Open Answer Form */
                  <div className="mt-4 space-y-3 pt-3 border-t border-slate-100">
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                      Write Verified Answer
                    </label>
                    <textarea
                      className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-24 resize-none transition-all placeholder:text-slate-400"
                      placeholder="Type the accurate response to send to the customer and teach Support Brain…"
                      value={form[q.id] || ''}
                      onChange={(e) => setForm((prev) => ({ ...prev, [q.id]: e.target.value }))}
                    />

                    <div className="flex flex-wrap items-center gap-3 pt-1">
                      <button
                        onClick={() => resolve(q, true)}
                        disabled={resolving === q.id}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors"
                      >
                        {resolving === q.id ? (
                          <Loader2 size={15} className="animate-spin" />
                        ) : (
                          <Brain size={16} />
                        )}
                        <span>Add this answer to the Brain</span>
                      </button>

                      <button
                        onClick={() => resolve(q, false)}
                        disabled={resolving === q.id}
                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200/80 disabled:opacity-50 text-slate-700 rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors"
                      >
                        <Send size={14} />
                        <span>Send Reply Only</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
