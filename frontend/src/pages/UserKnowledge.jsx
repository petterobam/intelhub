import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { BookOpen, Search, Clock, Tag, RefreshCw, Download, Crown, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

const TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} className={clsx(
      'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
      active ? 'bg-slate-800 text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-white'
    )}>{children}</button>
  )
}

export default function UserKnowledge() {
  const user = api.getUser() || {}
  const tierIdx = TIER_ORDER.indexOf(user.tier || 'free')
  const isV4Plus = tierIdx >= TIER_ORDER.indexOf('v4')

  const [tab, setTab] = useState('stats')
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadStats = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/user-kb/stats')
      setStats(res.data?.data || null)
    } catch { }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (!isV4Plus) { setLoading(false); return }
    loadStats()
  }, [loadStats, isV4Plus])

  if (loading) return <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  if (!isV4Plus) {
    return (
      <div className="text-center py-16">
        <Crown size={48} className="mx-auto text-slate-600 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">需要升级</h2>
        <p className="text-slate-400 text-sm">个人知识库功能需要 V4 及以上等级</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">个人知识库</h2>
        <p className="text-xs text-slate-500 mt-1">基于历史日报和订阅源的私有知识沉淀</p>
      </div>

      <div className="flex border-b border-slate-700 gap-1">
        <TabBtn active={tab === 'stats'} onClick={() => setTab('stats')}>概览</TabBtn>
        <TabBtn active={tab === 'topics'} onClick={() => setTab('topics')}>话题</TabBtn>
        <TabBtn active={tab === 'timeline'} onClick={() => setTab('timeline')}>时间线</TabBtn>
        <TabBtn active={tab === 'search'} onClick={() => setTab('search')}>搜索</TabBtn>
      </div>

      <div>
        {tab === 'stats' && <StatsTab stats={stats} onRebuild={loadStats} />}
        {tab === 'topics' && <TopicsTab />}
        {tab === 'timeline' && <TimelineTab />}
        {tab === 'search' && <SearchTab />}
      </div>
    </div>
  )
}

function StatsTab({ stats, onRebuild }) {
  const [building, setBuilding] = useState(false)
  const [msg, setMsg] = useState(null)

  const handleBuild = async () => {
    setBuilding(true)
    try {
      await api.post('/api/v1/user-kb/build')
      setMsg({ text: '构建已启动', ok: true })
      setTimeout(onRebuild, 2000)
    } catch (e) {
      setMsg({ text: e.message, ok: false })
    } finally { setBuilding(false) }
  }

  return (
    <div className="space-y-4">
      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={<Tag size={20} />} label="关注实体" value={stats?.entity_count ?? 0} />
        <StatCard icon={<BookOpen size={20} />} label="历史报告" value={stats?.report_count ?? 0} />
        <StatCard icon={<Clock size={20} />} label="话题数" value={stats?.topic_count ?? 0} />
      </div>

      <div className="flex items-center justify-between bg-slate-800 rounded-xl border border-slate-700 p-4">
        <div className="text-sm text-slate-400">
          {stats?.built
            ? `最后构建: ${stats.updated_at?.replace('T', ' ').substring(0, 16) || '-'}`
            : '尚未构建知识库'}
        </div>
        <div className="flex gap-2">
          <button onClick={handleBuild} disabled={building}
            className="flex items-center gap-2 px-3 py-1.5 bg-sky-500/20 text-sky-400 rounded-lg text-sm hover:bg-sky-500/30 disabled:opacity-50">
            <RefreshCw size={14} className={building ? 'animate-spin' : ''} />
            {building ? '构建中...' : '重新构建'}
          </button>
          <a href="/api/v1/user-kb/export" className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">
            <Download size={14} /> 导出
          </a>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 flex items-center gap-3">
      <div className="text-sky-400">{icon}</div>
      <div>
        <div className="text-xl font-bold text-white">{value}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
    </div>
  )
}

