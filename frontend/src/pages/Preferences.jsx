import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import DataSourcePicker from '../components/DataSourcePicker'
import { Settings, Save, CheckCircle, AlertCircle, Loader2, Crown, Plus, X, Rss, Play } from 'lucide-react'
import clsx from 'clsx'

const TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']

const TAG_TYPE_LABELS = {
  company: '公司',
  person: '人物',
  topic: '话题',
  sector: '行业',
}

const DATA_SOURCE_OPTIONS = [
  { key: 'hot_topics', label: '热点平台' },
  { key: 'policy', label: '政策' },
  { key: 'exchange', label: '交易所公告' },
  { key: 'financial', label: '财经数据' },
  { key: 'rss', label: 'RSS 数据源' },
]

export default function Preferences() {
  const user = api.getUser() || {}
  const tierIdx = TIER_ORDER.indexOf(user.tier || 'free')
  const isV2Plus = tierIdx >= TIER_ORDER.indexOf('v2')

  const [tagLibrary, setTagLibrary] = useState({})
  const [interestTags, setInterestTags] = useState([])
  const [platforms, setPlatforms] = useState([])
  const [rssSourceIds, setRssSourceIds] = useState([])
  const [userSourceIds, setUserSourceIds] = useState([])
  const [pushChannelIds, setPushChannelIds] = useState([])
  const [channels, setChannels] = useState([])
  const [sourceNames, setSourceNames] = useState({})
  const [userSources, setUserSources] = useState([])
  const [showRssPicker, setShowRssPicker] = useState(false)
  const [reportTime, setReportTime] = useState('08:00')
  const [pushMode, setPushMode] = useState('summary')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [customInputs, setCustomInputs] = useState({})
  const [testing, setTesting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [tagLibRes, interestsRes, pushRes] = await Promise.all([
        api.get('/api/v1/profile/tag-library'),
        api.get('/api/v1/profile/interests'),
        api.get('/api/v1/profile/push-settings'),
      ])
      setTagLibrary(tagLibRes.data?.data || {})
      const iData = interestsRes.data?.data || {}
      setInterestTags(iData.interest_tags || [])
      setPlatforms(iData.platforms || [])
      setRssSourceIds(iData.rss_source_ids || [])
      setUserSourceIds(iData.user_source_ids || [])
      setPushChannelIds(iData.push_channel_ids || [])
      setReportTime(pushRes.data?.data?.report_time || '08:00')
      setPushMode(pushRes.data?.data?.push_mode || 'summary')
    } catch { /* first load may fail */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Load source names for RSS chips
  useEffect(() => {
    if (platforms.includes('rss') || rssSourceIds.length > 0) {
      api.get('/api/v1/rss-sources').then(r => {
        const srcs = r.data?.data?.sources || []
        const map = {}
        srcs.forEach(s => { map[s.id] = s.name })
        setSourceNames(map)
      }).catch(() => {})
    }
  }, [platforms.includes('rss'), rssSourceIds.length])

  // Load user personal sources
  useEffect(() => {
    api.get('/api/v1/user-sources').then(r => {
      setUserSources(r.data?.data || [])
    }).catch(() => {})
  }, [])

  // Load push channels
  useEffect(() => {
    api.get('/api/v1/push-channels').then(r => {
      setChannels((r.data?.data || {}).channels || [])
    }).catch(() => {})
  }, [])

  const toggleTag = (type, value) => {
    const exists = interestTags.find(t => t.type === type && t.value === value)
    if (exists) {
      setInterestTags(interestTags.filter(t => !(t.type === type && t.value === value)))
    } else {
      setInterestTags([...interestTags, { type, value }])
    }
    setMsg(null)
  }

  const addCustomTag = (type) => {
    const val = (customInputs[type] || '').trim()
    if (!val) return
    const exists = interestTags.find(t => t.type === type && t.value === val)
    if (exists) return
    setInterestTags([...interestTags, { type, value: val }])
    setCustomInputs(prev => ({ ...prev, [type]: '' }))
    setMsg(null)
  }

  const togglePlatform = (key) => {
    setPlatforms(platforms.includes(key) ? platforms.filter(p => p !== key) : [...platforms, key])
    setMsg(null)
  }

  const handleSave = async () => {
    if (!isV2Plus) return
    setSaving(true)
    setMsg(null)
    try {
      await api.put('/api/v1/profile/interests', {
        interest_tags: interestTags,
        platforms,
        rss_source_ids: rssSourceIds,
        user_source_ids: userSourceIds,
        push_channel_ids: pushChannelIds,
      })
      await api.put('/api/v1/profile/push-settings', { report_time: reportTime, push_mode: pushMode })
      setMsg({ text: '偏好已保存', ok: true })
    } catch (e) {
      setMsg({ text: e.message, ok: false })
    } finally { setSaving(false) }
  }

  if (loading) return <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  if (!isV2Plus) {
    return (
      <div className="text-center py-16">
        <Crown size={48} className="mx-auto text-slate-600 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">需要升级</h2>
        <p className="text-slate-400 text-sm">偏好设置功能需要 V2 及以上等级</p>
      </div>
    )
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings size={24} className="text-sky-400" />
          <h2 className="text-2xl font-bold text-white">我的偏好</h2>
        </div>
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
          <Save size={14} /> {saving ? '保存中...' : '保存偏好'}
        </button>
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {/* Interest Tags */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h3 className="text-white font-medium mb-4">兴趣标签</h3>
        <div className="space-y-4">
          {Object.entries(TAG_TYPE_LABELS).map(([type, label]) => {
            const selectedInType = interestTags.filter(t => t.type === type)
            const libraryTags = tagLibrary[type] || []
            return (
              <div key={type}>
                <div className="text-xs text-slate-500 mb-2 font-medium uppercase">{label}</div>
                <div className="flex flex-wrap gap-2">
                  {selectedInType.map(tag => (
                    <button key={tag.value} onClick={() => toggleTag(type, tag.value)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500/20 text-sky-400 border border-sky-500/40 hover:bg-sky-500/30 transition-colors">
                      {tag.value}
                      <X size={10} className="opacity-60" />
                    </button>
                  ))}
                  {libraryTags.filter(t => !selectedInType.some(s => s.value === t)).slice(0, 12).map(tag => (
                    <button key={tag} onClick={() => toggleTag(type, tag)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700/50 text-slate-400 border border-slate-600 hover:border-slate-500 transition-colors">
                      {tag}
                    </button>
                  ))}
                  <div className="flex items-center gap-1">
                    <input
                      value={customInputs[type] || ''}
                      onChange={e => setCustomInputs(prev => ({ ...prev, [type]: e.target.value }))}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomTag(type) } }}
                      placeholder="自定义..."
                      className="w-24 bg-slate-900 border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
                    />
                    <button onClick={() => addCustomTag(type)}
                      className="p-1.5 rounded-lg bg-slate-700/50 text-slate-400 hover:text-sky-400 hover:bg-slate-700 transition-colors">
                      <Plus size={12} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Data Sources */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h3 className="text-white font-medium mb-4">数据源</h3>
        <div className="flex flex-wrap gap-2">
          {DATA_SOURCE_OPTIONS.map(src => (
            <label key={src.key} className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-700/50 px-3 py-2 rounded-lg border border-slate-600 cursor-pointer hover:border-sky-500 transition-colors">
              <input type="checkbox"
                checked={platforms.includes(src.key)}
                onChange={() => togglePlatform(src.key)}
                className="accent-sky-500"
              />
              {src.label}
            </label>
          ))}
        </div>
        {/* RSS 细化选择 */}
        {platforms.includes('rss') && (
          <div className="mt-3">
            <button type="button" onClick={() => setShowRssPicker(true)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white hover:border-sky-500 transition-colors text-left flex items-center gap-2">
              <Rss size={14} className="text-sky-400 shrink-0" />
              <span className="flex-1">
                {rssSourceIds.length > 0
                  ? `已细化 ${rssSourceIds.length} 个 RSS 源`
                  : '点击细化选择 RSS 数据源（留空则使用全部）'}
              </span>
              <span className="text-xs text-sky-400">选择</span>
            </button>
            {rssSourceIds.length > 0 && Object.keys(sourceNames).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {rssSourceIds.slice(0, 15).map(id => (
                  <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-500/10 text-sky-400 text-xs rounded border border-sky-500/30">
                    {sourceNames[id] || `#${id}`}
                    <button onClick={() => setRssSourceIds(rssSourceIds.filter(i => i !== id))}
                      className="hover:text-red-400"><X size={10} /></button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {/* 个人数据源 */}
        {userSources.length > 0 && (
          <div className="mt-3">
            <div className="text-xs text-slate-500 mb-2">个人数据源</div>
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {userSources.map(src => {
                const checked = userSourceIds.includes(src.id)
                return (
                  <label key={src.id}
                    className={clsx("flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-colors text-xs",
                      checked ? "bg-sky-500/10 border-sky-500/30 text-white" : "bg-slate-900 border-slate-600 text-slate-400 hover:border-slate-500")}>
                    <input type="checkbox" checked={checked}
                      onChange={() => setUserSourceIds(checked ? userSourceIds.filter(i => i !== src.id) : [...userSourceIds, src.id])}
                      className="accent-sky-500" />
                    <span className="flex-1 truncate">{src.display_name || src.source_id}</span>
                  </label>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Push Settings */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h3 className="text-white font-medium mb-4">推送设置</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">推送时间</label>
            <input type="time" value={reportTime} onChange={e => { setReportTime(e.target.value); setMsg(null) }}
              className={inputCls} />
            <p className="text-xs text-slate-600 mt-1">设置后系统按此时间自动生成偏好日报</p>
            <button onClick={async () => {
              setTesting(true)
              try {
                const res = await api.post('/api/v1/profile/test-daily')
                setMsg({ text: `日报生成中 (run: ${res.data?.data?.run_id})`, ok: true })
              } catch (e) {
                setMsg({ text: e.response?.data?.error || e.message, ok: false })
              } finally { setTesting(false) }
            }} disabled={testing}
              className="mt-2 flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-emerald-500/20 disabled:opacity-50 transition-colors">
              <Play size={12} /> {testing ? '生成中...' : '立即生成'}
            </button>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">推送模式</label>
            <select value={pushMode} onChange={e => { setPushMode(e.target.value); setMsg(null) }}
              className={inputCls}>
              <option value="summary">摘要模式</option>
              <option value="full">全文模式</option>
            </select>
          </div>
        </div>
        {/* Push Channels */}
        <div className="mt-4">
          <label className="block text-xs text-slate-400 mb-2">推送渠道（报告生成后自动推送）</label>
          {channels.length === 0 ? (
            <div className="text-xs text-slate-500 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2">
              暂无推送渠道，请先在「推送渠道」中配置
            </div>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              <label className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                <input type="checkbox" checked={pushChannelIds.includes('_email')}
                  onChange={() => setPushChannelIds(pushChannelIds.includes('_email') ? pushChannelIds.filter(id => id !== '_email') : [...pushChannelIds, '_email'])}
                  className="accent-sky-500" />
                <span className="text-sm text-slate-200">邮件推送</span>
                <span className="text-xs px-2 py-0.5 rounded bg-sky-500/10 text-sky-400">默认</span>
              </label>
              {channels.filter(c => c.enabled).map(c => (
                <label key={c.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                  <input type="checkbox" checked={pushChannelIds.includes(c.id)}
                    onChange={() => setPushChannelIds(pushChannelIds.includes(c.id) ? pushChannelIds.filter(id => id !== c.id) : [...pushChannelIds, c.id])}
                    className="accent-sky-500" />
                  <span className="text-sm text-slate-200">{c.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
                    {c.channel_label || c.channel_type}
                  </span>
                </label>
              ))}
            </div>
          )}
          {pushChannelIds.length > 0 && (
            <p className="text-xs text-slate-500 mt-1">已选择 {pushChannelIds.length} 个推送渠道</p>
          )}
        </div>
      </div>

      {/* RSS Source Picker Modal */}
      {showRssPicker && (
        <DataSourcePicker
          selectedIds={rssSourceIds}
          onConfirm={ids => { setRssSourceIds(ids); setShowRssPicker(false); setMsg(null) }}
          onClose={() => setShowRssPicker(false)}
        />
      )}
    </div>
  )
}
