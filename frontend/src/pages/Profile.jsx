import { useState } from 'react'
import { api } from '../api/client'
import { User, Lock, CheckCircle, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

export default function Profile() {
  const user = api.getUser() || {}
  const [displayName, setDisplayName] = useState(user.display_name || '')
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingPwd, setSavingPwd] = useState(false)
  const [msg, setMsg] = useState(null)

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const handleSaveProfile = async () => {
    setSavingProfile(true)
    try {
      const res = await api.put(`/api/v1/users/${user.id}`, { display_name: displayName })
      const updated = res.data?.data || {}
      api.setUser({ ...user, ...updated })
      showMsg('个人信息已更新')
    } catch (e) { showMsg(e.message, false) }
    finally { setSavingProfile(false) }
  }

  const handleChangePwd = async () => {
    if (!oldPwd || !newPwd) { showMsg('请填写旧密码和新密码', false); return }
    if (newPwd !== confirmPwd) { showMsg('两次输入的新密码不一致', false); return }
    if (newPwd.length < 6) { showMsg('新密码至少 6 个字符', false); return }
    setSavingPwd(true)
    try {
      await api.post('/api/v1/auth/change-password', { old_password: oldPwd, new_password: newPwd })
      setOldPwd(''); setNewPwd(''); setConfirmPwd('')
      showMsg('密码已修改')
    } catch (e) { showMsg(e.message, false) }
    finally { setSavingPwd(false) }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="space-y-6 w-full">
      <h2 className="text-2xl font-bold text-white">个人信息</h2>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {/* 基本信息 */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <User size={20} className="text-sky-400" />
          <h3 className="text-lg font-semibold text-white">基本资料</h3>
          <span className={clsx("text-xs px-2 py-0.5 rounded ml-2",
            user.role === 'admin' ? "bg-amber-500/20 text-amber-400" : "bg-sky-500/20 text-sky-400")}>
            {user.role === 'admin' ? '管理员' : '普通用户'}
          </span>
          {user.is_member && user.role !== 'admin' && (
            <span className="text-xs px-2 py-0.5 rounded ml-1 bg-violet-500/20 text-violet-400">会员</span>
          )}
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">邮箱</label>
            <input type="email" value={user.email || ''} disabled
              className={inputCls + " opacity-60 cursor-not-allowed"} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">显示名称</label>
            <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)}
              placeholder="输入你的名称" className={inputCls} />
          </div>
          <button onClick={handleSaveProfile} disabled={savingProfile}
            className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
            {savingProfile ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {/* 修改密码 */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <Lock size={20} className="text-sky-400" />
          <h3 className="text-lg font-semibold text-white">修改密码</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">旧密码</label>
            <input type="password" value={oldPwd} onChange={e => setOldPwd(e.target.value)}
              className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">新密码</label>
            <input type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)}
              className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">确认新密码</label>
            <input type="password" value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)}
              className={inputCls} />
          </div>
          <button onClick={handleChangePwd} disabled={savingPwd}
            className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 disabled:opacity-50">
            {savingPwd ? '修改中...' : '修改密码'}
          </button>
        </div>
      </div>
    </div>
  )
}
