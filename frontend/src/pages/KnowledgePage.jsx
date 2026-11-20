import { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import {
  Upload, Globe, FileText, Trash2, RefreshCw, Loader2,
  ChevronDown, ChevronUp, Brain, Edit2, X, Check, Eye
} from 'lucide-react'

function SourceBadge({ type }) {
  const map = {
    text: 'bg-blue-50 text-blue-700 border-blue-200',
    pdf: 'bg-rose-50 text-rose-700 border-rose-200',
    url: 'bg-emerald-50 text-emerald-700 border-emerald-200'
  }
  return (
    <span className={`px-2 py-0.5 text-xs font-semibold rounded-md border ${map[type] || 'bg-slate-50 text-slate-700 border-slate-200'}`}>
      {type?.toUpperCase()}
    </span>
  )
}

export default function KnowledgePage() {
  const [sources, setSources]         = useState([])
  const [loading, setLoading]         = useState(true)
  const [activeTab, setActiveTab]     = useState('text')
  const [text, setText]               = useState({ title: '', content: '' })
  const [url, setUrl]                 = useState({ url: '', title: '' })
  const [submitting, setSubmitting]   = useState(false)
  const [expandedSource, setExpandedSource] = useState(null)
  const [chunks, setChunks]           = useState({})
  const [editingSource, setEditingSource] = useState(null)
  const [editForm, setEditForm]       = useState({ title: '', content: '' })
  const [savingEdit, setSavingEdit]   = useState(false)
  const fileRef = useRef()

  const loadSources = () => {
    setLoading(true)
    api.get('/knowledge/sources')
      .then(r => setSources(Array.isArray(r.data) ? r.data : []))
      .catch(() => {
        toast.error('Failed to load knowledge sources')
        setSources([])
      })
      .finally(() => setLoading(false))
  }

  useEffect(loadSources, [])

  const submitText = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/knowledge/text', text)
      toast.success('Text knowledge ingested and embedded!')
      setText({ title: '', content: '' })
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add text')
    } finally {
      setSubmitting(false)
    }
  }

  const submitUrl = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/knowledge/url', url)
      toast.success('Website content scraped, chunked and embedded!')
      setUrl({ url: '', title: '' })
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to scrape URL')
    } finally {
      setSubmitting(false)
    }
  }

  const uploadPDF = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Only PDF files accepted')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    setSubmitting(true)
    try {
      await api.post('/knowledge/pdf', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      toast.success('PDF extracted, chunked, and embedded into pgvector!')
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload PDF')
    } finally {
      setSubmitting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const deleteSource = async (id) => {
    if (!confirm('Are you sure you want to delete this knowledge source and all its vector chunks?')) return
    try {
      await api.delete(`/knowledge/sources/${id}`)
      toast.success('Knowledge source and vectors deleted')
      loadSources()
    } catch {
      toast.error('Failed to delete knowledge source')
    }
  }

  const reprocess = async (id) => {
    try {
      await api.post(`/knowledge/sources/${id}/reprocess`)
      toast.success('Knowledge source re-chunked and re-embedded!')
      loadSources()
    } catch {
      toast.error('Failed to reprocess source')
    }
  }

  const viewChunks = async (id) => {
    if (expandedSource === id) {
      setExpandedSource(null)
      return
    }
    setExpandedSource(id)
    if (!chunks[id]) {
      try {
        const { data } = await api.get(`/knowledge/sources/${id}/chunks`)
        setChunks(c => ({ ...c, [id]: Array.isArray(data) ? data : [] }))
      } catch {
        toast.error('Failed to load chunks')
        setChunks(c => ({ ...c, [id]: [] }))
      }
    }
  }

  const openEditModal = (src) => {
    setEditingSource(src)
    setEditForm({
      title: src.title || '',
      content: src.original_content || '',
    })
  }

  const saveSourceEdit = async (e) => {
    e.preventDefault()
    if (!editingSource) return
    setSavingEdit(true)
    try {
      await api.patch(`/knowledge/sources/${editingSource.id}`, {
        title: editForm.title,
        content: editForm.content || undefined,
      })
      toast.success('Knowledge source updated and re-embedded!')
      setEditingSource(null)
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update knowledge source')
    } finally {
      setSavingEdit(false)
    }
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Knowledge Brain</h1>
        <p className="text-sm text-slate-500 mt-1">
          Add company policies, FAQs, product documentation, and website links. The AI uses these chunks to answer customer inquiries.
        </p>
      </div>

      {/* Ingestion Channels Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs mb-8">
        <div className="flex gap-2 mb-5 pb-4 border-b border-slate-100">
          {[
            { key: 'text', Icon: FileText, label: 'Add Plain Text' },
            { key: 'pdf',  Icon: Upload,   label: 'Upload PDF' },
            { key: 'url',  Icon: Globe,    label: 'Import Website URL' },
          ].map(({ key, Icon, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-colors ${
                activeTab === key
                  ? 'bg-indigo-50 text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>

        {/* Text Form */}
        {activeTab === 'text' && (
          <form onSubmit={submitText} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Document Title</label>
              <input
                className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3.5 py-2.5 rounded-xl focus:bg-white focus:outline-indigo-500"
                placeholder="e.g. Return & Refund Policy 2026"
                required
                value={text.title}
                onChange={e => setText(t => ({ ...t, title: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Knowledge Content</label>
              <textarea
                className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm p-3.5 rounded-xl h-36 resize-none focus:bg-white focus:outline-indigo-500 font-sans"
                placeholder="Paste store policies, pricing, guides, or specifications here..."
                required
                value={text.content}
                onChange={e => setText(t => ({ ...t, content: e.target.value }))}
              />
            </div>
            <button
              type="submit"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm px-4 py-2.5 rounded-xl transition-colors flex items-center gap-2 disabled:opacity-50"
              disabled={submitting}
            >
              {submitting && <Loader2 size={16} className="animate-spin" />}
              Save & Ingest into Brain
            </button>
          </form>
        )}

        {/* URL Form */}
        {activeTab === 'url' && (
          <form onSubmit={submitUrl} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Website URL</label>
              <input
                className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3.5 py-2.5 rounded-xl focus:bg-white focus:outline-indigo-500"
                placeholder="https://example.com/about-us"
                type="url"
                required
                value={url.url}
                onChange={e => setUrl(u => ({ ...u, url: e.target.value }))}
              />
              <span className="text-[11px] text-slate-400 mt-1 block">Protected by SSRF validation filters.</span>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Source Title (Optional)</label>
              <input
                className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3.5 py-2.5 rounded-xl focus:bg-white focus:outline-indigo-500"
                placeholder="Auto-detected from webpage title if left blank"
                value={url.title}
                onChange={e => setUrl(u => ({ ...u, title: e.target.value }))}
              />
            </div>
            <button
              type="submit"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm px-4 py-2.5 rounded-xl transition-colors flex items-center gap-2 disabled:opacity-50"
              disabled={submitting}
            >
              {submitting && <Loader2 size={16} className="animate-spin" />}
              Fetch, Clean & Chunk Webpage
            </button>
          </form>
        )}

        {/* PDF Form */}
        {activeTab === 'pdf' && (
          <div>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={uploadPDF} />
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-slate-200 hover:border-indigo-400 bg-slate-50 hover:bg-indigo-50/40 rounded-2xl p-10 text-center cursor-pointer transition-colors"
            >
              {submitting ? (
                <Loader2 size={28} className="animate-spin text-indigo-600 mx-auto mb-2" />
              ) : (
                <Upload size={28} className="text-slate-400 mx-auto mb-2" />
              )}
              <p className="text-sm font-semibold text-slate-700">
                {submitting ? 'Extracting text with PyMuPDF & generating embeddings…' : 'Click to select PDF document'}
              </p>
              <p className="text-xs text-slate-400 mt-1">Accepts PDF files up to 10MB</p>
            </div>
          </div>
        )}
      </div>

      {/* Sources List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">
            Knowledge Sources ({sources.length})
          </h2>
          <button
            onClick={loadSources}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="text-slate-400 text-sm py-8 text-center">Loading knowledge sources…</div>
        ) : sources.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400 shadow-xs">
            <Brain size={44} className="mx-auto mb-3 opacity-30 text-indigo-600" />
            <p className="font-semibold text-slate-700">No knowledge sources added yet</p>
            <p className="text-xs text-slate-400 mt-1">Use the forms above to feed your business Knowledge Brain.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map(src => (
              <div key={src.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs transition-shadow hover:shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <SourceBadge type={src.source_type} />
                      {src.is_processed ? (
                        <span className="px-2 py-0.5 text-xs font-semibold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Active ({src.chunk_count} Chunks)
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs font-semibold rounded-md bg-amber-50 text-amber-700 border border-amber-200">
                          Processing
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold text-slate-900 text-sm truncate" title={src.title}>
                      {src.title || src.file_name || src.source_url}
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">
                      Added on {new Date(src.created_at).toLocaleDateString()} · Source ID: <span className="font-mono text-slate-500">{src.id.slice(0, 8)}...</span>
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => viewChunks(src.id)}
                      className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                      title={expandedSource === src.id ? "Hide Chunks" : "View Individual Chunks"}
                    >
                      {expandedSource === src.id ? <ChevronUp size={16} /> : <Eye size={16} />}
                    </button>
                    <button
                      onClick={() => openEditModal(src)}
                      className="p-2 rounded-xl text-slate-500 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
                      title="Edit Source Title & Content"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => reprocess(src.id)}
                      className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                      title="Reprocess Source"
                    >
                      <RefreshCw size={16} />
                    </button>
                    <button
                      onClick={() => deleteSource(src.id)}
                      className="p-2 rounded-xl text-slate-500 hover:bg-rose-50 hover:text-rose-600 transition-colors"
                      title="Delete Source & Vectors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* Expanded Chunks Accordion */}
                {expandedSource === src.id && (
                  <div className="mt-4 border-t border-slate-100 pt-4">
                    <h4 className="text-xs font-semibold text-slate-700 mb-2.5">
                      Individual Vector Chunks ({Array.isArray(chunks[src.id]) ? chunks[src.id].length : 0})
                    </h4>
                    {!chunks[src.id] ? (
                      <div className="text-xs text-slate-400 py-2">Loading chunks…</div>
                    ) : !Array.isArray(chunks[src.id]) || chunks[src.id].length === 0 ? (
                      <div className="text-xs text-slate-400 py-2">No chunks found.</div>
                    ) : (
                      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                        {chunks[src.id].map(chunk => (
                          <div key={chunk.id} className="bg-slate-50 rounded-xl p-3 border border-slate-100 text-xs text-slate-700">
                            <div className="flex items-center justify-between text-slate-400 mb-1 text-[11px]">
                              <span>Chunk #{chunk.chunk_index + 1}</span>
                              <span className="font-mono">{chunk.token_count || 0} tokens · 768-dim vector</span>
                            </div>
                            <p className="line-clamp-3 leading-relaxed text-slate-800">{chunk.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit Source Modal */}
      {editingSource && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl border border-slate-100 overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Edit Knowledge Source</h3>
                <p className="text-xs text-slate-500 mt-0.5">Editing content will automatically regenerate fresh vector chunks.</p>
              </div>
              <button
                onClick={() => setEditingSource(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={saveSourceEdit} className="p-5 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">Source Title *</label>
                <input
                  className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3.5 py-2.5 rounded-xl focus:bg-white focus:outline-indigo-500"
                  value={editForm.title}
                  onChange={e => setEditForm(f => ({ ...f, title: e.target.value }))}
                  required
                />
              </div>
              {editingSource.source_type === 'text' && (
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">Content</label>
                  <textarea
                    className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm p-3.5 rounded-xl h-44 resize-none focus:bg-white focus:outline-indigo-500 font-sans"
                    value={editForm.content}
                    onChange={e => setEditForm(f => ({ ...f, content: e.target.value }))}
                  />
                </div>
              )}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setEditingSource(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-50"
                >
                  {savingEdit && <Loader2 size={15} className="animate-spin" />}
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
