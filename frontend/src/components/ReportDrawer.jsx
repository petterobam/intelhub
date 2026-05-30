import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { ArrowLeft, Loader2, Calendar, Tag } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ReportDrawer({ report, onClose }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!report) return
    setLoading(true)
    setError('')
    // Prefer fetching by DB ID (works for all report locations)
    const fetchUrl = report.id
      ? `/api/v1/reports/by-id/${report.id}`
      : `/api/v1/reports/detail/${report.name}?subdir=${report.subdir || ''}`
    api.get(fetchUrl)
      .then(res => {
        const md = res.data?.data?.md || ''
        setContent(md || (res.data?.data?.json ? '```json\n' + JSON.stringify(res.data.data.json, null, 2) + '\n```' : '无内容'))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [report])

  if (!report) return null

  const typeLabel = report.type === 'agent' ? 'AI 报告' : report.type === 'insight' ? '洞察报告' : report.type === 'heartbeat' ? '心跳报告' : report.type

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 overflow-y-auto">
      {/* Top bar */}
      <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-4xl mx-auto flex items-center gap-3 px-6 py-3">
          <button onClick={onClose}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={16} />
            返回
          </button>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className={clsx("text-xs px-1.5 py-0.5 rounded shrink-0",
              report.type === 'agent' ? 'bg-purple-500/15 text-purple-400' :
              report.type === 'insight' ? 'bg-sky-500/15 text-sky-400' :
              report.type === 'heartbeat' ? 'bg-green-500/15 text-green-400' :
              'bg-slate-700 text-slate-400'
            )}>{typeLabel}</span>
            <h1 className="text-sm font-semibold text-white truncate">{report.title || report.name}</h1>
          </div>
          {report.mtime && (
            <span className="text-xs text-slate-500 shrink-0 hidden sm:block">
              {new Date(report.mtime).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })}
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-500">
            <Loader2 className="animate-spin mr-2" size={18} /> 加载中...
          </div>
        ) : error ? (
          <div className="text-red-400 text-sm py-12 text-center">{error}</div>
        ) : (
          <article className="prose prose-invert prose-slate max-w-none
            prose-headings:text-white prose-headings:font-semibold
            prose-h1:text-2xl prose-h1:border-b prose-h1:border-slate-800 prose-h1:pb-3 prose-h1:mb-6
            prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
            prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
            prose-p:text-slate-300 prose-p:leading-relaxed
            prose-a:text-sky-400 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-white prose-strong:font-semibold
            prose-code:text-sky-300 prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-slate-800 prose-pre:border prose-pre:border-slate-700 prose-pre:rounded-lg
            prose-li:text-slate-300
            prose-blockquote:border-l-sky-500 prose-blockquote:text-slate-400
            prose-hr:border-slate-700
            prose-table:text-sm
            prose-th:text-slate-200 prose-th:bg-slate-800/50
            prose-td:border-slate-700
          ">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  )
}

function clsx(...args) {
  return args.filter(Boolean).join(' ')
}
