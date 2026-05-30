import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import { Search, ChevronDown, ChevronRight, X, Check, Loader2, Rss } from 'lucide-react'
import clsx from 'clsx'


export default function DataSourcePicker({ selectedIds, onConfirm, onClose }) {
  const [sources, setSources] = useState([])
  const [categories, setCategories] = useState({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [expandedCats, setExpandedCats] = useState(new Set())
  const [selected, setSelected] = useState(new Set(selectedIds || []))

  useEffect(() => {
    Promise.all([
      api.get('/api/v1/rss-sources'),
      api.get('/api/v1/rss-sources/categories'),
    ]).then(([srcRes, catRes]) => {
      setSources(srcRes.data?.data?.sources || [])
      setCategories(catRes.data?.data || {})
      // 默认展开第一个分类
      const cats = Object.keys(catRes.data?.data || {})
      if (cats.length > 0) setExpandedCats(new Set([cats[0]]))
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const filteredSources = useMemo(() => {
    if (!search.trim()) return sources
    const q = search.toLowerCase()
    return sources.filter(s =>
      s.name.toLowerCase().includes(q) || s.url.toLowerCase().includes(q) || (s.slug || '').toLowerCase().includes(q)
    )
  }, [sources, search])

  const groupedSources = useMemo(() => {
    const groups = {}
    for (const s of filteredSources) {
      const cat = s.category || '其他'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(s)
    }
    // 按分类中源数量排序
    const sorted = Object.entries(groups).sort((a, b) => b[1].length - a[1].length)
    return sorted
  }, [filteredSources])

  const toggleCat = (cat) => {
    setExpandedCats(prev => {
      const n = new Set(prev)
      n.has(cat) ? n.delete(cat) : n.add(cat)
      return n
    })
  }

  const toggleSource = (id) => {
    setSelected(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const toggleAll = (catSources) => {
    const allSelected = catSources.every(s => selected.has(s.id))
    setSelected(prev => {
      const n = new Set(prev)
      catSources.forEach(s => allSelected ? n.delete(s.id) : n.add(s.id))
      return n
    })
  }

  const selectAll = () => {
    setSelected(new Set(sources.map(s => s.id)))
  }

  const clearAll = () => {
    setSelected(new Set())
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-2">
            <Rss size={18} className="text-sky-400" />
            <h3 className="text-white font-semibold">选择数据源</h3>
            <span className="text-xs text-slate-500">{sources.length} 个源</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>

        {/* Search + actions */}
        <div className="px-5 py-3 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                value={search} onChange={e => setSearch(e.target.value)}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
                placeholder="搜索数据源名称或 URL..."
                autoFocus
              />
            </div>
            <button onClick={selectAll} className="px-3 py-2 text-xs text-sky-400 hover:text-sky-300 whitespace-nowrap">全选</button>
            <button onClick={clearAll} className="px-3 py-2 text-xs text-slate-400 hover:text-slate-300 whitespace-nowrap">清空</button>
          </div>
        </div>

        {/* Source list */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              <Loader2 className="animate-spin mr-2" size={16} /> 加载中...
            </div>
          ) : groupedSources.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              {search ? '没有匹配的数据源' : '暂无数据源，请先导入 RSS 数据'}
            </div>
          ) : (
            <div className="space-y-1">
              {groupedSources.map(([cat, catSources]) => {
                const isExpanded = expandedCats.has(cat)
                const catSelected = catSources.filter(s => selected.has(s.id)).length
                return (
                  <div key={cat}>
                    <div
                      onClick={() => toggleCat(cat)}
                      className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer select-none"
                    >
                      {isExpanded ? <ChevronDown size={14} className="text-slate-500 shrink-0" /> : <ChevronRight size={14} className="text-slate-500 shrink-0" />}
                      <span className="text-sm font-medium text-slate-300 flex-1">{cat}</span>
                      <span className="text-xs text-slate-500">{catSelected}/{catSources.length}</span>
                      <button
                        onClick={e => { e.stopPropagation(); toggleAll(catSources) }}
                        className={clsx("text-xs px-2 py-0.5 rounded border transition-colors",
                          catSelected === catSources.length && catSources.length > 0
                            ? "border-sky-500 text-sky-400 bg-sky-500/10"
                            : "border-slate-600 text-slate-400 hover:border-slate-500"
                        )}
                      >
                        {catSelected === catSources.length && catSources.length > 0 ? '取消' : '全选'}
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="ml-4 space-y-0.5">
                        {catSources.map(src => {
                          const isSelected = selected.has(src.id)
                          return (
                            <label
                              key={src.id}
                              className={clsx(
                                "flex items-center gap-2.5 px-3 py-1.5 rounded-lg cursor-pointer transition-colors",
                                isSelected ? "bg-sky-500/10" : "hover:bg-slate-700/30"
                              )}
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => toggleSource(src.id)}
                                className="accent-sky-500 shrink-0"
                              />
                              <span className={clsx("text-sm flex-1 truncate", isSelected ? "text-white" : "text-slate-400")}>
                                {src.name}
                              </span>
                              <span className="text-xs text-slate-600 truncate max-w-48">{src.url}</span>
                            </label>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-700 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-400">
            已选 <span className="text-sky-400 font-medium">{selected.size}</span> 个数据源
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">取消</button>
            <button onClick={() => onConfirm(Array.from(selected))} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 flex items-center gap-2">
              <Check size={14} />
              确认选择
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
