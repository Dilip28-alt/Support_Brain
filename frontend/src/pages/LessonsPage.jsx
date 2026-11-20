import { useEffect, useState } from 'react'
import api from '../services/api.js'
import toast from 'react-hot-toast'
import {
  BookOpen,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Loader2,
  Edit2,
  Check,
  X,
  Search,
  Sparkles,
  ShieldCheck,
  Clock
} from 'lucide-react'

export default function LessonsPage() {
  const [lessons, setLessons] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [editing, setEditing] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [creating, setCreating] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newLesson, setNewLesson] = useState({
    question: '',
    corrected_answer: '',
    owner_comment: '',
  })

  const load = () => {
    setLoading(true)
    api.get('/lessons/')
      .then((r) => setLessons(r.data))
      .catch(() => toast.error('Failed to load lessons'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggle = async (lesson) => {
    try {
      await api.patch(`/lessons/${lesson.id}`, { is_active: !lesson.is_active })
      toast.success(lesson.is_active ? 'Lesson deactivated' : 'Lesson activated')
      load()
    } catch {
      toast.error('Failed to update status')
    }
  }

  const deleteLesson = async (id) => {
    if (!window.confirm('Delete this lesson permanently?')) return
    try {
      await api.delete(`/lessons/${id}`)
      toast.success('Lesson deleted')
      load()
    } catch {
      toast.error('Failed to delete lesson')
    }
  }

  const saveEdit = async (id) => {
    try {
      await api.patch(`/lessons/${id}`, editForm)
      toast.success('Lesson updated & re-embedded!')
      setEditing(null)
      load()
    } catch {
      toast.error('Failed to save changes')
    }
  }

  const createLesson = async (e) => {
    e.preventDefault()
    if (!newLesson.question.trim() || !newLesson.corrected_answer.trim()) {
      toast.error('Please enter both question and correct answer')
      return
    }
    setCreating(true)
    try {
      await api.post('/lessons/', newLesson)
      toast.success('New lesson created & vector embedding indexed!')
      setNewLesson({ question: '', corrected_answer: '', owner_comment: '' })
      setShowAddForm(false)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create lesson')
    } finally {
      setCreating(false)
    }
  }

  const filtered = lessons.filter((l) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      l.question.toLowerCase().includes(q) ||
      l.corrected_answer.toLowerCase().includes(q) ||
      (l.owner_comment && l.owner_comment.toLowerCase().includes(q))
    )
  })

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BookOpen className="text-blue-600" size={26} />
            Lessons & Continuous Learning
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Lessons are verified owner corrections. When a customer asks a similar question, the lesson takes strict precedence over raw knowledge.
          </p>
        </div>

        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors self-start"
        >
          {showAddForm ? <X size={16} /> : <Plus size={16} />}
          <span>{showAddForm ? 'Close Form' : 'Add Manual Lesson'}</span>
        </button>
      </div>

      {/* Manual Add Lesson Form */}
      {showAddForm && (
        <div className="bg-white rounded-2xl border border-blue-200 p-6 mb-6 shadow-sm animate-in fade-in zoom-in-95">
          <div className="flex items-center gap-2 mb-4 text-blue-700 font-semibold text-sm">
            <Sparkles size={16} />
            <span>Create a New Verified Business Lesson</span>
          </div>
          <form onSubmit={createLesson} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Customer Question or Topic *
              </label>
              <input
                className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all placeholder:text-slate-400"
                placeholder="e.g., Do you offer refunds on digital goods?"
                required
                value={newLesson.question}
                onChange={(e) => setNewLesson((l) => ({ ...l, question: e.target.value }))}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Verified Correct Answer *
              </label>
              <textarea
                className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl p-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-24 resize-none transition-all placeholder:text-slate-400"
                placeholder="Enter the exact answer Support Brain should give whenever customers ask this or similar questions…"
                required
                value={newLesson.corrected_answer}
                onChange={(e) => setNewLesson((l) => ({ ...l, corrected_answer: e.target.value }))}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Owner Note / Context (optional)
              </label>
              <input
                className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 border border-slate-300 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all placeholder:text-slate-400"
                placeholder="e.g., Policy updated Q1 2026."
                value={newLesson.owner_comment}
                onChange={(e) => setNewLesson((l) => ({ ...l, owner_comment: e.target.value }))}
              />
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors"
                disabled={creating}
              >
                {creating && <Loader2 size={15} className="animate-spin" />}
                Save Lesson
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter / Search Bar */}
      <div className="relative mb-6">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Search lessons by question, answer, or comment…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
        />
      </div>

      {/* Lessons List */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400 text-sm">
          <Loader2 size={20} className="animate-spin text-blue-600 mr-2" />
          Loading lessons…
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 text-center py-16 px-4">
          <BookOpen size={44} className="mx-auto mb-3 text-slate-300" />
          <h3 className="text-base font-semibold text-slate-800">
            {searchQuery ? 'No matching lessons found' : 'No lessons created yet'}
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
            {searchQuery
              ? 'Try adjusting your search keywords.'
              : 'Lessons are automatically created when you correct a bad answer, resolve a pending question, or add one manually above.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((lesson) => {
            const isEditing = editing === lesson.id

            return (
              <div
                key={lesson.id}
                className={`bg-white rounded-2xl border p-5 transition-all shadow-sm ${
                  lesson.is_active ? 'border-slate-200' : 'border-slate-200/60 bg-slate-50/60 opacity-60'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded flex items-center gap-1 ${
                          lesson.is_active
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        <ShieldCheck size={11} />
                        {lesson.is_active ? 'Active Lesson' : 'Deactivated'}
                      </span>
                      <span className="text-xs text-slate-400">
                        Triggered {lesson.usage_count} times
                      </span>
                      <span className="text-xs text-slate-400">·</span>
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <Clock size={11} />
                        {new Date(lesson.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    {isEditing ? (
                      <div className="space-y-3 mt-2">
                        <div>
                          <label className="text-[11px] font-semibold text-slate-500 uppercase">Correct Answer</label>
                          <textarea
                            className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-20 resize-none"
                            value={editForm.corrected_answer ?? lesson.corrected_answer}
                            onChange={(e) => setEditForm((f) => ({ ...f, corrected_answer: e.target.value }))}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] font-semibold text-slate-500 uppercase">Owner Note</label>
                          <input
                            className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            value={editForm.owner_comment ?? lesson.owner_comment ?? ''}
                            onChange={(e) => setEditForm((f) => ({ ...f, owner_comment: e.target.value }))}
                          />
                        </div>
                      </div>
                    ) : (
                      <>
                        <h3 className="text-base font-semibold text-slate-900 leading-snug mb-2">
                          "{lesson.question}"
                        </h3>

                        <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl">
                          <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-0.5">
                            Verified Answer
                          </p>
                          <p className="text-sm text-slate-900 whitespace-pre-wrap font-medium">
                            {lesson.corrected_answer}
                          </p>
                        </div>

                        {lesson.owner_comment && (
                          <p className="text-xs text-slate-500 italic mt-2">
                            Note: {lesson.owner_comment}
                          </p>
                        )}
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => saveEdit(lesson.id)}
                          title="Save Changes"
                          className="p-2 rounded-xl text-emerald-600 hover:bg-emerald-50 transition-colors"
                        >
                          <Check size={18} />
                        </button>
                        <button
                          onClick={() => setEditing(null)}
                          title="Cancel"
                          className="p-2 rounded-xl text-slate-400 hover:bg-slate-100 transition-colors"
                        >
                          <X size={18} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            setEditing(lesson.id)
                            setEditForm({
                              corrected_answer: lesson.corrected_answer,
                              owner_comment: lesson.owner_comment,
                            })
                          }}
                          title="Edit Lesson"
                          className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                        >
                          <Edit2 size={16} />
                        </button>

                        <button
                          onClick={() => toggle(lesson)}
                          title={lesson.is_active ? 'Deactivate Lesson' : 'Activate Lesson'}
                          className="p-2 rounded-xl text-slate-400 hover:bg-slate-100 transition-colors"
                        >
                          {lesson.is_active ? (
                            <ToggleRight size={22} className="text-emerald-500" />
                          ) : (
                            <ToggleLeft size={22} className="text-slate-400" />
                          )}
                        </button>

                        <button
                          onClick={() => deleteLesson(lesson.id)}
                          title="Delete Lesson"
                          className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
