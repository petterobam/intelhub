import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Heart, Globe, AlertTriangle, Activity, RefreshCw, CircleDot, ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

const PAGE_SIZE = 8

export default function Health() {
  const [health, setHealth] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [schedulers, setSchedulers] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedWorker, setExpandedWorker] = useState(null)
  const [pageMap, setPageMap] = useState({})

  const fetchData = () => {
    Promise.all([
      api.get('/api/v1/health'),
      api.get('/api/v1/health/crawlers'),
      api.get('/api/v1/health/schedulers'),
    ]).then(([h, c, s]) => {
      setHealth(h.data?.data || h.data || {})
      setFreshness(c.data?.data || c.data || {})
      setSchedulers(s.data?.data || null)
    }).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => {
    try {
      const c = localStorage.getItem('intelhub_health_cache')
      if (c) {
        const d = JSON.parse(c)
        if (d.health) setHealth(d.health)
        if (d.freshness) setFreshness(d.freshness)
        setLoading(false)
      }
    } catch { /* ignore */ }
    fetchData()
  }, [])

  if (loading) return <div className="text-slate-400">加载中...</div>

  const score = health?.health_score || 0
  const status = health?.status || 'unknown'
  const platforms = freshness?.platforms || []
  const scoreColor = score >= 70 ? 'text-emerald-400' : score >= 40 ? 'text-amber-400' : 'text-red-400'
  const statusLabel = status === 'ok' ? '正常运行' : status === 'degraded' ? '性能下降' : '需要关注'
  const sum = schedulers?.summary || {}

  const toggleWorker = (wid) => {
    setExpandedWorker(prev => prev === wid ? null : wid)
    setPageMap(prev => ({ ...prev, [wid]: 0 }))
  }

  return (
    <div className="space-y-6">
      {/* 顶部统计 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-6 text-center">
          <Heart size={28} className="mx-auto mb-2 text-blue-400" />
          <div className={clsx("text-4xl font-bold tracking-tight", scoreColor)}>{score}</div>
          <div className="text-xs text-slate-500 mt-1">{statusLabel}</div>
        </div>
        <div className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-6 text-center">
          <Globe size={28} className="mx-auto mb-2 text-blue-400" />
          <div className="text-4xl font-bold text-white tracking-tight">{freshness?.fresh_count || 0}<span className="text-lg text-slate-500">/{platforms.length}</span></div>
          <div className="text-xs text-slate-500 mt-1">平台正常</div>
        </div>
        <div className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-6 text-center">
          <AlertTriangle size={28} className="mx-auto mb-2 text-amber-400" />
          <div className="text-4xl font-bold text-white tracking-tight">{freshness?.critical_count || 0}</div>
          <div className="text-xs text-slate-500 mt-1">异常平台</div>
        </div>
      </div>

      {/* 调度器监控 */}
      <div className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-blue-400" />
            <h3 className="text-sm font-semibold text-white">调度器监控</h3>
          </div>
          <button onClick={fetchData} className="text-slate-500 hover:text-blue-400 transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>

        {!schedulers ? (
          <p className="text-slate-600 text-xs">暂无数据</p>
        ) : (
          <>
            {/* 统计卡片 */}
            <div className="grid grid-cols-5 gap-2 mb-4">
              <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                <div className="text-lg font-bold text-white">{sum.alive_workers || 0}</div>
                <div className="text-[10px] text-slate-500">存活 Worker</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                <div className="text-lg font-bold text-blue-400">{sum.system_tasks || 0}</div>
                <div className="text-[10px] text-slate-500">系统任务</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                <div className="text-lg font-bold text-purple-400">{sum.user_tasks || 0}</div>
                <div className="text-[10px] text-slate-500">用户任务</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                <div className="text-lg font-bold text-white">{(sum.system_tasks || 0) + (sum.user_tasks || 0)}</div>
                <div className="text-[10px] text-slate-500">总注册</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                <div className="text-lg font-bold text-emerald-400">{sum.running_tasks || 0}</div>
                <div className="text-[10px] text-slate-500">运行中</div>
              </div>
            </div>

            {/* Worker 列表 + 任务明细 */}
            <div className="space-y-1.5">
              {(schedulers.workers || []).map(w => {
                const isOpen = expandedWorker === w.worker_id && w.alive
                const tasks = w.role === 'system'
                  ? (schedulers.system_tasks || [])
                  : w.role === 'user'
                    ? (schedulers.user_tasks || [])
                    : []
                const page = pageMap[w.worker_id] || 0
                const totalPages = Math.ceil(tasks.length / PAGE_SIZE)
                const pageTasks = tasks.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

                return (
                  <div key={w.worker_id}>
                    {/* Worker 头 */}
                    <button
                      onClick={() => toggleWorker(w.worker_id)}
                      className="w-full flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors text-left"
                    >
                      <div className="flex items-center gap-2">
                        {isOpen ? <ChevronDown size={12} className="text-slate-500" /> : <ChevronRight size={12} className="text-slate-500" />}
                        <CircleDot size={7} className={w.alive ? "text-emerald-400" : "text-slate-600"} />
                        <span className="text-xs text-white font-medium">{w.worker_id}</span>
                        <span className={clsx(
                          "text-[9px] px-1.5 py-0.5 rounded font-medium",
                          w.role === 'system' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'
                        )}>{w.role}</span>
                        <span className="text-[10px] text-slate-600">{tasks.length} 个任务</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] text-slate-600">PID {w.pid || '-'}</span>
                        <span className={clsx("text-[10px]", w.alive ? "text-emerald-400" : "text-red-400")}>
                          {w.alive ? '存活' : '离线'}
                        </span>
                        <span className="text-[10px] text-slate-600">
                          {w.last_heartbeat ? new Date(w.last_heartbeat).toLocaleTimeString('zh-CN') : '-'}
                        </span>
                      </div>
                    </button>

                    {/* 展开的任务列表 — 仅存活 worker */}
                    {isOpen && w.alive && tasks.length > 0 && (
                      <div className="ml-5 mt-1 mb-2 border-l border-[#1a2540]/80 pl-3">
                        {/* 表头 */}
                        <div className="grid grid-cols-12 gap-2 px-2 py-1 text-[9px] text-slate-500 uppercase tracking-wider">
                          <div className="col-span-4">名称</div>
                          <div className="col-span-2">类型</div>
                          <div className="col-span-2">调度</div>
                          <div className="col-span-1">运行</div>
                          <div className="col-span-1">失败</div>
                          <div className="col-span-2">最近执行</div>
                        </div>
                        {pageTasks.map(t => (
                          <div key={t.id} className={clsx(
                            "grid grid-cols-12 gap-2 px-2 py-1.5 rounded text-[11px] transition-colors",
                            t.running ? 'bg-blue-500/5' : 'hover:bg-white/[0.02]'
                          )}>
                            <div className="col-span-4 flex items-center gap-1.5 min-w-0">
                              {t.running && <CircleDot size={6} className="text-blue-400 animate-pulse shrink-0" />}
                              <span className={clsx("truncate", t.running ? "text-blue-400" : "text-slate-300")}>{t.name}</span>
                              {t.owner && <span className="text-[9px] text-slate-600 shrink-0">({t.owner})</span>}
                            </div>
                            <div className="col-span-2 text-slate-500">{t.task_type}</div>
                            <div className="col-span-2 text-slate-500">{t.schedule_type}</div>
                            <div className="col-span-1 text-slate-400">{t.run_count || 0}</div>
                            <div className={clsx("col-span-1", (t.fail_count || 0) > 0 ? "text-red-400" : "text-slate-500")}>{t.fail_count || 0}</div>
                            <div className="col-span-2 text-slate-600 truncate">
                              {t.last_run ? new Date(t.last_run).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                            </div>
                          </div>
                        ))}
                        {/* 分页 */}
                        {totalPages > 1 && (
                          <div className="flex items-center justify-between px-2 mt-2">
                            <span className="text-[10px] text-slate-600">
                              第 {page + 1}/{totalPages} 页，共 {tasks.length} 条
                            </span>
                            <div className="flex gap-1">
                              <button
                                disabled={page === 0}
                                    onClick={() => setPageMap(p => ({ ...p, [w.worker_id]: Math.max(0, page - 1) }))}
                                className="text-[10px] px-2 py-0.5 rounded bg-white/[0.03] text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                              >上一页</button>
                              <button
                                disabled={page >= totalPages - 1}
                                onClick={() => setPageMap(p => ({ ...p, [w.worker_id]: Math.min(totalPages - 1, page + 1) }))}
                                className="text-[10px] px-2 py-0.5 rounded bg-white/[0.03] text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                              >下一页</button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {isOpen && w.alive && tasks.length === 0 && (
                      <div className="ml-5 mt-1 mb-2 text-[10px] text-slate-600 pl-3">无注册任务</div>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* 平台采集状态 */}
      {platforms.length > 0 && (
        <div className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-5">
          <h3 className="text-sm font-semibold text-white mb-3">平台采集状态</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-1">
            {platforms.map(p => {
              const dots = { fresh: 'bg-emerald-400', stale: 'bg-amber-400', critical: 'bg-red-400', missing: 'bg-slate-600' }
              return (
                <div key={p.platform} className="flex items-center gap-2 py-1">
                  <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", dots[p.status] || 'bg-slate-600')} />
                  <span className="text-[11px] text-slate-300 truncate">{p.platform}</span>
                  <span className="text-[10px] text-slate-600 ml-auto shrink-0">{p.age_minutes}m</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
