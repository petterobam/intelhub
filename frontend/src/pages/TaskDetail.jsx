import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import {
  ArrowLeft, Play, Pause, RefreshCw, Trash2, Clock, CheckCircle2, XCircle,
  AlertTriangle, FileText, ChevronRight, ChevronDown, Loader2, Edit3, Send, Users
} from 'lucide-react'
import { ScriptPreviewModal } from './ScriptsTemplates'
import { TaskFormModal } from './Tasks'
import clsx from 'clsx'


function Badge({ status }) {
  const map = {
    done: { color: 'bg-green-500/20 text-green-400', icon: CheckCircle2, label: '成功' },
    failed: { color: 'bg-red-500/20 text-red-400', icon: XCircle, label: '失败' },
    running: { color: 'bg-sky-500/20 text-sky-400', icon: Loader2, label: '运行中' },
    timeout: { color: 'bg-yellow-500/20 text-yellow-400', icon: AlertTriangle, label: '超时' },
  }
  const cfg = map[status] || map.failed
  const Icon = cfg.icon
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', cfg.color)}>
      <Icon size={12} className={status === 'running' ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  )
}


function formatDuration(ms) {
  if (!ms) return '-'
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'K'
  return (bytes / 1024 / 1024).toFixed(1) + 'M'
}

function formatTime(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').substring(0, 19)
}


// 数据预览弹窗
function PreviewModal({ path, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!path) return
    setLoading(true)
    api.get(`/api/v1/data/preview?path=${encodeURIComponent(path)}`).then(r => {
      setData(r.data?.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [path])

  if (!path) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-4xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <div>
            <h3 className="text-white font-medium text-sm">{data?.filename || '预览'}</h3>
            <p className="text-slate-500 text-xs">{path} | {data ? formatSize(data.size) : ''}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">&times;</button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="text-center text-slate-500 py-8"><Loader2 className="animate-spin inline" size={20} /> 加载中...</div>
          ) : data?.is_json ? (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
              {JSON.stringify(data.parsed, null, 2)}
            </pre>
          ) : (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">{data?.content || '(empty)'}</pre>
          )}
        </div>
      </div>
    </div>
  )
}


// Tab 按钮
function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} className={clsx(
      'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
      active ? 'bg-slate-800 text-sky-400 border-b-2 border-sky-400' : 'text-slate-400 hover:text-white'
    )}>{children}</button>
  )
}


const SOURCE_LABELS = {
  hot_topics: '热点平台', policy: '政策', exchange: '交易所',
  financial: '财经数据', rss: 'RSS',
}

function ScriptDisplay({ script, taskType, onPreview }) {
  if (!script) return <span className="text-slate-600 ml-2 text-xs">无配置</span>

  // Shell script path
  if (script.includes('/') && script.endsWith('.sh')) {
    return <span className="text-sky-400 ml-2 font-mono text-xs cursor-pointer hover:underline" onClick={onPreview}>{script}</span>
  }

  // JSON config
  try {
    const cfg = JSON.parse(script)
    const items = []

    if (cfg.sources?.length) {
      items.push({ label: '数据源', value: cfg.sources.map(s => SOURCE_LABELS[s] || s).join('、') })
    }
    if (cfg.source_ids?.length) {
      items.push({ label: 'RSS 源', value: `${cfg.source_ids.length} 个` })
    }
    if (cfg.rss_source_ids?.length) {
      items.push({ label: 'RSS 细化', value: `${cfg.rss_source_ids.length} 个源` })
    }
    if (cfg.user_source_ids?.length) {
      items.push({ label: '个人数据源', value: `${cfg.user_source_ids.length} 个` })
    }
    if (cfg.push_channel_ids?.length) {
      items.push({ label: '推送渠道', value: `${cfg.push_channel_ids.length} 个` })
    }
    if (cfg.use_preferences) {
      items.push({ label: '使用偏好', value: '是' })
    }
    if (cfg.trend_reference !== undefined) {
      items.push({ label: '趋势参考', value: cfg.trend_reference ? '是' : '否' })
    }
    if (cfg.use_harness !== undefined) {
      items.push({ label: 'AI Harness', value: cfg.use_harness ? '是' : '否' })
    }
    if (cfg.model) {
      items.push({ label: '模型', value: cfg.model })
    }
    if (cfg.template_id) {
      items.push({ label: '模板', value: cfg.template_id })
    }
    if (cfg.type) {
      items.push({ label: '类型', value: cfg.type === 'rss' ? 'RSS 采集' : cfg.type === 'user_rss' ? '个人 RSS' : cfg.type })
    }

    if (items.length === 0) {
      return <span className="text-slate-400 ml-2 font-mono text-xs">{script}</span>
    }

    return (
      <div className="mt-1 ml-2 flex flex-wrap gap-x-4 gap-y-1">
        {items.map((it, i) => (
          <span key={i} className="text-xs">
            <span className="text-slate-500">{it.label}:</span>{' '}
            <span className="text-slate-200">{it.value}</span>
          </span>
        ))}
      </div>
    )
  } catch {
    return <span className="text-slate-400 ml-2 font-mono text-xs">{script}</span>
  }
}


