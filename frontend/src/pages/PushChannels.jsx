import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Send, Plus, Trash2, Settings, Mail, MessageSquare, Bot, Radio, ToggleLeft, ToggleRight, RefreshCw, Pencil } from 'lucide-react'

const CHANNEL_ICONS = { email: Mail, feishu: MessageSquare, dingtalk: Bot, telegram: Radio }
const CHANNEL_LABELS = { email: '邮件', feishu: '飞书', dingtalk: '钉钉', telegram: 'Telegram' }

const CHANNEL_FIELDS = {
  email: [{ key: 'email', label: '收件邮箱', placeholder: 'user@example.com', type: 'email' }],
  feishu: [{ key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://open.feishu.cn/open-apis/bot/v2/hook/...' }],
  dingtalk: [
    { key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://oapi.dingtalk.com/robot/send?access_token=...' },
    { key: 'secret', label: '签名密钥 (可选)', placeholder: 'SEC...' },
  ],
  telegram: [
    { key: 'bot_token', label: 'Bot Token', placeholder: '123456:ABC...' },
    { key: 'chat_id', label: 'Chat ID', placeholder: '-1001234567890' },
  ],
}

function AddModal({ onClose, onCreated }) {
  const [type, setType] = useState('feishu')
  const [name, setName] = useState('')
  const [config, setConfig] = useState({})
  const [saving, setSaving] = useState(false)

  const fields = CHANNEL_FIELDS[type] || []

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await api.post('/api/v1/push-channels', { channel_type: type, name, config })
      onCreated()
      onClose()
    } catch (e) {
      alert(e.message)
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-white mb-4">添加推送渠道</h2>

        <label className="block text-sm text-slate-400 mb-1">渠道类型</label>
        <div className="flex gap-2 mb-4">
          {Object.entries(CHANNEL_LABELS).map(([k, label]) => (
            <button key={k} onClick={() => { setType(k); setConfig({}) }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${type === k ? 'bg-sky-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>
              {label}
            </button>
          ))}
        </div>

        <label className="block text-sm text-slate-400 mb-1">名称</label>
        <input value={name} onChange={e => setName(e.target.value)}
          placeholder="如：我的飞书群" className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm mb-4" />

        {fields.map(f => (
          <div key={f.key} className="mb-3">
            <label className="block text-sm text-slate-400 mb-1">{f.label}</label>
            <input value={config[f.key] || ''} onChange={e => setConfig({ ...config, [f.key]: e.target.value })}
              type={f.type || 'text'} placeholder={f.placeholder}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>
        ))}

        <div className="flex justify-end gap-3 mt-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white">取消</button>
          <button onClick={handleSave} disabled={saving || !name.trim()}
            className="px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PushChannels() {
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [testing, setTesting] = useState(null)
  const [editCh, setEditCh] = useState(null)

  const load = async () => {
    try {
      const res = await api.get('/api/v1/push-channels')
      setChannels(res.data?.data?.channels || res.data?.channels || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleTest = async (id) => {
    setTesting(id)
    try {
      const res = await api.post(`/api/v1/push-channels/${id}/test`)
      alert(res.message || '测试消息已发送')
    } catch (e) {
      alert('发送失败: ' + e.message)
    }
    setTesting(null)
  }

  const handleToggle = async (ch) => {
    try {
      await api.put(`/api/v1/push-channels/${ch.id}`, { enabled: !ch.enabled })
      load()
    } catch (e) { alert(e.message) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除该推送渠道？')) return
    try {
      await api.delete(`/api/v1/push-channels/${id}`)
      load()
    } catch (e) { alert(e.message) }
  }

  if (loading) return <div className="text-slate-500 text-sm p-4">加载中...</div>

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">推送渠道</h1>
          <p className="text-sm text-slate-500 mt-1">管理报告推送渠道，支持邮件、飞书、钉钉、Telegram</p>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600">
          <Plus size={16} />添加渠道
        </button>
      </div>

      {channels.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Send size={40} className="mx-auto mb-3 opacity-30" />
          <p>尚未配置推送渠道</p>
          <p className="text-sm mt-1">点击上方按钮添加你的第一个推送渠道</p>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map(ch => {
            const Icon = CHANNEL_ICONS[ch.channel_type] || Send
            const configEntries = Object.entries(ch.config || {}).filter(([k]) => ch.config[k])
            return (
              <div key={ch.id} className="bg-slate-800/80 border border-slate-700/50 rounded-xl p-4 flex items-center gap-4">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${ch.enabled ? 'bg-sky-500/20 text-sky-400' : 'bg-slate-700 text-slate-500'}`}>
                  <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm">{ch.name}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
                      {ch.channel_label}
                    </span>
                    {!ch.enabled && <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-500">已禁用</span>}
                  </div>
                  <div className="text-xs text-slate-500 mt-1 truncate">
                    {configEntries.map(([k, v]) => `${k}: ${v}`).join(' · ')}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => setEditCh(ch)}
                    className="p-2 rounded-lg text-slate-400 hover:text-sky-400 hover:bg-slate-700" title="编辑">
                    <Pencil size={16} />
                  </button>
                  <button onClick={() => handleTest(ch.id)} disabled={testing === ch.id || !ch.enabled}
                    className="p-2 rounded-lg text-slate-400 hover:text-sky-400 hover:bg-slate-700 disabled:opacity-30" title="发送测试">
                    {testing === ch.id ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
                  </button>
                  <button onClick={() => handleToggle(ch)} className="p-2 rounded-lg text-slate-400 hover:bg-slate-700" title={ch.enabled ? '禁用' : '启用'}>
                    {ch.enabled ? <ToggleRight size={20} className="text-sky-400" /> : <ToggleLeft size={20} />}
                  </button>
                  <button onClick={() => handleDelete(ch.id)}
                    className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-700" title="删除">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showAdd && <AddModal onClose={() => setShowAdd(false)} onCreated={load} />}
      {editCh && <EditModal channel={editCh} onClose={() => setEditCh(null)} onSaved={load} />}
    </div>
  )
}

function EditModal({ channel, onClose, onSaved }) {
  const [name, setName] = useState(channel.name || '')
  const [config, setConfig] = useState(channel.config || {})
  const [saving, setSaving] = useState(false)

  const fields = CHANNEL_FIELDS[channel.channel_type] || []
  const inputCls = "w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm"

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await api.put(`/api/v1/push-channels/${channel.id}`, { name, config })
      onSaved()
      onClose()
    } catch (e) {
      alert(e.message)
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-white mb-4">编辑推送渠道</h2>

        <div className="flex items-center gap-2 mb-4">
          <span className="px-3 py-1.5 rounded-lg text-sm font-medium bg-sky-500/20 text-sky-400">
            {CHANNEL_LABELS[channel.channel_type] || channel.channel_type}
          </span>
          <span className="text-xs text-slate-500">渠道类型不可更改</span>
        </div>

        <label className="block text-sm text-slate-400 mb-1">名称</label>
        <input value={name} onChange={e => setName(e.target.value)}
          className={`${inputCls} mb-4`} />

        {fields.map(f => (
          <div key={f.key} className="mb-3">
            <label className="block text-sm text-slate-400 mb-1">{f.label}</label>
            <input value={config[f.key] || ''} onChange={e => setConfig({ ...config, [f.key]: e.target.value })}
              type={f.type || 'text'} placeholder={f.placeholder}
              className={inputCls} />
          </div>
        ))}

        <div className="flex justify-end gap-3 mt-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white">取消</button>
          <button onClick={handleSave} disabled={saving || !name.trim()}
            className="px-4 py-2 bg-sky-500 text-white text-sm rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
