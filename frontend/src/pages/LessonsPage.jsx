import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import { BookOpen, Plus, Trash2, ToggleLeft, ToggleRight, Loader2, Edit2, Check, X } from 'lucide-react'

export default function LessonsPage() {
  const [lessons, setLessons]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]   = useState(null)
  const [editForm, setEditForm] = useState({})
  const [creating, setCreating] = useState(false)
  const [newLesson, setNewLesson] = useState({ question: '', corrected_answer: '', owner_comment: '' })

  const load = () => {
    setLoading(true)
    api.get('/lessons/').then(r => setLessons(r.data)).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggle = async (lesson) => {
    await api.patch(`/lessons/${lesson.id}`, { is_active: !lesson.is_active })
    toast.success(lesson.is_active ? 'Lesson deactivated' : 'Lesson activated')
    load()
  }

  const deleteLesson = async (id) => {
    if (!confirm('Delete this lesson?')) return
    await api.delete(`/lessons/${id}`)
    toast.success('Lesson deleted')
    load()
  }

  const saveEdit = async (id) => {
    await api.patch(`/lessons/${id}`, editForm)
    toast.success('Lesson updated')
    setEditing(null)
    load()
  }

  const createLesson = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      await api.post('/lessons/', newLesson)
      toast.success('Lesson created!')
      setNewLesson({ question: '', corrected_answer: '', owner_comment: '' })
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create lesson')
    } finally { setCreating(false) }
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Lessons</h1>
      <p className="text-sm text-gray-500 mb-6">
        Lessons are corrections the AI learns from. When a customer asks a similar question,
        the corrected answer takes priority over the Knowledge Brain.
      </p>

      {/* Create lesson */}
      <div className="card mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Add Manual Lesson</h2>
        <form onSubmit={createLesson} className="space-y-3">
          <input className="input" placeholder="Customer question" required
            value={newLesson.question} onChange={e => setNewLesson(l => ({ ...l, question: e.target.value }))} />
          <textarea className="input h-20 resize-none" placeholder="Correct answer" required
            value={newLesson.corrected_answer} onChange={e => setNewLesson(l => ({ ...l, corrected_answer: e.target.value }))} />
          <input className="input" placeholder="Comment (optional)"
            value={newLesson.owner_comment} onChange={e => setNewLesson(l => ({ ...l, owner_comment: e.target.value }))} />
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={creating}>
            {creating && <Loader2 size={14} className="animate-spin" />}
            <Plus size={16} /> Create Lesson
          </button>
        </form>
      </div>

      {/* Lessons list */}
      {loading ? <div className="text-gray-400 text-sm">Loading…</div> : lessons.length === 0 ? (
        <div className="card text-center py-12 text-gray-400">
          <BookOpen size={36} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">No lessons yet. They are created automatically from bad feedback.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {lessons.map(lesson => (
            <div key={lesson.id} className={`card border ${lesson.is_active ? 'border-gray-100' : 'border-gray-50 opacity-60'}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {editing === lesson.id ? (
                    <div className="space-y-2">
                      <textarea className="input h-16 resize-none text-sm" value={editForm.corrected_answer || lesson.corrected_answer}
                        onChange={e => setEditForm(f => ({ ...f, corrected_answer: e.target.value }))} />
                      <input className="input text-sm" placeholder="Comment" value={editForm.owner_comment || lesson.owner_comment || ''}
                        onChange={e => setEditForm(f => ({ ...f, owner_comment: e.target.value }))} />
                    </div>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-gray-900 mb-1">{lesson.question}</p>
                      <p className="text-sm text-green-700 bg-green-50 rounded px-2 py-1 mb-1">{lesson.corrected_answer}</p>
                      {lesson.owner_comment && <p className="text-xs text-gray-500">{lesson.owner_comment}</p>}
                      <p className="text-xs text-gray-400 mt-1">Used {lesson.usage_count} times · {new Date(lesson.created_at).toLocaleDateString()}</p>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {editing === lesson.id ? (
                    <>
                      <button onClick={() => saveEdit(lesson.id)} className="p-1.5 rounded text-green-600 hover:bg-green-50"><Check size={16} /></button>
                      <button onClick={() => setEditing(null)} className="p-1.5 rounded text-gray-400 hover:bg-gray-50"><X size={16} /></button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => { setEditing(lesson.id); setEditForm({}) }}
                        className="p-1.5 rounded text-gray-400 hover:bg-gray-50 hover:text-gray-700">
                        <Edit2 size={16} />
                      </button>
                      <button onClick={() => toggle(lesson)} title={lesson.is_active ? 'Deactivate' : 'Activate'}
                        className="p-1.5 rounded text-gray-400 hover:bg-gray-50">
                        {lesson.is_active ? <ToggleRight size={18} className="text-green-500" /> : <ToggleLeft size={18} />}
                      </button>
                      <button onClick={() => deleteLesson(lesson.id)}
                        className="p-1.5 rounded text-gray-400 hover:bg-red-50 hover:text-red-600">
                        <Trash2 size={16} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
