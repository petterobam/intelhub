import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import { Activity, FileText, RefreshCw, AlertTriangle,
  CheckCircle, Zap } from 'lucide-react'
import clsx from 'clsx'

const relTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}d`
}

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
      <div className="flex items-center gap-2.5 mb-2.5">
        <div className={clsx("p-1.5 rounded-lg", `bg-${color}-500/15`)}>
          <Icon size={16} className={clsx(`text-${color}-400`)} />
        </div>
        <span className="text-slate-500 text-xs">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
      {sub && <div className="text-[11px] text-slate-600 mt-0.5">{sub}</div>}
    </div>
  )
}

function SystemHealth({ data }) {
  const { health_score, status, workers_total, workers_alive, platforms_total,
    platforms_fresh, platforms_stale, platforms_critical, platforms, alerts } = data

  const scoreColor = health_score >= 70 ? 'text-emerald-400' : health_score >= 40 ? 'text-yellow-400' : 'text-red-400'
  const scoreLabel = status === 'ok' ? '正常' : status === 'degraded' ? '降级' : '异常'

  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 h-full">
      <h3 className="text-white text-sm font-semibold mb-3">系统健康</h3>

      <div className="flex items-center gap-4 mb-3">
        <div className="text-center">
          <div className={clsx("text-3xl font-bold", scoreColor)}>{health_score}</div>
          <div className="text-[10px] text-slate-500">健康评分 · {scoreLabel}</div>
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Worker</span>
            <span className={clsx(workers_alive === workers_total ? 'text-emerald-400' : 'text-yellow-400')}>
              {workers_alive}/{workers_total} 在线
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">平台数据</span>
            <span>
              <span className="text-emerald-400">{platforms_fresh}</span>
              {platforms_stale > 0 && <span className="text-yellow-400 ml-1">{platforms_stale}慢</span>}
              {platforms_critical > 0 && <span className="text-red-400 ml-1">{platforms_critical}挂</span>}
              <span className="text-slate-600 ml-1">/ {platforms_total}</span>
            </span>
          </div>
        </div>
      </div>

      {platforms?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {platforms.slice(0, 16).map(p => (
            <div key={p.platform} className="flex items-center gap-1" title={`${p.platform} — ${p.age_minutes}m`}>
              <div className={clsx("w-1.5 h-1.5 rounded-full",
                p.status === 'fresh' ? 'bg-emerald-400' : p.status === 'stale' ? 'bg-yellow-400' : 'bg-red-400'
              )} />
              <span className="text-[10px] text-slate-500">{p.platform?.slice(0, 8)}</span>
            </div>
          ))}
        </div>
      )}

      {alerts?.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {alerts.slice(0, 2).map((a, i) => (
            <div key={i} className="flex items-center gap-1 text-[10px] text-red-400/80">
              <AlertTriangle size={10} />{a}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TaskExec({ data }) {
  const { recent_runs, last_24h, last_failures } = data

  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 h-full">
      <h3 className="text-white text-sm font-semibold mb-3">任务执行</h3>

      <div className="flex items-center gap-3 mb-3 text-[11px]">
        <span className="text-slate-500">24h:</span>
        <span className="text-slate-300">{last_24h.total} 次</span>
        <span className="text-emerald-400">{last_24h.done} 成功</span>
        {last_24h.failed > 0 && <span className="text-red-400">{last_24h.failed} 失败</span>}
        <span className="text-slate-600">
          {last_24h.avg_duration_ms ? `${(last_24h.avg_duration_ms / 1000).toFixed(1)}s` : ''}
        </span>
      </div>

      <div className="space-y-1 max-h-[180px] overflow-y-auto">
        {recent_runs.slice(0, 10).map(r => (
          <div key={r.id} className="flex items-center gap-2 text-[11px] py-0.5">
            <div className={clsx("w-1.5 h-1.5 rounded-full shrink-0",
              r.status === 'done' ? 'bg-emerald-400' :
              r.status === 'failed' ? 'bg-red-400' :
              r.status === 'running' ? 'bg-blue-400 animate-pulse' : 'bg-slate-500'
            )} />
            <span className="text-slate-300 truncate flex-1">{r.task_name}</span>
            <span className="text-slate-600 shrink-0">
              {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : relTime(r.started_at)}
            </span>
          </div>
        ))}
        {recent_runs.length === 0 && (
          <p className="text-slate-600 text-xs">暂无执行记录</p>
        )}
      </div>

      {last_failures.length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-700/50">
          <div className="text-[10px] text-red-400/60 mb-1">最近失败</div>
          {last_failures.slice(0, 3).map((f, i) => (
            <div key={i} className="text-[10px] text-red-400/80 truncate" title={f.error}>
              {f.task_name}: {f.error?.slice(0, 60)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const EVENT_ICONS = {
  report: FileText,
  task_done: CheckCircle,
}
const EVENT_COLORS = {
  report: 'text-purple-400',
  task_done: 'text-sky-400',
}

function ActivityFeed({ items }) {
  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 h-full">
      <h3 className="text-white text-sm font-semibold mb-3">动态</h3>
      <div className="space-y-1.5 max-h-[260px] overflow-y-auto">
        {items.map((e, i) => {
          const Icon = EVENT_ICONS[e.type] || Activity
          const color = EVENT_COLORS[e.type] || 'text-slate-400'
          return (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <Icon size={12} className={clsx(color, 'mt-0.5 shrink-0')} />
              <span className="text-slate-300 flex-1 truncate">{e.desc}</span>
              <span className="text-slate-600 shrink-0">{relTime(e.time)}</span>
            </div>
          )
        })}
        {items.length === 0 && (
          <p className="text-slate-600 text-xs">暂无动态</p>
        )}
      </div>
    </div>
  )
}

function Hotspots({ items }) {
  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60 h-full">
      <h3 className="text-white text-sm font-semibold mb-3">热点</h3>
      <div className="space-y-1">
        {items.map((h, i) => (
          <div key={i} className="flex items-center gap-2 text-[11px] py-0.5">
            <span className={clsx("w-4 text-right font-bold",
              i === 0 ? 'text-yellow-400' : i === 1 ? 'text-slate-300' : i === 2 ? 'text-orange-400' : 'text-slate-600'
            )}>{i + 1}</span>
            <span className="text-slate-300 flex-1 truncate">{h.keyword}</span>
            <span className="text-slate-600 shrink-0">{h.platform_count}p</span>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-slate-600 text-xs">暂无热点</p>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const loadData = useCallback(async (useCache = true) => {
    if (useCache) {
      try {
        const c = localStorage.getItem('intelhub_dashboard_v2')
        if (c) {
          const cached = JSON.parse(c)
          if (cached.ts && Date.now() - cached.ts < 60000) {
            setData(cached.d)
            setLoading(false)
            setLastRefresh(new Date(cached.ts))
            return
          }
        }
      } catch { /* ignore */ }
    }

    try {
      const res = await api.get('/api/v1/admin/dashboard')
      const d = res.data?.data || res.data || {}
      setData(d)
      setLastRefresh(new Date())
      localStorage.setItem('intelhub_dashboard_v2', JSON.stringify({ d, ts: Date.now() }))
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    const timer = setInterval(() => loadData(false), 60000)
    return () => clearInterval(timer)
  }, [loadData])

  if (loading) return <div className="text-slate-500 text-sm">加载中...</div>
  if (!data) return <div className="text-slate-500 text-sm">暂无数据</div>

  const s = data.top_stats || {}

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white tracking-tight">Dashboard</h2>
        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="text-[10px] text-slate-600">
              {lastRefresh.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button onClick={() => loadData(false)}
            className="text-slate-500 hover:text-slate-300 transition-colors">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Activity} label="任务" value={s.tasks_total || 0}
          sub={s.tasks_running > 0 ? `${s.tasks_running} 运行中` : '全部空闲'} color="blue" />
        <StatCard icon={FileText} label="今日报告" value={s.reports_today || 0} color="purple" />
        <StatCard icon={Zap} label="系统健康" value={data.system_health?.health_score ?? '-'}
          sub={data.system_health?.status === 'ok' ? '正常' : '异常'} color="emerald" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <SystemHealth data={data.system_health || {}} />
        <TaskExec data={data.task_exec || { recent_runs: [], last_24h: {}, last_failures: [] }} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ActivityFeed items={data.activity_feed || []} />
        <Hotspots items={data.hotspots || []} />
      </div>
    </div>
  )
}
