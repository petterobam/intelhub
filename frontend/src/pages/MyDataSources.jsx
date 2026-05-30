import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { Rss, Youtube, Tv, Plus, Trash2, RefreshCw, Power, PowerOff, Loader2, Crown, CheckCircle, AlertCircle, X } from 'lucide-react'
import clsx from 'clsx'

const TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']

const TYPE_CONFIG = {
  rss: { label: 'RSS', icon: Rss, color: 'text-orange-400', placeholder: 'https://example.com/feed' },
  bilibili: { label: 'Bilibili', icon: Tv, color: 'text-blue-400', placeholder: 'UP主 UID (如: 12345678)' },
  youtube: { label: 'YouTube', icon: Youtube, color: 'text-red-400', placeholder: '频道 ID (如: UCxxxxxx)' },
}

export default function MyDataSources() {
  const user = api.getUser() || {}
  const tierIdx = TIER_ORDER.indexOf(user.tier || 'free')
  const isV3Plus = tierIdx >= TIER_ORDER.indexOf('v3')

  const [sources, setSources] = useState([])
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [msg, setMsg] = useState(null)

  const load = useCallback(async () => {
    try {
      const [srcRes, qRes] = await Promise.all([
        api.get('/api/v1/user-sources'),
        api.get('/api/v1/user-sources/quota'),
      ])
      setSources(srcRes.data?.data || [])
      setQuota(qRes.data?.data || null)
    } catch { }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (!isV3Plus) { setLoading(false); return }
    load()
  }, [load, isV3Plus])

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const toggleEnabled = async (src) => {
    try {
      await api.put(`/api/v1/user-sources/${src.id}`, { enabled: !src.enabled })
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const doFetch = async (src) => {
    try {
      await api.post(`/api/v1/user-sources/${src.id}/fetch`)
      showMsg('采集成功')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const deleteSource = async (id) => {
    if (!confirm('确定删除此数据源？')) return
    try {
      await api.delete(`/api/v1/user-sources/${id}`)
      showMsg('已删除')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  if (loading) return <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  if (!isV3Plus) {
    return (
      <div className="text-center py-16">
        <Crown size={48} className="mx-auto text-slate-600 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">需要升级</h2>
        <p className="text-slate-400 text-sm">数据源管理功能需要 V3 及以上等级</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">我的数据源</h2>
          <p className="text-xs text-slate-500 mt-1">添加 RSS、B站、YouTube 等内容源</p>
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

      {quota && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 flex items-center justify-between">
          <div className="text-sm text-slate-400">
            配额: <span className="text-white font-medium">{quota.used}</span> / {quota.limit} 个数据源
          </div>
          <span className={clsx("text-xs px-2 py-0.5 rounded", quota.remaining > 0 ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
            {quota.remaining > 0 ? `剩余 ${quota.remaining}` : '已满'}
          </span>
        </div>
      )}

      <div className="space-y-3">
        {sources.map(src => {
          const tc = TYPE_CONFIG[src.type] || TYPE_CONFIG.rss
          const Icon = tc.icon
          return (
            <div key={src.id} className={clsx(
              "bg-slate-800 rounded-xl border p-4 flex items-center gap-4",
              src.enabled ? "border-slate-700" : "border-slate-700/50 opacity-60"
            )}>
              <Icon size={20} className={tc.color} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white font-medium truncate">{src.display_name || src.source_id}</div>
                <div className="text-xs text-slate-500 truncate">{src.source_id}</div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-slate-600">{tc.label}</span>
                  {src.item_count > 0 && <span className="text-xs text-slate-600">{src.item_count} 条</span>}
                  {src.last_fetched && <span className="text-xs text-slate-600">
                    {new Date(src.last_fetched).toLocaleDateString('zh-CN')}
                  </span>}
                  {src.status === 'error' && <span className="text-xs text-red-400">错误</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => doFetch(src)} className="text-slate-500 hover:text-sky-400" title="立即采集">
                  <RefreshCw size={15} />
                </button>
                <button onClick={() => toggleEnabled(src)} className="text-slate-500 hover:text-white" title={src.enabled ? '停用' : '启用'}>
                  {src.enabled ? <Power size={15} /> : <PowerOff size={15} />}
                </button>
                <button onClick={() => deleteSource(src.id)} className="text-slate-500 hover:text-red-400" title="删除">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          )
        })}
        {sources.length === 0 && (
          <div className="text-center text-slate-500 py-12">暂无数据源，点击右上角添加</div>
        )}
      </div>

      {showAdd && <AddSourceModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load() }} />}
    </div>
  )
}

function AddSourceModal({ onClose, onSaved }) {
  const [type, setType] = useState('rss')
  const [sourceId, setSourceId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [validating, setValidating] = useState(false)
  const [validated, setValidated] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleValidate = async () => {
    if (!sourceId.trim()) return
    setValidating(true)
    setError('')
    try {
      const res = await api.post('/api/v1/user-sources', {
        type, source_id: sourceId.trim(), display_name: displayName.trim(),
      })
      onSaved()
    } catch (e) {
      if (e.response?.data?.error?.message) {
        setError(e.response.data.error.message)
      } else {
        setError(e.message)
      }
    } finally {
      setValidating(false)
    }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
  const tc = TYPE_CONFIG[type]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">添加数据源</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="space-y-4">
          {error && <div className="bg-red-900/30 text-red-400 text-sm rounded-lg px-3 py-2">{error}</div>}

          <div>
            <label className="block text-sm text-slate-400 mb-1">类型</label>
            <div className="flex gap-2">
              {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                <button key={key} onClick={() => { setType(key); setError('') }}
                  className={clsx('flex-1 px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition-colors',
                    type === key ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40' : 'bg-slate-700/50 text-slate-400 border border-slate-600'
                  )}>
                  <cfg.icon size={14} /> {cfg.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">源地址 / ID *</label>
            <input value={sourceId} onChange={e => { setSourceId(e.target.value); setError('') }}
              placeholder={tc.placeholder} className={inputCls} />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">显示名称（可选）</label>
            <input value={displayName} onChange={e => setDisplayName(e.target.value)}
              placeholder="留空自动获取" className={inputCls} />
          </div>

          <div className="flex gap-3 pt-2">
            <button onClick={handleValidate} disabled={validating || !sourceId.trim()}
              className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
              {validating ? '验证中...' : '添加'}
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
