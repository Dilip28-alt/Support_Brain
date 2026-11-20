import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import { Send, Loader2, Zap } from 'lucide-react'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
})

export default function ChatWidgetPage() {
  const { slug } = useParams()
  const [business, setBusiness]       = useState(null)
  const [messages, setMessages]       = useState([])
  const [input, setInput]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [customerName, setCustomerName] = useState('')
  const [started, setStarted]         = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    publicApi.get(`/widget/${slug}`)
      .then(r => setBusiness(r.data))
      .catch(() => setBusiness(null))
  }, [slug])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const start = () => {
    if (!customerName.trim()) { return }
    setStarted(true)
    setMessages([{
      role: 'assistant',
      content: `Hi ${customerName}! 👋 I'm the ${business?.business_name} support assistant. How can I help you today?`,
      id: 'welcome',
    }])
  }

  const send = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')

    const userMsg = { role: 'user', content: question, id: Date.now().toString() }
    setMessages(m => [...m, userMsg])
    setLoading(true)

    try {
      const { data } = await publicApi.post('/chat', {
        business_slug: slug,
        question,
        customer_name: customerName || null,
        conversation_id: conversationId || null,
      })

      setConversationId(data.conversation_id)
      setMessages(m => [...m, {
        role: 'assistant',
        content: data.answer,
        id: data.message_id,
        sources: data.source_chunks,
        is_pending: data.is_pending,
        confidence: data.confidence_score,
      }])
    } catch {
      setMessages(m => [...m, {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        id: 'error',
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  if (business === null && !slug) {
    return <div className="flex h-screen items-center justify-center text-gray-400">Business not found.</div>
  }

  return (
    <div className="flex flex-col h-screen max-w-lg mx-auto bg-white shadow-xl">
      {/* Header */}
      <div className="bg-brand-600 p-4 text-white">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-white/20 rounded-full flex items-center justify-center">
            <Zap size={18} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-sm">{business?.business_name || 'Support'}</p>
            <p className="text-xs text-brand-200">AI Support Assistant · Usually replies instantly</p>
          </div>
        </div>
      </div>

      {/* Welcome / Name gate */}
      {!started ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center mb-4">
            <Zap size={32} className="text-brand-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">{business?.business_name} Support</h2>
          <p className="text-sm text-gray-500 text-center mb-6">
            Get instant answers to your questions, powered by AI.
          </p>
          <div className="w-full max-w-xs space-y-3">
            <input
              className="input text-center"
              placeholder="Your name (optional)"
              value={customerName}
              onChange={e => setCustomerName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && setStarted(true)}
            />
            <button
              onClick={() => setStarted(true)}
              className="btn-primary w-full"
            >
              Start Chat
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-brand-600 text-white rounded-tr-sm'
                    : 'bg-gray-100 text-gray-900 rounded-tl-sm'
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  {msg.is_pending && (
                    <p className="text-xs mt-1 opacity-70">
                      📬 A team member will follow up with you.
                    </p>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs opacity-60 cursor-pointer">View sources</summary>
                      <div className="mt-1 space-y-1">
                        {msg.sources.slice(0, 2).map((s, i) => (
                          <p key={i} className="text-xs opacity-70 italic line-clamp-2">
                            {s.source_title || 'Knowledge Base'}: {s.content?.slice(0, 80)}…
                          </p>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
                  <Loader2 size={16} className="animate-spin text-gray-400" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-100">
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="Ask a question…"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={loading}
              />
              <button
                onClick={send}
                className="btn-primary px-4 flex items-center justify-center"
                disabled={loading || !input.trim()}
              >
                <Send size={16} />
              </button>
            </div>
            <p className="text-xs text-gray-400 text-center mt-2">Powered by Support Brain AI</p>
          </div>
        </>
      )}
    </div>
  )
}
