import { useAuth } from '../hooks/useAuth.jsx'

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="max-w-2xl space-y-6">
        {/* Business Info */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Workspace</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-500">Business ID</label>
              <p className="text-sm font-mono text-gray-700 mt-0.5">{user?.business_id}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Business Slug</label>
              <p className="text-sm font-mono text-gray-700 mt-0.5">{user?.business_slug}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Public Chat URL</label>
              <p className="text-sm font-mono text-brand-600 mt-0.5 break-all">
                {window.location.origin}/chat/{user?.business_slug}
              </p>
            </div>
          </div>
        </div>

        {/* Embed widget */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-900 mb-2">Embed Chat Widget</h2>
          <p className="text-sm text-gray-500 mb-3">
            Add this snippet to your website to embed the Support Brain chat widget:
          </p>
          <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 overflow-x-auto">
{`<iframe
  src="${window.location.origin}/chat/${user?.business_slug}"
  width="400" height="600"
  style="border:none;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.12)"
></iframe>`}
          </pre>
        </div>

        {/* AI Settings note */}
        <div className="card bg-blue-50 border-blue-100">
          <h2 className="text-sm font-semibold text-blue-800 mb-1">AI Configuration</h2>
          <p className="text-xs text-blue-700">
            Model: <strong>gemini-1.5-flash</strong> · Embeddings: <strong>text-embedding-004</strong> (768-dim)
          </p>
          <p className="text-xs text-blue-600 mt-1">
            Confidence threshold: 0.75 · Top-K chunks: 5 · Lesson similarity threshold: 0.80
          </p>
        </div>
      </div>
    </div>
  )
}
