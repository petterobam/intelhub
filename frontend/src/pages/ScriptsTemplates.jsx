import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { FileCode, FileText, Eye, Save, RotateCcw, Plus, Trash2, X, Loader2 } from 'lucide-react'
import clsx from 'clsx'


// ── Tab Button ───────────────────────────────────────────────────────────────
function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} className={clsx(
      'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
      active ? 'bg-slate-800 text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-white'
    )}>{children}</button>
  )
}


// ── File list + editor panel ─────────────────────────────────────────────────
function FileEditor({ category, title }) {
  const [files, setFiles] = useState([])
  const [selected, setSelected] = useState(null)
  const [content, setContent] = useState('')
  const [original, setOriginal] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const loadFiles = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/scripts')
      const list = category === 'shell'
        ? res.data?.data?.shell_scripts || []
        : res.data?.data?.agent_prompts || []
      setFiles(list)
      localStorage.setItem(`intelhub_scripts_${category}`, JSON.stringify(list))
    } catch {}
  }, [category])

  useEffect(() => {
    // Read cache first
    try {
      const c = localStorage.getItem(`intelhub_scripts_${category}`)
      if (c) setFiles(JSON.parse(c))
    } catch { /* ignore */ }
    loadFiles()
  }, [loadFiles])

  const selectFile = async (f) => {
    setLoading(true)
    setMsg('')
    try {
      const res = await api.get(`/api/v1/scripts/${f.filename}?category=${category}`)
      const data = res.data?.data
      setSelected(f)
      setContent(data?.content || '')
      setOriginal(data?.content || '')
    } catch {
      setSelected(f)
      setContent('')
      setOriginal('')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!selected) return
    setSaving(true)
    setMsg('')
    try {
      await api.put(`/api/v1/scripts/${selected.filename}`, { content, category })
      setOriginal(content)
      setMsg('保存成功')
      loadFiles()
    } catch (e) {
      setMsg('保存失败: ' + (e.message || ''))
    } finally {
      setSaving(false)
    }
  }

  const handleRevert = () => {
    setContent(original)
    setMsg('已还原')
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + 'B'
    return (bytes / 1024).toFixed(1) + 'K'
  }

  const formatTime = (iso) => {
    if (!iso) return ''
    return iso.replace('T', ' ').substring(0, 16)
  }

  const modified = content !== original

  return (
    <div className="flex gap-4 h-[calc(100vh-220px)]">
      {/* Left: file list */}
      <div className="w-1/3 bg-slate-800 rounded-xl border border-slate-700 overflow-y-auto">
        <div className="px-4 py-3 border-b border-slate-700 text-sm text-slate-400 font-medium">
          {title} ({files.length})
        </div>
        {files.map(f => (
          <div key={f.filename}
            onClick={() => selectFile(f)}
            className={clsx(
              'px-4 py-3 cursor-pointer transition-colors border-b border-slate-700/50',
              selected?.filename === f.filename ? 'bg-sky-500/10 border-l-2 border-l-sky-400' : 'hover:bg-slate-700/50'
            )}>
            <div className="flex items-center gap-2">
              {category === 'shell'
                ? <FileCode size={14} className="text-green-400 shrink-0" />
                : <FileText size={14} className="text-purple-400 shrink-0" />}
              <span className="text-sm text-white font-mono truncate">{f.filename}</span>
            </div>
            <div className="flex gap-3 mt-1 text-xs text-slate-500">
              <span>{formatSize(f.size)}</span>
              <span>{formatTime(f.modified)}</span>
            </div>
          </div>
        ))}
        {files.length === 0 && (
          <div className="px-4 py-8 text-center text-slate-500 text-sm">暂无文件</div>
        )}
      </div>

      {/* Right: editor */}
      <div className="flex-1 bg-slate-800 rounded-xl border border-slate-700 flex flex-col">
        {selected ? (
          <>
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
              <div className="flex items-center gap-2">
                <span className="text-sm text-white font-medium font-mono">{selected.filename}</span>
                {modified && <span className="text-xs text-yellow-400">*(modified)</span>}
              </div>
              <div className="flex items-center gap-2">
                {msg && <span className={clsx('text-xs', msg.includes('失败') ? 'text-red-400' : 'text-green-400')}>{msg}</span>}
                <button onClick={handleRevert} disabled={!modified}
                  className={clsx('px-3 py-1.5 rounded text-xs flex items-center gap-1',
                    modified ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-slate-700/50 text-slate-600 cursor-not-allowed')}>
                  <RotateCcw size={12} /> 还原
                </button>
                <button onClick={handleSave} disabled={saving || !modified}
                  className={clsx('px-3 py-1.5 rounded text-xs flex items-center gap-1',
                    modified && !saving ? 'bg-sky-500 text-white hover:bg-sky-600' : 'bg-slate-700/50 text-slate-600 cursor-not-allowed')}>
                  <Save size={12} /> {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
            <div className="flex-1 p-4 overflow-hidden">
              {loading ? (
                <div className="text-center text-slate-500 py-8"><Loader2 className="animate-spin inline mr-2" size={16} />加载中...</div>
              ) : (
                <textarea
                  value={content}
                  onChange={e => { setContent(e.target.value); setMsg('') }}
                  className="w-full h-full bg-slate-900 text-slate-300 font-mono text-xs leading-relaxed resize-none border border-slate-700 rounded-lg p-4 focus:outline-none focus:border-sky-500"
                  spellCheck={false}
                />
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
            选择左侧文件查看内容
          </div>
        )}
      </div>
    </div>
  )
}


// ── Report Template Form Modal ───────────────────────────────────────────────
function TemplateFormModal({ template, onClose, onSaved }) {
  const isEdit = !!template
  const [form, setForm] = useState({
    name: template?.name || '',
    description: template?.description || '',
    prompt_template: template?.prompt_template || '',
    data_sources: template?.data_sources || ['hot_topics', 'policy', 'exchange', 'financial'],
    trend_reference: template?.trend_reference !== false,
    max_items_per_source: template?.max_items_per_source || 50,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (key, val) => setForm(prev => ({ ...prev, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.prompt_template.trim()) {
      setError('名称和提示词模板为必填')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      if (isEdit) {
        await api.put(`/api/v1/report-templates/${template.id}`, form)
      } else {
        await api.post('/api/v1/report-templates', form)
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
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
          <h3 className="text-white font-semibold">{isEdit ? '编辑模板' : '新建模板'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {error && <div className="bg-red-900/30 text-red-400 text-sm rounded-lg px-3 py-2">{error}</div>}

          <div>
            <label className={labelCls}>模板名称 *</label>
            <input value={form.name} onChange={e => handleChange('name', e.target.value)}
              className={inputCls} placeholder="如：每日投资洞察" />
          </div>

          <div>
            <label className={labelCls}>描述</label>
            <input value={form.description} onChange={e => handleChange('description', e.target.value)}
              className={inputCls} placeholder="模板用途描述" />
          </div>

          <div>
            <label className={labelCls}>提示词模板 *</label>
            <textarea value={form.prompt_template}
              onChange={e => handleChange('prompt_template', e.target.value)}
              rows={10}
              className={inputCls + " font-mono text-xs leading-relaxed"}
              placeholder={"你是一个专业的投资分析助手。\n\n## 数据\n{hot_topics}\n\n请生成..."}
            />
          </div>

          <div>
            <label className={labelCls}>数据源</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {[
                { key: 'hot_topics', label: '热点平台' },
                { key: 'policy', label: '政策' },
                { key: 'exchange', label: '交易所公告' },
                { key: 'financial', label: '财经数据' },
              ].map(src => (
                <label key={src.key} className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800 px-2.5 py-1 rounded-md border border-slate-600 cursor-pointer hover:border-sky-500">
                  <input type="checkbox"
                    checked={form.data_sources?.includes(src.key) ?? true}
                    onChange={e => {
                      const srcs = form.data_sources || []
                      const next = e.target.checked
                        ? [...new Set([...srcs, src.key])]
                        : srcs.filter(s => s !== src.key)
                      handleChange('data_sources', next)
                    }}
                    className="accent-sky-500"
                  />
                  {src.label}
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>每源最大条数</label>
              <input type="number" value={form.max_items_per_source} min={1} max={500}
                onChange={e => handleChange('max_items_per_source', parseInt(e.target.value) || 50)}
                className={inputCls} />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox"
                  checked={form.trend_reference}
                  onChange={e => handleChange('trend_reference', e.target.checked)}
                  className="accent-sky-500"
                />
                趋势参考（对比历史报告）
              </label>
            </div>
          </div>

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


// ── Report Templates Tab ─────────────────────────────────────────────────────
function ReportTemplatesTab() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [editTemplate, setEditTemplate] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/report-templates')
      const d = res.data?.data || []
      setTemplates(d)
      localStorage.setItem('intelhub_report_templates', JSON.stringify(d))
    } catch {} finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Read cache first
    try {
      const c = localStorage.getItem('intelhub_report_templates')
      if (c) { setTemplates(JSON.parse(c)); setLoading(false) }
    } catch { /* ignore */ }
    load()
  }, [load])

  const handleDelete = async (id) => {
    if (!confirm('确定删除此模板?')) return
    try { await api.delete(`/api/v1/report-templates/${id}`); load() } catch {}
  }

  const sourceLabels = { hot_topics: '热点', policy: '政策', exchange: '交易所', financial: '财经' }

  if (loading) return <div className="text-center text-slate-500 py-12"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 flex items-center gap-2">
          <Plus size={14} /> 新建模板
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map(t => (
          <div key={t.id} className="bg-slate-800 rounded-xl border border-slate-700 p-4 flex flex-col">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h4 className="text-white font-medium text-sm">{t.name}</h4>
                <p className="text-xs text-slate-500 mt-0.5">{t.description || '无描述'}</p>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setEditTemplate(t)} className="p-1 rounded hover:bg-slate-700 text-yellow-400" title="编辑">
                  <FileText size={14} />
                </button>
                <button onClick={() => handleDelete(t.id)} className="p-1 rounded hover:bg-slate-700 text-red-400" title="删除">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1 mb-3">
              {(t.data_sources || []).map(s => (
                <span key={s} className="px-2 py-0.5 bg-slate-700 text-slate-300 rounded text-xs">
                  {sourceLabels[s] || s}
                </span>
              ))}
            </div>
            <pre className="flex-1 bg-slate-900 rounded-lg p-3 text-xs text-slate-400 font-mono overflow-hidden max-h-32 whitespace-pre-wrap">
              {t.prompt_template?.substring(0, 200)}{t.prompt_template?.length > 200 ? '...' : ''}
            </pre>
            <div className="mt-3 text-xs text-slate-600">
              更新: {t.updated_at?.replace('T', ' ').substring(0, 16) || '-'}
            </div>
          </div>
        ))}
      </div>
      {templates.length === 0 && (
        <div className="text-center text-slate-500 py-12">暂无报告模板，点击右上角新建</div>
      )}

      {showCreate && <TemplateFormModal onClose={() => setShowCreate(false)} onSaved={load} />}
      {editTemplate && <TemplateFormModal template={editTemplate} onClose={() => setEditTemplate(null)} onSaved={load} />}
    </div>
  )
}


// ── Script Preview Modal (shared) ────────────────────────────────────────────
export function ScriptPreviewModal({ filename, category, onClose }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!filename) return
    setLoading(true)
    api.get(`/api/v1/scripts/${filename}?category=${category || 'shell'}`).then(r => {
      setContent(r.data?.data?.content || '')
    }).catch(() => setContent('加载失败')).finally(() => setLoading(false))
  }, [filename, category])

  if (!filename) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-4xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <h3 className="text-white font-medium text-sm font-mono">{filename}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">&times;</button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="text-center text-slate-500 py-8"><Loader2 className="animate-spin inline mr-2" size={16} />加载中...</div>
          ) : (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">{content}</pre>
          )}
        </div>
      </div>
    </div>
  )
}


// ── Main Page ────────────────────────────────────────────────────────────────
export default function ScriptsTemplates() {
  const [tab, setTab] = useState('shell')

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">脚本与模板</h2>
        <p className="text-xs text-slate-500 mt-1">管理 Shell 脚本、Agent 提示词、报告模板</p>
      </div>

      <div className="flex border-b border-slate-700 gap-1">
        <TabBtn active={tab === 'shell'} onClick={() => setTab('shell')}>Shell 脚本</TabBtn>
        <TabBtn active={tab === 'prompt'} onClick={() => setTab('prompt')}>Agent 提示词</TabBtn>
        <TabBtn active={tab === 'templates'} onClick={() => setTab('templates')}>报告模板</TabBtn>
      </div>

      <div>
        {tab === 'shell' && <FileEditor category="shell" title="Shell 脚本" />}
        {tab === 'prompt' && <FileEditor category="prompt" title="Agent 提示词" />}
        {tab === 'templates' && <ReportTemplatesTab />}
      </div>
    </div>
  )
}
