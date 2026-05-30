import { useEffect, useState, useRef } from 'react'
import { api } from '../api/client'
import { Globe, Play, RefreshCw, Plus, X, Edit3, Trash2, CheckCircle } from 'lucide-react'
import clsx from 'clsx'

const CATEGORY_LABELS = { hot_topics: '热点平台', policy: '政策监控', exchange: '交易所', financial: '金融数据' }
const METHOD_OPTIONS = [{ value: 'browser', label: '浏览器' }, { value: 'api', label: 'API' }]
const PRIORITY_OPTIONS = [{ value: 'high', label: '高' }, { value: 'medium', label: '中' }, { value: 'low', label: '低' }]


function NodeFormModal({ node, categories, onClose, onSaved }) {
  const isEdit = !!node
  const [form, setForm] = useState({
    name: node?.name || '',
    platform_id: node?.platform_id || '',
    category: node?.category || 'hot_topics',
    url: node?.url || '',
    method: node?.method || 'browser',
    schedule: node?.schedule || '90m',
    priority: node?.priority || 'medium',
    enabled: node?.enabled !== undefined ? node.enabled : true,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (key, val) => setForm(prev => ({ ...prev, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.platform_id.trim()) {
      setError('名称和标识符为必填项')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      if (isEdit) {
        await api.put(`/api/v1/crawlers/nodes/${node.id}`, form)
      } else {
        await api.post('/api/v1/crawlers/nodes', form)
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err.message || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
  const labelCls = "block text-xs text-slate-400 mb-1"

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <h3 className="text-white font-semibold">{isEdit ? '编辑爬虫节点' : '新增爬虫节点'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && <div className="bg-red-900/30 text-red-400 text-sm rounded-lg px-3 py-2">{error}</div>}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>显示名称 *</label>
              <input value={form.name} onChange={e => handleChange('name', e.target.value)}
                className={inputCls} placeholder="如：36氪" />
            </div>
            <div>
              <label className={labelCls}>唯一标识 *</label>
              <input value={form.platform_id} onChange={e => handleChange('platform_id', e.target.value.toLowerCase().replace(/\s/g, ''))}
                className={inputCls + " font-mono"} placeholder="如：36kr（不可改）" disabled={isEdit} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>分类</label>
              <select value={form.category} onChange={e => handleChange('category', e.target.value)} className={inputCls}>
                {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
                <option value="other">其他</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>优先级</label>
              <select value={form.priority} onChange={e => handleChange('priority', e.target.value)} className={inputCls}>
                {PRIORITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className={labelCls}>数据源 URL</label>
            <input value={form.url} onChange={e => handleChange('url', e.target.value)}
              className={inputCls + " font-mono"} placeholder="https://..." />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>采集方式</label>
              <select value={form.method} onChange={e => handleChange('method', e.target.value)} className={inputCls}>
                {METHOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>采集周期</label>
              <input value={form.schedule} onChange={e => handleChange('schedule', e.target.value)}
                className={inputCls} placeholder="90m 或 0 9 * * 1-5" />
            </div>
          </div>

          {isEdit && (
            <div className="flex items-center gap-2">
              <label className={labelCls + " mb-0"}>启用状态</label>
              <button type="button" onClick={() => handleChange('enabled', !form.enabled)}
                className={clsx("relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                  form.enabled ? 'bg-sky-500' : 'bg-slate-600')}>
                <span className={clsx("inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform",
                  form.enabled ? 'translate-x-4.5' : 'translate-x-1')} />
              </button>
              <span className="text-xs text-slate-400">{form.enabled ? '已启用' : '已禁用'}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">取消</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 disabled:opacity-50">
              {submitting ? '保存中...' : (isEdit ? '保存' : '创建')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


export default function Crawlers() {
  const [nodes, setNodes] = useState({})
  const [statuses, setStatuses] = useState({})
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editNode, setEditNode] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = async () => {
    try {
      const r = await api.get('/api/v1/crawlers/nodes')
      const list = r.data?.data?.nodes || []
      const grouped = {}
      for (const n of list) {
        const cat = n.category || 'other'
        if (!grouped[cat]) grouped[cat] = []
        grouped[cat].push(n)
      }
      setNodes(grouped)
      localStorage.setItem('intelhub_crawlers_cache', JSON.stringify(grouped))
    } catch {}
    setLoading(false)
  }

  useEffect(() => {
    // Read cache first
    try {
      const c = localStorage.getItem('intelhub_crawlers_cache')
      if (c) { setNodes(JSON.parse(c)); setLoading(false) }
    } catch { /* ignore */ }
    load()
  }, [])

  const checkStatus = async (node) => {
    try {
      // 直接用 node 的 platform_id 查数据新鲜度
      const r = await api.get(`/api/v1/crawlers/${node.platform_id}/status`)
      setStatuses(prev => ({ ...prev, [node.platform_id]: r.data?.data || {} }))
    } catch {
      setStatuses(prev => ({ ...prev, [node.platform_id]: { status: 'unknown' } }))
    }
  }

  const checkAll = async () => {
    const all = Object.values(nodes).flat()
    for (const n of all) {
      await checkStatus(n)
    }
  }

  const handleDelete = async (node) => {
    if (node.builtin) { alert('内置节点不能删除'); return }
    if (!confirm(`确定删除爬虫节点 "${node.name}"？`)) return
    setDeleting(node.platform_id)
    try {
      await api.delete(`/api/v1/crawlers/nodes/${node.id}`)
      load()
    } catch (err) {
      alert('删除失败: ' + (err.message || '未知错误'))
    }
    setDeleting(null)
  }

  const statusColor = (s) => s === 'fresh' ? 'bg-green-500' : s === 'stale' ? 'bg-yellow-500' : s === 'critical' ? 'bg-red-500' : 'bg-slate-500'
  const statusText = (s) => s === 'fresh' ? '正常' : s === 'stale' ? '过期' : s === 'critical' ? '严重' : '无数据'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">爬虫节点</h2>
          <p className="text-xs text-slate-500 mt-1">
            {Object.values(nodes).flat().length} 个节点 ·
            内置节点来自 platforms.yaml，用户节点存储在数据库
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={checkAll} className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700 flex items-center gap-2">
            <RefreshCw size={14} /> 刷新状态
          </button>
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 flex items-center gap-2">
            <Plus size={14} /> 新增节点
          </button>
        </div>
      </div>

      {loading && <div className="text-slate-400 py-8 text-center">加载中...</div>}

      {Object.entries(nodes).map(([category, nodelist]) => (
        <div key={category}>
          <h3 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
            <span>{CATEGORY_LABELS[category] || category}</span>
            <span className="text-slate-600 font-normal">({nodelist.length})</span>
          </h3>
          <div className="grid grid-cols-3 gap-4">
            {nodelist.map(node => {
              const st = statuses[node.platform_id] || {}
              return (
                <div key={node.platform_id} className="bg-slate-800 rounded-xl p-4 border border-slate-700 hover:border-slate-600 transition-colors">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Globe size={15} className="text-sky-400 shrink-0" />
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-medium text-white">{node.name}</span>
                          {node.builtin && <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-500">内置</span>}
                          {node.enabled === false && <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-600">禁用</span>}
                        </div>
                        <div className="text-xs text-slate-500 font-mono">{node.platform_id} · {node.method}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => checkStatus(node)} className="p-1 rounded hover:bg-slate-700">
                        <RefreshCw size={11} className="text-slate-400" />
                      </button>
                      {!node.builtin && (
                        <>
                          <button onClick={() => setEditNode(node)} className="p-1 rounded hover:bg-slate-700">
                            <Edit3 size={11} className="text-emerald-400" />
                          </button>
                          <button onClick={() => handleDelete(node)} className="p-1 rounded hover:bg-slate-700">
                            <Trash2 size={11} className="text-red-400" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className={clsx("w-2 h-2 rounded-full", statusColor(st.status))} />
                      <span className="text-xs text-slate-400">{statusText(st.status)}</span>
                      {st.priority && <span className={`text-xs px-1 rounded ${node.priority === 'high' ? 'bg-red-900/30 text-red-400' : 'bg-slate-700 text-slate-400'}`}>{node.priority}</span>}
                    </div>
                    {st.latest_file && <div className="text-xs text-slate-500 truncate">{st.latest_file}</div>}
                    {st.age_minutes !== undefined && st.age_minutes !== null && (
                      <div className="text-xs text-slate-500">{st.age_minutes} 分钟前</div>
                    )}
                    {st.item_count !== undefined && st.item_count > 0 && (
                      <div className="text-xs text-slate-500">{st.item_count} 条数据</div>
                    )}
                    {node.schedule && <div className="text-xs text-slate-600 font-mono">{node.schedule}</div>}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {Object.keys(nodes).length === 0 && !loading && (
        <div className="text-center py-12 text-slate-500">
          <Globe size={40} className="mx-auto mb-3 text-slate-700" />
          <p>暂无爬虫节点，点击右上角新增</p>
        </div>
      )}

      {showCreate && <NodeFormModal categories={Object.keys(CATEGORY_LABELS)} onClose={() => setShowCreate(false)} onSaved={load} />}
      {editNode && <NodeFormModal node={editNode} onClose={() => setEditNode(null)} onSaved={load} />}
    </div>
  )
}
