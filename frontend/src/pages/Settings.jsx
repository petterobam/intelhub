import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Settings as SettingsIcon, Mail, RefreshCw, Loader2, CheckCircle, AlertCircle, Globe } from 'lucide-react'
import clsx from 'clsx'

const MASK = '••••••••'

const SECTIONS = [
  { key: 'llm', label: 'LLM 配置', icon: SettingsIcon },
  { key: 'smtp', label: '邮件服务', icon: Mail },
  { key: 'site', label: '站点配置', icon: Globe },
]

export default function SettingsPage() {
  const [section, setSection] = useState('llm')
  const [settings, setSettings] = useState(null)
  const [llmForm, setLlmForm] = useState({ api_key: '', base_url: '', model: '' })
  const [smtpForm, setSmtpForm] = useState({ host: '', port: 465, user: '', password: '', from_name: 'IntelHub', use_tls: true })
  const [siteForm, setSiteForm] = useState({ site_url: '' })
  const [models, setModels] = useState([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [saving, setSaving] = useState('')
  const [msg, setMsg] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadSettings() }, [])

  const loadSettings = async () => {
    try {
      const res = await api.get('/api/v1/settings')
      const data = res.data?.data || res.data || {}
      setSettings(data)
      const llm = data.llm || {}
      setLlmForm({
        api_key: llm.configured ? MASK : '',
        base_url: llm.base_url || '',
        model: llm.model || '',
      })
      const smtp = data.smtp || {}
      setSmtpForm({
        host: smtp.host || '',
        port: smtp.port || 465,
        user: smtp.user || '',
        password: smtp.configured ? MASK : '',
        from_name: smtp.from_name || 'IntelHub',
        use_tls: smtp.use_tls !== false,
      })
      const site = data.site || {}
      setSiteForm({
        site_url: site.site_url || '',
      })
    } catch { } finally { setLoading(false) }
  }

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const saveLlm = async () => {
    setSaving('llm')
    try {
      await api.put('/api/v1/settings', { llm: llmForm })
      showMsg('LLM 配置已保存')
      loadSettings()
    } catch (e) { showMsg(e.message, false) }
    finally { setSaving('') }
  }

  const saveSmtp = async () => {
    setSaving('smtp')
    try {
      await api.put('/api/v1/settings', { smtp: smtpForm })
      showMsg('SMTP 配置已保存')
      loadSettings()
    } catch (e) { showMsg(e.message, false) }
    finally { setSaving('') }
  }

  const saveSite = async () => {
    setSaving('site')
    try {
      await api.put('/api/v1/settings', { site: siteForm })
      showMsg('站点配置已保存')
      loadSettings()
    } catch (e) { showMsg(e.message, false) }
    finally { setSaving('') }
  }

  const testSmtp = async () => {
    setSaving('smtp-test')
    try {
      const testEmail = prompt('请输入测试邮箱地址:')
      if (!testEmail) { setSaving(''); return }
      await api.post('/api/v1/settings/smtp/test', { to: testEmail })
      showMsg(`测试邮件已发送至 ${testEmail}`)
    } catch (e) { showMsg(e.message, false) }
    finally { setSaving('') }
  }

  const fetchModels = async () => {
    setFetchingModels(true)
    try {
      const res = await api.get('/api/v1/settings/models')
      const list = res.data?.data || []
      setModels(list)
      if (list.length > 0 && !llmForm.model) {
        setLlmForm(f => ({ ...f, model: list[0].id }))
      }
    } catch (e) { showMsg('获取模型列表失败: ' + e.message, false) }
    finally { setFetchingModels(false) }
  }

  if (loading) return <div className="text-slate-400">加载中...</div>

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"

  return (
    <div className="h-[calc(100vh-80px)] flex gap-6">
      {/* 左侧菜单 */}
      <div className="w-48 shrink-0 bg-slate-800 rounded-xl border border-slate-700 p-2 flex flex-col gap-1">
        <h2 className="px-3 py-2 text-lg font-bold text-white">配置中心</h2>
        {SECTIONS.map(s => {
          const Icon = s.icon
          const active = section === s.key
          return (
            <button key={s.key} onClick={() => setSection(s.key)}
              className={clsx(
                'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors w-full text-left',
                active ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              )}>
              <Icon size={16} />
              {s.label}
            </button>
          )
        })}
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 min-w-0 overflow-y-auto space-y-4">
        {msg && (
          <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
            msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
            {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {msg.text}
          </div>
        )}

        {/* LLM 配置 */}
        {section === 'llm' && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center gap-2 mb-4">
              <SettingsIcon size={20} className="text-sky-400" />
              <h3 className="text-lg font-semibold text-white">LLM 配置</h3>
              {settings?.llm?.sdk_available && <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">SDK 可用</span>}
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">API Key *</label>
                <input type="password" value={llmForm.api_key} onChange={e => setLlmForm(f => ({ ...f, api_key: e.target.value }))}
                  placeholder="sk-ant-..." className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Base URL</label>
                <input type="text" value={llmForm.base_url} onChange={e => setLlmForm(f => ({ ...f, base_url: e.target.value }))}
                  placeholder="https://open.bigmodel.cn/api/anthropic" className={inputCls} />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm text-slate-400">Model</label>
                  <button onClick={fetchModels} disabled={fetchingModels || !llmForm.base_url}
                    className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 disabled:opacity-50">
                    {fetchingModels ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    {fetchingModels ? '获取中...' : '获取模型列表'}
                  </button>
                </div>
                {models.length > 0 ? (
                  <select value={llmForm.model} onChange={e => setLlmForm(f => ({ ...f, model: e.target.value }))}
                    className={inputCls}>
                    <option value="">-- 选择模型 --</option>
                    {models.map(m => <option key={m.id} value={m.id}>{m.display_name || m.id}</option>)}
                  </select>
                ) : (
                  <input type="text" value={llmForm.model} onChange={e => setLlmForm(f => ({ ...f, model: e.target.value }))}
                    placeholder="claude-sonnet-4-20250514" className={inputCls} />
                )}
              </div>
              <button onClick={saveLlm} disabled={saving === 'llm'}
                className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-50">
                {saving === 'llm' ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        )}

        {/* SMTP 配置 */}
        {section === 'smtp' && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center gap-2 mb-4">
              <Mail size={20} className="text-sky-400" />
              <h3 className="text-lg font-semibold text-white">邮件服务配置</h3>
              {settings?.smtp?.configured && <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">已配置</span>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">SMTP Host *</label>
                <input type="text" value={smtpForm.host} onChange={e => setSmtpForm(f => ({ ...f, host: e.target.value }))}
                  placeholder="smtp.qq.com" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">端口</label>
                <input type="number" value={smtpForm.port} onChange={e => setSmtpForm(f => ({ ...f, port: parseInt(e.target.value) || 465 }))}
                  className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">SMTP User *</label>
                <input type="text" value={smtpForm.user} onChange={e => setSmtpForm(f => ({ ...f, user: e.target.value }))}
                  placeholder="noreply@example.com" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">SMTP Password *</label>
                <input type="password" value={smtpForm.password} onChange={e => setSmtpForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="授权码" className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">发件人名称</label>
                <input type="text" value={smtpForm.from_name} onChange={e => setSmtpForm(f => ({ ...f, from_name: e.target.value }))}
                  className={inputCls} />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                  <input type="checkbox" checked={smtpForm.use_tls} onChange={e => setSmtpForm(f => ({ ...f, use_tls: e.target.checked }))}
                    className="rounded" />
                  使用 TLS/SSL
                </label>
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={saveSmtp} disabled={saving === 'smtp'}
                className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-50">
                {saving === 'smtp' ? '保存中...' : '保存'}
              </button>
              <button onClick={testSmtp} disabled={saving === 'smtp-test'}
                className="bg-slate-700 text-slate-300 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-600 transition-colors disabled:opacity-50">
                {saving === 'smtp-test' ? '发送中...' : '测试邮件'}
              </button>
            </div>
          </div>
        )}

        {/* 站点配置 */}
        {section === 'site' && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center gap-2 mb-4">
              <Globe size={20} className="text-sky-400" />
              <h3 className="text-lg font-semibold text-white">站点配置</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">站点域名</label>
                <input type="text" value={siteForm.site_url} onChange={e => setSiteForm(f => ({ ...f, site_url: e.target.value }))}
                  placeholder="https://www.intelhub.club" className={inputCls} />
                <p className="text-xs text-slate-500 mt-1">用于生成报告在线访问链接，发送邮件时会附带此域名的报告链接</p>
              </div>
              <button onClick={saveSite} disabled={saving === 'site'}
                className="bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-50">
                {saving === 'site' ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
