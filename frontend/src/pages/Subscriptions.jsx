import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Mail, Plus, Trash2, Send, ToggleLeft, ToggleRight, X, UserPlus, UserCheck, Pencil } from 'lucide-react'
import clsx from 'clsx'

export default function Subscriptions() {
  const [subs, setSubs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editSub, setEditSub] = useState(null)
  const [msg, setMsg] = useState(null)
  const isAdmin = (api.getUser() || {}).role === 'admin'

  useEffect(() => {
    // Read cache first
    try {
      const cached = localStorage.getItem('intelhub_subs_cache')
      if (cached) {
        setSubs(JSON.parse(cached))
        setLoading(false)
      }
    } catch { /* ignore */ }
    load()
  }, [])

  const load = async () => {
    try {
      const res = await api.get('/api/v1/subscriptions')
      const data = res.data?.data || res.data || []
      setSubs(data)
      localStorage.setItem('intelhub_subs_cache', JSON.stringify(data))
    } catch { } finally { setLoading(false) }
  }

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const toggleEnabled = async (sub) => {
    try {
      await api.put(`/api/v1/subscriptions/${sub.id}`, { enabled: !sub.enabled })
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const deleteSub = async (id) => {
    if (!confirm('确认删除此订阅？')) return
    try {
      await api.delete(`/api/v1/subscriptions/${id}`)
      showMsg('已删除')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const testSub = async (sub) => {
    try {
      const res = await api.post(`/api/v1/subscriptions/${sub.id}/test`)
      showMsg(res.data?.data?.message || '测试邮件已发送')
    } catch (e) { showMsg(e.message, false) }
  }

  const initUser = async (sub) => {
    if (!confirm(`确认为 ${sub.email} 创建平台账号？将自动发送包含密码的欢迎邮件。`)) return
    try {
      const res = await api.post(`/api/v1/subscriptions/${sub.id}/init-user`)
      showMsg(res.data?.data?.message || '账号已创建')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  if (loading) return <div className="text-slate-400">加载中...</div>

  const title = isAdmin ? '订阅中心' : '我的订阅'
  const emptyText = isAdmin
    ? '暂无订阅者'
    : '你还没有订阅任何报告'
  const emptyDesc = isAdmin
    ? '点击"新增订阅"添加邮箱，绑定报告任务接收推送'
    : '点击"新增订阅"选择要订阅的报告任务'

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">{title}</h2>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30">
          <Plus size={16} /> 新增订阅
        </button>
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.text}
        </div>
      )}

      {showAdd && <AddModal isAdmin={isAdmin} onSaved={() => { setShowAdd(false); load() }} onClose={() => setShowAdd(false)} />}
      {editSub && <EditModal sub={editSub} onSaved={() => { setEditSub(null); load() }} onClose={() => setEditSub(null)} />}

      {subs.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-10 border border-slate-700 text-center">
          <Mail size={48} className="mx-auto mb-4 text-slate-600" />
          <p className="text-slate-400">{emptyText}</p>
          <p className="text-sm text-slate-600 mt-1">{emptyDesc}</p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase">
                {isAdmin && <th className="text-left px-5 py-3">邮箱</th>}
                {isAdmin && <th className="text-left px-4 py-3">名称</th>}
                <th className="text-left px-4 py-3">订阅任务</th>
                <th className="text-left px-4 py-3">推送渠道</th>
                <th className="text-center px-4 py-3">状态</th>
                {isAdmin && <th className="text-center px-4 py-3">账号</th>}
                <th className="text-right px-5 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {subs.map(sub => (
                <tr key={sub.id} className="border-b border-slate-700/50 last:border-0 hover:bg-slate-700/20">
                  {isAdmin && <td className="px-5 py-3 text-sm text-slate-200">{sub.email}</td>}
                  {isAdmin && <td className="px-4 py-3 text-sm text-slate-400">{sub.name || '-'}</td>}
                  <td className="px-4 py-3">
                    <span className="text-xs bg-sky-500/10 text-sky-400 px-2 py-0.5 rounded">
                      {sub.task_name || sub.task_id || '-'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(sub.channel_labels || []).map((ch, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                          {ch.name}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {isAdmin ? (
                      <button onClick={() => toggleEnabled(sub)} className="text-slate-400 hover:text-white">
                        {sub.enabled
                          ? <ToggleRight size={22} className="text-sky-400" />
                          : <ToggleLeft size={22} />}
                      </button>
                    ) : (
                      <span className={clsx("text-xs px-2 py-0.5 rounded",
                        sub.enabled ? "bg-green-500/10 text-green-400" : "bg-slate-700 text-slate-500")}>
                        {sub.enabled ? '已启用' : '已禁用'}
                      </span>
                    )}
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-center">
                      {sub.has_user ? (
                        <span className="inline-flex items-center gap-1 text-xs bg-green-500/10 text-green-400 px-2 py-0.5 rounded">
                          <UserCheck size={12} /> 已注册
                        </span>
                      ) : (
                        <button onClick={() => initUser(sub)} title="创建平台账号"
                          className="inline-flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 transition-colors">
                          <UserPlus size={13} /> 初始化
                        </button>
                      )}
                    </td>
                  )}
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => setEditSub(sub)} title="编辑"
                        className="text-slate-500 hover:text-sky-400 transition-colors">
                        <Pencil size={15} />
                      </button>
                      {isAdmin && (
                        <button onClick={() => testSub(sub)} title="发送测试邮件"
                          className="text-slate-500 hover:text-sky-400 transition-colors">
                          <Send size={15} />
                        </button>
                      )}
                      <button onClick={() => deleteSub(sub.id)} title="删除"
                        className="text-slate-500 hover:text-red-400 transition-colors">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function AddModal({ isAdmin, onSaved, onClose }) {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [taskId, setTaskId] = useState('')
  const [selectedChannelIds, setSelectedChannelIds] = useState(['_email'])
  const [reportTasks, setReportTasks] = useState([])
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [targetUser, setTargetUser] = useState(null)

  useEffect(() => {
    api.get('/api/v1/subscriptions/report-tasks').then(res => setReportTasks(res.data?.data || [])).catch(() => {})
    if (!isAdmin) {
      api.get('/api/v1/push-channels').then(res => {
        setChannels((res.data?.data || res).channels || [])
      }).catch(() => {}).finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  // 管理员输入邮箱后，查找该用户的推送渠道
  const lookupUser = async () => {
    if (!isAdmin || !email || !email.includes('@')) {
      setTargetUser(null)
      setChannels([])
      setSelectedChannelIds(['_email'])
      return
    }
    try {
      const res = await api.get(`/api/v1/users/by-email?email=${encodeURIComponent(email)}`)
      const user = res.data?.data
      setTargetUser(user)
      if (user && user.id) {
        const chRes = await api.get(`/api/v1/push-channels?user_id=${user.id}`)
        setChannels((chRes.data?.data || {}).channels || [])
      } else {
        setChannels([])
        setSelectedChannelIds(['_email'])
      }
    } catch {
      setTargetUser(null)
      setChannels([])
      setSelectedChannelIds(['_email'])
    }
  }

  const toggleChannel = (id) => {
    setSelectedChannelIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleSave = async () => {
    if (isAdmin && (!email || !email.includes('@'))) { alert('请输入有效邮箱'); return }
    if (!taskId) { alert('请选择要订阅的报告任务'); return }
    setSaving(true)
    try {
      const payload = { task_id: taskId }
      if (isAdmin) { payload.email = email; payload.name = name }
      payload.channel_ids = selectedChannelIds
      await api.post('/api/v1/subscriptions', payload)
      onSaved()
    } catch (e) { alert('添加失败: ' + e.message) }
    finally { setSaving(false) }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">新增订阅</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="space-y-4">
          {isAdmin && (
            <>
              <div>
                <label className="block text-sm text-slate-400 mb-1">邮箱 *</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} onBlur={lookupUser}
                  placeholder="user@example.com" className={inputCls} />
                {targetUser === null && email.includes('@') && (
                  <p className="text-xs text-slate-600 mt-1">未找到已注册用户，将使用邮件推送</p>
                )}
                {targetUser && (
                  <p className="text-xs text-green-400 mt-1">已匹配用户：{targetUser.email}</p>
                )}
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">联系人名称</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="可选"
                  className={inputCls} />
              </div>
            </>
          )}
          {!isAdmin && (
            <p className="text-sm text-slate-400">将使用你的注册邮箱自动订阅所选报告任务。</p>
          )}
          <div>
            <label className="block text-sm text-slate-400 mb-1">订阅报告任务 *</label>
            {loading ? (
              <div className="text-sm text-slate-500">加载任务列表...</div>
            ) : reportTasks.length === 0 ? (
              <div className="text-sm text-red-400">暂无报告任务，请先创建报告类型的任务</div>
            ) : (
              <select value={taskId} onChange={e => setTaskId(e.target.value)} className={inputCls}>
                <option value="">-- 选择报告任务 --</option>
                {reportTasks.map(t => (
                  <option key={t.id} value={t.id}>{t.name} ({t.module}) {!t.enabled ? ' [已禁用]' : ''}</option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">推送渠道（可多选）</label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              <label className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                <input type="checkbox" checked={selectedChannelIds.includes('_email')}
                  onChange={() => toggleChannel('_email')}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500 focus:ring-offset-0" />
                <span className="text-sm text-slate-200">邮件推送</span>
                <span className="text-xs px-2 py-0.5 rounded bg-sky-500/10 text-sky-400">默认</span>
              </label>
              {channels.filter(c => c.enabled).map(c => (
                <label key={c.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                  <input type="checkbox" checked={selectedChannelIds.includes(c.id)}
                    onChange={() => toggleChannel(c.id)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500 focus:ring-offset-0" />
                  <span className="text-sm text-slate-200">{c.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
                    {c.channel_label || c.channel_type}
                  </span>
                </label>
              ))}
            </div>
            <p className="text-xs text-slate-600 mt-1">不选任何渠道时默认邮件推送</p>
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={saving || !taskId}
              className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
              {saving ? '保存中...' : '添加'}
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

function EditModal({ sub, onSaved, onClose }) {
  const [selectedChannelIds, setSelectedChannelIds] = useState(
    sub.channel_ids && sub.channel_ids.length > 0
      ? sub.channel_ids
      : ['_email']
  )
  const [channels, setChannels] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/api/v1/push-channels').then(res => {
      const data = res.data?.data || res
      setChannels(data.channels || [])
    }).catch(() => {})
  }, [])

  const toggleChannel = (id) => {
    setSelectedChannelIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put(`/api/v1/subscriptions/${sub.id}`, { channel_ids: selectedChannelIds })
      onSaved()
    } catch (e) { alert('保存失败: ' + e.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">编辑订阅渠道</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="space-y-4">
          <div className="text-sm text-slate-400">
            订阅任务：<span className="text-slate-200">{sub.task_name || '-'}</span>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">推送渠道（可多选）</label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              <label className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                <input type="checkbox" checked={selectedChannelIds.includes('_email')}
                  onChange={() => toggleChannel('_email')}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500 focus:ring-offset-0" />
                <span className="text-sm text-slate-200">邮件推送</span>
                <span className="text-xs text-slate-500">{sub.email}</span>
              </label>
              {channels.filter(c => c.enabled).map(c => (
                <label key={c.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                  <input type="checkbox" checked={selectedChannelIds.includes(c.id)}
                    onChange={() => toggleChannel(c.id)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500 focus:ring-offset-0" />
                  <span className="text-sm text-slate-200">{c.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
                    {c.channel_label || c.channel_type}
                  </span>
                </label>
              ))}
            </div>
            <p className="text-xs text-slate-600 mt-1">不选任何渠道时默认邮件推送</p>
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
