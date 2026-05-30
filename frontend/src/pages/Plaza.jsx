import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import ReportDrawer from '../components/ReportDrawer'
import DataDrawer from '../components/DataDrawer'
import {
  Flame, FileText, Rss, Database, Clock, Landmark, BarChart3,
  TrendingUp, ChevronRight, ExternalLink, Loader2,
  Newspaper, MoreHorizontal, Sparkles
} from 'lucide-react'

import clsx from 'clsx'


const MODULE_ICONS = {
  hot_topics: { icon: Flame, color: 'text-red-400', bg: 'bg-red-500/10' },
  policy: { icon: Landmark, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  exchange: { icon: BarChart3, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  financial: { icon: TrendingUp, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  rss: { icon: Rss, color: 'text-purple-400', bg: 'bg-purple-500/10' },
}

const REPORT_TYPE_MAP = {
  agent: { label: 'AI', cls: 'bg-purple-500/10 text-purple-400' },
  analysis: { label: 'AI', cls: 'bg-purple-500/10 text-purple-400' },
  report: { label: 'AI', cls: 'bg-purple-500/10 text-purple-400' },
  reports: { label: 'AI', cls: 'bg-purple-500/10 text-purple-400' },
  insight: { label: '洞察', cls: 'bg-sky-500/10 text-sky-400' },
  heartbeat: { label: '心跳', cls: 'bg-green-500/10 text-green-400' },
}
const defaultTypeBadge = { label: 'AI', cls: 'bg-purple-500/10 text-purple-400' }

export default function Plaza() {
  // Feed state
  const [feedItems, setFeedItems] = useState([])
  const [feedTasks, setFeedTasks] = useState([])
  const [selectedTask, setSelectedTask] = useState('')
  const [feedLoading, setFeedLoading] = useState(true)
  const [feedExpanded, setFeedExpanded] = useState(false)

  // Data explorer state
  const [dataTree, setDataTree] = useState({})
  const [treeLoading, setTreeLoading] = useState(true)
  const [dataDrawerKey, setDataDrawerKey] = useState(null) // module key to open

  // Reports state
  const [reportGroups, setReportGroups] = useState([])
  const [reportsLoading, setReportsLoading] = useState(true)
  const [selectedReport, setSelectedReport] = useState(null)
  const [expandedGroup, setExpandedGroup] = useState(null)

  useEffect(() => {
    api.get('/api/v1/plaza/feed').then(res => {
      setFeedItems(res.data?.data?.items || [])
      setFeedTasks(res.data?.data?.tasks || [])
    }).finally(() => setFeedLoading(false))

    api.get('/api/v1/plaza/data-tree').then(res => {
      setDataTree(res.data?.data || {})
    }).finally(() => setTreeLoading(false))

    api.get('/api/v1/plaza/reports').then(res => {
      setReportGroups(res.data?.data?.groups || [])
    }).finally(() => setReportsLoading(false))
  }, [])

  // Feed task switch
  useEffect(() => {
    if (!selectedTask) return
    setFeedLoading(true)
    setFeedExpanded(false)
    api.get(`/api/v1/plaza/feed?task_id=${selectedTask}`).then(res => {
      setFeedItems(res.data?.data?.items || [])
    }).finally(() => setFeedLoading(false))
  }, [selectedTask])

  return (
    <div className="space-y-10">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1.5">
          <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-orange-500/20 to-amber-500/10 border border-orange-500/20 flex items-center justify-center">
            <Flame size={18} className="text-orange-400" />
          </span>
          <h1 className="text-2xl font-bold text-white tracking-tight">情报广场</h1>
        </div>
        <p className="text-sm text-slate-500 pl-12">全网数据实时聚合，智能情报一站浏览</p>
      </div>

      {/* Banner: 关于平台 */}
      <Link to="/about"
        className="block bg-gradient-to-r from-blue-500/10 via-sky-500/8 to-purple-500/10 border border-[#1a2540]/80 rounded-xl p-4 hover:border-sky-500/30 transition-all duration-200 group">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/15 flex items-center justify-center">
              <Sparkles size={18} className="text-sky-400" />
            </div>
            <div>
              <div className="text-sm font-medium text-white group-hover:text-sky-400 transition-colors">探索 IntelHub 的愿景与未来</div>
              <div className="text-[11px] text-slate-500 mt-0.5">从数据采集到智能分析，了解我们的能力与演进方向</div>
            </div>
          </div>
          <ChevronRight size={16} className="text-slate-600 group-hover:text-sky-400 transition-colors" />
        </div>
      </Link>

      {/* ── 最新情报 ── */}
      <section>
        <div className="flex items-center gap-2.5 mb-4">
          <Newspaper size={17} className="text-blue-400" />
          <h2 className="text-base font-semibold text-white">最新情报</h2>
          {feedLoading && <Loader2 size={14} className="animate-spin text-blue-400" />}
        </div>

        {/* Task tabs */}
        <div className="flex gap-1.5 overflow-x-auto pb-2 mb-4">
          <button onClick={() => { setSelectedTask(''); setFeedExpanded(false); setFeedLoading(true); api.get('/api/v1/plaza/feed').then(r => { setFeedItems(r.data?.data?.items || []) }).finally(() => setFeedLoading(false)) }}
            className={clsx("px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-200 shrink-0",
              !selectedTask ? "bg-blue-500/15 text-blue-400 shadow-sm shadow-blue-500/5" : "bg-white/[0.03] text-slate-400 hover:text-slate-200 hover:bg-white/[0.06]"
            )}>
            全部
          </button>
          {feedTasks.map(t => (
            <button key={t.task_id} onClick={() => setSelectedTask(t.task_id)}
              className={clsx("px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-200 shrink-0",
                selectedTask === t.task_id ? "bg-blue-500/15 text-blue-400 shadow-sm shadow-blue-500/5" : "bg-white/[0.03] text-slate-400 hover:text-slate-200 hover:bg-white/[0.06]"
              )}>
              {t.task_name}
            </button>
          ))}
        </div>

        {/* Feed items */}
        <div className="grid gap-2.5 md:grid-cols-2">
          {(feedExpanded ? feedItems : feedItems.slice(0, 8)).map((item, i) => (
            <a key={i} href={item.url} target="_blank" rel="noopener"
              className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-3.5 hover:border-[#2a3f5f]/80 hover:bg-[#141e34] transition-all duration-200 flex items-start gap-3 group">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] text-slate-200 font-medium leading-snug line-clamp-2 group-hover:text-blue-400 transition-colors">{item.title}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-[11px] text-slate-500">{item.source_name}</span>
                  {item.timestamp && <span className="text-[11px] text-slate-600">{new Date(item.timestamp).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>}
                </div>
              </div>
              <ExternalLink size={13} className="text-slate-600 group-hover:text-blue-400 transition-colors shrink-0 mt-0.5" />
            </a>
          ))}
          {feedItems.length === 0 && !feedLoading && (
            <div className="col-span-2 text-center py-12 text-slate-500 text-sm">暂无情报数据</div>
          )}
        </div>
        {!feedExpanded && feedItems.length > 8 && (
          <button onClick={() => {
            setFeedExpanded(true)
            setFeedLoading(true)
            const url = selectedTask
              ? `/api/v1/plaza/feed?task_id=${selectedTask}&limit=100`
              : '/api/v1/plaza/feed?limit=100'
            api.get(url).then(r => { setFeedItems(r.data?.data?.items || []) }).finally(() => setFeedLoading(false))
          }}
            className="mt-3 text-xs text-slate-400 hover:text-blue-400 transition-colors flex items-center gap-1">
            <MoreHorizontal size={14} />
            查看更多情报
          </button>
        )}
      </section>

      {/* ── 报告橱窗 ── */}
      <section>
        <div className="flex items-center gap-2.5 mb-4">
          <FileText size={17} className="text-blue-400" />
          <h2 className="text-base font-semibold text-white">报告橱窗</h2>
          {reportsLoading && <Loader2 size={14} className="animate-spin text-blue-400" />}
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {reportGroups.map(group => {
            const preview = group.reports.slice(0, 3)
            const hasMore = group.reports.length > 3
            return (
              <div key={group.task_id}
                className="bg-[#111a2e]/60 rounded-xl border border-[#1a2540]/80 p-4 flex flex-col hover:border-[#2a3f5f]/60 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-white">{group.task_name}</h3>
                  <span className="text-[11px] text-slate-500 bg-white/[0.03] px-2 py-0.5 rounded-full">{group.report_count} 份</span>
                </div>
                <div className="space-y-1 flex-1">
                  {preview.map((r, i) => (
                    <div key={r.id || i}
                      className="flex items-start gap-2.5 p-2 rounded-lg hover:bg-white/[0.03] cursor-pointer transition-all duration-200 group"
                      onClick={() => setSelectedReport(r)}>
                      <span className={clsx("mt-0.5 text-[10px] px-1.5 py-0.5 rounded-md shrink-0 font-medium", (REPORT_TYPE_MAP[r.type] || defaultTypeBadge).cls)}>{(REPORT_TYPE_MAP[r.type] || defaultTypeBadge).label}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-slate-300 line-clamp-1 group-hover:text-blue-400 transition-colors">{r.title || r.name}</p>
                        <span className="text-[10px] text-slate-600">
                          {r.mtime && new Date(r.mtime).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                {hasMore && (
                  <button onClick={() => setExpandedGroup(expandedGroup === group.task_id ? null : group.task_id)}
                    className="mt-2 flex items-center gap-1 text-xs text-slate-400 hover:text-blue-400 transition-colors self-start">
                    <MoreHorizontal size={14} />
                    {expandedGroup === group.task_id ? '收起' : `共 ${group.reports.length} 份`}
                  </button>
                )}
                {expandedGroup === group.task_id && hasMore && (
                  <div className="space-y-1 mt-2 pt-2 border-t border-[#1a2540]/60">
                    {group.reports.slice(3).map((r, i) => (
                      <div key={r.id || `more-${i}`}
                        className="flex items-start gap-2.5 p-2 rounded-lg hover:bg-white/[0.03] cursor-pointer transition-all duration-200 group"
                        onClick={() => setSelectedReport(r)}>
                        <span className={clsx("mt-0.5 text-xs px-1.5 py-0.5 rounded shrink-0",
                          r.type === 'agent' ? 'bg-purple-500/10 text-purple-400' :
                          r.type === 'insight' ? 'bg-sky-500/10 text-sky-400' :
                          r.type === 'heartbeat' ? 'bg-green-500/10 text-green-400' :
                          'bg-slate-700 text-slate-400'
                        )}>{r.type === 'agent' ? 'AI' : r.type === 'insight' ? '洞察' : r.type === 'heartbeat' ? '心跳' : r.type}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-slate-300 line-clamp-1 group-hover:text-sky-400 transition-colors">{r.title || r.name}</p>
                          <span className="text-[10px] text-slate-600">
                            {r.mtime && new Date(r.mtime).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {reportGroups.length === 0 && !reportsLoading && (
            <div className="col-span-full text-center py-8 text-slate-500 text-sm">暂无报告</div>
          )}
        </div>
      </section>

      {/* ── 数据集市 ── */}
      <section>
        <div className="flex items-center gap-2.5 mb-4">
          <Database size={17} className="text-blue-400" />
          <h2 className="text-base font-semibold text-white">数据集市</h2>
          {treeLoading && <Loader2 size={14} className="animate-spin text-blue-400" />}
        </div>

        {!treeLoading && (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {Object.entries(dataTree).map(([key, info]) => {
              const cfg = MODULE_ICONS[key] || MODULE_ICONS.rss
              const Icon = cfg.icon
              const childCount = info.source_count || (info.children || []).length
              const totalItems = info.total_items || (info.children || []).reduce((s, c) => s + (c.item_count || 0), 0)
              return (
                <div key={key}
                  className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-4 hover:border-[#2a3f5f]/80 hover:bg-[#141e34] transition-all duration-200 cursor-pointer group"
                  onClick={() => setDataDrawerKey(key)}>
                  <div className={clsx("w-10 h-10 rounded-lg flex items-center justify-center mb-3", cfg.bg)}>
                    <Icon size={20} className={cfg.color} />
                  </div>
                  <h3 className="text-sm font-semibold text-white mb-1">{info.label}</h3>
                  <p className="text-[11px] text-slate-500">{childCount} 个渠道 · {totalItems} 条数据</p>
                  <ChevronRight size={13} className="text-slate-600 group-hover:text-blue-400 mt-2.5 transition-colors" />
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Report Drawer */}
      {selectedReport && (
        <ReportDrawer report={selectedReport} onClose={() => setSelectedReport(null)} />
      )}

      {/* Data Drawer */}
      {dataDrawerKey && dataTree[dataDrawerKey] && (
        <DataDrawer moduleKey={dataDrawerKey} moduleData={dataTree[dataDrawerKey]} onClose={() => setDataDrawerKey(null)} />
      )}
    </div>
  )
}
