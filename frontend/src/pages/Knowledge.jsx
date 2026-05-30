import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import { BookOpen, TrendingUp, Building2, Share2, Search, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

const TABS = [
  { key: 'topics', label: '话题排行', icon: TrendingUp },
  { key: 'industry', label: '行业分析', icon: Building2 },
  { key: 'graph', label: '实体图谱', icon: Share2 },
  { key: 'search', label: '搜索', icon: Search },
]

export default function Knowledge() {
  const [stats, setStats] = useState(null)
  const [topics, setTopics] = useState(null)
  const [industry, setIndustry] = useState(null)
  const [graph, setGraph] = useState(null)
  const [tab, setTab] = useState('topics')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [expandedIndustry, setExpandedIndustry] = useState(null)
  const [building, setBuilding] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadStats = useCallback(() => {
    api.get('/api/v1/kb/stats').then(r => setStats(r.data?.data || r.data || {})).catch(() => {})
  }, [])

  useEffect(() => {
    // Read cache first
    try {
      const c = localStorage.getItem('intelhub_kb_cache')
      if (c) {
        const d = JSON.parse(c)
        if (d.stats) setStats(d.stats)
        if (d.topics) setTopics(d.topics)
        if (d.industry) setIndustry(d.industry)
        if (d.graph) setGraph(d.graph)
        setLoading(false)
      }
    } catch { /* ignore */ }
    Promise.all([
      api.get('/api/v1/kb/stats'),
      api.get('/api/v1/kb/topics'),
      api.get('/api/v1/kb/industry'),
      api.get('/api/v1/kb/graph'),
    ]).then(([s, t, i, g]) => {
      const d = {
        stats: s.data?.data || s.data || {},
        topics: t.data?.data || t.data || {},
        industry: i.data?.data || i.data || {},
        graph: g.data?.data || g.data || {},
      }
      setStats(d.stats)
      setTopics(d.topics)
      setIndustry(d.industry)
      setGraph(d.graph)
      localStorage.setItem('intelhub_kb_cache', JSON.stringify(d))
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const r = await api.get(`/api/v1/kb/search?q=${encodeURIComponent(searchQuery)}`)
      setSearchResults(r.data?.data || r.data || [])
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleBuild = async () => {
    setBuilding(true)
    try {
      await api.post('/api/v1/kb/build', { module: 'all' })
      // Reload after a delay
      setTimeout(() => {
        loadStats()
        Promise.all([
          api.get('/api/v1/kb/topics'),
          api.get('/api/v1/kb/industry'),
          api.get('/api/v1/kb/graph'),
        ]).then(([t, i, g]) => {
          setTopics(t.data?.data || t.data || {})
          setIndustry(i.data?.data || i.data || {})
          setGraph(g.data?.data || g.data || {})
        }).catch(() => {})
      }, 2000)
    } catch {
    } finally {
      setBuilding(false)
    }
  }

  if (loading) return <div className="text-slate-400">加载中...</div>

  // Compute summary numbers
  const topicCount = topics?.top20?.length || 0
  const industryMap = industry?.industries || {}
  const industryCount = Object.keys(industryMap).length
  const nodeCount = graph?.nodes?.length || 0
  const edgeCount = graph?.edges?.length || 0

  const modules = stats?.modules || {}

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">知识库</h2>
        <button
          onClick={handleBuild}
          disabled={building}
          className={clsx(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            building
              ? "bg-slate-700 text-slate-400 cursor-not-allowed"
              : "bg-sky-500/20 text-sky-400 hover:bg-sky-500/30"
          )}
        >
          <RefreshCw size={16} className={building ? "animate-spin" : ""} />
          {building ? '构建中...' : '重新构建'}
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-slate-800 rounded-xl p-8 border border-slate-700 text-center">
          <TrendingUp size={40} className="mx-auto mb-3 text-sky-400" />
          <div className="text-5xl font-bold text-white mb-2">{topicCount}</div>
          <div className="text-sm text-slate-400">话题总数</div>
          <div className="text-xs text-slate-600 mt-2">
            {modules.topics?.status === 'ok'
              ? `更新于 ${new Date(modules.topics.last_updated).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
              : '暂无数据'}
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-8 border border-slate-700 text-center">
          <Building2 size={40} className="mx-auto mb-3 text-sky-400" />
          <div className="text-5xl font-bold text-white mb-2">{industryCount}</div>
          <div className="text-sm text-slate-400">行业分类</div>
          <div className="text-xs text-slate-600 mt-2">
            {modules.industry?.status === 'ok'
              ? `更新于 ${new Date(modules.industry.last_updated).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
              : '暂无数据'}
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-8 border border-slate-700 text-center">
          <Share2 size={40} className="mx-auto mb-3 text-sky-400" />
          <div className="text-5xl font-bold text-white mb-2">{nodeCount}</div>
          <div className="text-sm text-slate-400">实体节点</div>
          <div className="text-xs text-slate-600 mt-2">{edgeCount} 条关系</div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 bg-slate-800/50 rounded-lg p-1 w-fit">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={clsx(
              "flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              tab === t.key
                ? "bg-slate-700 text-sky-400"
                : "text-slate-400 hover:text-white hover:bg-slate-700/50"
            )}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        {tab === 'topics' && <TopicsTab topics={topics} />}
        {tab === 'industry' && <IndustryTab industry={industryMap} expanded={expandedIndustry} setExpanded={setExpandedIndustry} />}
        {tab === 'graph' && <GraphTab graph={graph} />}
        {tab === 'search' && (
          <SearchTab
            query={searchQuery}
            setQuery={setSearchQuery}
            results={searchResults}
            searching={searching}
            onSearch={handleSearch}
          />
        )}
      </div>
    </div>
  )
}

function TopicsTab({ topics }) {
  const top20 = topics?.top20 || []
  if (!top20.length) return <p className="text-slate-500 text-sm">暂无话题数据</p>

  return (
    <div>
      <h3 className="text-white font-semibold mb-4">热点话题 Top {top20.length}</h3>
      <div className="space-y-2">
        {top20.map((item, i) => (
          <div key={i} className="flex items-start gap-3 py-2 border-b border-slate-700/50 last:border-0">
            <span className={clsx(
              "text-xs font-bold px-2 py-0.5 rounded min-w-[2rem] text-center",
              i < 3 ? "bg-sky-500/20 text-sky-400" : "bg-slate-700 text-slate-400"
            )}>
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-slate-200 truncate">{item.title || item.keyword || '-'}</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {item.source && <span className="mr-3">来源: {item.source}</span>}
                {item.score !== undefined && <span>热度: {item.score}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function IndustryTab({ industry, expanded, setExpanded }) {
  const entries = Object.entries(industry)
  if (!entries.length) return <p className="text-slate-500 text-sm">暂无行业数据</p>

  return (
    <div>
      <h3 className="text-white font-semibold mb-4">行业分类 ({entries.length})</h3>
      <div className="space-y-2">
        {entries.map(([name, items]) => {
          const isOpen = expanded === name
          const itemList = Array.isArray(items) ? items : []
          return (
            <div key={name} className="border border-slate-700/50 rounded-lg">
              <button
                onClick={() => setExpanded(isOpen ? null : name)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isOpen ? <ChevronDown size={16} className="text-slate-400" /> : <ChevronRight size={16} className="text-slate-400" />}
                  <span className="text-sm text-slate-200 font-medium">{name}</span>
                </div>
                <span className="text-xs text-slate-500 bg-slate-700 px-2 py-0.5 rounded">{itemList.length} 条</span>
              </button>
              {isOpen && itemList.length > 0 && (
                <div className="px-4 pb-3 space-y-1">
                  {itemList.slice(0, 20).map((item, i) => (
                    <div key={i} className="text-xs text-slate-400 py-1 border-t border-slate-700/30">
                      {item.title || item.name || JSON.stringify(item).slice(0, 80)}
                    </div>
                  ))}
                  {itemList.length > 20 && (
                    <div className="text-xs text-slate-600 pt-1">还有 {itemList.length - 20} 条...</div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function GraphTab({ graph }) {
  const nodes = graph?.nodes || []
  const edges = graph?.edges || []
  if (!nodes.length && !edges.length) return <p className="text-slate-500 text-sm">暂无图谱数据</p>

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-white font-semibold mb-3">实体节点 ({nodes.length})</h3>
        {nodes.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {nodes.slice(0, 50).map((node, i) => (
              <span key={i} className="text-xs bg-slate-700 text-sky-300 px-3 py-1 rounded-full">
                {typeof node === 'string' ? node : node.name || node.id || JSON.stringify(node)}
              </span>
            ))}
            {nodes.length > 50 && <span className="text-xs text-slate-600 self-center">+{nodes.length - 50} 更多</span>}
          </div>
        ) : <p className="text-slate-500 text-xs">无节点</p>}
      </div>

      <div>
        <h3 className="text-white font-semibold mb-3">关系列表 ({edges.length})</h3>
        {edges.length > 0 ? (
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {edges.slice(0, 100).map((edge, i) => (
              <div key={i} className="text-xs text-slate-400 py-1 border-b border-slate-700/30 flex items-center gap-2">
                <span className="text-sky-300">{edge.from || edge.source}</span>
                <span className="text-slate-600">→</span>
                <span className="text-amber-300">{edge.relation || edge.type || '-'}</span>
                <span className="text-slate-600">→</span>
                <span className="text-sky-300">{edge.to || edge.target}</span>
              </div>
            ))}
            {edges.length > 100 && <div className="text-xs text-slate-600 pt-2">还有 {edges.length - 100} 条关系...</div>}
          </div>
        ) : <p className="text-slate-500 text-xs">无关系数据</p>}
      </div>
    </div>
  )
}

function SearchTab({ query, setQuery, results, searching, onSearch }) {
  return (
    <div>
      <div className="flex gap-3 mb-4">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onSearch()}
          placeholder="搜索话题、行业、实体..."
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
        />
        <button
          onClick={onSearch}
          disabled={searching}
          className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-50"
        >
          {searching ? '搜索中...' : '搜索'}
        </button>
      </div>

      {!results.length && !searching && query && (
        <p className="text-slate-500 text-sm">输入关键词并点击搜索</p>
      )}

      {searching && <p className="text-slate-400 text-sm">搜索中...</p>}

      {results.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs text-slate-500">找到 {results.length} 条结果</div>
          {results.map((item, i) => (
            <div key={i} className="bg-slate-900 rounded-lg p-3 border border-slate-700/50">
              <div className="flex items-center gap-2 mb-1">
                <span className={clsx(
                  "text-xs px-2 py-0.5 rounded",
                  item.match_type === 'topic' ? 'bg-sky-500/20 text-sky-400' :
                  item.match_type === 'industry' ? 'bg-amber-500/20 text-amber-400' :
                  'bg-green-500/20 text-green-400'
                )}>
                  {item.match_type === 'topic' ? '话题' :
                   item.match_type === 'industry' ? '行业' :
                   item.match_type === 'industry_item' ? '行业条目' : '结果'}
                </span>
                <span className="text-sm text-slate-200 font-medium">
                  {item.title || item.name || item.keyword || '-'}
                </span>
              </div>
              {item.source && <div className="text-xs text-slate-500">来源: {item.source}</div>}
              {item.industry && <div className="text-xs text-slate-500">行业: {item.industry}</div>}
              {item.item_count !== undefined && <div className="text-xs text-slate-500">条目数: {item.item_count}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