function TopicsTab() {
  const [topics, setTopics] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/api/v1/user-kb/topics').then(r => setTopics(r.data?.data || {})).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-slate-400 text-center py-4"><Loader2 className="animate-spin inline" /></div>

  const entries = Object.entries(topics)
  if (!entries.length) return <div className="text-slate-500 text-center py-8">暂无话题数据</div>

  return (
    <div className="space-y-3">
      {entries.map(([date, items]) => (
        <div key={date} className="bg-slate-800 rounded-xl border border-slate-700 p-4">
          <h4 className="text-sm text-sky-400 font-medium mb-2">{date}</h4>
          <div className="space-y-1">
            {(items || []).slice(0, 10).map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={clsx('px-1.5 py-0.5 rounded', item.source === 'daily_report' ? 'bg-sky-500/10 text-sky-400' : 'bg-purple-500/10 text-purple-400')}>
                  {item.source === 'daily_report' ? '日报' : '订阅'}
                </span>
                <span className="text-slate-300 truncate">{item.title}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function TimelineTab() {
  const [entities, setEntities] = useState([])
  const [selected, setSelected] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/api/v1/user-kb/stats').then(r => {
      // We need entity names — load entities.json indirectly via search
    }).catch(() => {})
    // Get entities from stats page or search
    api.get('/api/v1/user-kb/search?q=').catch(() => {})
    setLoading(false)
  }, [])

  // Actually load entities from the user profile tags
  useEffect(() => {
    api.get('/api/v1/profile/interests').then(r => {
      const tags = r.data?.data?.interest_tags || []
      setEntities(tags)
      if (tags.length > 0) {
        loadTimeline(tags[0].value)
      }
    }).catch(() => { setLoading(false) })
  }, [])

  const loadTimeline = async (entity) => {
    setSelected(entity)
    try {
      const res = await api.get(`/api/v1/user-kb/timeline/${encodeURIComponent(entity)}`)
      setItems(res.data?.data?.items || [])
    } catch { setItems([]) }
  }

  if (loading) return <div className="text-slate-400 text-center py-4"><Loader2 className="animate-spin inline" /></div>

  return (
    <div className="flex gap-4 h-[calc(100vh-280px)]">
      <div className="w-1/3 bg-slate-800 rounded-xl border border-slate-700 overflow-y-auto">
        <div className="px-4 py-3 border-b border-slate-700 text-sm text-slate-400">实体列表</div>
        {entities.map((e, i) => (
          <div key={i} onClick={() => loadTimeline(e.value)}
            className={clsx('px-4 py-3 cursor-pointer border-b border-slate-700/50 hover:bg-slate-700/50',
              selected === e.value && 'bg-sky-500/10 border-l-2 border-l-sky-400')}>
            <div className="text-sm text-white">{e.value}</div>
            <div className="text-xs text-slate-500">{e.type}</div>
          </div>
        ))}
        {entities.length === 0 && <div className="px-4 py-8 text-center text-slate-500 text-sm">请先设置兴趣标签</div>}
      </div>
      <div className="flex-1 bg-slate-800 rounded-xl border border-slate-700 overflow-y-auto">
        {selected ? (
          <div className="p-4 space-y-3">
            <h4 className="text-white font-medium">{selected} — 时间线</h4>
            {items.map((item, i) => (
              <div key={i} className="bg-slate-900 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-sky-400">{item.timestamp?.substring(0, 10)}</span>
                  <span className={clsx('text-xs px-1.5 py-0.5 rounded',
                    item.source === 'daily_report' ? 'bg-sky-500/10 text-sky-400' : 'bg-purple-500/10 text-purple-400')}>
                    {item.source === 'daily_report' ? '日报' : '订阅'}
                  </span>
                </div>
                <div className="text-sm text-slate-300">{item.title}</div>
              </div>
            ))}
            {items.length === 0 && <div className="text-slate-500 text-sm text-center py-4">暂无数据</div>}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">选择左侧实体查看时间线</div>
        )}
      </div>
    </div>
  )
}

function SearchTab() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const res = await api.get('/api/v1/user-kb/search', { params: { q: query } })
      setResults(res.data?.data || [])
    } catch { setResults([]) }
    finally { setSearching(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索个人知识库..."
          className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500" />
        <button onClick={handleSearch} disabled={searching}
          className="px-4 py-2 bg-sky-500/20 text-sky-400 rounded-lg text-sm hover:bg-sky-500/30 disabled:opacity-50">
          {searching ? '搜索中...' : '搜索'}
        </button>
      </div>

      <div className="space-y-2">
        {results.map((r, i) => (
          <div key={i} className="bg-slate-800 rounded-lg border border-slate-700 p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className={clsx('text-xs px-1.5 py-0.5 rounded',
                r.type === 'entity' ? 'bg-amber-500/10 text-amber-400' : 'bg-sky-500/10 text-sky-400')}>
                {r.type === 'entity' ? '实体' : '条目'}
              </span>
              {r.date && <span className="text-xs text-slate-500">{r.date}</span>}
            </div>
            <div className="text-sm text-slate-300">{r.name || r.title}</div>
          </div>
        ))}
        {results.length === 0 && query && !searching && (
          <div className="text-slate-500 text-sm text-center py-8">未找到相关内容</div>
        )}
      </div>
    </div>
  )
}
