import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import { Search, ChevronDown, ChevronRight, X, Check, Loader2, Rss, User } from 'lucide-react'
import clsx from 'clsx'


export default function PersonalDataSourcePicker({ selectedSystemIds, selectedUserIds, onConfirm, onClose }) {
  const [systemSources, setSystemSources] = useState([])
  const [userSources, setUserSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [expandedGroups, setExpandedGroups] = useState(new Set(['system']))
  const [selectedSys, setSelectedSys] = useState(new Set(selectedSystemIds || []))
  const [selectedUsr, setSelectedUsr] = useState(new Set(selectedUserIds || []))

  useEffect(() => {
    Promise.all([
      api.get('/api/v1/rss-sources').catch(() => ({ data: { data: { sources: [] } } })),
      api.get('/api/v1/user-sources').catch(() => ({ data: { data: [] } })),
    ]).then(([sysRes, usrRes]) => {
      setSystemSources(sysRes.data?.data?.sources || [])
      setUserSources(usrRes.data?.data || [])
    }).finally(() => setLoading(false))
  }, [])

  const filteredSystem = useMemo(() => {
    if (!search.trim()) return systemSources
    const q = search.toLowerCase()
    return systemSources.filter(s =>
      s.name.toLowerCase().includes(q) || (s.slug || '').toLowerCase().includes(q)
    )
  }, [systemSources, search])

  const filteredUser = useMemo(() => {
    if (!search.trim()) return userSources
    const q = search.toLowerCase()
    return userSources.filter(s =>
      (s.display_name || '').toLowerCase().includes(q) || (s.source_id || '').toLowerCase().includes(q)
    )
  }, [userSources, search])

  // Group system sources by category
  const groupedSystem = useMemo(() => {
    const groups = {}
    for (const s of filteredSystem) {
      const cat = s.category || '其他'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(s)
    }
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length)
  }, [filteredSystem])

  const toggleGroup = (key) => {
    setExpandedGroups(prev => {
      const n = new Set(prev)
      n.has(key) ? n.delete(key) : n.add(key)
      return n
    })
  }

  const toggleSys = (id) => {
    setSelectedSys(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const toggleUsr = (id) => {
    setSelectedUsr(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const selectAllSys = () => setSelectedSys(new Set(systemSources.map(s => s.id)))
  const clearAllSys = () => setSelectedSys(new Set())
  const selectAllUsr = () => setSelectedUsr(new Set(userSources.map(s => s.id)))
  const clearAllUsr = () => setSelectedUsr(new Set())

  const handleConfirm = () => {
    onConfirm({
      system_source_ids: Array.from(selectedSys),
      user_source_ids: Array.from(selectedUsr),
    })
  }

  const totalSelected = selectedSys.size + selectedUsr.size

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-2">
            <Rss size={18} className="text-sky-400" />
            <h3 className="text-white font-semibold">选择数据源</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>

        {/* Search */}
        <div className="px-5 py-3 border-b border-slate-700 shrink-0">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search} onChange={e => setSearch(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
              placeholder="搜索数据源..."
              autoFocus
            />
          </div>
        </div>

        {/* Source list */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              <Loader2 className="animate-spin mr-2" size={16} /> 加载中...
            </div>
          ) : (
            <div className="space-y-1">
              {/* System sources group */}
              <div>
                <div onClick={() => toggleGroup('system')}
                  className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer select-none">
                  {expandedGroups.has('system') ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
                  <Rss size={14} className="text-sky-400" />
                  <span className="text-sm font-medium text-slate-300 flex-1">系统数据源</span>
                  <span className="text-xs text-slate-500">{selectedSys.size}/{systemSources.length}</span>
                  <button onClick={e => { e.stopPropagation(); selectAllSys() }}
                    className="text-xs px-2 py-0.5 rounded border border-slate-600 text-slate-400 hover:border-slate-500">全选</button>
                  <button onClick={e => { e.stopPropagation(); clearAllSys() }}
                    className="text-xs px-2 py-0.5 rounded border border-slate-600 text-slate-400 hover:border-slate-500">清空</button>
                </div>

                {expandedGroups.has('system') && groupedSystem.map(([cat, catSources]) => {
                  const catSelected = catSources.filter(s => selectedSys.has(s.id)).length
                  return (
                    <div key={cat} className="ml-4">
                      <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-slate-500">
                        <span className="flex-1">{cat}</span>
                        <span>{catSelected}/{catSources.length}</span>
                      </div>
                      <div className="space-y-0.5">
                        {catSources.map(src => {
                          const isSelected = selectedSys.has(src.id)
                          return (
                            <label key={src.id}
                              className={clsx("flex items-center gap-2.5 px-3 py-1.5 rounded-lg cursor-pointer transition-colors",
                                isSelected ? "bg-sky-500/10" : "hover:bg-slate-700/30"
                              )}>
                              <input type="checkbox" checked={isSelected} onChange={() => toggleSys(src.id)} className="accent-sky-500 shrink-0" />
                              <span className={clsx("text-sm flex-1 truncate", isSelected ? "text-white" : "text-slate-400")}>{src.name}</span>
                              {src.slug && <span className="text-xs text-slate-600">{src.slug}</span>}
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* User sources group */}
              {userSources.length > 0 && (
                <div>
                  <div onClick={() => toggleGroup('user')}
                    className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer select-none">
                    {expandedGroups.has('user') ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
                    <User size={14} className="text-purple-400" />
                    <span className="text-sm font-medium text-slate-300 flex-1">我的数据源</span>
                    <span className="text-xs text-slate-500">{selectedUsr.size}/{userSources.length}</span>
                  </div>

                  {expandedGroups.has('user') && (
                    <div className="ml-4 space-y-0.5">
                      {filteredUser.map(src => {
                        const isSelected = selectedUsr.has(src.id)
                        return (
                          <label key={src.id}
                            className={clsx("flex items-center gap-2.5 px-3 py-1.5 rounded-lg cursor-pointer transition-colors",
                              isSelected ? "bg-purple-500/10" : "hover:bg-slate-700/30"
                            )}>
                            <input type="checkbox" checked={isSelected} onChange={() => toggleUsr(src.id)} className="accent-purple-500 shrink-0" />
                            <span className={clsx("text-sm flex-1 truncate", isSelected ? "text-white" : "text-slate-400")}>
                              {src.display_name || src.source_id}
                            </span>
                            <span className="text-xs text-slate-600">{src.type}</span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-700 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-400">
            已选 <span className="text-sky-400 font-medium">{totalSelected}</span> 个数据源
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">取消</button>
            <button onClick={handleConfirm} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 flex items-center gap-2">
              <Check size={14} /> 确认选择
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
