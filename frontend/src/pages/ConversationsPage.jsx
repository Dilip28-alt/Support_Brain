import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import { ThumbsUp, ThumbsDown, RotateCcw, MessageSquare, Loader2, ChevronRight } from 'lucide-react'

function FeedbackModal({ msg, question, onClose, onSubmit }) {
  const [correct, setCorrect] = useState('')
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(false)
  const submit = async () => {
    if (!correct.trim()) { toast.error('Please provide the correct answer'); return }
    setLoading(true)
    await onSubmit({ correct_answer: correct, owner_comment: comment })
    setLoading(false)
  }
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-5 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Provide Correct Answer</h3>
          <p className="text-sm text-gray-500 mt-1">This will create a lesson so the AI learns from the correction.</p>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1 block">AI's Answer (incorrect)</label>
            <p className="text-sm text-gray-700 bg-red-50 rounded p-3 border border-red-100">{msg.content}</p>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Correct Answer *</label>
            <textarea className="input h-24 resize-none" placeholder="Enter the correct answer…"
              value={correct} onChange={e => setCorrect(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Comment (optional)</label>
            <input className="input" placeholder="Why was the AI's answer wrong?" value={comment}
              onChange={e => setComment(e.target.value)} />
          </div>
        </div>
        <div className="p-5 border-t border-gray-100 flex gap-2 justify-end">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary flex items-center gap-2" onClick={submit} disabled={loading}>
            {loading && <Loader2 size={14} className="animate-spin" />} Save Lesson
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([])
  const [selected, setSelected]           = useState(null)
  const [messages, setMessages]           = useState([])
  const [loading, setLoading]             = useState(true)
  const [feedbackModal, setFeedbackModal] = useState(null)
  const [askAgainResult, setAskAgainResult] = useState(null)
  const [askAgainLoading, setAskAgainLoading] = useState(null)

  useEffect(() => {
    api.get('/conversations').then(r => setConversations(r.data)).finally(() => setLoading(false))
  }, [])

  const selectConversation = async (conv) => {
    setSelected(conv)
    setAskAgainResult(null)
    const { data } = await api.get(`/conversations/${conv.id}/messages`)
    setMessages(data)
  }

  const sendFeedback = async (msg, type, extras = {}) => {
    const userMsg = messages.find(m => m.role === 'user' && new Date(m.created_at) < new Date(msg.created_at))
    await api.post('/feedback', {
      message_id: msg.id,
      conversation_id: selected.id,
      feedback_type: type,
      question: userMsg?.content,
      ai_answer: msg.content,
      ...extras,
    })
    toast.success(type === 'good' ? '👍 Positive feedback saved!' : '📚 Lesson created from correction!')
    setFeedbackModal(null)
  }

  const askAgain = async (msg) => {
    setAskAgainLoading(msg.id)
    setAskAgainResult(null)
    try {
      const { data } = await api.post('/ask-again', { message_id: msg.id, conversation_id: selected.id })
      setAskAgainResult(data)
    } catch { toast.error('Failed to re-run question') }
    finally { setAskAgainLoading(null) }
  }

  return (
    <div className="p-8 h-full flex flex-col">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Conversations</h1>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* List */}
        <div className="w-80 shrink-0 overflow-y-auto space-y-2">
          {loading ? <div className="text-gray-400 text-sm">Loading…</div> : conversations.length === 0 ? (
            <div className="text-center text-gray-400 py-12">
              <MessageSquare size={36} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No conversations yet</p>
            </div>
          ) : conversations.map(conv => (
            <button key={conv.id} onClick={() => selectConversation(conv)}
              className={`w-full text-left p-4 rounded-xl border transition-colors ${
                selected?.id === conv.id
                  ? 'border-brand-200 bg-brand-50'
                  : 'border-gray-100 bg-white hover:border-gray-200'
              }`}>
              <p className="font-medium text-sm text-gray-900 truncate">{conv.customer_name || 'Anonymous'}</p>
              <p className="text-xs text-gray-500 mt-0.5">{conv.message_count} messages · {new Date(conv.created_at).toLocaleDateString()}</p>
              {conv.is_resolved && <span className="badge-green mt-1">Resolved</span>}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          {!selected ? (
            <div className="flex items-center justify-center h-64 text-gray-400">
              <div className="text-center">
                <ChevronRight size={36} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">Select a conversation</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}>
                  <div className={`max-w-lg rounded-xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-gray-100 text-gray-900'
                      : 'bg-brand-600 text-white'
                  }`}>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {/* Feedback buttons for assistant messages */}
                    {msg.role === 'assistant' && (
                      <div className="flex gap-1 mt-2 pt-2 border-t border-white/20">
                        <button onClick={() => sendFeedback(msg, 'good')} title="Good answer"
                          className="p-1.5 rounded hover:bg-white/20 transition-colors">
                          <ThumbsUp size={12} />
                        </button>
                        <button onClick={() => setFeedbackModal(msg)} title="Bad answer"
                          className="p-1.5 rounded hover:bg-white/20 transition-colors">
                          <ThumbsDown size={12} />
                        </button>
                        <button onClick={() => askAgain(msg)} title="Ask This Question Again"
                          className="p-1.5 rounded hover:bg-white/20 transition-colors flex items-center gap-1 text-xs">
                          {askAgainLoading === msg.id ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                          Ask Again
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Ask Again result */}
              {askAgainResult && (
                <div className="card border-brand-100 bg-brand-50 mt-4">
                  <h3 className="text-sm font-semibold text-brand-800 mb-3">Ask This Question Again — Comparison</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">Previous Answer</p>
                      <p className="text-sm text-gray-700 bg-white rounded p-3 border border-gray-100">{askAgainResult.previous_answer}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-green-700 mb-1">New Answer {askAgainResult.lesson_retrieved ? '✅ Lesson Used' : ''}</p>
                      <p className="text-sm text-gray-700 bg-white rounded p-3 border border-green-100">{askAgainResult.new_answer}</p>
                    </div>
                  </div>
                  {askAgainResult.lesson_used && (
                    <p className="text-xs text-brand-600 mt-2">📚 Lesson ID: {askAgainResult.lesson_used}</p>
                  )}
                  {askAgainResult.knowledge_source_used && (
                    <p className="text-xs text-gray-500 mt-1">📄 Source: {askAgainResult.knowledge_source_used}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Feedback modal */}
      {feedbackModal && (
        <FeedbackModal
          msg={feedbackModal}
          onClose={() => setFeedbackModal(null)}
          onSubmit={(extras) => {
            const userMsg = messages.find(m => m.role === 'user' && new Date(m.created_at) < new Date(feedbackModal.created_at))
            return sendFeedback(feedbackModal, 'bad', { question: userMsg?.content, ...extras })
          }}
        />
      )}
    </div>
  )
}
