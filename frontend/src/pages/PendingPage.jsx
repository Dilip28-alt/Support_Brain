import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import { HelpCircle, CheckCircle, Loader2, MessageSquare, Mail, Brain } from 'lucide-react'

export default function PendingPage() {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading]     = useState(true)
  const [resolving, setResolving] = useState(null)
  const [form, setForm]           = useState({})

  const load = (status = 'open') => {
    setLoading(true)
    api.get(`/pending/?status_filter=${status}`).then(r => setQuestions(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const resolve = async (q, addToBrain = true) => {
    const answer = form[q.id]?.trim()
    if (!answer) { toast.error('Please enter an answer'); return }
    setResolving(q.id)
    try {
      await api.post(`/pending/${q.id}/resolve`, {
        owner_answer: answer,
        add_to_brain: addToBrain,
        send_via_channel: true,
      })
      toast.success(addToBrain ? 'Answer added to Brain and reply sent!' : 'Reply sent to customer!')
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to resolve')
    } finally { setResolving(null) }
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Pending Questions</h1>

      {loading ? <div className="text-gray-400 text-sm">Loading…</div> : questions.length === 0 ? (
        <div className="card text-center py-16 text-gray-400">
          <CheckCircle size={40} className="mx-auto mb-3 text-green-400" />
          <p className="font-medium text-gray-700">All caught up!</p>
          <p className="text-sm mt-1">No open pending questions.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {questions.map(q => (
            <div key={q.id} className="card">
              <div className="flex items-start gap-3 mb-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  q.source === 'email' ? 'bg-blue-100' : 'bg-purple-100'
                }`}>
                  {q.source === 'email' ? <Mail size={15} className="text-blue-600" /> : <MessageSquare size={15} className="text-purple-600" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={q.source === 'email' ? 'badge-blue' : 'badge-gray'}>
                      {q.source}
                    </span>
                    <p className="text-xs text-gray-500">{new Date(q.created_at).toLocaleString()}</p>
                  </div>
                  <p className="font-medium text-gray-900">{q.customer_question}</p>
                  {q.customer_name && <p className="text-xs text-gray-500 mt-0.5">From: {q.customer_name}</p>}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Your Answer</label>
                <textarea
                  className="input h-24 resize-none"
                  placeholder="Type your answer here…"
                  value={form[q.id] || ''}
                  onChange={e => setForm(f => ({ ...f, [q.id]: e.target.value }))}
                />
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    onClick={() => resolve(q, true)}
                    className="btn-primary flex items-center gap-2"
                    disabled={resolving === q.id}
                  >
                    {resolving === q.id ? <Loader2 size={15} className="animate-spin" /> : <Brain size={15} />}
                    Add this answer to the Brain
                  </button>
                  <button
                    onClick={() => resolve(q, false)}
                    className="px-4 py-2 border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-lg text-sm font-medium transition-colors"
                    disabled={resolving === q.id}
                  >
                    Send Reply Only
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
