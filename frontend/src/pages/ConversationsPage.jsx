import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import {
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  MessageSquare,
  Loader2,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  X,
  Sparkles,
  BookOpen,
  ArrowRight
} from 'lucide-react'

function FeedbackModal({ msg, userQuestion, onClose, onSubmit }) {
  const [correct, setCorrect] = useState('')
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!correct.trim()) {
      toast.error('Please provide the correct answer')
      return
    }
    setLoading(true)
    try {
      await onSubmit({ correct_answer: correct.trim(), owner_comment: comment.trim() })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95">
        <div className="p-5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-base flex items-center gap-2">
              <Sparkles size={18} />
              Teach Support Brain (Create Lesson)
            </h3>
            <p className="text-xs text-blue-100 mt-0.5">
              Your correction is saved as a verified lesson and takes priority for future questions.
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 text-white/80 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {userQuestion && (
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                Customer Question
              </label>
              <p className="text-sm text-slate-800 bg-slate-50 rounded-xl p-3 border border-slate-200">
                {userQuestion}
              </p>
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-rose-600 uppercase tracking-wider block mb-1">
              AI Answer (Needs Correction)
            </label>
            <p className="text-sm text-slate-700 bg-rose-50/70 rounded-xl p-3 border border-rose-100 italic">
              {msg.content}
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-emerald-700 uppercase tracking-wider block mb-1">
              Correct Answer *
            </label>
            <textarea
              className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-28 resize-none transition-all placeholder:text-slate-400"
              placeholder="Enter the accurate, verified answer that customers should receive…"
              value={correct}
              onChange={(e) => setCorrect(e.target.value)}
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
              Owner Note / Why was this wrong? (Optional)
            </label>
            <input
              className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all placeholder:text-slate-400"
              placeholder="e.g., Updated return policy from 30 days to 45 days in 2026."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>
        </div>

        <div className="p-4 bg-slate-50 border-t border-slate-200 flex gap-2 justify-end">
          <button className="px-4 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-200/60 transition-colors" onClick={onClose}>
            Cancel
          </button>
          <button
            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-xl text-sm font-medium flex items-center gap-2 shadow-sm transition-colors disabled:opacity-50"
            onClick={submit}
            disabled={loading}
          >
            {loading && <Loader2 size={15} className="animate-spin" />}
            Save Lesson & Teach AI
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([])
  const [selected, setSelected] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [feedbackModal, setFeedbackModal] = useState(null)
  const [askAgainResult, setAskAgainResult] = useState(null)
  const [askAgainLoading, setAskAgainLoading] = useState(null)

  useEffect(() => {
    api.get('/conversations')
      .then((r) => setConversations(r.data))
      .catch(() => toast.error('Failed to load conversations'))
      .finally(() => setLoading(false))
  }, [])

  const selectConversation = async (conv) => {
    setSelected(conv)
    setAskAgainResult(null)
    try {
      const { data } = await api.get(`/conversations/${conv.id}/messages`)
      setMessages(data)
    } catch {
      toast.error('Failed to load messages')
    }
  }

  const findPrecedingUserMsg = (assistantMsg) => {
    const preceding = messages.filter(
      (m) => m.role === 'user' && new Date(m.created_at) <= new Date(assistantMsg.created_at)
    )
    return preceding.length > 0 ? preceding[preceding.length - 1] : null
  }

  const sendFeedback = async (msg, type, extras = {}) => {
    const userMsg = findPrecedingUserMsg(msg)
    try {
      await api.post('/feedback', {
        message_id: msg.id,
        conversation_id: selected.id,
        feedback_type: type,
        question: userMsg?.content,
        ai_answer: msg.content,
        ...extras,
      })
      toast.success(
        type === 'good'
          ? '👍 Positive feedback recorded!'
          : '📚 Lesson created! Future similar questions will use this answer.'
      )
      setFeedbackModal(null)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save feedback')
    }
  }

  const askAgain = async (msg) => {
    setAskAgainLoading(msg.id)
    setAskAgainResult(null)
    const userMsg = findPrecedingUserMsg(msg)
    try {
      const { data } = await api.post('/ask-again', {
        message_id: msg.id,
        conversation_id: selected.id,
        question: userMsg?.content,
      })
      setAskAgainResult(data)
      toast.success('Re-evaluated question against current Knowledge Brain & Lessons!')
    } catch {
      toast.error('Failed to re-run question')
    } finally {
      setAskAgainLoading(null)
    }
  }

  return (
    <div className="p-8 h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Customer Conversations</h1>
          <p className="text-sm text-slate-500 mt-1">
            Review live customer chats, rate AI responses, teach corrections, and re-run questions side-by-side.
          </p>
        </div>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Conversation List Sidebar */}
        <div className="w-80 shrink-0 overflow-y-auto space-y-2 pr-1">
          {loading ? (
            <div className="flex items-center justify-center p-8 text-slate-400 text-sm">
              <Loader2 size={18} className="animate-spin mr-2 text-blue-600" />
              Loading conversations…
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center text-slate-400 py-16 bg-white rounded-2xl border border-slate-200">
              <MessageSquare size={36} className="mx-auto mb-2 opacity-30 text-slate-400" />
              <p className="text-sm font-medium text-slate-600">No conversations yet</p>
              <p className="text-xs text-slate-400 mt-1">Customer chats via widget will appear here.</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => selectConversation(conv)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  selected?.id === conv.id
                    ? 'border-blue-500 bg-blue-50/60 shadow-sm'
                    : 'border-slate-200/80 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <p className="font-semibold text-sm text-slate-900 truncate">
                    {conv.customer_name || 'Anonymous Visitor'}
                  </p>
                  {conv.is_resolved && (
                    <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
                      Resolved
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500">
                  {conv.customer_email || 'No email provided'}
                </p>
                <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-100">
                  <span>{conv.message_count} messages</span>
                  <span>{new Date(conv.created_at).toLocaleDateString()}</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Message Thread Area */}
        <div className="flex-1 min-w-0 bg-white rounded-2xl border border-slate-200 flex flex-col overflow-hidden shadow-sm">
          {!selected ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 p-8 text-center">
              <MessageSquare size={44} className="mb-3 opacity-20" />
              <p className="text-base font-semibold text-slate-700">No Conversation Selected</p>
              <p className="text-xs text-slate-400 mt-1 max-w-sm">
                Select a conversation from the sidebar to inspect messages, give feedback, and compare answers.
              </p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Header Info */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs text-slate-600">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-800">
                    {selected.customer_name || 'Anonymous Visitor'}
                  </span>
                  {selected.customer_email && (
                    <span className="text-slate-400 font-mono">({selected.customer_email})</span>
                  )}
                </div>
                <span>Started: {new Date(selected.created_at).toLocaleString()}</span>
              </div>

              {/* Messages */}
              {messages.map((msg) => {
                const isUser = msg.role === 'user'
                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isUser ? 'items-start' : 'items-end'}`}
                  >
                    <div
                      className={`max-w-xl rounded-2xl px-4 py-3 text-sm shadow-sm ${
                        isUser
                          ? 'bg-slate-100 text-slate-800 rounded-tl-sm'
                          : 'bg-blue-600 text-white rounded-tr-sm'
                      }`}
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                      {/* Feedback & Actions for Assistant Messages */}
                      {!isUser && (
                        <div className="flex items-center gap-1.5 mt-2.5 pt-2 border-t border-white/20 text-xs">
                          <span className="text-[11px] text-blue-100 mr-1 font-medium">Was this helpful?</span>
                          <button
                            onClick={() => sendFeedback(msg, 'good')}
                            title="Mark Good Answer"
                            className="p-1 rounded hover:bg-white/20 text-white/90 hover:text-white transition-colors flex items-center gap-1"
                          >
                            <ThumbsUp size={13} />
                            <span className="text-[11px]">Good</span>
                          </button>
                          <button
                            onClick={() => setFeedbackModal(msg)}
                            title="Mark Bad Answer & Create Lesson"
                            className="p-1 rounded hover:bg-white/20 text-white/90 hover:text-white transition-colors flex items-center gap-1"
                          >
                            <ThumbsDown size={13} />
                            <span className="text-[11px]">Bad (Correct)</span>
                          </button>

                          <div className="h-3 w-[1px] bg-white/30 mx-1" />

                          <button
                            onClick={() => askAgain(msg)}
                            title="Re-run question through current AI & Lessons"
                            className="p-1 px-2 rounded hover:bg-white/20 text-white/90 hover:text-white transition-colors flex items-center gap-1 font-medium text-[11px] bg-white/10"
                          >
                            {askAgainLoading === msg.id ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              <RotateCcw size={12} />
                            )}
                            Ask This Question Again
                          </button>
                        </div>
                      )}
                    </div>

                    <span className="text-[10px] text-slate-400 mt-1 px-1">
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                )
              })}

              {/* Ask This Question Again - Side-by-Side Comparison Card */}
              {askAgainResult && (
                <div className="mt-6 p-5 rounded-2xl bg-gradient-to-br from-indigo-50/70 to-blue-50/70 border border-indigo-200 shadow-sm animate-in fade-in slide-in-from-bottom-2">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
                        <RotateCcw size={16} />
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-900">
                          Ask This Question Again — Side-by-Side Evaluation
                        </h3>
                        <p className="text-xs text-slate-500">
                          Comparing original AI output against newly learned lessons & knowledge.
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setAskAgainResult(null)}
                      className="text-slate-400 hover:text-slate-600 p-1"
                    >
                      <X size={16} />
                    </button>
                  </div>

                  <div className="mb-3 p-2.5 bg-white rounded-xl border border-indigo-100 text-xs text-slate-700">
                    <span className="font-semibold text-slate-500 mr-2">Evaluated Question:</span>
                    <span className="font-medium text-slate-900">"{askAgainResult.original_question}"</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Previous Answer */}
                    <div className="bg-white rounded-xl p-4 border border-slate-200">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                          Previous Answer
                        </span>
                        <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                          Original AI
                        </span>
                      </div>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                        {askAgainResult.previous_answer}
                      </p>
                    </div>

                    {/* New Answer */}
                    <div className="bg-emerald-50/50 rounded-xl p-4 border border-emerald-200">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 flex items-center gap-1">
                          <CheckCircle2 size={13} className="text-emerald-600" />
                          New Answer (Current Pipeline)
                        </span>
                        {askAgainResult.lesson_retrieved && (
                          <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded flex items-center gap-1">
                            <ShieldCheck size={11} /> Lesson Applied
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-900 whitespace-pre-wrap leading-relaxed font-medium">
                        {askAgainResult.new_answer}
                      </p>
                    </div>
                  </div>

                  {/* Badges / Citations */}
                  <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-indigo-100 text-xs text-slate-600">
                    {askAgainResult.lesson_used && (
                      <span className="flex items-center gap-1 font-mono text-[11px] text-indigo-700 bg-white px-2.5 py-1 rounded-lg border border-indigo-200">
                        <BookOpen size={12} />
                        Lesson #{String(askAgainResult.lesson_used).slice(0, 8)}
                      </span>
                    )}
                    {askAgainResult.knowledge_source_used && (
                      <span className="flex items-center gap-1 text-[11px] text-slate-700 bg-white px-2.5 py-1 rounded-lg border border-slate-200">
                        📄 Source: {askAgainResult.knowledge_source_used}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bad Feedback Correction Modal */}
      {feedbackModal && (
        <FeedbackModal
          msg={feedbackModal}
          userQuestion={findPrecedingUserMsg(feedbackModal)?.content}
          onClose={() => setFeedbackModal(null)}
          onSubmit={(extras) => {
            const userMsg = findPrecedingUserMsg(feedbackModal)
            return sendFeedback(feedbackModal, 'bad', { question: userMsg?.content, ...extras })
          }}
        />
      )}
    </div>
  )
}
