import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Users as UsersIcon, Plus, Trash2, Edit3, X, CheckCircle, AlertCircle, ToggleLeft, ToggleRight, Crown } from 'lucide-react'
import clsx from 'clsx'

const TIER_OPTIONS = [
  { value: 'free', label: 'Free', color: 'text-slate-400' },
  { value: 'v1', label: 'V1', color: 'text-green-400' },
  { value: 'v2', label: 'V2', color: 'text-blue-400' },
  { value: 'v3', label: 'V3', color: 'text-purple-400' },
  { value: 'v4', label: 'V4', color: 'text-amber-400' },
  { value: 'v5', label: 'V5', color: 'text-rose-400' },
]

export default function Users() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [msg, setMsg] = useState(null)

  const load = async () => {
    try {
      const res = await api.get('/api/v1/users')
      const d = res.data?.data || []
      setUsers(d)
      localStorage.setItem('intelhub_users_cache', JSON.stringify(d))
    } catch { } finally { setLoading(false) }
  }

  useEffect(() => {
    try {
      const c = localStorage.getItem('intelhub_users_cache')
      if (c) { setUsers(JSON.parse(c)); setLoading(false) }
    } catch { /* ignore */ }
    load()
  }, [])

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const toggleEnabled = async (user) => {
    try {
      await api.put(`/api/v1/users/${user.id}`, { enabled: !user.enabled })
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const toggleMember = async (user) => {
    try {
      await api.put(`/api/v1/users/${user.id}`, { is_member: !user.is_member })
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const deleteUser = async (id) => {
    if (!confirm('确定删除此用户？')) return
    try {
      await api.delete(`/api/v1/users/${id}`)
      showMsg('已删除')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  if (loading) return <div className="text-slate-400">加载中...</div>

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <UsersIcon size={24} className="text-sky-400" />
          <h2 className="text-2xl font-bold text-white">用户管理</h2>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30">
          <Plus size={16} /> 新增用户
        </button>
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {showAdd && <UserFormModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load() }} />}
      {editUser && <UserFormModal user={editUser} onClose={() => setEditUser(null)} onSaved={() => { setEditUser(null); load() }} />}

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase">
              <th className="text-left px-5 py-3">邮箱</th>
              <th className="text-left px-4 py-3">名称</th>
              <th className="text-left px-4 py-3">角色</th>
              <th className="text-center px-4 py-3">会员</th>
              <th className="text-center px-4 py-3">等级</th>
              <th className="text-center px-4 py-3">状态</th>
              <th className="text-left px-4 py-3">创建时间</th>
              <th className="text-right px-5 py-3">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => {
              const tierInfo = TIER_OPTIONS.find(t => t.value === (u.tier || 'free')) || TIER_OPTIONS[0]
              return (
                <tr key={u.id} className="border-b border-slate-700/50 last:border-0 hover:bg-slate-700/20">
                  <td className="px-5 py-3 text-sm text-slate-200">{u.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-400">{u.display_name || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={clsx("text-xs px-2 py-0.5 rounded",
                      u.role === 'admin' ? "bg-amber-500/20 text-amber-400" : "bg-sky-500/20 text-sky-400")}>
                      {u.role === 'admin' ? '管理员' : '用户'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {u.role !== 'admin' && (
                      <button onClick={() => toggleMember(u)} className="text-slate-400 hover:text-white">
                        {u.is_member ? <ToggleRight size={22} className="text-violet-400" /> : <ToggleLeft size={22} />}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={clsx("text-xs font-semibold", tierInfo.color)}>
                      {tierInfo.value !== 'free' && <Crown size={10} className="inline mr-0.5" />}
                      {tierInfo.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleEnabled(u)} className="text-slate-400 hover:text-white">
                      {u.enabled ? <ToggleRight size={22} className="text-sky-400" /> : <ToggleLeft size={22} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => setEditUser(u)} className="text-slate-500 hover:text-yellow-400"><Edit3 size={15} /></button>
                      <button onClick={() => deleteUser(u.id)} className="text-slate-500 hover:text-red-400"><Trash2 size={15} /></button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function UserFormModal({ user, onClose, onSaved }) {
  const isEdit = !!user
  const [email, setEmail] = useState(user?.email || '')
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(user?.role || 'user')
  const [tier, setTier] = useState(user?.tier_raw || user?.tier || 'free')
  const [tierExpires, setTierExpires] = useState(() => {
    if (!user?.tier_expires_at) return ''
    return user.tier_expires_at.substring(0, 16)
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!email) { alert('请输入邮箱'); return }
    if (!isEdit && !password) { alert('请输入密码'); return }
    if (password && password.length < 6) { alert('密码至少 6 个字符'); return }
    setSaving(true)
    try {
      if (isEdit) {
        const payload = { display_name: displayName, role, tier }
        if (tierExpires) payload.tier_expires_at = new Date(tierExpires).toISOString()
        else payload.tier_expires_at = null
        if (password) payload.password = password
        await api.put(`/api/v1/users/${user.id}`, payload)
      } else {
        await api.post('/api/v1/users', { email, display_name: displayName, password, role, tier })
      }
      onSaved()
    } catch (e) { alert('操作失败: ' + e.message) }
    finally { setSaving(false) }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">{isEdit ? '编辑用户' : '新增用户'}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">邮箱 *</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              disabled={isEdit} placeholder="user@example.com" className={inputCls + (isEdit ? ' opacity-60' : '')} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">{isEdit ? '新密码（留空不改）' : '密码 *'}</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder={isEdit ? '留空则不修改' : '至少 6 个字符'} className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">显示名称</label>
            <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)}
              placeholder="可选" className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-400 mb-1">角色</label>
              <select value={role} onChange={e => setRole(e.target.value)} className={inputCls}>
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">等级</label>
              <select value={tier} onChange={e => setTier(e.target.value)} className={inputCls}>
                {TIER_OPTIONS.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          {tier !== 'free' && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">等级到期时间（留空=永久）</label>
              <input type="datetime-local" value={tierExpires} onChange={e => setTierExpires(e.target.value)}
                className={inputCls} />
            </div>
          )}
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
