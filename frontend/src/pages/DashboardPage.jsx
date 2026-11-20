import { useEffect, useState, useRef } from 'react'
import { useAuth } from '../hooks/useAuth.jsx'
import api from '../services/api.js'
import axios from 'axios'
import toast from 'react-hot-toast'
import {
  Brain, MessageSquare, HelpCircle, BookOpen, TrendingUp,
  Send, Loader2, Sparkles, Copy, Check, ExternalLink, ThumbsUp, ThumbsDown
} from 'lucide-react'

function StatCard({ label, value, Icon, color }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
        <Icon size={22} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value ?? 0}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [loadingStats, setLoadingStats] = useState(true)

  // Live Chat Console State
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hello! I'm Support Brain AI. Ask me anything to test what I've learned from your Knowledge Brain and Lessons.`,
      sources: [],
    }
  ])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [copied, setCopied] = useState(false)
  const chatBottomRef = useRef(null)

  const publicChatUrl = user?.business_slug
    ? `${window.location.origin}/chat/${user.business_slug}`
    : ''

  const loadStats = () => {
    api.get('/analytics/summary')
      .then(r => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoadingStats(false))
  }

  useEffect(() => {
    loadStats()
  }, [])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const copyLink = () => {
    if (!publicChatUrl) return
    navigator.clipboard.writeText(publicChatUrl)
    setCopied(true)
    toast.success('Public Chat URL copied to clipboard!')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSendMessage = async (e) => {
    if (e) e.preventDefault()
    if (!input.trim() || chatLoading || !user?.business_slug) return

    const question = input.trim()
    setInput('')

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
    }
    setMessages(prev => [...prev, userMessage])
    setChatLoading(true)

    try {
      const { data } = await axios.post('/api/chat', {
        business_slug: user.business_slug,
        question,
        customer_name: user?.full_name || 'Owner (Test)',
        conversation_id: conversationId || null,
      })

      setConversationId(data.conversation_id)
      setMessages(prev => [
        ...prev,
        {
          id: data.message_id,
          role: 'assistant',
          content: data.answer,
          sources: data.source_chunks || [],
          is_pending: data.is_pending,
          confidence: data.confidence_score,
          lesson_used: data.lesson_used,
        }
      ])
      // Refresh stats in background
      loadStats()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to get answer from AI')
      setMessages(prev => [
        ...prev,
        {
          id: 'error-' + Date.now(),
          role: 'assistant',
          content: 'Error: Could not retrieve answer. Please make sure knowledge has been added to your Brain.',
          sources: [],
        }
      ])
    } finally {
      setChatLoading(false)
    }
  }

  const handleFeedback = async (msgId, type) => {
    if (!conversationId) return
    const msg = messages.find(m => m.id === msgId)
    if (!msg) return

    try {
      await api.post('/feedback', {
        message_id: msgId,
        conversation_id: conversationId,
        feedback_type: type,
        ai_answer: msg.content,
      })
      toast.success(type === 'good' ? '👍 Positive feedback recorded' : 'Feedback noted. Go to Lessons to teach the correct answer.')
      loadStats()
    } catch {
      toast.error('Could not save feedback')
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''} 👋
          </h1>
          <p className="text-gray-500 mt-1">
            Here's what's happening with your support system.
          </p>
        </div>

        {/* Public chat URL badge */}
        {publicChatUrl && (
          <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl p-2 shadow-sm">
            <span className="text-xs text-gray-500 font-mono px-2 truncate max-w-xs">
              {publicChatUrl}
            </span>
            <button
              onClick={copyLink}
              className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors"
              title="Copy URL"
            >
              {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
            </button>
            <a
              href={publicChatUrl}
              target="_blank"
              rel="noreferrer"
              className="p-1.5 hover:bg-gray-100 rounded-lg text-brand-600 transition-colors"
              title="Open Public Chat Window"
            >
              <ExternalLink size={16} />
            </a>
          </div>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard label="Total Questions"   value={stats?.total_questions}   Icon={MessageSquare} color="bg-blue-500" />
        <StatCard label="AI Answers"        value={stats?.total_ai_answers}  Icon={Brain}         color="bg-brand-600" />
        <StatCard label="Good Answers"      value={stats?.good_answers}      Icon={TrendingUp}    color="bg-green-500" />
        <StatCard label="Pending Questions" value={stats?.pending_questions} Icon={HelpCircle}    color="bg-yellow-500" />
        <StatCard label="Lessons Created"   value={stats?.lessons_created}   Icon={BookOpen}      color="bg-purple-500" />
        <StatCard label="Lessons Used"      value={stats?.lessons_used}      Icon={Sparkles}      color="bg-indigo-500" />
      </div>

      {/* Live Chat Interface */}
      <div className="card !p-0 overflow-hidden border border-gray-200 shadow-sm flex flex-col h-[560px]">
        {/* Chat Header */}
        <div className="bg-brand-600 px-6 py-4 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-white/20 rounded-lg flex items-center justify-center">
              <Brain size={20} className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-base leading-tight">Live Support Brain Test Console</h2>
                <span className="bg-emerald-400/20 text-emerald-200 text-[11px] font-medium px-2 py-0.5 rounded-full border border-emerald-400/30">
                  Online
                </span>
              </div>
              <p className="text-xs text-brand-100">
                Workspace: <span className="font-mono">{user?.business_slug || 'xyz-company'}</span> · Testing your Knowledge Brain & Lessons
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setMessages([{
                id: 'welcome-' + Date.now(),
                role: 'assistant',
                content: `Chat session reset. What question would you like to test?`,
                sources: [],
              }])
              setConversationId(null)
            }}
            className="text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg text-white transition-colors"
          >
            Reset Session
          </button>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-gray-50/50">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-brand-600 text-white rounded-br-sm'
                    : 'bg-white text-gray-900 border border-gray-200 rounded-bl-sm'
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                {/* Assistant metadata badges */}
                {msg.role === 'assistant' && msg.id !== 'welcome' && (
                  <div className="mt-3 pt-2 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      {msg.confidence !== undefined && (
                        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                          msg.confidence >= 0.75
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          Confidence: {Math.round((msg.confidence || 0) * 100)}%
                        </span>
                      )}
                      {msg.lesson_used && (
                        <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-[11px] font-medium flex items-center gap-1">
                          <BookOpen size={11} /> Lesson Prioritized
                        </span>
                      )}
                      {msg.is_pending && (
                        <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded text-[11px] font-medium flex items-center gap-1">
                          <HelpCircle size={11} /> Pending Question Created
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleFeedback(msg.id, 'good')}
                        className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-green-600 transition-colors"
                        title="Good answer"
                      >
                        <ThumbsUp size={13} />
                      </button>
                      <button
                        onClick={() => handleFeedback(msg.id, 'bad')}
                        className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-red-600 transition-colors"
                        title="Bad answer"
                      >
                        <ThumbsDown size={13} />
                      </button>
                    </div>
                  </div>
                )}

                {/* Source citations */}
                {msg.sources && msg.sources.length > 0 && (
                  <details className="mt-2 text-xs text-gray-500">
                    <summary className="cursor-pointer hover:text-gray-700 font-medium">
                      Sources ({msg.sources.length} chunks used)
                    </summary>
                    <div className="mt-1.5 space-y-1.5 pl-2 border-l-2 border-brand-200">
                      {msg.sources.map((s, idx) => (
                        <div key={idx} className="bg-gray-50 p-2 rounded text-[11px] text-gray-600">
                          <p className="font-semibold text-gray-800">{s.source_title || 'Knowledge Chunk'}</p>
                          <p className="line-clamp-2 mt-0.5">{s.content}</p>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            </div>
          ))}

          {chatLoading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2 text-sm text-gray-500">
                <Loader2 size={16} className="animate-spin text-brand-600" />
                <span>Consulting Knowledge Brain…</span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendMessage} className="p-4 bg-white border-t border-gray-200">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask a question (e.g. 'What are your working hours?' or 'What services do you provide?')"
              className="input flex-1 py-2.5"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={chatLoading || !input.trim()}
              className="btn-primary flex items-center gap-2 px-5 py-2.5"
            >
              {chatLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              <span>Send</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
