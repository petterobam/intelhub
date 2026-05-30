import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Send, Loader2, Users, User, ChevronDown, ChevronRight, CheckCircle, AlertCircle, X, Mail, MessageSquare, Bot, Radio } from 'lucide-react'
import clsx from 'clsx'

const CHANNEL_ICONS = { email: Mail, feishu: MessageSquare, dingtalk: Bot, telegram: Radio }
const CHANNEL_LABELS = { email: '邮件', feishu: '飞书', dingtalk: '钉钉', telegram: 'Telegram' }

export default function PushReportModal({ report, onClose, onDone, admin = false }) {
  const [mode, setMode] = useState(admin ? 'all' : 'user')
  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [selectedChannelIds, setSelectedChannelIds] = useState([])
  const [myChannels, setMyChannels] = useState([])
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)
  const [expandedUser, setExpandedUser] = useState(null)

  // 从报告记录获取 ID 和标题
  const reportId = report.id || ''
  const reportTitle = report.title || report.name || ''

  // 加载管理员用户列表
  useEffect(() => {
    if (!admin) return
    api.get('/api/v1/push-channels/all-users')
      .then(res => {
        const list = res.data?.data?.users || []
        setUsers(list)
      })
      .catch(() => {})
  }, [admin])

  // 加载当前用户自己的渠道
  useEffect(() => {
    if (admin) return
    api.get('/api/v1/push-channels')
      .then(res => {
        const chs = res.data?.data?.channels || res.data?.channels || []
        setMyChannels(chs)
        setSelectedChannelIds(chs.map(c => c.id))
      })
      .catch(() => {})
  }, [admin])

  const toggleChannel = (id) => {
    setSelectedChannelIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handlePush = async () => {
    setSending(true)
    setResult(null)
    try {
      const payload = {
        report_id: reportId,
        mode,
      }
      if (mode === 'user') {
        payload.user_id = admin ? selectedUserId : api.getUser()?.id
        if (selectedChannelIds.length > 0) {
          payload.channel_ids = selectedChannelIds
        }
      }
      const res = await api.post('/api/v1/reports/push', payload)
      const data = res.data?.data || res.data || {}
      setResult({ ok: true, sent: data.sent || 0, failed: data.failed || 0, message: data.message })
      onDone?.(data)
    } catch (e) {
      setResult({ ok: false, message: e.response?.data?.error?.message || e.message || '推送失败' })
    }
    setSending(false)
  }

  // 管理员模式下，获取选中用户的渠道
  const selectedUser = users.find(u => u.id === selectedUserId)
  const targetChannels = admin
    ? (selectedUser?.channels || [])
    : myChannels

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-lg shadow-2xl border border-slate-700 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Send size={18} className="text-sky-400" />
            推送报告
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>

        {/* 报告信息 */}
        <div className="bg-slate-900/60 rounded-lg px-3 py-2 mb-4 text-sm text-slate-300 truncate">
          {report.title || report.name}
        </div>

        {/* 管理员模式切换 */}
        {admin && (
          <div className="flex gap-2 mb-4">
            <button onClick={() => setMode('all')}
              className={clsx('flex-1 px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-colors',
                mode === 'all' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40' : 'bg-slate-700/50 text-slate-400 border border-slate-600'
              )}>
              <Users size={14} /> 全员推送
            </button>
            <button onClick={() => setMode('user')}
              className={clsx('flex-1 px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-colors',
                mode === 'user' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40' : 'bg-slate-700/50 text-slate-400 border border-slate-600'
              )}>
              <User size={14} /> 指定用户
            </button>
          </div>
        )}

        {/* 管理员选择用户 */}
        {admin && mode === 'user' && (
          <div className="mb-4 space-y-2">
            <label className="block text-sm text-slate-400">选择用户</label>
            <select value={selectedUserId} onChange={e => { setSelectedUserId(e.target.value); setSelectedChannelIds([]) }}
              className={inputCls}>
              <option value="">选择用户...</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>
                  {u.display_name || u.email} {u.channels.length > 0 ? `(${u.channels.length}个渠道)` : '(无渠道)'}
                </option>
              ))}
            </select>

            {/* 选中用户的渠道 */}
            {selectedUser && targetChannels.length > 0 && (
              <div className="bg-slate-900/40 rounded-lg p-3 space-y-2">
                <div className="text-xs text-slate-500 mb-1">选择推送渠道</div>
                <button onClick={() => setSelectedChannelIds(
                  selectedChannelIds.length === targetChannels.length ? [] : targetChannels.map(c => c.id)
                )} className="text-xs text-sky-400 hover:text-sky-300 mb-1">
                  {selectedChannelIds.length === targetChannels.length ? '取消全选' : '全选'}
                </button>
                {targetChannels.map(ch => {
                  const Icon = CHANNEL_ICONS[ch.channel_type] || Send
                  const checked = selectedChannelIds.includes(ch.id)
                  return (
                    <label key={ch.id} className={clsx(
                      "flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors",
                      checked ? "bg-sky-500/10 text-white" : "text-slate-400 hover:bg-slate-700/50"
                    )}>
                      <input type="checkbox" checked={checked} onChange={() => toggleChannel(ch.id)}
                        className="rounded border-slate-600 bg-slate-700 text-sky-500 focus:ring-sky-500" />
                      <Icon size={14} />
                      <span className="text-sm">{ch.name}</span>
                      <span className="text-xs text-slate-500">{CHANNEL_LABELS[ch.channel_type]}</span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* 普通用户选择渠道 */}
        {!admin && myChannels.length > 0 && (
          <div className="mb-4">
            <div className="text-sm text-slate-400 mb-2">选择推送渠道</div>
            <div className="space-y-2">
              <button onClick={() => setSelectedChannelIds(
                selectedChannelIds.length === myChannels.length ? [] : myChannels.map(c => c.id)
              )} className="text-xs text-sky-400 hover:text-sky-300 mb-1">
                {selectedChannelIds.length === myChannels.length ? '取消全选' : '全选'}
              </button>
              {myChannels.map(ch => {
                const Icon = CHANNEL_ICONS[ch.channel_type] || Send
                const checked = selectedChannelIds.includes(ch.id)
                return (
                  <label key={ch.id} className={clsx(
                    "flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors border",
                    checked ? "bg-sky-500/10 border-sky-500/30 text-white" : "border-slate-700 text-slate-400 hover:bg-slate-700/50"
                  )}>
                    <input type="checkbox" checked={checked} onChange={() => toggleChannel(ch.id)}
                      className="rounded border-slate-600 bg-slate-700 text-sky-500 focus:ring-sky-500" />
                    <Icon size={16} className={ch.enabled !== false ? 'text-sky-400' : 'text-slate-600'} />
                    <div className="flex-1">
                      <span className="text-sm">{ch.name}</span>
                      <span className="text-xs text-slate-500 ml-2">{CHANNEL_LABELS[ch.channel_type]}</span>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
        )}

        {!admin && myChannels.length === 0 && (
          <div className="mb-4 bg-slate-900/40 rounded-lg p-4 text-center text-sm text-slate-500">
            暂无推送渠道，请先在「推送渠道」页面配置
          </div>
        )}

        {/* 推送结果 */}
        {result && (
          <div className={clsx(
            "flex items-center gap-2 px-4 py-3 rounded-lg text-sm mb-4",
            result.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
          )}>
            {result.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {result.ok
              ? `推送完成: 成功 ${result.sent} 个${result.failed > 0 ? `, 失败 ${result.failed} 个` : ''}`
              : result.message
            }
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 pt-2">
          <button onClick={handlePush}
            disabled={sending || (mode === 'user' && admin && !selectedUserId) || (!admin && selectedChannelIds.length === 0)}
            className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
            {sending ? <><Loader2 size={14} className="animate-spin" /> 推送中...</> : <><Send size={14} /> 立即推送</>}
          </button>
          <button onClick={onClose}
            className="bg-slate-700 text-slate-400 px-4 py-2 rounded-lg text-sm hover:bg-slate-600">
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}
