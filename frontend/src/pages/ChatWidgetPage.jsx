import { useState, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import {
  Send,
  Loader2,
  Zap,
  RotateCcw,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Clock,
  Mail,
  ShieldCheck,
  AlertCircle,
  MessageSquare,
  CheckCircle2,
  HelpCircle,
  User,
  ArrowRight
} from 'lucide-react'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 45000,
})

export default function ChatWidgetPage() {
  const { slug: routeSlug } = useParams()
  const [searchParams] = useSearchParams()
  const queryToken = searchParams.get('token')
  const querySlug = searchParams.get('slug')

  const effectiveSlug = routeSlug || querySlug
  const effectiveToken = queryToken

  const [business, setBusiness] = useState(null)
  const [loadingBusiness, setLoadingBusiness] = useState(true)
  const [businessError, setBusinessError] = useState(null)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [customerName, setCustomerName] = useState('')
  const [customerEmail, setCustomerEmail] = useState('')
  const [showEmailInput, setShowEmailInput] = useState(false)
  const [expandedSources, setExpandedSources] = useState({})

  // Mode switcher: 'chat' or 'email'
  const [activeTab, setActiveTab] = useState('chat')

  // Email Inquiry form state
  const [emailForm, setEmailForm] = useState({
    sender_name: '',
    sender_email: '',
    subject: '',
    message: '',
  })
  const [sendingEmail, setSendingEmail] = useState(false)
  const [emailSuccess, setEmailSuccess] = useState(null)
  const [emailError, setEmailError] = useState(null)

  const bottomRef = useRef(null)

  useEffect(() => {
    async function fetchBusiness() {
      setLoadingBusiness(true)
      setBusinessError(null)
      try {
        let res
        if (effectiveToken) {
          res = await publicApi.get(`/chat/public/info?token=${encodeURIComponent(effectiveToken)}`)
        } else if (effectiveSlug) {
          res = await publicApi.get(`/chat/public/info?slug=${encodeURIComponent(effectiveSlug)}`)
        } else {
          setBusinessError('No business specified in URL (missing slug or widget token).')
          setLoadingBusiness(false)
          return
        }
        setBusiness(res.data)
        // Add initial welcoming message
        setMessages([
          {
            id: 'welcome',
            role: 'assistant',
            content: `Hello! 👋 I am the AI support assistant for ${res.data.name}. Ask me anything about our services, pricing, or policies.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            sources: [],
          },
        ])
      } catch (err) {
        console.error('Failed to load business info:', err)
        setBusinessError('Business not found or inactive.')
      } finally {
        setLoadingBusiness(false)
      }
    }

    fetchBusiness()
  }, [effectiveSlug, effectiveToken])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const toggleSource = (msgId) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }))
  };

  const handleClearChat = () => {
    if (messages.length <= 1 || window.confirm('Clear conversation history?')) {
      setConversationId(null)
      setMessages([
        {
          id: 'welcome-' + Date.now(),
          role: 'assistant',
          content: `Chat cleared. How else can I help you today?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: [],
        },
      ])
    }
  }

  const handleSendEmailInquiry = async (e) => {
    e.preventDefault()
    if (!emailForm.sender_email.trim() || !emailForm.subject.trim() || !emailForm.message.trim()) {
      setEmailError('Please provide your email address, subject, and question.')
      return
    }
    setSendingEmail(true)
    setEmailError(null)
    setEmailSuccess(null)
    try {
      const payload = {
        sender_name: emailForm.sender_name.trim() || 'Customer',
        sender_email: emailForm.sender_email.trim(),
        subject: emailForm.subject.trim(),
        message: emailForm.message.trim(),
        business_token: effectiveToken || null,
        business_slug: effectiveSlug || null,
      }
      const { data } = await publicApi.post('/chat/public/email-inquiry', payload)
      setEmailSuccess(data.message || 'Your inquiry has been successfully sent to support!')
      setEmailForm({ sender_name: '', sender_email: '', subject: '', message: '' })
    } catch (err) {
      console.error('Email inquiry error:', err)
      setEmailError(err.response?.data?.detail || 'Failed to submit inquiry. Please check your connection and try again.')
    } finally {
      setSendingEmail(false)
    }
  }

  const switchToEmailWithQuestion = (initialQuestion = '') => {
    setEmailForm((prev) => ({
      ...prev,
      sender_name: prev.sender_name || customerName,
      sender_email: prev.sender_email || customerEmail,
      subject: prev.subject || (initialQuestion ? `Question: ${initialQuestion.slice(0, 50)}…` : 'Customer Inquiry'),
      message: initialQuestion || prev.message,
    }))
    setActiveTab('email')
  }

  const send = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg = {
      role: 'user',
      content: question,
      id: 'usr-' + Date.now(),
      timestamp: timeStr,
    }
    setMessages((m) => [...m, userMsg])
    setLoading(true)

    try {
      const payload = {
        question,
        customer_name: customerName.trim() || null,
        customer_email: customerEmail.trim() || null,
        conversation_id: conversationId || null,
      }
      if (effectiveToken) {
        payload.business_token = effectiveToken
      } else if (effectiveSlug) {
        payload.business_slug = effectiveSlug
      }

      const { data } = await publicApi.post('/chat', payload)

      setConversationId(data.conversation_id)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: data.answer,
          id: data.message_id || 'ast-' + Date.now(),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: data.source_chunks || [],
          is_pending: data.is_pending,
          lesson_used: data.lesson_used,
          confidence_score: data.confidence_score,
        },
      ])
    } catch (err) {
      console.error('Chat error:', err)
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout')
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: isTimeout
            ? 'The server is currently waking up from cold start. Please click Send once more in a few seconds!'
            : 'Sorry, I encountered a temporary connection issue. Please try asking again.',
          id: 'err-' + Date.now(),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: [],
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (loadingBusiness) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 text-slate-500">
        <Loader2 className="animate-spin text-blue-600 mb-2" size={32} />
        <p className="text-sm">Connecting to Support Brain…</p>
      </div>
    )
  }

  if (businessError || !business) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 p-6 text-center">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-3">
          <AlertCircle size={24} />
        </div>
        <h2 className="text-lg font-semibold text-slate-800">Chat Unavailable</h2>
        <p className="text-sm text-slate-500 max-w-sm mt-1">{businessError || 'Unable to connect to this business.'}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen max-w-lg mx-auto bg-white shadow-2xl border-x border-slate-200">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-700 p-4 text-white flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center font-bold text-white shadow-inner">
            <Zap size={20} className="text-white fill-white/20" />
          </div>
          <div>
            <h1 className="font-semibold text-base leading-tight">{business.name}</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <p className="text-xs text-blue-100 font-medium">AI Support Brain · Instant answers</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {activeTab === 'chat' && (
            <button
              onClick={handleClearChat}
              title="Clear Conversation"
              className="text-blue-100 hover:text-white p-2 rounded-lg hover:bg-white/10 transition-colors"
              aria-label="Clear chat"
            >
              <RotateCcw size={17} />
            </button>
          )}
        </div>
      </header>

      {/* Mode Switcher Tabs: Live Chat vs Email Support */}
      <div className="flex border-b border-slate-200 bg-white">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border-b-2 ${
            activeTab === 'chat'
              ? 'border-blue-600 text-blue-600 bg-blue-50/40'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50'
          }`}
        >
          <MessageSquare size={14} />
          <span>Live AI Chat</span>
        </button>
        <button
          onClick={() => setActiveTab('email')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border-b-2 ${
            activeTab === 'email'
              ? 'border-blue-600 text-blue-600 bg-blue-50/40'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50'
          }`}
        >
          <Mail size={14} />
          <span>Ask via Email</span>
        </button>
      </div>

      {/* VIEW 1: Live AI Chat */}
      {activeTab === 'chat' && (
        <>
          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
            {messages.map((msg) => {
              const isUser = msg.role === 'user'
              const hasSources = msg.sources && msg.sources.length > 0
              const isSourcesOpen = expandedSources[msg.id]

              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} transition-all`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                      isUser
                        ? 'bg-blue-600 text-white rounded-tr-sm'
                        : 'bg-white text-slate-800 border border-slate-200/80 rounded-tl-sm'
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                    {/* Pending fallback indicator */}
                    {msg.is_pending && (
                      <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs flex flex-col gap-2">
                        <div className="flex items-start gap-2">
                          <Mail size={14} className="mt-0.5 flex-shrink-0 text-amber-600" />
                          <div>
                            <span className="font-semibold">Forwarded to Support Team:</span>
                            <p className="mt-0.5 text-amber-700">
                              Our team will review your inquiry. You can also send this question directly through email support.
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => switchToEmailWithQuestion(messages.filter(m => m.role === 'user').slice(-1)[0]?.content || '')}
                          className="self-start text-[11px] font-medium text-amber-800 bg-amber-100 hover:bg-amber-200 px-2.5 py-1 rounded transition-colors flex items-center gap-1"
                        >
                          <Mail size={12} /> Send as official email inquiry
                        </button>
                      </div>
                    )}

                    {/* Lesson-applied badge */}
                    {msg.lesson_used && (
                      <div className="mt-2 flex items-center gap-1 text-[11px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 w-fit">
                        <ShieldCheck size={12} />
                        Verified Business Lesson applied
                      </div>
                    )}

                    {/* Grounding Source Citations */}
                    {hasSources && (
                      <div className="mt-3 pt-2 border-t border-slate-100">
                        <button
                          onClick={() => toggleSource(msg.id)}
                          className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                        >
                          <BookOpen size={13} />
                          <span>{msg.sources.length} Knowledge Sources cited</span>
                          {isSourcesOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        </button>

                        {isSourcesOpen && (
                          <div className="mt-2 space-y-2">
                            {msg.sources.map((s, idx) => (
                              <div
                                key={s.chunk_id || idx}
                                className="p-2 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600"
                              >
                                <div className="flex items-center justify-between font-semibold text-slate-800 mb-1">
                                  <span className="truncate max-w-[200px]">📄 {s.source_title || 'Knowledge Base'}</span>
                                  <span className="text-[10px] text-slate-400 font-mono">
                                    chunk #{String(s.chunk_id).slice(0, 8)}
                                  </span>
                                </div>
                                <p className="italic text-slate-500 line-clamp-3">
                                  "{s.content}"
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Timestamp */}
                  <div className="flex items-center gap-1 mt-1 px-1 text-[11px] text-slate-400">
                    <Clock size={10} />
                    <span>{msg.timestamp}</span>
                  </div>
                </div>
              )
            })}

            {loading && (
              <div className="flex items-center gap-2 text-slate-400 text-xs py-2 px-1">
                <Loader2 size={16} className="animate-spin text-blue-600" />
                <span>Consulting Knowledge Brain…</span>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Customer Info (Optional Email / Name drawer) */}
          <div className="px-4 py-2 bg-slate-100/70 border-t border-slate-200 text-xs text-slate-600 flex items-center justify-between">
            <button
              onClick={() => setShowEmailInput(!showEmailInput)}
              className="flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium"
            >
              <Mail size={13} />
              <span>{customerEmail ? `Notifications to: ${customerEmail}` : 'Add email for follow-up notifications'}</span>
            </button>
            {customerEmail && (
              <button
                onClick={() => { setCustomerEmail(''); setCustomerName('') }}
                className="text-slate-400 hover:text-slate-600 text-[11px]"
              >
                Clear
              </button>
            )}
          </div>

          {showEmailInput && (
            <div className="p-3 bg-slate-50 border-t border-slate-200 grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="block text-slate-500 mb-1 font-medium">Your Name (optional)</label>
                <input
                  type="text"
                  placeholder="Jane Doe"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-slate-500 mb-1 font-medium">Your Email (optional)</label>
                <input
                  type="email"
                  placeholder="jane@example.com"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          {/* Input Form */}
          <div className="p-3 bg-white border-t border-slate-200">
            <div className="flex items-center gap-2">
              <input
                className="flex-1 bg-slate-50 hover:bg-slate-100/80 focus:bg-white text-slate-800 border border-slate-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all placeholder:text-slate-400"
                placeholder="Type your question…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={loading}
              />
              <button
                onClick={send}
                disabled={loading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white p-2.5 rounded-xl transition-colors shadow-sm flex items-center justify-center flex-shrink-0"
                aria-label="Send message"
              >
                <Send size={18} />
              </button>
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
              <span className="flex items-center gap-1">
                <Zap size={11} className="text-amber-500" />
                <span>Powered by <strong>Support Brain</strong></span>
              </span>
              <button
                onClick={() => switchToEmailWithQuestion(input)}
                className="text-blue-600 hover:underline flex items-center gap-1"
              >
                <Mail size={11} /> Ask via Email instead
              </button>
            </div>
          </div>
        </>
      )}

      {/* VIEW 2: Ask via Email Support */}
      {activeTab === 'email' && (
        <div className="flex-1 overflow-y-auto p-5 bg-slate-50 flex flex-col justify-between">
          <div className="space-y-4">
            {/* Business Contact Badge */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200/70 rounded-2xl p-4">
              <div className="flex items-center gap-2.5 mb-1.5">
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center">
                  <Mail size={16} />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">{business.name} Email Support</h3>
                  <p className="text-xs text-slate-500">Ask your question and receive a reply directly in your inbox</p>
                </div>
              </div>

              {business.support_email && (
                <div className="mt-2 pt-2 border-t border-blue-200/50 flex items-center justify-between text-xs text-slate-600">
                  <span>Support Inbox:</span>
                  <a
                    href={`mailto:${business.support_email}`}
                    className="font-medium text-blue-700 hover:underline font-mono"
                  >
                    {business.support_email}
                  </a>
                </div>
              )}
            </div>

            {/* Success State */}
            {emailSuccess ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 text-center space-y-3">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle2 size={24} />
                </div>
                <h4 className="font-semibold text-slate-900 text-base">Inquiry Received!</h4>
                <p className="text-xs text-slate-600 leading-relaxed max-w-sm mx-auto">
                  {emailSuccess}
                </p>
                <div className="pt-2 flex flex-col sm:flex-row gap-2 justify-center">
                  <button
                    onClick={() => setEmailSuccess(null)}
                    className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-colors"
                  >
                    Send Another Question
                  </button>
                  <button
                    onClick={() => setActiveTab('chat')}
                    className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
                  >
                    Back to Live Chat
                  </button>
                </div>
              </div>
            ) : (
              /* Email Inquiry Form */
              <form onSubmit={handleSendEmailInquiry} className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm space-y-3">
                {emailError && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                    <AlertCircle size={14} className="flex-shrink-0" />
                    <span>{emailError}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1 flex items-center gap-1">
                      <User size={12} className="text-slate-400" /> Your Name
                    </label>
                    <input
                      type="text"
                      placeholder="Jane Doe"
                      value={emailForm.sender_name}
                      onChange={(e) => setEmailForm((f) => ({ ...f, sender_name: e.target.value }))}
                      className="w-full px-3 py-2 text-xs bg-slate-50 focus:bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-800"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1 flex items-center gap-1">
                      <Mail size={12} className="text-slate-400" /> Your Email <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="email"
                      required
                      placeholder="jane@example.com"
                      value={emailForm.sender_email}
                      onChange={(e) => setEmailForm((f) => ({ ...f, sender_email: e.target.value }))}
                      className="w-full px-3 py-2 text-xs bg-slate-50 focus:bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-800"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1 flex items-center gap-1">
                    <HelpCircle size={12} className="text-slate-400" /> Subject <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g., Question about product warranty & return period"
                    value={emailForm.subject}
                    onChange={(e) => setEmailForm((f) => ({ ...f, subject: e.target.value }))}
                    className="w-full px-3 py-2 text-xs bg-slate-50 focus:bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-800"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1 flex items-center gap-1">
                    <MessageSquare size={12} className="text-slate-400" /> Your Question or Details <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    required
                    rows={4}
                    placeholder="Please write your question in detail here. We will review our documentation and respond promptly…"
                    value={emailForm.message}
                    onChange={(e) => setEmailForm((f) => ({ ...f, message: e.target.value }))}
                    className="w-full px-3 py-2 text-xs bg-slate-50 focus:bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-800 resize-none"
                  />
                </div>

                <button
                  type="submit"
                  disabled={sendingEmail}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-xl text-xs flex items-center justify-center gap-2 transition-colors shadow-sm"
                >
                  {sendingEmail ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>Sending inquiry to support…</span>
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      <span>Send Question via Email</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>

          <p className="text-[11px] text-slate-400 text-center mt-4">
            Inquiries are processed by Support Brain RAG and routed to {business.name}'s support team.
          </p>
        </div>
      )}
    </div>
  )
}
