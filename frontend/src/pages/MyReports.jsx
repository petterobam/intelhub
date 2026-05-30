import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import ReportDrawer from '../components/ReportDrawer'
import PushReportModal from '../components/PushReportModal'
import { FileText, Inbox, Mail, Loader2, ExternalLink, Clock, Layers, Send, Sparkles, Heart, BarChart3, TrendingUp, Activity, Sun } from 'lucide-react'
import clsx from 'clsx'

const TYPE_META = {
  insight:   { label: '洞察报告', icon: Sparkles,    color: 'text-blue-400',   bg: 'bg-blue-900/30' },
  heartbeat: { label: '心跳检测', icon: Heart,       color: 'text-green-400',  bg: 'bg-green-900/30' },
  aggregate: { label: '数据聚合', icon: Layers,      color: 'text-purple-400', bg: 'bg-purple-900/30' },
  resonance: { label: '共振分析', icon: Activity,    color: 'text-orange-400', bg: 'bg-orange-900/30' },
  trend:     { label: '趋势分析', icon: TrendingUp,   color: 'text-cyan-400',  bg: 'bg-cyan-900/30' },
  agent:     { label: 'Agent 报告', icon: BarChart3, color: 'text-pink-400',  bg: 'bg-pink-900/30' },
  reports:   { label: '综合简报', icon: Layers,      color: 'text-emerald-400', bg: 'bg-emerald-900/30' },
  report:    { label: '分析报告', icon: BarChart3,   color: 'text-amber-400',  bg: 'bg-amber-900/30' },
  analysis:  { label: '分析报告', icon: BarChart3,   color: 'text-amber-400',  bg: 'bg-amber-900/30' },
  personal_daily: { label: '偏好日报', icon: Sun,    color: 'text-orange-400', bg: 'bg-orange-900/30' },
  other:     { label: '其他', icon: FileText,         color: 'text-slate-400', bg: 'bg-slate-800/30' },
}

export default function MyReports() {
  // 一级 tab: personal / subscription / daily
  const [scope, setScope] = useState('personal')
  // 二级 tab: 'all' | task_id
  const [activeTaskId, setActiveTaskId] = useState('all')

  const [data, setData] = useState({
    personal: { reports: [], tasks: [] },
    subscription: { reports: [], tasks: [] },
    daily: { reports: [] },
    has_daily_enabled: false,
  })
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [pushReport, setPushReport] = useState(null)

  useEffect(() => {
    setLoading(true)
    api.get('/api/v1/user-reports')
      .then(res => {
        setData(res.data?.data || data)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const currentGroup = data[scope] || { reports: [], tasks: [] }
  const reports = currentGroup.reports || []
  const tasks = currentGroup.tasks || []

  const filtered = useMemo(() => {
    if (activeTaskId === 'all') return reports
    return reports.filter(r => r.task_id === activeTaskId)
  }, [reports, activeTaskId])

  // 切换 scope 时重置二级 tab
  const switchScope = (s) => {
    setScope(s)
    setActiveTaskId('all')
  }

  const openPreview = (r) => {
    setSelected({
      id: r.id,
      name: '',
      subdir: '',
      title: r.title,
      type: r.report_type,
      mtime: r.generated_at,
    })
  }

  return (
    <div className="space-y-6 w-full">
      <div>
        <h2 className="text-2xl font-bold text-white">我的报告</h2>
        <p className="text-xs text-slate-500 mt-1">查看个人报告和订阅的系统报告</p>
      </div>

      {/* 一级 tab: 个人 / 订阅 / 偏好日报 */}
      <div className="flex gap-1 bg-slate-800 rounded-lg p-1 w-fit">
        {[
          { key: 'personal', label: '个人报告', icon: FileText },
          { key: 'subscription', label: '订阅报告', icon: Mail },
          ...(data.has_daily_enabled ? [{ key: 'daily', label: '偏好日报', icon: Sun }] : []),
        ].map(t => (
          <button key={t.key} onClick={() => switchScope(t.key)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              scope === t.key ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'
            )}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {/* 二级 tab: 全部 + 各任务名 */}
      {tasks.length > 1 && (
        <div className="flex gap-1 bg-slate-800/60 rounded-lg p-1 w-fit flex-wrap">
          <button
            onClick={() => setActiveTaskId('all')}
            className={clsx(
              'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
              activeTaskId === 'all' ? 'bg-slate-600/60 text-slate-200' : 'text-slate-500 hover:text-slate-300'
            )}>
            <Layers size={12} className="inline mr-1 -mt-0.5" />全部
          </button>
          {tasks.map(t => (
            <button key={t.task_id} onClick={() => setActiveTaskId(t.task_id)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                activeTaskId === t.task_id ? 'bg-slate-600/60 text-slate-200' : 'text-slate-500 hover:text-slate-300'
              )}>
              {t.task_name}
            </button>
          ))}
        </div>
      )}

      {/* 报告列表 */}
      {loading ? (
        <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <Inbox size={48} className="mx-auto text-slate-600 mb-4" />
          <p className="text-slate-500">
            {scope === 'personal' ? '暂无个人报告' : scope === 'subscription' ? '暂无订阅报告' : '暂无偏好日报'}
          </p>
          {scope === 'daily' && (
            <p className="text-xs text-slate-600 mt-2">
              请在「我的偏好」中设置推送时间并保存，或在偏好页点击「立即生成」
            </p>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map(r => (
            <ReportCard key={r.id} report={r} onPreview={() => openPreview(r)} onPush={() => setPushReport(r)} />
          ))}
        </div>
      )}

      {selected && (
        <ReportDrawer report={selected} onClose={() => setSelected(null)} />
      )}

      {pushReport && (
        <PushReportModal
          report={pushReport}
          onClose={() => setPushReport(null)}
          onDone={() => setPushReport(null)}
        />
      )}
    </div>
  )
}

function ReportCard({ report, onPreview, onPush }) {
  const isSub = report.source === 'subscription'
  const date = report.generated_at ? new Date(report.generated_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''
  const meta = TYPE_META[report.report_type] || TYPE_META.other
  const Icon = meta.icon

  return (
    <div
      onClick={onPreview}
      className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-3 hover:border-sky-500/40 cursor-pointer transition-all group">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 flex-shrink-0 ${meta.color}`} />
        <span className="text-sm text-white font-medium truncate group-hover:text-sky-400 transition-colors">{report.title}</span>
      </div>
      {report.summary && (
        <p className="text-xs text-slate-400 mb-1 truncate">{report.summary}</p>
      )}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1">
          {report.task_name && (
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-700/50 text-slate-400">{report.task_name}</span>
          )}
          <span className={clsx('px-1.5 py-0.5 rounded text-[10px]', meta.bg, meta.color)}>{meta.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={e => { e.stopPropagation(); onPush() }}
            className="p-1 rounded text-slate-600 hover:text-sky-400 hover:bg-slate-700 transition-all" title="推送">
            <Send size={12} />
          </button>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {date}
          </span>
        </div>
      </div>
    </div>
  )
}
