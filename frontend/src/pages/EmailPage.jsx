import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import {
  Mail, ExternalLink, Loader2, Send, CheckCircle, Edit2,
  Settings2, Plus, Sparkles, RefreshCw, Trash2, ArrowDownLeft,
  ArrowUpRight, AlertCircle, ShieldCheck, Zap
} from 'lucide-react'

export default function EmailPage() {
  const [accounts, setAccounts] = useState([])
  const [emails, setEmails] = useState([])
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [editDraft, setEditDraft] = useState({})
  const [sending, setSending] = useState(null)
  const [filter, setFilter] = useState('all') // all, draft, sent

  // Modals
  const [showSmtpModal, setShowSmtpModal] = useState(false)
  const [showSimulateModal, setShowSimulateModal] = useState(false)
  const [showComposeModal, setShowComposeModal] = useState(false)

  // Forms
  const [smtpForm, setSmtpForm] = useState({
    email_address: '',
    imap_host: '',
    imap_port: 993,
    smtp_host: '',
    smtp_port: 587,
    username: '',
    password: '',
    processing_mode: 'review',
  })
  const [connectingSmtp, setConnectingSmtp] = useState(false)

  const [simForm, setSimForm] = useState({
    sender_name: 'Alex Johnson',
    sender_email: 'alex.customer@gmail.com',
    subject: 'Question regarding free laptop bags',
    body: 'Hello, do you provide free laptop bags with laptop purchases? Thanks!',
  })
  const [simulating, setSimulating] = useState(false)

  const [composeForm, setComposeForm] = useState({
    recipient: '',
    subject: '',
    body: '',
  })
  const [composing, setComposing] = useState(false)

  const loadData = () => {
    Promise.all([
      api.get('/email/accounts'),
      api.get('/email/messages'),
    ])
      .then(([a, e]) => {
        setAccounts(a.data || [])
        setEmails(e.data || [])
      })
      .catch(() => toast.error('Failed to load email data'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  const connectGmail = async () => {
    try {
      const { data } = await api.get('/email/oauth/url')
      window.location.href = data.url
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start Gmail OAuth')
    }
  }

  const handleSmtpConnect = async (e) => {
    e.preventDefault()
    setConnectingSmtp(true)
    try {
      await api.post('/email/smtp-imap/connect', smtpForm)
      toast.success('Inbox connected successfully!')
      setShowSmtpModal(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to connect SMTP/IMAP inbox')
    } finally {
      setConnectingSmtp(false)
    }
  }

  const updateMode = async (acc, newMode) => {
    try {
      await api.patch(`/email/accounts/${acc.id}`, { processing_mode: newMode })
      toast.success(
        newMode === 'auto'
          ? '⚡ Switched to Auto Mode (AI sends high-confidence answers automatically)'
          : '📝 Switched to Review Mode (Owner reviews drafts before sending)'
      )
      loadData()
    } catch (err) {
      toast.error('Failed to update mode')
    }
  }

  const disconnectAccount = async (id) => {
    if (!confirm('Disconnect this email inbox?')) return
    try {
      await api.delete(`/email/accounts/${id}`)
      toast.success('Account disconnected')
      loadData()
    } catch (err) {
      toast.error('Failed to disconnect')
    }
  }

  const fetchEmails = async () => {
    setFetching(true)
    try {
      await api.post('/email/fetch')
      toast.success('Checking inbox for new emails…')
      setTimeout(() => loadData(), 2500)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to fetch emails')
    } finally {
      setFetching(false)
    }
  }

  const sendReply = async (email) => {
    if (email.status === 'sent') {
      toast.error('This email has already been replied to. Duplicate sending is not allowed.')
      return
    }
    setSending(email.id)
    try {
      await api.post('/email/messages/send', {
        email_message_id: email.id,
        reply_body: editDraft[email.id] !== undefined ? editDraft[email.id] : email.draft_reply,
      })
      toast.success('Reply sent in thread!')
      loadData()
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to send reply'
      if (detail.includes('expired') || detail.includes('reconnect') || detail.includes('invalid_grant')) {
        toast.error('⚠️ Gmail connection expired. Please click "Connect Gmail" above to reconnect.', { duration: 6000 })
        loadData()
      } else {
        toast.error(detail)
      }
    } finally {
      setSending(null)
    }
  }

  const saveDraft = async (email) => {
    if (editDraft[email.id] === undefined) return
    try {
      await api.patch(`/email/messages/${email.id}/draft`, {
        draft_reply: editDraft[email.id],
      })
      toast.success('Draft saved')
      loadData()
    } catch (err) {
      toast.error('Failed to save draft')
    }
  }

  const handleSimulate = async (e) => {
    e.preventDefault()
    setSimulating(true)
    try {
      await api.post('/email/simulate-incoming', simForm)
      toast.success('Customer email received & processed by Brain!')
      setShowSimulateModal(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Simulation failed')
    } finally {
      setSimulating(false)
    }
  }

  const handleCompose = async (e) => {
    e.preventDefault()
    setComposing(true)
    try {
      await api.post('/email/compose', composeForm)
      toast.success('Email sent successfully!')
      setShowComposeModal(false)
      setComposeForm({ recipient: '', subject: '', body: '' })
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send composed email')
      loadData()
    } finally {
      setComposing(false)
    }
  }

  const filteredEmails = emails.filter((em) => {
    if (filter === 'draft') return em.status === 'draft' || em.status === 'pending'
    if (filter === 'sent') return em.status === 'sent'
    if (filter === 'failed') return em.status === 'failed'
    return true
  })

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Email Customer Support</h1>
          <p className="text-sm text-gray-500 mt-1">
            Connect an inbox, let the Brain draft replies, and send via Review or Auto mode.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {accounts.length > 0 && (
            <>
              <button
                onClick={fetchEmails}
                className="btn-secondary flex items-center gap-2"
                disabled={fetching}
              >
                <RefreshCw size={14} className={fetching ? 'animate-spin' : ''} />
                Fetch New Emails
              </button>
              <button
                onClick={() => setShowComposeModal(true)}
                className="btn-secondary flex items-center gap-2"
              >
                <Send size={14} /> Compose Email
              </button>
            </>
          )}
          <button
            onClick={() => setShowSimulateModal(true)}
            className="btn-secondary border-purple-200 text-purple-700 bg-purple-50 hover:bg-purple-100 flex items-center gap-2"
          >
            <Sparkles size={14} /> Simulate Customer Email
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSmtpModal(true)}
              className="btn-secondary flex items-center gap-2"
            >
              <Mail size={15} /> Connect SMTP/IMAP
            </button>
            <button
              onClick={connectGmail}
              className="btn-primary flex items-center gap-2"
            >
              <Mail size={15} /> Connect Gmail
            </button>
          </div>
        </div>
      </div>

      {/* Reconnect Required Banner */}
      {accounts.some((a) => a.status === 'error') && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 flex items-start justify-between gap-3 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertCircle className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />
            <div>
              <h4 className="font-semibold text-sm">Gmail Authorization Expired</h4>
              <p className="text-xs text-amber-700 mt-0.5">
                Google requires periodic re-authorization for test applications. Please click <strong>Reconnect Gmail</strong> to refresh permissions and restore full email sending capabilities.
              </p>
            </div>
          </div>
          <button
            onClick={connectGmail}
            className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shrink-0 transition-colors shadow-sm"
          >
            <Mail size={13} /> Reconnect Gmail Now
          </button>
        </div>
      )}

      {/* Connected Inboxes Section */}
      {accounts.length > 0 && (
        <div className="card mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <ShieldCheck size={16} className="text-green-600" /> Connected Inbox (
            {accounts.length})
          </h2>
          <div className="space-y-3">
            {accounts.map((acc) => (
              <div
                key={acc.id}
                className="flex flex-wrap items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 gap-4"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-50 border border-brand-200 rounded-full flex items-center justify-center text-brand-600">
                    <Mail size={18} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-gray-900">{acc.email_address}</p>
                      <span
                        className={
                          acc.status === 'connected' ? 'badge-green' : 'badge-red'
                        }
                      >
                        {acc.status === 'error' ? 'RECONNECT NEEDED' : acc.status}
                      </span>
                    </div>
                    {acc.status === 'error' && (
                      <p className="text-xs text-rose-600 font-medium mt-1 flex items-center gap-1">
                        <AlertCircle size={12} /> Google OAuth token expired. Please click Reconnect Gmail.
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-0.5">
                      Mode:{' '}
                      <strong className="text-gray-700 uppercase">
                        {acc.processing_mode}
                      </strong>{' '}
                      —{' '}
                      {acc.processing_mode === 'auto'
                        ? 'AI auto-sends if confident; queues to Pending if unsure'
                        : 'Owner sees draft and clicks Send'}
                    </p>
                  </div>
                </div>

                {/* Mode Selector Toggle */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={connectGmail}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 transition-colors ${
                      acc.status === 'error'
                        ? 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm animate-pulse'
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200'
                    }`}
                    title="Reconnect Gmail to grant fresh Google OAuth token"
                  >
                    <Mail size={13} /> Reconnect Gmail
                  </button>

                  <div className="flex bg-white rounded-lg p-1 border border-gray-200">
                    <button
                      onClick={() => updateMode(acc, 'review')}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        acc.processing_mode === 'review'
                          ? 'bg-brand-600 text-white shadow-sm'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                    >
                      Review Mode
                    </button>
                    <button
                      onClick={() => updateMode(acc, 'auto')}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1 transition-colors ${
                        acc.processing_mode === 'auto'
                          ? 'bg-purple-600 text-white shadow-sm'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                    >
                      <Zap size={12} /> Auto Mode
                    </button>
                  </div>

                  <button
                    onClick={() => disconnectAccount(acc.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Disconnect inbox"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-gray-200 pb-3 mb-4">
        <div className="flex gap-2">
          {[
            { id: 'all', label: `All Emails (${emails.length})` },
            {
              id: 'draft',
              label: `Needs Review / Drafts (${
                emails.filter((e) => e.status === 'draft' || e.status === 'pending')
                  .length
              })`,
            },
            {
              id: 'sent',
              label: `Sent (${emails.filter((e) => e.status === 'sent').length})`,
            },
            {
              id: 'failed',
              label: `Failed (${emails.filter((e) => e.status === 'failed').length})`,
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === tab.id
                  ? 'bg-gray-900 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-400">
          Replies stay in the same thread · Duplicate send protection active
        </p>
      </div>

      {/* Email Inbox Content */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">
          <Loader2 size={32} className="animate-spin mx-auto mb-2 text-brand-600" />
          <p className="text-sm">Loading email threads…</p>
        </div>
      ) : accounts.length === 0 && emails.length === 0 ? (
        <div className="card text-center py-16 text-gray-400">
          <Mail size={44} className="mx-auto mb-3 opacity-30 text-brand-600" />
          <p className="font-semibold text-gray-800 text-base">No Inbox Connected Yet</p>
          <p className="text-sm text-gray-500 max-w-md mx-auto mt-1 mb-5">
            Connect your Gmail or any standard SMTP/IMAP inbox to enable AI customer
            support email replies, or click "Simulate Customer Email" to test right now.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => setShowSimulateModal(true)}
              className="btn-secondary text-sm flex items-center gap-2"
            >
              <Sparkles size={15} /> Simulate Test Email
            </button>
            <button
              onClick={() => setShowSmtpModal(true)}
              className="btn-secondary text-sm flex items-center gap-2"
            >
              <Mail size={15} /> Connect SMTP/IMAP
            </button>
            <button
              onClick={connectGmail}
              className="btn-primary text-sm flex items-center gap-2"
            >
              <Mail size={15} /> Connect Gmail
            </button>
          </div>
        </div>
      ) : filteredEmails.length === 0 ? (
        <div className="card text-center py-12 text-gray-400">
          <p className="text-sm">No emails found for this filter.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredEmails.map((email) => {
            const isOutgoing = email.direction === 'outgoing'
            return (
              <div
                key={email.id}
                className={`card border-l-4 ${
                  email.status === 'failed'
                    ? 'border-l-rose-500 bg-rose-50/20'
                    : isOutgoing
                    ? 'border-l-green-500 bg-green-50/20'
                    : email.status === 'sent'
                    ? 'border-l-blue-400'
                    : 'border-l-brand-600'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-medium flex items-center gap-1 ${
                          email.status === 'failed'
                            ? 'bg-rose-100 text-rose-700'
                            : isOutgoing
                            ? 'bg-green-100 text-green-700'
                            : 'bg-purple-100 text-purple-700'
                        }`}
                      >
                        {isOutgoing ? (
                          <>
                            <ArrowUpRight size={12} /> Outgoing Reply
                          </>
                        ) : (
                          <>
                            <ArrowDownLeft size={12} /> Customer Email
                          </>
                        )}
                      </span>
                      <h3 className="font-semibold text-gray-900">{email.subject}</h3>
                    </div>
                    <p className="text-xs text-gray-500">
                      From: <strong className="text-gray-700">{email.sender}</strong> → To:{' '}
                      <span className="text-gray-700">{email.recipient}</span>
                    </p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400 mt-1">
                      <span>Msg ID: <code className="text-gray-600 bg-gray-100 px-1 py-0.5 rounded font-mono text-[10px]">{email.gmail_message_id}</code></span>
                      <span>Thread ID: <code className="text-gray-600 bg-gray-100 px-1 py-0.5 rounded font-mono text-[10px]">{email.gmail_thread_id}</code></span>
                      {email.related_message_id && (
                        <span>Reply To: <code className="text-purple-700 bg-purple-50 px-1 py-0.5 rounded font-mono text-[10px]">{email.related_message_id}</code></span>
                      )}
                      <span>
                        {email.sent_at
                          ? `Sent: ${new Date(email.sent_at).toLocaleString()}`
                          : email.received_at
                          ? `Received: ${new Date(email.received_at).toLocaleString()}`
                          : `Created: ${new Date(email.created_at).toLocaleString()}`}
                      </span>
                    </div>
                  </div>

                  <div className="shrink-0">
                    <span
                      className={
                        email.status === 'sent'
                          ? 'badge-green'
                          : email.status === 'draft'
                          ? 'badge-blue'
                          : email.status === 'failed'
                          ? 'bg-rose-100 text-rose-700 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-rose-200'
                          : 'badge-yellow'
                      }
                    >
                      {email.status.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Email Body */}
                <div className="bg-white rounded-lg p-3 text-sm text-gray-800 border border-gray-100 mb-3 whitespace-pre-wrap">
                  <p className="text-xs text-gray-400 mb-1 font-semibold uppercase">
                    {isOutgoing ? 'Sent Message' : 'Customer Message'}
                  </p>
                  {email.body_text || '(no plain text body)'}
                </div>

                {/* AI Draft Answer from Brain (Review Mode) */}
                {!isOutgoing && email.draft_reply && email.status !== 'sent' && (
                  <div className="mt-3 p-4 bg-brand-50/50 rounded-xl border border-brand-100">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-xs font-semibold text-brand-900 flex items-center gap-1.5">
                        <Sparkles size={14} className="text-brand-600" /> AI Draft Reply
                        (Generated from Knowledge Brain)
                      </label>
                      <span className="text-xs text-brand-600">Review & Edit</span>
                    </div>

                    <textarea
                      className="input h-32 resize-none text-sm bg-white"
                      defaultValue={email.draft_reply}
                      onChange={(e) =>
                        setEditDraft((d) => ({ ...d, [email.id]: e.target.value }))
                      }
                      placeholder="Review or edit draft answer here…"
                    />

                    <div className="flex flex-wrap items-center justify-between gap-2 mt-3">
                      <p className="text-xs text-gray-500">
                        Will be sent in thread with subject:{' '}
                        <strong>
                          {email.subject?.toLowerCase().startsWith('re:')
                            ? email.subject
                            : `Re: ${email.subject}`}
                        </strong>
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveDraft(email)}
                          className="btn-secondary text-xs px-3 py-1.5"
                        >
                          Save Draft Changes
                        </button>
                        <button
                          onClick={() => sendReply(email)}
                          className="btn-primary flex items-center gap-2 text-xs px-4 py-1.5"
                          disabled={sending === email.id}
                        >
                          {sending === email.id ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <Send size={13} />
                          )}
                          Send Reply (Review Mode)
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Sent confirmation */}
                {email.status === 'sent' && !isOutgoing && (
                  <div className="flex items-center gap-2 text-green-700 bg-green-50 px-3 py-2 rounded-lg text-xs font-medium">
                    <CheckCircle size={15} /> Reply sent in thread · Duplicate send
                    prevented
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* MODAL: Connect SMTP / IMAP */}
      {showSmtpModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 animate-in fade-in zoom-in duration-200">
            <h2 className="text-lg font-bold text-gray-900 mb-1">
              Connect SMTP & IMAP Inbox
            </h2>
            <p className="text-xs text-gray-500 mb-4">
              Connect any custom email account (Zoho, Outlook, Namecheap, Google App
              Password, etc.).
            </p>

            <form onSubmit={handleSmtpConnect} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="support@yourcompany.com"
                  className="input text-sm"
                  value={smtpForm.email_address}
                  onChange={(e) =>
                    setSmtpForm((f) => ({ ...f, email_address: e.target.value }))
                  }
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="text-xs font-semibold text-gray-700">IMAP Host</label>
                  <input
                    type="text"
                    required
                    placeholder="imap.mail.com"
                    className="input text-sm"
                    value={smtpForm.imap_host}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, imap_host: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-700">IMAP Port</label>
                  <input
                    type="number"
                    required
                    className="input text-sm"
                    value={smtpForm.imap_port}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, imap_port: parseInt(e.target.value) || 993 }))
                    }
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="text-xs font-semibold text-gray-700">SMTP Host</label>
                  <input
                    type="text"
                    required
                    placeholder="smtp.mail.com"
                    className="input text-sm"
                    value={smtpForm.smtp_host}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, smtp_host: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-700">SMTP Port</label>
                  <input
                    type="number"
                    required
                    className="input text-sm"
                    value={smtpForm.smtp_port}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, smtp_port: parseInt(e.target.value) || 587 }))
                    }
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-gray-700">Username</label>
                  <input
                    type="text"
                    required
                    placeholder="Username or email"
                    className="input text-sm"
                    value={smtpForm.username}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, username: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-700">Password</label>
                  <input
                    type="password"
                    required
                    placeholder="App password"
                    className="input text-sm"
                    value={smtpForm.password}
                    onChange={(e) =>
                      setSmtpForm((f) => ({ ...f, password: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700">Initial Mode</label>
                <select
                  className="input text-sm"
                  value={smtpForm.processing_mode}
                  onChange={(e) =>
                    setSmtpForm((f) => ({ ...f, processing_mode: e.target.value }))
                  }
                >
                  <option value="review">Review Mode (Owner approves before sending)</option>
                  <option value="auto">Auto Mode (AI sends automatically if confident)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowSmtpModal(false)}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connectingSmtp}
                  className="btn-primary text-sm flex items-center gap-2"
                >
                  {connectingSmtp && <Loader2 size={14} className="animate-spin" />}
                  Test & Connect
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Simulate Customer Email */}
      {showSimulateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-2 text-purple-700 mb-1">
              <Sparkles size={18} />
              <h2 className="text-lg font-bold text-gray-900">
                Simulate Incoming Customer Email
              </h2>
            </div>
            <p className="text-xs text-gray-500 mb-4">
              Test how Support Brain reads incoming customer emails, references your
              Knowledge Brain + Lessons, and either drafts or auto-replies.
            </p>

            {/* Quick Test Presets */}
            <div className="mb-4">
              <p className="text-xs font-semibold text-gray-600 mb-1.5">Quick Presets:</p>
              <div className="flex flex-wrap gap-1.5">
                {[
                  {
                    label: 'Laptop Bags Question',
                    subj: 'Free laptop bags inquiry',
                    body: 'Do you provide free laptop bags with every purchase?',
                  },
                  {
                    label: 'Return Policy',
                    subj: 'Return window question',
                    body: 'How many days do I have to return an item if unopened?',
                  },
                  {
                    label: 'Unanswered Question',
                    subj: 'Swimming pool question',
                    body: 'Do you have a heated swimming pool on premises?',
                  },
                ].map((p, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() =>
                      setSimForm((f) => ({ ...f, subject: p.subj, body: p.body }))
                    }
                    className="text-xs bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 px-2 py-1 rounded-md"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleSimulate} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-gray-700">Customer Name</label>
                  <input
                    type="text"
                    required
                    className="input text-sm"
                    value={simForm.sender_name}
                    onChange={(e) =>
                      setSimForm((f) => ({ ...f, sender_name: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-700">Customer Email</label>
                  <input
                    type="email"
                    required
                    className="input text-sm"
                    value={simForm.sender_email}
                    onChange={(e) =>
                      setSimForm((f) => ({ ...f, sender_email: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700">Email Subject</label>
                <input
                  type="text"
                  required
                  className="input text-sm"
                  value={simForm.subject}
                  onChange={(e) =>
                    setSimForm((f) => ({ ...f, subject: e.target.value }))
                  }
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700">Email Body</label>
                <textarea
                  required
                  rows={4}
                  className="input text-sm resize-none"
                  value={simForm.body}
                  onChange={(e) =>
                    setSimForm((f) => ({ ...f, body: e.target.value }))
                  }
                />
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowSimulateModal(false)}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={simulating}
                  className="btn-primary bg-purple-600 hover:bg-purple-700 text-sm flex items-center gap-2"
                >
                  {simulating && <Loader2 size={14} className="animate-spin" />}
                  Simulate & Process Through Brain
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Compose Email */}
      {showComposeModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 animate-in fade-in zoom-in duration-200">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Compose New Email</h2>
            <p className="text-xs text-gray-500 mb-4">
              Send an email to a customer from your connected inbox.
            </p>

            <form onSubmit={handleCompose} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700">To Email</label>
                <input
                  type="email"
                  required
                  placeholder="customer@example.com"
                  className="input text-sm"
                  value={composeForm.recipient}
                  onChange={(e) =>
                    setComposeForm((f) => ({ ...f, recipient: e.target.value }))
                  }
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700">Subject</label>
                <input
                  type="text"
                  required
                  placeholder="Subject line"
                  className="input text-sm"
                  value={composeForm.subject}
                  onChange={(e) =>
                    setComposeForm((f) => ({ ...f, subject: e.target.value }))
                  }
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700">Message Body</label>
                <textarea
                  required
                  rows={4}
                  className="input text-sm resize-none"
                  placeholder="Type your message here…"
                  value={composeForm.body}
                  onChange={(e) =>
                    setComposeForm((f) => ({ ...f, body: e.target.value }))
                  }
                />
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowComposeModal(false)}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={composing}
                  className="btn-primary text-sm flex items-center gap-2"
                >
                  {composing && <Loader2 size={14} className="animate-spin" />}
                  Send Email
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
