import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import TierGuard from '../components/TierGuard'
import { TaskFormModal } from './Tasks'
import { Play, Pause, Trash2, Plus, RefreshCw, Edit3, Eye, Loader2, CheckCircle, AlertCircle, X, Copy, Check } from 'lucide-react'
import clsx from 'clsx'

const TASK_TYPES = [
  { value: 'crawler', label: '数据采集' },
  { value: 'report', label: '报告生成' },
]

const SCOPE_TABS = [
  { key: 'mine', label: '我的任务' },
  { key: 'platform', label: '平台任务' },
]

const TYPE_TABS = [
  { key: 'all', label: '全部', types: null },
  { key: 'crawler', label: '采集', types: ['crawler'] },
  { key: 'report', label: '报告', types: ['report'] },
]

export default function MyTasks() {
  const navigate = useNavigate()
  const [myTasks, setMyTasks] = useState([])
  const [platformTasks, setPlatformTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editingTask, setEditingTask] = useState(null)
  const [previewTask, setPreviewTask] = useState(null)
  const [msg, setMsg] = useState(null)
  const [scopeTab, setScopeTab] = useState('mine')
  const [typeTab, setTypeTab] = useState('all')

  const load = useCallback(async () => {
    try {
      const [mineRes, platRes] = await Promise.all([
        api.get('/api/v1/user-tasks').catch(() => ({ data: { data: [] } })),
        api.get('/api/v1/user-tasks/platform').catch(() => ({ data: { data: [] } })),
      ])
      setMyTasks(mineRes.data?.data || [])
      setPlatformTasks(platRes.data?.data || [])
    } catch { }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const handleRun = async (id) => {
    try {
      await api.post(`/api/v1/user-tasks/${id}/run`)
      showMsg('任务已启动')
      setTimeout(load, 2000)
    } catch (e) { showMsg(e.message, false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此任务？')) return
    try {
      await api.delete(`/api/v1/user-tasks/${id}`)
      showMsg('已删除')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const handleToggle = async (task) => {
    try {
      if (task.enabled) {
        await api.post(`/api/v1/user-tasks/${task.id}/pause`)
      } else {
        await api.post(`/api/v1/user-tasks/${task.id}/resume`)
      }
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const handleCloseModal = () => {
    setShowCreate(false)
    setEditingTask(null)
  }

  const handleSaved = () => {
    handleCloseModal()
    load()
  }

  const userSubmitFn = async (payload, isEdit, task) => {
    if (isEdit) {
      await api.put(`/api/v1/user-tasks/${task.id}`, payload)
    } else {
      await api.post('/api/v1/user-tasks', payload)
    }
  }

  const isPlatform = scopeTab === 'platform'
  const sourceTasks = isPlatform ? platformTasks : myTasks
  const typeConfig = TYPE_TABS.find(t => t.key === typeTab) || TYPE_TABS[0]
  const tasks = typeConfig.types ? sourceTasks.filter(t => typeConfig.types.includes(t.task_type)) : sourceTasks

  const scopeCounts = { mine: myTasks.length, platform: platformTasks.length }
  const typeCounts = {}
  TYPE_TABS.forEach(tab => {
    typeCounts[tab.key] = tab.types ? sourceTasks.filter(t => tab.types.includes(t.task_type)).length : sourceTasks.length
  })

  if (loading) return <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  return (
    <TierGuard minTier="v2">
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">我的任务</h2>
          <p className="text-xs text-slate-500 mt-1">{isPlatform ? '参考平台任务配置，创建自己的任务' : '管理个人采集和报告任务'}</p>
        </div>
        {!isPlatform && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30">
            <Plus size={16} /> 创建任务
          </button>
        )}
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {/* Scope Tab */}
      <div className="flex items-center gap-2">
        {SCOPE_TABS.map(s => (
          <button key={s.key} onClick={() => { setScopeTab(s.key); setTypeTab('all') }}
            className={clsx("px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              scopeTab === s.key
                ? "bg-indigo-600 text-white"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            )}>
            {s.label} ({scopeCounts[s.key]})
          </button>
        ))}
      </div>

      {/* Type Tab */}
      <div className="flex items-center gap-2">
        {TYPE_TABS.map(t => (
          <button key={t.key} onClick={() => setTypeTab(t.key)}
            className={clsx("px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              typeTab === t.key
                ? "bg-sky-600 text-white"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            )}>
            {t.label} ({typeCounts[t.key] || 0})
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {tasks.map(task => (
          <TaskCard key={task.id} task={task}
            readOnly={isPlatform}
            onClick={isPlatform ? () => setPreviewTask(task) : () => navigate(`/my-tasks/${task.id}`)}
            onRun={() => handleRun(task.id)}
            onToggle={() => handleToggle(task)}
            onEdit={() => setEditingTask(task)}
            onDelete={() => handleDelete(task.id)} />
        ))}
        {tasks.length === 0 && (
          <div className="text-center text-slate-500 py-12">
            {isPlatform ? '暂无平台任务' : '暂无任务，点击右上角创建'}
          </div>
        )}
      </div>

      {(showCreate || editingTask) && (
        <TaskFormModal
          task={editingTask}
          defaultType="crawler"
          allowedTypes={['crawler', 'report']}
          submitFn={userSubmitFn}
          userMode
          onClose={handleCloseModal}
          onSaved={handleSaved}
        />
      )}

      {previewTask && (
        <TaskPreviewModal task={previewTask} onClose={() => setPreviewTask(null)} />
      )}
    </div>
    </TierGuard>
  )
}

// ── 平台任务预览（表单格式，只读） ──────────────────────────────
function TaskPreviewModal({ task, onClose }) {
  const [sourceNames, setSourceNames] = useState({})
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api.get('/api/v1/rss-sources').then(r => {
      const srcs = r.data?.data?.sources || []
      const map = {}
      srcs.forEach(s => { map[s.id] = s.name })
      setSourceNames(map)
    }).catch(() => {})
  }, [])

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const script = (() => {
    try { return typeof task.script === 'string' ? JSON.parse(task.script) : task.script || {} }
    catch { return {} }
  })()
  const schedule = (() => {
    try { return typeof task.schedule_config === 'string' ? JSON.parse(task.schedule_config) : task.schedule_config || {} }
    catch { return {} }
  })()
  const typeLabel = TASK_TYPES.find(t => t.value === task.task_type)?.label || task.task_type

  const fieldCls = "w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300"
  const labelCls = "block text-xs text-slate-500 mb-1"

  const scheduleDesc = (() => {
    if (task.schedule_description) return task.schedule_description
    if (schedule.cron) return `Cron: ${schedule.cron}`
    if (schedule.type === 'interval') return `间隔: ${schedule.interval_minutes || schedule.minutes || '?'} 分钟`
    return task.schedule_type || '-'
  })()

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
          <div className="flex items-center gap-2">
            <Eye size={16} className="text-indigo-400" />
            <h3 className="text-white font-semibold">平台任务预览</h3>
            <span className="text-xs bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded">只读</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* 基本信息 */}
          <div>
            <label className={labelCls}>任务名称</label>
            <div className={fieldCls}>{task.name}</div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>模块</label>
              <div className={fieldCls}>{task.module || '-'}</div>
            </div>
            <div>
              <label className={labelCls}>任务类型</label>
              <div className={fieldCls}>{typeLabel}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>执行周期</label>
              <div className={fieldCls}>{scheduleDesc}</div>
            </div>
            <div>
              <label className={labelCls}>状态</label>
              <div className={fieldCls}>{task.enabled ? '已启用' : '已禁用'}</div>
            </div>
          </div>

          {task.description && (
            <div>
              <label className={labelCls}>描述</label>
              <div className={fieldCls}>{task.description}</div>
            </div>
          )}

          {/* 报告配置 */}
          {task.task_type === 'report' && (
            <div className="space-y-3 p-4 bg-slate-900/40 rounded-lg border border-slate-700/50">
              <div className="text-xs text-slate-400 font-medium uppercase tracking-wide">报告配置</div>

              {script.template_id && (
                <div>
                  <label className={labelCls}>报告模板</label>
                  <div className={fieldCls}>{script.template_id}</div>
                </div>
              )}

              {script.sources && script.sources.length > 0 && (
                <div>
                  <label className={labelCls}>数据源</label>
                  <div className="flex flex-wrap gap-1.5">
                    {script.sources.map(s => (
                      <span key={s} className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {script.rss_source_ids && script.rss_source_ids.length > 0 && (
                <div>
                  <label className={labelCls}>RSS 源 ({script.rss_source_ids.length} 个)</label>
                  <div className="flex flex-wrap gap-1.5">
                    {script.rss_source_ids.map(id => (
                      <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-500/10 text-sky-400 text-xs rounded border border-sky-500/30">
                        {sourceNames[id] || `#${id}`}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {script.model && (
                <div>
                  <label className={labelCls}>模型</label>
                  <div className={fieldCls}>{script.model}</div>
                </div>
              )}

              {script.prompt && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className={labelCls + " mb-0"}>Prompt</label>
                    <button onClick={() => handleCopy(script.prompt)}
                      className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300">
                      {copied ? <><Check size={12} /> 已复制</> : <><Copy size={12} /> 复制</>}
                    </button>
                  </div>
                  <pre className="bg-slate-900/60 border border-slate-700/50 rounded-lg px-3 py-2 text-xs text-slate-400 font-mono leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">{script.prompt}</pre>
                </div>
              )}
            </div>
          )}

          {/* 采集配置 */}
          {task.task_type === 'crawler' && script.prompt && (
            <div>
              <label className={labelCls}>配置</label>
              <pre className="bg-slate-900/60 border border-slate-700/50 rounded-lg px-3 py-2 text-xs text-slate-400 font-mono leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                {typeof script === 'object' ? JSON.stringify(script, null, 2) : script}
              </pre>
            </div>
          )}

          {/* 统计 */}
          <div className="grid grid-cols-3 gap-4 pt-2 border-t border-slate-700/50">
            <div className="text-center">
              <div className="text-lg text-white font-medium">{task.run_count || 0}</div>
              <div className="text-xs text-slate-500">总运行</div>
            </div>
            <div className="text-center">
              <div className="text-lg text-green-400 font-medium">{task.success_count || 0}</div>
              <div className="text-xs text-slate-500">成功</div>
            </div>
            <div className="text-center">
              <div className="text-lg text-red-400 font-medium">{task.fail_count || 0}</div>
              <div className="text-xs text-slate-500">失败</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function TaskCard({ task, readOnly, onClick, onRun, onToggle, onEdit, onDelete }) {
  const typeLabel = TASK_TYPES.find(t => t.value === task.task_type)?.label || task.task_type
  const lastRun = task.last_run ? new Date(task.last_run).toLocaleString('zh-CN') : '-'

  return (
    <div onClick={onClick} className={clsx(
      "bg-slate-800 rounded-xl border p-4 cursor-pointer hover:border-slate-600 transition-colors",
      task.enabled ? "border-slate-700" : "border-slate-700/50 opacity-60"
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={clsx("inline-block w-2.5 h-2.5 rounded-full",
            task.enabled ? (task.status === 'running' ? 'bg-sky-400 animate-pulse' : 'bg-green-400') : 'bg-slate-500'
          )} />
          <div>
            <div className="text-sm text-white font-medium">{task.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs bg-slate-700 text-slate-400 px-2 py-0.5 rounded">{typeLabel}</span>
              <span className="text-xs text-slate-500">{task.schedule_description}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right mr-2">
            <div className="text-xs text-slate-400">
              <span className="text-green-400">{task.success_count}</span>
              <span className="mx-0.5">/</span>
              <span className="text-red-400">{task.fail_count}</span>
              <span className="text-slate-600 ml-1">({task.run_count}次)</span>
            </div>
            <div className="text-xs text-slate-600">{lastRun}</div>
          </div>
          {readOnly ? (
            <button onClick={e => { e.stopPropagation(); onClick() }} className="p-2 rounded text-indigo-400 hover:bg-slate-700" title="预览配置">
              <Eye size={15} />
            </button>
          ) : (
            <>
              <button onClick={e => { e.stopPropagation(); onRun() }} disabled={!task.enabled}
                className={clsx("p-2 rounded", task.enabled ? 'text-sky-400 hover:bg-slate-700' : 'text-slate-600 cursor-not-allowed')}
                title="运行">
                <Play size={15} />
              </button>
              <button onClick={e => { e.stopPropagation(); onToggle() }}
                className={clsx("p-2 rounded", task.enabled ? 'text-emerald-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-700')}
                title={task.enabled ? '暂停' : '恢复'}>
                {task.enabled ? <Pause size={15} /> : <RefreshCw size={15} />}
              </button>
              <button onClick={e => { e.stopPropagation(); onEdit() }} className="p-2 rounded text-yellow-400 hover:bg-slate-700" title="编辑">
                <Edit3 size={15} />
              </button>
              <button onClick={e => { e.stopPropagation(); onDelete() }} className="p-2 rounded text-red-400 hover:bg-slate-700" title="删除">
                <Trash2 size={15} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