function PushChannelsTab({ task, userMode, pushChannels, subscriptions }) {
  const [userInfo, setUserInfo] = useState(null)

  // Parse push_channel_ids from script config
  let channelIds = []
  try {
    if (task.script?.startsWith('{')) {
      channelIds = JSON.parse(task.script).push_channel_ids || []
    }
  } catch {}

  // Load user info for user tasks
  useEffect(() => {
    const uid = task.user_id
    if (!uid) return
    api.get('/api/v1/push-channels/all-users').then(r => {
      const users = (r.data?.data || {}).users || []
      const u = users.find(u => u.id === uid)
      if (u) setUserInfo(u)
    }).catch(() => {})
  }, [task.user_id])

  // User task (has user_id): show user + their channels like subscription format
  const isUserTask = userMode || task.user_id || task.is_auto

  if (isUserTask) {
    if (channelIds.length === 0) {
      return <p className="text-slate-500 text-center py-8">未配置推送渠道，请在偏好设置或编辑任务时选择推送渠道</p>
    }
    const channelMap = {}
    pushChannels.forEach(c => { channelMap[c.id] = c })

    // Build channel labels like subscription format
    const channelLabels = channelIds.map(cid => {
      if (cid === '_email') return { name: '邮件推送', type: 'email' }
      const ch = channelMap[cid]
      if (!ch) return null
      return { name: ch.name, type: ch.channel_label || ch.channel_type }
    }).filter(Boolean)

    const displayName = userInfo?.display_name || userInfo?.email || task.user_email || `用户 ${task.user_id}`

    return (
      <div className="space-y-2">
        <p className="text-xs text-slate-500 mb-2">推送对象</p>
        <div className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700">
          <div className="flex items-center gap-2 mb-1.5">
            <Users size={13} className="text-slate-400" />
            <span className="text-sm text-white">{displayName}</span>
            {userInfo?.email && displayName !== userInfo.email && (
              <span className="text-xs text-slate-500">{userInfo.email}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 ml-5">
            {channelLabels.map((ch, i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300">
                {ch.name}
                {ch.type !== ch.name && <span className="text-slate-500 ml-1">{ch.type}</span>}
              </span>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Platform task: show subscription channels
  if (subscriptions.length === 0) {
    return <p className="text-slate-500 text-center py-8">暂无订阅者，请在订阅中心添加订阅</p>
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500 mb-2">共 {subscriptions.length} 个订阅者</p>
      {subscriptions.map(sub => (
        <div key={sub.id} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700">
          <div className="flex items-center gap-2 mb-1.5">
            <Users size={13} className="text-slate-400" />
            <span className="text-sm text-white">{sub.name || sub.email}</span>
            <span className="text-xs text-slate-500">{sub.email}</span>
            {sub.enabled ? (
              <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">已启用</span>
            ) : (
              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-500">已禁用</span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 ml-5">
            {(sub.channel_labels || []).map((ch, i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300">
                {ch.name}
              </span>
            ))}
            {(!sub.channel_labels || sub.channel_labels.length === 0) && (
              <span className="text-xs text-slate-600">邮件推送</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}


export default function TaskDetail({ userMode }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState(null)
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('overview')
  const [previewPath, setPreviewPath] = useState(null)
  const [scriptPreview, setScriptPreview] = useState(null)
  const [expandedRun, setExpandedRun] = useState(null)
  const [runModel, setRunModel] = useState('')
  const [availableModels, setAvailableModels] = useState([])
  const [isRunning, setIsRunning] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [userOutputs, setUserOutputs] = useState([])
  const [pushChannels, setPushChannels] = useState([])
  const [subscriptions, setSubscriptions] = useState([])
  const pollRef = useRef(null)
  const apiBase = userMode ? '/api/v1/user-tasks' : '/api/v1/tasks'

  const load = useCallback(async () => {
    try {
      const [taskRes, runsRes] = await Promise.all([
        api.get(`${apiBase}/${id}`),
        api.get(`${apiBase}/${id}/runs`),
      ])
      const taskData = taskRes.data?.data
      setTask(taskData)
      const runsData = runsRes.data?.data
      setRuns(Array.isArray(runsData) ? runsData : (runsData?.items || []))

      // Load push channels (for report/crawler tasks)
      if (taskData?.task_type === 'report' || taskData?.task_type === 'crawler') {
        // For user tasks, load that user's channels (admin can query by user_id)
        const chUrl = taskData.user_id
          ? `/api/v1/push-channels?user_id=${taskData.user_id}`
          : '/api/v1/push-channels'
        api.get(chUrl).then(r => {
          setPushChannels((r.data?.data || {}).channels || [])
        }).catch(() => {})
      }
      // Load subscriptions for platform tasks (no user_id)
      if (!taskData?.user_id && taskData?.task_type === 'report') {
        api.get('/api/v1/subscriptions').then(r => {
          const allSubs = r.data?.data || []
          setSubscriptions(allSubs.filter(s => s.task_id === id))
        }).catch(() => {})
      }

      // Check async job status
      try {
        const statusRes = await api.get(`${apiBase}/${id}/status`)
        const st = statusRes.data?.data?.status
        setIsRunning(st === 'running')
      } catch {
        setIsRunning(false)
      }

      // Load user outputs if user mode
      if (userMode) {
        try {
          const outRes = await api.get(`${apiBase}/${id}/outputs`)
          setUserOutputs(outRes.data?.data || [])
        } catch { /* ignore */ }
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [id, apiBase, userMode])

  useEffect(() => { load() }, [load])

  // Poll while running
  useEffect(() => {
    if (!isRunning) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get(`${apiBase}/${id}/status`)
        const st = res.data?.data?.status
        if (st === 'done' || st === 'failed' || st === 'timeout' || st === 'error') {
          setIsRunning(false)
          load()
        }
      } catch {
        setIsRunning(false)
        load()
      }
    }, 2000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [isRunning, id, load])

  // Fetch models for analysis/report tasks
  useEffect(() => {
    if (task && (task.task_type === 'analysis' || task.task_type === 'report')) {
      api.get('/api/v1/chat/models').then(r => {
        setAvailableModels(r.data?.data || [])
      }).catch(() => {})
      // Pre-fill model from task config
      try {
        const cfg = typeof task.schedule_config === 'string' ? JSON.parse(task.schedule_config) : task.schedule_config
        if (cfg?.model) setRunModel(cfg.model)
      } catch {}
      try {
        if (task.script && task.script.startsWith('{')) {
          const cfg = JSON.parse(task.script)
          if (cfg.model) setRunModel(cfg.model)
        }
      } catch {}
    }
  }, [task])

  const handleRun = async () => {
    setIsRunning(true)
    try {
      await api.post(`${apiBase}/${id}/run`)
    } catch {
      setIsRunning(false)
    }
  }

  const handleToggle = async () => {
    await api.put(`${apiBase}/${id}`, { enabled: !task.enabled })
    load()
  }

  const handleDelete = async () => {
    if (confirm('确定删除此任务?')) {
      await api.delete(`${apiBase}/${id}`)
      navigate(userMode ? '/my-tasks' : '/tasks')
    }
  }

  if (loading) return <div className="text-center text-slate-500 py-12"><Loader2 className="animate-spin inline mr-2" />加载中...</div>
  if (!task) return <div className="text-center text-red-400 py-12">任务不存在</div>

  const lastRun = task.last_run_detail
  const artifacts = userMode ? [] : (lastRun?.artifacts || [])

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(userMode ? '/my-tasks' : '/tasks')} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-white">{task.name}</h2>
            <span className={clsx("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
              task.enabled
                ? (isRunning ? 'bg-sky-500/20 text-sky-400' : 'bg-green-500/20 text-green-400')
                : 'bg-slate-500/20 text-slate-500'
            )}>
              {isRunning && <span className="inline-block w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />}
              {isRunning ? '运行中' : task.enabled ? '已启用' : '已暂停'}
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            {task.module} · {task.task_type} · {task.schedule_description || task.schedule_type}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {/* Model selector for analysis/report tasks */}
          {(task.task_type === 'analysis' || task.task_type === 'report') && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-500">模型:</span>
              {availableModels.length > 0 ? (
                <select value={runModel} onChange={e => setRunModel(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-sky-500">
                  <option value="">默认</option>
                  {availableModels.map(m => (
                    <option key={m.id} value={m.id}>{m.display_name || m.id}</option>
                  ))}
                </select>
              ) : (
                <input value={runModel} onChange={e => setRunModel(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 w-32 focus:outline-none focus:border-sky-500"
                  placeholder="默认模型" />
              )}
            </div>
          )}
          {/* Run button - disabled when running */}
          <button onClick={handleRun} disabled={isRunning || !task.enabled}
            className={clsx("px-4 py-2 rounded-lg text-sm flex items-center gap-2",
              isRunning
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : !task.enabled
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-sky-500 text-white hover:bg-sky-600'
            )}>
            {isRunning
              ? <><span className="inline-block w-3 h-3 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" /> 执行中</>
              : <><Play size={14} /> 执行</>
            }
          </button>
          {/* Toggle enable/disable */}
          <button onClick={handleToggle} title={task.enabled ? '暂停任务' : '启用任务'}
            className={clsx("p-2 rounded-lg transition-colors", task.enabled ? 'text-emerald-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-800')}>
            {task.enabled ? <Pause size={16} /> : <RefreshCw size={16} />}
          </button>
          {/* Edit */}
          <button onClick={() => setShowEdit(true)} title="编辑任务"
            className="p-2 rounded-lg text-yellow-400 hover:bg-slate-800 transition-colors">
            <Edit3 size={16} />
          </button>
          {/* Delete */}
          <button onClick={handleDelete} title="删除任务"
            className="p-2 rounded-lg text-red-400 hover:bg-slate-800 transition-colors">
            <Trash2 size={16} />
          </button>
          {/* Refresh */}
          <button onClick={load} className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总执行', value: task.run_count, color: 'text-white' },
          { label: '成功', value: task.success_count, color: 'text-green-400' },
          { label: '失败', value: task.fail_count, color: 'text-red-400' },
          { label: '最近执行', value: task.last_run ? formatTime(task.last_run).split(' ')[1] : '-', color: 'text-sky-400' },
        ].map((c, i) => (
          <div key={i} className="bg-slate-800 rounded-xl border border-slate-700 p-4">
            <p className="text-xs text-slate-500 mb-1">{c.label}</p>
            <p className={clsx('text-2xl font-bold', c.color)}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 gap-1">
        <TabBtn active={tab === 'overview'} onClick={() => setTab('overview')}>概览</TabBtn>
        {!userMode && <TabBtn active={tab === 'artifacts'} onClick={() => setTab('artifacts')}>产物 ({artifacts.length})</TabBtn>}
        {userMode && <TabBtn active={tab === 'outputs'} onClick={() => setTab('outputs')}>我的产出 ({userOutputs.length})</TabBtn>}
        {(task.task_type === 'report' || task.task_type === 'crawler') && (
          <TabBtn active={tab === 'channels'} onClick={() => setTab('channels')}>
            <span className="flex items-center gap-1"><Send size={12} /> 推送渠道</span>
          </TabBtn>
        )}
        <TabBtn active={tab === 'history'} onClick={() => setTab('history')}>执行记录 ({runs.length})</TabBtn>
      </div>

      {/* Tab 内容 */}
      <div className="bg-slate-800 rounded-b-xl border border-t-0 border-slate-700 p-4">
        {/* 概览 */}
        {tab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-slate-500">任务 ID:</span> <span className="text-white ml-2">{task.id}</span></div>
              <div><span className="text-slate-500">模块:</span> <span className="text-white ml-2">{task.module}</span></div>
              <div className="col-span-2">
                <span className="text-slate-500">配置:</span>
                <ScriptDisplay script={task.script} taskType={task.task_type} onPreview={() => setScriptPreview(task.script?.split('/').pop())} />
              </div>
              <div className="col-span-2"><span className="text-slate-500">描述:</span> <span className="text-white ml-2">{task.description || '-'}</span></div>
            </div>
            {lastRun && (
              <div className="mt-4 pt-4 border-t border-slate-700">
                <h4 className="text-sm font-medium text-slate-300 mb-2">最近执行</h4>
                <div className="flex items-center gap-3 text-sm">
                  <Badge status={lastRun.status} />
                  <span className="text-slate-400">{formatTime(lastRun.started_at)}</span>
                  <span className="text-slate-400">耗时 {formatDuration(lastRun.duration_ms)}</span>
                  {!userMode && lastRun.artifacts?.length > 0 && (
                    <span className="text-sky-400">{lastRun.artifacts.length} 个产物</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 产物清单 */}
        {tab === 'artifacts' && (
          <div>
            {artifacts.length > 0 ? (
              <div className="space-y-1">
                {artifacts.map((a, i) => (
                  <div key={i} onClick={() => setPreviewPath(a.path)}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700 cursor-pointer transition-colors">
                    <FileText size={14} className="text-sky-400 shrink-0" />
                    <span className="text-sm text-white flex-1">{a.name}</span>
                    <span className="text-xs text-slate-500">{formatSize(a.size)}</span>
                    <ChevronRight size={14} className="text-slate-600" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">暂无产物（执行任务后自动记录）</p>
            )}
          </div>
        )}

        {/* 我的产出 (user mode) */}
        {tab === 'outputs' && userMode && (
          <div>
            {userOutputs.length > 0 ? (
              <div className="space-y-1">
                {userOutputs.map((f, i) => (
                  <div key={i} onClick={() => setPreviewPath(f.path)}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700 cursor-pointer transition-colors">
                    <FileText size={14} className="text-sky-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-white">{f.name}</span>
                      <span className="text-xs text-slate-500 ml-2">{f.path}</span>
                    </div>
                    <span className="text-xs text-slate-500">{formatSize(f.size)}</span>
                    <ChevronRight size={14} className="text-slate-600" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">暂无产出文件（执行采集任务后自动生成）</p>
            )}
          </div>
        )}

        {/* 历史记录 */}
        {tab === 'channels' && <PushChannelsTab task={task} userMode={userMode} pushChannels={pushChannels} subscriptions={subscriptions} />}
        {tab === 'history' && (
          <div>
            {runs.length > 0 ? (
              <div className="space-y-1">
                {runs.map((r) => (
                  <div key={r.id}>
                    <div onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-700 cursor-pointer transition-colors">
                      {expandedRun === r.id ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
                      <Badge status={r.status} />
                      <span className="text-sm text-slate-300 flex-1">{formatTime(r.started_at)}</span>
                      <span className="text-xs text-slate-500">{formatDuration(r.duration_ms)}</span>
                      <span className="text-xs text-slate-500">{r.trigger_type === 'manual' ? '手动' : '定时'}</span>
                    </div>
                    {expandedRun === r.id && (
                      <div className="ml-8 mt-1 mb-2 space-y-2">
                        {r.stdout && (
                          <pre className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 font-mono overflow-auto max-h-80 whitespace-pre-wrap">
                            {r.stdout}
                          </pre>
                        )}
                        {r.stderr && (
                          <div>
                            <p className="text-xs text-red-400 mb-1">stderr:</p>
                            <pre className="bg-red-950/30 rounded-lg p-3 text-xs text-red-300 font-mono overflow-auto max-h-40 whitespace-pre-wrap">
                              {r.stderr}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-center py-8">暂无执行记录</p>
            )}
          </div>
        )}
      </div>

      {/* 预览弹窗 */}
      <PreviewModal path={previewPath} onClose={() => setPreviewPath(null)} />
      <ScriptPreviewModal filename={scriptPreview} category="shell" onClose={() => setScriptPreview(null)} />

      {/* 编辑弹窗 */}
      {showEdit && task && (
        <TaskFormModal task={task} onClose={() => setShowEdit(false)} onSaved={load}
          userMode={userMode}
          allowedTypes={userMode ? ['crawler', 'report'] : undefined}
          submitFn={userMode ? async (payload, isEdit, t) => {
            if (isEdit) {
              await api.put(`/api/v1/user-tasks/${t.id}`, payload)
            } else {
              await api.post('/api/v1/user-tasks', payload)
            }
          } : undefined}
        />
      )}
    </div>
  )
}
