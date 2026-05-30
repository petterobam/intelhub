import { useState, useEffect } from 'react'
import { api } from '../api/client'
import {
  ArrowLeft, ChevronRight, ExternalLink, Loader2,
  Database, Flame, Landmark, BarChart3, TrendingUp, Rss
} from 'lucide-react'
import clsx from 'clsx'

const MODULE_ICONS = {
  hot_topics: { icon: Flame, color: 'text-red-400', bg: 'bg-red-500/10' },
  policy: { icon: Landmark, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  exchange: { icon: BarChart3, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  financial: { icon: TrendingUp, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  rss: { icon: Rss, color: 'text-purple-400', bg: 'bg-purple-500/10' },
}

export default function DataDrawer({ moduleKey, moduleData, onClose }) {
  const [subdir, setSubdir] = useState(null)
  const [subdirLabel, setSubdirLabel] = useState('')
  const [detailItems, setDetailItems] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [rssTab, setRssTab] = useState('')

  const cfg = MODULE_ICONS[moduleKey] || MODULE_ICONS.rss
  const Icon = cfg.icon
  const isRss = moduleKey === 'rss'

  // RSS task groups
  const rssGroups = isRss ? (moduleData?.task_groups || []) : []
  const activeGroup = rssGroups.find(g => g.task_id === rssTab) || rssGroups[0]

  // Default RSS tab
  useEffect(() => {
    if (isRss && rssGroups.length > 0 && !rssTab) {
      setRssTab(rssGroups[0].task_id)
    }
  }, [isRss, rssGroups, rssTab])

  // Load detail when subdir selected
  useEffect(() => {
    if (!subdir) return
    setDetailLoading(true)
    api.get(`/api/v1/plaza/data-detail?module=${moduleKey}&subdir=${subdir}`).then(res => {
      setDetailItems(res.data?.data?.items || [])
    }).catch(() => setDetailItems([])).finally(() => setDetailLoading(false))
  }, [moduleKey, subdir])

  // Non-RSS children
  const children = !isRss ? (moduleData?.children || []) : []

  // Current items to show at level 1
  const level1Children = isRss ? (activeGroup?.children || []) : children

  const goBack = () => {
    if (subdir) {
      setSubdir(null)
      setSubdirLabel('')
      setDetailItems([])
    } else {
      onClose()
    }
  }

  if (!moduleData) return null

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 overflow-y-auto">
      {/* Top bar */}
      <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-4xl mx-auto flex items-center gap-3 px-6 py-3">
          <button onClick={goBack}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={16} />
            {subdir ? subdirLabel : '返回'}
          </button>
          <div className="h-4 w-px bg-slate-700" />
          <div className={clsx("w-7 h-7 rounded flex items-center justify-center shrink-0", cfg.bg)}>
            <Icon size={15} className={cfg.color} />
          </div>
          <h1 className="text-sm font-semibold text-white truncate">{moduleData.label}</h1>
          <span className="text-xs text-slate-500 shrink-0">
            {moduleData.source_count || 0} 个渠道 · {moduleData.total_items || 0} 条
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* RSS task tabs (level 1 only) */}
        {isRss && !subdir && rssGroups.length > 1 && (
          <div className="flex gap-1 overflow-x-auto pb-3 mb-4">
            {rssGroups.map(g => (
              <button key={g.task_id} onClick={() => setRssTab(g.task_id)}
                className={clsx("px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors shrink-0",
                  rssTab === g.task_id ? "bg-purple-500/20 text-purple-400" : "bg-slate-800 text-slate-400 hover:text-white"
                )}>
                {g.task_name}
                <span className="ml-1 text-slate-500">{g.total_items}</span>
              </button>
            ))}
          </div>
        )}

        {/* Level 1: Sub-channels grid */}
        {!subdir && (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {level1Children.map(ch => (
              <div key={ch.name}
                className="bg-slate-800 rounded-xl border border-slate-700 p-4 hover:border-slate-500 cursor-pointer transition-colors group"
                onClick={() => { setSubdir(ch.name); setSubdirLabel(ch.display_name || ch.name) }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-white font-medium group-hover:text-sky-400 transition-colors">{ch.display_name || ch.name}</span>
                  <span className="text-xs text-slate-500">{ch.item_count} 条</span>
                </div>
                {ch.latest_time && (
                  <span className="text-xs text-slate-600">
                    更新于 {new Date(ch.latest_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
                <ChevronRight size={14} className="text-slate-600 group-hover:text-slate-400 mt-2 transition-colors" />
              </div>
            ))}
            {level1Children.length === 0 && (
              <div className="col-span-full text-center py-12 text-slate-500 text-sm">暂无数据</div>
            )}
          </div>
        )}

        {/* Level 2: Article list */}
        {subdir && (
          detailLoading ? (
            <div className="flex items-center justify-center py-20 text-slate-500">
              <Loader2 className="animate-spin mr-2" size={18} /> 加载中...
            </div>
          ) : (
            <div className="space-y-2">
              {detailItems.map((item, i) => (
                <a key={i} href={item.url || '#'} target="_blank" rel="noopener"
                  className="bg-slate-800 rounded-lg border border-slate-700 p-3 hover:border-slate-500 transition-colors flex items-start gap-3 group block">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium group-hover:text-sky-400 transition-colors">{item.title || '(无标题)'}</p>
                    {item.summary && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{item.summary}</p>}
                    {item.timestamp && <span className="text-xs text-slate-600 mt-1 block">{item.timestamp}</span>}
                  </div>
                  {item.url && <ExternalLink size={13} className="text-slate-600 group-hover:text-sky-400 shrink-0 mt-0.5" />}
                </a>
              ))}
              {detailItems.length === 0 && (
                <div className="text-center py-12 text-slate-500 text-sm">暂无数据</div>
              )}
            </div>
          )
        )}
      </div>
    </div>
  )
}
