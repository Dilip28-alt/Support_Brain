import { useEffect, useState, useRef } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import { Upload, Globe, FileText, Trash2, RefreshCw, Eye, Loader2, Plus, ChevronDown, ChevronUp, Brain } from 'lucide-react'

function SourceBadge({ type }) {
  const map = { text: 'badge-blue', pdf: 'badge-red', url: 'badge-green' }
  return <span className={map[type] || 'badge-gray'}>{type?.toUpperCase()}</span>
}

export default function KnowledgePage() {
  const [sources, setSources]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [activeTab, setActiveTab] = useState('text')
  const [text, setText]           = useState({ title: '', content: '' })
  const [url, setUrl]             = useState({ url: '', title: '' })
  const [submitting, setSubmitting] = useState(false)
  const [expandedSource, setExpandedSource] = useState(null)
  const [chunks, setChunks]       = useState({})
  const fileRef = useRef()

  const loadSources = () => {
    setLoading(true)
    api.get('/knowledge/sources')
      .then(r => setSources(Array.isArray(r.data) ? r.data : []))
      .catch(err => {
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
      toast.success('Text knowledge added!')
      setText({ title: '', content: '' })
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add text')
    } finally { setSubmitting(false) }
  }

  const submitUrl = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await api.post('/knowledge/url', url)
      toast.success('URL scraped and added!')
      setUrl({ url: '', title: '' })
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to scrape URL')
    } finally { setSubmitting(false) }
  }

  const uploadPDF = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) { toast.error('Only PDF files accepted'); return }
    const fd = new FormData()
    fd.append('file', file)
    setSubmitting(true)
    try {
      await api.post('/knowledge/pdf', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      toast.success('PDF uploaded and processed!')
      loadSources()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload PDF')
    } finally { setSubmitting(false); e.target.value = '' }
  }

  const deleteSource = async (id) => {
    if (!confirm('Delete this knowledge source and all its chunks?')) return
    await api.delete(`/knowledge/sources/${id}`)
    toast.success('Deleted')
    loadSources()
  }

  const reprocess = async (id) => {
    await api.post(`/knowledge/sources/${id}/reprocess`)
    toast.success('Reprocessed!')
    loadSources()
  }

  const viewChunks = async (id) => {
    if (expandedSource === id) { setExpandedSource(null); return }
    setExpandedSource(id)
    if (!chunks[id]) {
      const { data } = await api.get(`/knowledge/sources/${id}/chunks`)
      setChunks(c => ({ ...c, [id]: data }))
    }
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Knowledge Brain</h1>

      {/* Add knowledge tabs */}
      <div className="card mb-6">
        <div className="flex gap-2 mb-4 border-b border-gray-100 pb-3">
          {[
            { key: 'text', Icon: FileText, label: 'Add Text' },
            { key: 'url',  Icon: Globe,    label: 'Import URL' },
            { key: 'pdf',  Icon: Upload,   label: 'Upload PDF' },
          ].map(({ key, Icon, label }) => (
            <button key={key} onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === key ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-50'
              }`}>
              <Icon size={15} />{label}
            </button>
          ))}
        </div>

        {activeTab === 'text' && (
          <form onSubmit={submitText} className="space-y-3">
            <input className="input" placeholder="Title" required value={text.title}
              onChange={e => setText(t => ({ ...t, title: e.target.value }))} />
            <textarea className="input h-32 resize-none" placeholder="Paste your knowledge content here…"
              required value={text.content}
              onChange={e => setText(t => ({ ...t, content: e.target.value }))} />
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={submitting}>
              {submitting && <Loader2 size={14} className="animate-spin" />} Add to Brain
            </button>
          </form>
        )}

        {activeTab === 'url' && (
          <form onSubmit={submitUrl} className="space-y-3">
            <input className="input" placeholder="https://yourwebsite.com/faq" type="url" required
              value={url.url} onChange={e => setUrl(u => ({ ...u, url: e.target.value }))} />
            <input className="input" placeholder="Title (optional)" value={url.title}
              onChange={e => setUrl(u => ({ ...u, title: e.target.value }))} />
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={submitting}>
              {submitting && <Loader2 size={14} className="animate-spin" />} Scrape & Add
            </button>
          </form>
        )}

        {activeTab === 'pdf' && (
          <div>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={uploadPDF} />
            <div onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-brand-300 hover:bg-brand-50 transition-colors">
              {submitting ? (
                <Loader2 size={24} className="animate-spin text-brand-600 mx-auto mb-2" />
              ) : (
                <Upload size={24} className="text-gray-400 mx-auto mb-2" />
              )}
              <p className="text-sm text-gray-600">{submitting ? 'Processing PDF…' : 'Click to upload PDF (max 10MB)'}</p>
            </div>
          </div>
        )}
      </div>

      {/* Sources list */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Knowledge Sources ({sources.length})
        </h2>
        {loading ? (
          <div className="text-gray-400 text-sm">Loading…</div>
        ) : sources.length === 0 ? (
          <div className="card text-center text-gray-400 py-12">
            <Brain size={40} className="mx-auto mb-3 opacity-30" />
            <p>No knowledge added yet. Add your first source above.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map(src => (
              <div key={src.id} className="card">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <SourceBadge type={src.source_type} />
                      {src.is_processed ? (
                        <span className="badge-green">Processed</span>
                      ) : (
                        <span className="badge-yellow">Pending</span>
                      )}
                    </div>
                    <p className="font-medium text-gray-900 truncate">{src.title || src.file_name || src.source_url}</p>
                    <p className="text-xs text-gray-500 mt-1">{src.chunk_count} chunks · {new Date(src.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => viewChunks(src.id)}
                      className="p-2 rounded-lg text-gray-400 hover:bg-gray-50 hover:text-gray-700" title="View chunks">
                      {expandedSource === src.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button onClick={() => reprocess(src.id)}
                      className="p-2 rounded-lg text-gray-400 hover:bg-gray-50 hover:text-gray-700" title="Reprocess">
                      <RefreshCw size={16} />
                    </button>
                    <button onClick={() => deleteSource(src.id)}
                      className="p-2 rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600" title="Delete">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* Expanded chunks */}
                {expandedSource === src.id && chunks[src.id] && (
                  <div className="mt-4 border-t border-gray-100 pt-4 space-y-2 max-h-64 overflow-y-auto">
                    {chunks[src.id].map(chunk => (
                      <div key={chunk.id} className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700">
                        <p className="text-xs text-gray-400 mb-1">Chunk {chunk.chunk_index + 1} · {chunk.token_count} tokens</p>
                        <p className="line-clamp-3">{chunk.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
