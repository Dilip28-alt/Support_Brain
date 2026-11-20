import { useState } from 'react'
import { useAuth } from '../hooks/useAuth.jsx'
import { Copy, Check, ExternalLink, ShieldCheck, Key, Code, Building, Cpu } from 'lucide-react'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { user } = useAuth()
  const [copiedToken, setCopiedToken] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  const [copiedSnippet, setCopiedSnippet] = useState(false)

  const publicChatUrl = `${window.location.origin}/chat/${user?.business_slug || ''}`
  const widgetToken = user?.widget_token || 'sb_pub_default'
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

  const embedSnippet = `<script src="${backendUrl}/widget.js"
        data-business-token="${widgetToken}"
        data-backend-url="${backendUrl}"></script>`

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'token') {
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    } else if (type === 'link') {
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    } else if (type === 'snippet') {
      setCopiedSnippet(true)
      setTimeout(() => setCopiedSnippet(false), 2000)
    }
    toast.success('Copied to clipboard!')
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Workspace Settings</h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage your business identity, public customer access channels, and widget security tokens.
        </p>
      </div>

      <div className="space-y-6">
        {/* Workspace Identity Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-slate-100">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
              <Building size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Business Details</h2>
              <p className="text-xs text-slate-500">Multi-tenant business identifiers and owner identity</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
              <span className="text-xs font-medium text-slate-500 block mb-1">Business Name</span>
              <span className="text-sm font-semibold text-slate-900 block truncate">
                {user?.business_name || 'Support Brain Business'}
              </span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
              <span className="text-xs font-medium text-slate-500 block mb-1">Workspace Owner</span>
              <span className="text-sm font-semibold text-slate-900 block truncate">
                {user?.full_name} ({user?.email})
              </span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
              <span className="text-xs font-medium text-slate-500 block mb-1">Business Slug</span>
              <span className="text-sm font-mono text-slate-800 block truncate">
                {user?.business_slug}
              </span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
              <span className="text-xs font-medium text-slate-500 block mb-1">Business UUID</span>
              <span className="text-xs font-mono text-slate-600 block truncate">
                {user?.business_id}
              </span>
            </div>
          </div>
        </div>

        {/* Public Customer Access & Widget Security */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-slate-100">
            <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600">
              <ShieldCheck size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Customer Access & Widget Token</h2>
              <p className="text-xs text-slate-500">Public customer channels with zero authentication required for customers</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Public Chat Link */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Direct Public Customer Chat Link
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={publicChatUrl}
                  className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm font-mono px-3.5 py-2.5 rounded-xl focus:outline-none"
                />
                <button
                  onClick={() => copyToClipboard(publicChatUrl, 'link')}
                  className="shrink-0 p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                  title="Copy link"
                >
                  {copiedLink ? <Check size={18} className="text-emerald-600" /> : <Copy size={18} />}
                </button>
                <a
                  href={publicChatUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0 p-2.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-600 transition-colors"
                  title="Open chat in new tab"
                >
                  <ExternalLink size={18} />
                </a>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Share this link directly with customers. They can chat anonymously without signing in.
              </p>
            </div>

            {/* Public Widget Token */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5 flex items-center gap-1.5">
                <Key size={13} className="text-indigo-600" />
                Public Widget Token
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={widgetToken}
                  className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm font-mono px-3.5 py-2.5 rounded-xl focus:outline-none"
                />
                <button
                  onClick={() => copyToClipboard(widgetToken, 'token')}
                  className="shrink-0 p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                  title="Copy token"
                >
                  {copiedToken ? <Check size={18} className="text-emerald-600" /> : <Copy size={18} />}
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                This secure token authorizes customer requests for your business on external websites.
              </p>
            </div>

            {/* Embed Script Snippet */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Code size={13} className="text-indigo-600" />
                  Website Embed Snippet
                </label>
                <button
                  onClick={() => copyToClipboard(embedSnippet, 'snippet')}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
                >
                  {copiedSnippet ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                  Copy Code
                </button>
              </div>
              <div className="relative">
                <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto border border-slate-800">
                  {embedSnippet}
                </pre>
              </div>
              <p className="text-xs text-slate-400 mt-1.5">
                Paste this script tag into the HTML of any website right before the closing <code className="text-slate-600 bg-slate-100 px-1 py-0.5 rounded">&lt;/body&gt;</code> tag.
              </p>
            </div>
          </div>
        </div>

        {/* AI & RAG Engine Specifications */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center text-violet-600">
              <Cpu size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">AI Intelligence Engine</h2>
              <p className="text-xs text-slate-500">Live verified Google Gemini API models powering this workspace</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-violet-50/60 rounded-xl border border-violet-100">
              <span className="font-semibold text-violet-900 block mb-0.5">Primary Generation Model</span>
              <span className="font-mono text-violet-700">gemini-3.8-flash</span>
            </div>
            <div className="p-3 bg-violet-50/60 rounded-xl border border-violet-100">
              <span className="font-semibold text-violet-900 block mb-0.5">Semantic Vector Embedding</span>
              <span className="font-mono text-violet-700">gemini-embedding-001 (768 dims)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
