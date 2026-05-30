import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { MessageSquare, Send, Loader2, ChevronDown, ChevronUp, Archive } from 'lucide-react'
import clsx from 'clsx'

const CATEGORY_MAP = {
  general: { label: '建议', cls: 'bg-sky-500/20 text-sky-400' },
  bug: { label: '问题', cls: 'bg-red-500/20 text-red-400' },
  feature: { label: '功能', cls: 'bg-purple-500/20 text-purple-400' },
  other: { label: '其他', cls: 'bg-slate-500/20 text-slate-400' },
}

const STATUS_MAP = {
  pending: { label: '待处理', cls: 'bg-yellow-500/20 text-yellow-400' },
  replied: { label: '已回复', cls: 'bg-emerald-500/20 text-emerald-400' },
  scheduled: { label: '已排期', cls: 'bg-blue-500/20 text-blue-400' },
  evaluating: { label: '评估中', cls: 'bg-purple-500/20 text-purple-400' },
  archived: { label: '已归档', cls: 'bg-slate-500/20 text-slate-500' },
}

const STATUS_OPTIONS = Object.entries(STATUS_MAP).map(([k, v]) => ({ value: k, label: v.label }))

function FeedbackCard({ fb, isAdmin, onReply, onStatus, replying, replyText, setReplyText }) {
  const cat = CATEGORY_MAP[fb.category] || CATEGORY_MAP.other
  const st = STATUS_MAP[fb.status] || STATUS_MAP.pending
  const isArchived = fb.status === 'archived'

  return (
    <div className={clsx(
      "bg-slate-800 rounded-xl p-4 border border-slate-700 transition-all",
      isArchived && "opacity-60"
    )}>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className={`text-[10px] px-2 py-0.5 rounded ${cat.cls}`}>{cat.label}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded ${st.cls}`}>{st.label}</span>
        {isAdmin && fb.nickname && (
          <span className="text-[11px] text-slate-400">{fb.nickname}</span>
        )}
        <span className="text-[11px] text-slate-600 ml-auto">
          {fb.created_at && new Date(fb.created_at).toLocaleString('zh-CN')}
        </span>
      </div>
      <p className="text-sm text-slate-300 whitespace-pre-wrap">{fb.content}</p>

      {/* Admin reply */}
      {fb.reply && (
        <div className="mt-3 pl-3 border-l-2 border-sky-500/30">
          <p className="text-xs text-slate-500 mb-1">管理员回复</p>
          <p className="text-sm text-slate-300 whitespace-pre-wrap">{fb.reply}</p>
        </div>
      )}

      {/* Admin actions */}
      {isAdmin && (
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700/50">
          <select value={fb.status}
            onChange={e => onStatus(fb.id, e.target.value)}
            className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-sky-500">
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {replying === fb.id ? (
            <div className="flex-1 flex items-center gap-2">
              <input type="text" value={replyText}
                onChange={e => setReplyText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && replyText.trim()) onReply(fb.id, replyText.trim()) }}
                placeholder="输入回复..."
                autoFocus
                className="flex-1 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500" />
              <button onClick={() => onReply(fb.id, replyText.trim())}
                className="text-xs text-sky-400 hover:text-sky-300 px-2 py-1">发送</button>
              <button onClick={() => { setReplyText(''); onReply(null) }}
                className="text-xs text-slate-500 hover:text-slate-300 px-1">取消</button>
            </div>
          ) : (
            <button onClick={() => { setReplyText(''); onReply(fb.id) }}
              className="text-xs text-slate-500 hover:text-sky-400 transition-colors">回复</button>
          )}
        </div>
      )}
    </div>
  )
}

export default function Feedback() {
  const user = api.getUser() || {}
  const isAdmin = user.role === 'admin'

  const [feedbacks, setFeedbacks] = useState([])
  const [archivedFeedbacks, setArchivedFeedbacks] = useState([])
  const [showArchived, setShowArchived] = useState(false)
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('general')
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [replying, setReplying] = useState(null)
  const [replyText, setReplyText] = useState('')

  useEffect(() => { loadFeedback() }, [])

  const loadFeedback = async () => {
    setLoading(true)
    try {
      if (isAdmin) {
        const [activeRes, archivedRes] = await Promise.all([
          api.get('/api/v1/feedback/admin?per_page=50&status=pending'),
          Promise.resolve(null),
        ])
        // Load all and split client-side
        const allRes = await api.get('/api/v1/feedback/admin?per_page=100')
        const all = allRes.data?.data?.items || []
        setFeedbacks(all.filter(f => f.status !== 'archived'))
        setArchivedFeedbacks(all.filter(f => f.status === 'archived'))
      } else {
        const res = await api.get('/api/v1/feedback/mine')
        setFeedbacks(res.data?.data || [])
      }
    } catch { /* not logged in */ }
    setLoading(false)
  }

  const handleSubmit = async () => {
    if (!content.trim()) return
    setSubmitting(true)
    try {
      await api.post('/api/v1/feedback', { content: content.trim(), category })
      setContent('')
      loadFeedback()
    } catch (e) {
      alert(e.response?.data?.error || e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReply = async (fid, reply) => {
    if (!fid) { setReplying(null); return }
    if (!reply) { setReplying(fid); return }
    try {
      await api.post(`/api/v1/feedback/admin/${fid}/reply`, { reply })
      setReplying(null)
      setReplyText('')
      loadFeedback()
    } catch (e) {
      alert(e.response?.data?.error || e.message)
    }
  }

  const handleStatus = async (fid, status) => {
    try {
      await api.post(`/api/v1/feedback/admin/${fid}/status`, { status })
      loadFeedback()
    } catch (e) {
      alert(e.response?.data?.error || e.message)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-lg bg-sky-500/10 flex items-center justify-center">
          <MessageSquare size={18} className="text-sky-400" />
        </span>
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            {isAdmin ? '反馈管理' : '用户反馈'}
          </h2>
          <p className="text-xs text-slate-500">
            {isAdmin ? `${feedbacks.length} 条待处理` : '帮助我们变得更好'}
          </p>
        </div>
      </div>

      {/* Submit form (not admin-only view) */}
      <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
        <div className="flex items-center gap-2 mb-3">
          {Object.entries(CATEGORY_MAP).map(([key, val]) => (
            <button key={key} onClick={() => setCategory(key)}
              className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${category === key ? val.cls : 'bg-slate-700/50 text-slate-500 hover:text-slate-300'}`}>
              {val.label}
            </button>
          ))}
        </div>
        <textarea value={content} onChange={e => setContent(e.target.value)}
          placeholder="告诉我们你的想法、遇到的问题、或想要的功能..."
          rows={3}
          className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 resize-none" />
        <div className="flex justify-between items-center mt-3">
          <span className="text-xs text-slate-600">{content.length}/2000</span>
          <button onClick={handleSubmit} disabled={submitting || !content.trim()}
            className="flex items-center gap-1.5 bg-sky-500/20 text-sky-400 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-40">
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {submitting ? '提交中...' : '提交反馈'}
          </button>
        </div>
      </div>

      {/* Feedback list */}
      {loading ? (
        <div className="text-slate-500 text-sm text-center py-8">加载中...</div>
      ) : feedbacks.length === 0 && (!isAdmin || archivedFeedbacks.length === 0) ? (
        <div className="text-center py-12">
          <MessageSquare size={32} className="text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">还没有反馈记录</p>
          <p className="text-slate-600 text-xs mt-1">提交你的第一条反馈吧</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {feedbacks.map(fb => (
              <FeedbackCard key={fb.id} fb={fb} isAdmin={isAdmin}
                onReply={handleReply} onStatus={handleStatus}
                replying={replying} replyText={replyText} setReplyText={setReplyText} />
            ))}
          </div>

          {/* Archived section (admin only) */}
          {isAdmin && archivedFeedbacks.length > 0 && (
            <div className="mt-4">
              <button onClick={() => setShowArchived(!showArchived)}
                className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <Archive size={12} />
                已归档 ({archivedFeedbacks.length})
                {showArchived ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showArchived && (
                <div className="space-y-3 mt-3">
                  {archivedFeedbacks.map(fb => (
                    <FeedbackCard key={fb.id} fb={fb} isAdmin={isAdmin}
                      onReply={handleReply} onStatus={handleStatus}
                      replying={replying} replyText={replyText} setReplyText={setReplyText} />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
