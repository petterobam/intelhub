import { useEffect, useState, useMemo } from 'react'
import { api } from '../api/client'
import { Rss, Plus, Trash2, Edit3, X, CheckCircle, AlertCircle, ToggleLeft, ToggleRight, Search, RefreshCw, Loader2, ExternalLink } from 'lucide-react'
import clsx from 'clsx'


export default function RssSources() {
  const [sources, setSources] = useState([])
  const [categories, setCategories] = useState({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [msg, setMsg] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [editSrc, setEditSrc] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [deleting, setDeleting] = useState(false)

  const load = async () => {
    try {
      const params = new URLSearchParams()
      if (catFilter) params.set('category', catFilter)
      if (search.trim()) params.set('q', search.trim())
      const [srcRes, catRes] = await Promise.all([
        api.get(`/api/v1/rss-sources?${params}`),
        api.get('/api/v1/rss-sources/categories'),
      ])
      setSources(srcRes.data?.data?.sources || [])
      setCategories(catRes.data?.data || {})
    } catch { } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [catFilter])
  useEffect(() => {
    const t = setTimeout(() => load(), 300)
    return () => clearTimeout(t)
  }, [search])

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const toggleEnabled = async (src) => {
    try {
      await api.put(`/api/v1/rss-sources/${src.id}/toggle`)
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const deleteOne = async (id) => {
    if (!confirm('确定删除此数据源？')) return
    try {
      await api.delete(`/api/v1/rss-sources/${id}`)
      showMsg('已删除')
      setSelected(prev => { const n = new Set(prev); n.delete(id); return n })
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const batchDelete = async () => {
    if (!confirm(`确定删除选中的 ${selected.size} 个数据源？`)) return
    setDeleting(true)
    try {
      await api.post('/api/v1/rss-sources/batch-delete', { ids: Array.from(selected) })
      showMsg(`已删除 ${selected.size} 个数据源`)
      setSelected(new Set())
      load()
    } catch (e) { showMsg(e.message, false) }
    finally { setDeleting(false) }
  }

  const toggleSelect = (id) => {
    setSelected(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  // 按分类分组
  const grouped = useMemo(() => {
    const groups = {}
    for (const s of sources) {
      const cat = s.category || '其他'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(s)
    }
    // 按数量降序
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length)
  }, [sources])

  const total = Object.values(categories).reduce((a, b) => a + b, 0)
  const enabledCount = sources.filter(s => s.enabled).length

  if (loading) return <div className="flex items-center gap-2 text-slate-400"><Loader2 className="animate-spin" size={16} />加载中...</div>

  return (
    <div className="space-y-6">
      {/* 顶栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Rss size={24} className="text-sky-400" />
          <div>
            <h2 className="text-2xl font-bold text-white">RSS 管理</h2>
            <p className="text-xs text-slate-500 mt-0.5">{total} 个数据源 · {enabledCount} 个已启用</p>
          </div>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30">
          <Plus size={16} /> 添加数据源
        </button>
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {/* 搜索 + 筛选 + 批量操作 */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            placeholder="搜索名称或 URL..." />
        </div>
        <select value={catFilter} onChange={e => setCatFilter(e.target.value)}
          className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500">
          <option value="">全部分类</option>
          {Object.entries(categories).sort((a, b) => b[1] - a[1]).map(([cat, count]) => (
            <option key={cat} value={cat}>{cat} ({count})</option>
          ))}
        </select>
        <button onClick={load} className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-700">
          <RefreshCw size={16} />
        </button>
        {selected.size > 0 && (
          <button onClick={batchDelete} disabled={deleting}
            className="flex items-center gap-1.5 px-3 py-2 bg-red-500/10 text-red-400 rounded-lg text-sm hover:bg-red-500/20 disabled:opacity-50">
            <Trash2 size={14} />
            删除 ({selected.size})
          </button>
        )}
      </div>

      {showAdd && <SourceFormModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); showMsg('已添加'); load() }} />}
      {editSrc && <SourceFormModal source={editSrc} onClose={() => setEditSrc(null)} onSaved={() => { setEditSrc(null); showMsg('已更新'); load() }} />}

      {/* 分类标题 + 卡片平铺 */}
      <div className="space-y-8">
        {grouped.map(([cat, items]) => (
          <div key={cat}>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-semibold text-slate-300">{cat}</h3>
              <span className="text-xs text-slate-600">{items.length}</span>
            </div>
            <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
              {items.map(src => {
                const isSelected = selected.has(src.id)
                return (
                  <div key={src.id}
                    onClick={(e) => { if (e.shiftKey) toggleSelect(src.id) }}
                    className={clsx(
                      "group relative bg-slate-800 rounded-lg p-3.5 border transition-colors",
                      isSelected ? "border-sky-500/60 bg-sky-900/10" :
                      src.enabled ? "border-slate-700/60 hover:border-slate-600" : "border-slate-700/30 opacity-40"
                    )}>
                    {/* 右上角操作 */}
                    <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => toggleEnabled(src)}
                        className="p-1 rounded hover:bg-slate-700"
                        title={src.enabled ? '禁用' : '启用'}>
                        {src.enabled
                          ? <ToggleRight size={16} className="text-sky-400" />
                          : <ToggleLeft size={16} className="text-slate-500" />}
                      </button>
                      <button onClick={() => setEditSrc(src)}
                        className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-yellow-400"
                        title="编辑">
                        <Edit3 size={13} />
                      </button>
                      <button onClick={() => deleteOne(src.id)}
                        className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-red-400"
                        title="删除">
                        <Trash2 size={13} />
                      </button>
                    </div>

                    {/* 选择框 */}
                    <input type="checkbox" checked={isSelected}
                      onChange={() => toggleSelect(src.id)}
                      className="absolute top-2 left-2 accent-sky-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="选择" />

                    {/* 内容 */}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Rss size={13} className={clsx("shrink-0", src.enabled ? "text-sky-400" : "text-slate-600")} />
                        <span className="text-sm text-white font-medium truncate">{src.name}</span>
                        {src.slug && (
                          <span className="shrink-0 text-[10px] leading-none font-mono text-sky-400/60 bg-sky-400/10 px-1.5 py-0.5 rounded max-w-[120px] truncate">
                            {src.slug}
                          </span>
                        )}
                      </div>
                      <a href={src.url} target="_blank" rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="flex items-center gap-1 text-[11px] text-slate-500 font-mono truncate mt-1 pl-[21px] hover:text-sky-400 transition-colors"
                        title={src.url}>
                        <ExternalLink size={10} className="shrink-0" />
                        <span className="truncate">{src.url}</span>
                      </a>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {grouped.length === 0 && !loading && (
          <div className="text-center py-16 text-slate-500">
            {search || catFilter ? '没有匹配的数据源' : '暂无数据源'}
          </div>
        )}
      </div>
    </div>
  )
}


function SourceFormModal({ source, onClose, onSaved }) {
  const isEdit = !!source
  const [form, setForm] = useState({
    name: source?.name || '',
    slug: source?.slug || '',
    url: source?.url || '',
    category: source?.category || '其他',
    description: source?.description || '',
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!form.name.trim() || !form.url.trim()) {
      alert('名称和 URL 必填')
      return
    }
    setSaving(true)
    try {
      if (isEdit) {
        await api.put(`/api/v1/rss-sources/${source.id}`, form)
      } else {
        await api.post('/api/v1/rss-sources', form)
      }
      onSaved()
    } catch (e) {
      alert('操作失败: ' + (e.response?.data?.error?.message || e.message))
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">{isEdit ? '编辑数据源' : '添加数据源'}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">名称 *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="如：36氪" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">别名 (slug)</label>
            <input value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value.replace(/[^a-z0-9-]/g, '') }))}
              placeholder="如：36kr，留空自动从 URL 生成" className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">URL *</label>
            <input value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              placeholder="https://..." className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">分类</label>
            <input value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              placeholder="综合资讯、科技/AI、财经商业..." className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">描述</label>
            <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="可选" className={inputCls} />
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving}
              className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
              {saving ? '保存中...' : '保存'}
            </button>
            <button onClick={onClose}
              className="bg-slate-700 text-slate-400 px-4 py-2 rounded-lg text-sm hover:bg-slate-600">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
