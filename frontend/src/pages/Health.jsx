import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import { Heart, Globe, AlertTriangle, Activity, RefreshCw, CircleDot,
  ChevronDown, ChevronRight, Cpu, Clock, CheckCircle,
  XCircle, Zap, Flame, Rss, Landmark, TrendingUp, Newspaper, FileText
} from 'lucide-react'
import clsx from 'clsx'

const PAGE_SIZE = 8

const CATEGORY_META = {
  hot_topics: { label: '热点话题', icon: Flame, color: 'orange' },
  policy: { label: '政策法规', icon: Newspaper, color: 'blue' },
  exchange: { label: '交易所', icon: TrendingUp, color: 'sky' },
  financial: { label: '财经数据', icon: Landmark, color: 'purple' },
  rss: { label: 'RSS 订阅', icon: Rss, color: 'emerald' },
}

export default function Health() {
  const [health, setHealth] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [schedulers, setSchedulers] = useState(null)
  const [taskStats, setTaskStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedWorker, setExpandedWorker] = useState(null)
  const [pageMap, setPageMap] = useState({})
  const [expandedCategories, setExpandedCategories] = useState({})
  const [showInvalidRss, setShowInvalidRss] = useState(false)
  const [invalidRssPage, setInvalidRssPage] = useState(0)

  const fetchData = useCallback(() => {
    Promise.all([
      api.get('/api/v1/health'),
      api.get('/api/v1/health/crawlers'),
      api.get('/api/v1/health/schedulers'),
      api.get('/api/v1/health/task-stats'),
    ]).then(([h, c, s, ts]) => {
      const d = {
        health: h.data?.data || h.data || {},
        freshness: c.data?.data || c.data || {},
        schedulers: s.data?.data || null,
        taskStats: ts.data?.data || null,
      }
      setHealth(d.health)
      setFreshness(d.freshness)
      setSchedulers(d.schedulers)
      setTaskStats(d.taskStats)
      try { localStorage.setItem('intelhub_health_cache', JSON.stringify(d)) } catch {}
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    try {
      const c = localStorage.getItem('intelhub_health_cache')
      if (c) {
        const d = JSON.parse(c)
        if (d.health) setHealth(d.health)
        if (d.freshness) setFreshness(d.freshness)
        if (d.schedulers) setSchedulers(d.schedulers)
        if (d.taskStats) setTaskStats(d.taskStats)
        setLoading(false)
      }
    } catch { /* ignore */ }
    fetchData()
  }, [fetchData])

  if (loading) return <div className="text-slate-400">加载中...</div>

  const score = health?.health_score || 0
  const status = health?.status || 'unknown'
  const scoreColor = score >= 70 ? 'text-emerald-400' : score >= 40 ? 'text-amber-400' : 'text-red-400'
  const statusLabel = status === 'ok' ? '正常运行' : status === 'degraded' ? '性能下降' : '需要关注'
  const statusBg = status === 'ok' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : status === 'degraded' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
  const sum = schedulers?.summary || {}
  const stats = taskStats || {}
  const categoryGroups = freshness?.category_groups || {}
  const totalPlatforms = freshness?.platforms?.length || 0
  const freshCount = freshness?.fresh_count || 0
  const criticalCount = freshness?.critical_count || 0

  const toggleWorker = (wid) => {
    setExpandedWorker(prev => prev === wid ? null : wid)
    setPageMap(prev => ({ ...prev, [wid]: 0 }))
  }

  const toggleCategory = (cat) => {
    setExpandedCategories(prev => ({ ...prev, [cat]: !prev[cat] }))
  }

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold text-white tracking-tight">系统健康</h2>
          <span className={clsx("text-[11px] px-2 py-0.5 rounded-full border font-medium", statusBg)}>
            {statusLabel}
          </span>
        </div>
        <button onClick={fetchData} className="text-slate-500 hover:text-slate-300 transition-colors">
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Top stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-blue-500/15"><Heart size={14} className="text-blue-400" /></div>
            <span className="text-slate-500 text-xs">健康评分</span>
          </div>
          <div className="flex items-end gap-2">
            <span className={clsx("text-3xl font-bold tracking-tight", scoreColor)}>{score}</span>
            <span className="text-xs text-slate-600 mb-1">/100</span>
          </div>
        </div>

        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-emerald-500/15"><Globe size={14} className="text-emerald-400" /></div>
            <span className="text-slate-500 text-xs">平台数据</span>
          </div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold text-white tracking-tight">{freshCount}</span>
            <span className="text-sm text-slate-600 mb-1">/ {totalPlatforms}</span>
          </div>
          {(freshness?.critical_count > 0) && (
            <div className="text-[10px] mt-1">
              <span className="text-red-400">{freshness.critical_count} 异常</span>
            </div>
          )}
        </div>

        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-purple-500/15"><Cpu size={14} className="text-purple-400" /></div>
            <span className="text-slate-500 text-xs">Worker</span>
          </div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold text-white tracking-tight">{sum.alive_workers || 0}</span>
            <span className="text-sm text-slate-600 mb-1">/ {sum.total_workers || 0}</span>
          </div>
        </div>

        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-sky-500/15"><Zap size={14} className="text-sky-400" /></div>
            <span className="text-slate-500 text-xs">运行中</span>
          </div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold text-white tracking-tight">{sum.running_tasks || 0}</span>
            <span className="text-sm text-slate-600 mb-1">任务</span>
          </div>
        </div>
      </div>

      {/* Task execution stats */}
      {stats.last_24h && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="bg-slate-800/60 rounded-xl p-3.5 border border-slate-700/60">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Activity size={12} className="text-slate-500" />
              <span className="text-[11px] text-slate-500">24h 执行</span>
            </div>
            <span className="text-xl font-bold text-white">{stats.last_24h.total || 0}</span>
          </div>
          <div className="bg-slate-800/60 rounded-xl p-3.5 border border-slate-700/60">
            <div className="flex items-center gap-1.5 mb-1.5">
              <CheckCircle size={12} className="text-emerald-500" />
              <span className="text-[11px] text-slate-500">成功</span>
            </div>
            <span className="text-xl font-bold text-emerald-400">{stats.last_24h.done || 0}</span>
          </div>
          <div className="bg-slate-800/60 rounded-xl p-3.5 border border-slate-700/60">
            <div className="flex items-center gap-1.5 mb-1.5">
              <XCircle size={12} className="text-red-500" />
              <span className="text-[11px] text-slate-500">失败</span>
            </div>
            <span className="text-xl font-bold text-red-400">{stats.last_24h.failed || 0}</span>
          </div>
          <div className="bg-slate-800/60 rounded-xl p-3.5 border border-slate-700/60">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Clock size={12} className="text-blue-500" />
              <span className="text-[11px] text-slate-500">平均耗时</span>
            </div>
            <span className="text-xl font-bold text-white">
              {stats.last_24h.avg_duration_ms ? `${(stats.last_24h.avg_duration_ms / 1000).toFixed(1)}s` : '-'}
            </span>
          </div>
          <div className="bg-slate-800/60 rounded-xl p-3.5 border border-slate-700/60">
            <div className="flex items-center gap-1.5 mb-1.5">
              <FileText size={12} className="text-purple-500" />
              <span className="text-[11px] text-slate-500">成功率</span>
            </div>
            <span className={clsx("text-xl font-bold",
              (stats.last_24h.total > 0 && stats.last_24h.done / stats.last_24h.total >= 0.9) ? 'text-emerald-400' :
              stats.last_24h.failed > 0 ? 'text-amber-400' : 'text-white'
            )}>
              {stats.last_24h.total > 0 ? `${Math.round((stats.last_24h.done || 0) / stats.last_24h.total * 100)}%` : '-'}
            </span>
          </div>
        </div>
      )}

      {/* Scheduler monitoring */}
      <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Cpu size={16} className="text-blue-400" />
            <h3 className="text-sm font-semibold text-white">调度器监控</h3>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-4 text-[11px]">
              <span className="text-slate-500">系统任务 <span className="text-blue-400 font-medium">{sum.system_tasks || 0}</span></span>
              <span className="text-slate-500">总注册 <span className="text-white font-medium">{(sum.system_tasks || 0) + (sum.user_tasks || 0)}</span></span>
            </div>
          </div>
        </div>

        {!schedulers ? (
          <p className="text-slate-600 text-xs">暂无数据</p>
        ) : (
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

                  {isOpen && w.alive && tasks.length > 0 && (
                    <div className="ml-5 mt-1 mb-2 border-l border-slate-700/60 pl-3">
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
            {(!schedulers.workers || schedulers.workers.length === 0) && (
              <p className="text-slate-600 text-xs py-3 text-center">暂无 Worker 注册</p>
            )}
          </div>
        )}
      </div>

      {/* RSS 数据源健康摘要 */}
      {categoryGroups.rss && (() => {
        const rss = categoryGroups.rss
        const invalidList = (rss.platforms || []).filter(p => p.status === 'critical' || p.status === 'missing')
        const validCount = rss.fresh + rss.stale
        const pageSize = 20
        const totalPages = Math.ceil(invalidList.length / pageSize)
        const pageItems = invalidList.slice(invalidRssPage * pageSize, (invalidRssPage + 1) * pageSize)
        return (
          <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Rss size={15} className="text-emerald-400" />
                <h3 className="text-sm font-semibold text-white">RSS 数据源健康</h3>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <div className="text-lg font-bold text-emerald-400">{validCount}</div>
                  <div className="text-[10px] text-slate-500">有效</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-red-400">{rss.critical}</div>
                  <div className="text-[10px] text-slate-500">无效</div>
                </div>
                <div className="w-32 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${rss.total > 0 ? (validCount / rss.total) * 100 : 0}%` }} />
                </div>
                <span className="text-[10px] text-slate-500">{rss.total} 总计</span>
              </div>
            </div>

            {invalidList.length > 0 && (
              <div className="border-t border-slate-700/40 pt-3">
                <button
                  onClick={() => { setShowInvalidRss(!showInvalidRss); setInvalidRssPage(0) }}
                  className="flex items-center gap-1.5 text-xs text-red-400/80 hover:text-red-300 transition-colors"
                >
                  {showInvalidRss ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  <AlertTriangle size={12} />
                  <span>{invalidList.length} 个无效数据源</span>
                  <span className="text-[10px] text-slate-600 ml-1">（无数据或访问不通）</span>
                </button>

                {showInvalidRss && (
                  <div className="mt-2">
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-1">
                      {pageItems.map(p => (
                        <div key={p.platform} className="flex items-center gap-2 py-0.5" title={`${p.status} — ${p.age_minutes >= 9999 ? '无数据' : `${(p.age_minutes / 60).toFixed(0)}h前`}`}>
                          <span className="w-1.5 h-1.5 rounded-full shrink-0 bg-red-400" />
                          <span className="text-[11px] text-slate-400 truncate">{p.platform}</span>
                          <span className="text-[9px] text-slate-600 ml-auto shrink-0">
                            {p.age_minutes >= 9999 ? '无数据' : `${(p.age_minutes / 60).toFixed(0)}h`}
                          </span>
                        </div>
                      ))}
                    </div>
                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[10px] text-slate-600">
                          第 {invalidRssPage + 1}/{totalPages} 页，共 {invalidList.length} 条
                        </span>
                        <div className="flex gap-1">
                          <button disabled={invalidRssPage === 0}
                            onClick={() => setInvalidRssPage(p => Math.max(0, p - 1))}
                            className="text-[10px] px-2 py-0.5 rounded bg-white/[0.03] text-slate-400 hover:text-white disabled:opacity-30"
                          >上一页</button>
                          <button disabled={invalidRssPage >= totalPages - 1}
                            onClick={() => setInvalidRssPage(p => Math.min(totalPages - 1, p + 1))}
                            className="text-[10px] px-2 py-0.5 rounded bg-white/[0.03] text-slate-400 hover:text-white disabled:opacity-30"
                          >下一页</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })()}

      {/* 分类采集状态 */}
      {Object.keys(categoryGroups).length > 0 && (
        <div className="space-y-3">
          {Object.entries(categoryGroups).filter(([k]) => k !== 'rss').map(([catKey, catData]) => {
            const meta = CATEGORY_META[catKey] || { label: catKey, icon: Globe, color: 'slate' }
            const CatIcon = meta.icon
            const isExpanded = expandedCategories[catKey]
            const platforms = catData.platforms || []
            const displayPlatforms = isExpanded ? platforms : platforms.slice(0, 12)
            const hasMore = !isExpanded && platforms.length > displayPlatforms.length

            return (
              <div key={catKey} className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <CatIcon size={15} className={`text-${meta.color}-400`} />
                    <h3 className="text-sm font-semibold text-white">{meta.label}</h3>
                    <span className="text-[10px] text-slate-500">{catData.total} 个数据源</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 text-[11px]">{catData.fresh} 正常</span>
                    {catData.stale > 0 && <span className="text-amber-400 text-[11px]">{catData.stale} 过期</span>}
                    {catData.critical > 0 && <span className="text-red-400 text-[11px]">{catData.critical} 异常</span>}
                    <div className="w-24 h-1.5 bg-slate-700 rounded-full overflow-hidden ml-1">
                      <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${catData.total > 0 ? (catData.fresh / catData.total) * 100 : 0}%` }} />
                    </div>
                  </div>
                </div>

                {platforms.length > 0 ? (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-1">
                      {displayPlatforms.map(p => {
                        const dots = { fresh: 'bg-emerald-400', stale: 'bg-amber-400', critical: 'bg-red-400', missing: 'bg-slate-600' }
                        return (
                          <div key={p.platform} className="flex items-center gap-2 py-1">
                            <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", dots[p.status] || 'bg-slate-600')} />
                            <span className="text-[11px] text-slate-300 truncate">{p.platform}</span>
                            <span className="text-[10px] text-slate-600 ml-auto shrink-0">
                              {p.age_minutes >= 9999 ? '-' : p.age_minutes < 60 ? `${p.age_minutes}m` : `${(p.age_minutes / 60).toFixed(1)}h`}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                    {(hasMore || isExpanded) && (
                      <button
                        onClick={() => toggleCategory(catKey)}
                        className="mt-2 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                      >
                        {isExpanded ? '收起' : `展开全部 ${platforms.length} 个数据源`}
                      </button>
                    )}
                  </>
                ) : (
                  <p className="text-[11px] text-slate-600">暂无数据</p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Fallback: 无 category_groups 时展示平铺列表 */}
      {!Object.keys(categoryGroups).length && freshness?.platforms?.length > 0 && (
        <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/60">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Globe size={16} className="text-emerald-400" />
              <h3 className="text-sm font-semibold text-white">平台采集状态</h3>
            </div>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 正常</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> 延迟</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-400" /> 异常</span>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-1">
            {freshness.platforms.map(p => {
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

      {/* Alerts */}
      {freshness?.alerts?.length > 0 && (
        <div className="bg-red-500/5 rounded-xl p-4 border border-red-500/20">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-red-400" />
            <h3 className="text-sm font-semibold text-red-400">告警</h3>
          </div>
          <div className="space-y-1">
            {freshness.alerts.map((a, i) => (
              <div key={i} className="text-[11px] text-red-400/80">{a}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
