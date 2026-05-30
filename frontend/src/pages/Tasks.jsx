import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Play, Pause, Trash2, Plus, RefreshCw, X, Edit3, ChevronDown, Eye, Loader2, Rss } from 'lucide-react'
import { ScriptPreviewModal } from './ScriptsTemplates'
import DataSourcePicker from '../components/DataSourcePicker'
import clsx from 'clsx'

const TASK_TYPE_OPTIONS = [
  { value: 'crawler', label: '爬虫' },
  { value: 'analysis', label: '分析' },
  { value: 'report', label: '报告' },
  { value: 'knowledge', label: '知识库' },
  { value: 'script', label: '脚本' },
]

const TASK_TABS = [
  { key: 'crawler', label: '采集', types: ['crawler'] },
  { key: 'analysis', label: '分析', types: ['analysis'] },
  { key: 'report', label: '报告', types: ['report'] },
  { key: 'system', label: '系统', types: ['knowledge', 'script'] },
]

function TaskRow({ task, isRunning, showUser, onRun, onPause, onResume, onDelete, onEdit, onClick, onToggle }) {
  const nextRun = task.next_run_time
    ? new Date(task.next_run_time).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
    : (task.worker_paused ? '已暂停' : '-')

  return (
    <tr
      onClick={() => onClick(task.id)}
      className={"border-b border-slate-700/50 hover:bg-slate-700/40 transition-colors cursor-pointer" + (isRunning ? ' bg-sky-900/20' : '') + (!task.enabled ? ' opacity-60' : '')}
    >
      <td className="py-3 px-3">
        <div className="flex items-center gap-2">
          <span className={clsx("inline-block w-2 h-2 rounded-full",
            task.enabled ? (isRunning ? 'bg-sky-400 animate-pulse' : 'bg-green-400') : 'bg-slate-500')} />
          <div>
            <div className="text-sm text-white font-medium">{task.name}</div>
            <div className="text-xs text-slate-500">
              {task.module} · {task.task_type}
              {showUser && task.user_display_name && <span className="text-violet-400 ml-1">· {task.user_display_name} ({task.user_email})</span>}
            </div>
          </div>
          {isRunning && <span className="ml-1 text-xs text-sky-400 animate-pulse">执行中</span>}
        </div>
      </td>
      <td className="py-3 px-3 text-xs text-slate-400">
        <div className="font-medium text-slate-300">{task.schedule_description || '-'}</div>
        <div className="text-slate-500 mt-0.5">{task.enabled ? `下次: ${nextRun}` : '已禁用'}</div>
      </td>
      <td className="py-3 px-3 text-xs text-slate-400">
        <div>
          <span className="text-green-400">{task.success_count}</span>
          <span className="mx-0.5">/</span>
          <span className="text-red-400">{task.fail_count}</span>
        </div>
        <div className="text-slate-500">{task.run_count}次</div>
      </td>
      <td className="py-3 px-3">
        <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
          <button onClick={() => onRun(task.id)} disabled={isRunning || !task.enabled}
            className={clsx("p-1.5 rounded text-sky-400", isRunning || !task.enabled ? 'opacity-30 cursor-not-allowed' : 'hover:bg-slate-700')}
            title="立即运行">
            {isRunning
              ? <span className="inline-block w-3 h-3 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
              : <Play size={14} />}
          </button>
          <button onClick={() => onToggle(task.id, !task.enabled)}
            className={clsx("p-1.5 rounded", task.enabled ? 'hover:bg-slate-700 text-emerald-400' : 'hover:bg-slate-700 text-slate-500')}
            title={task.enabled ? '禁用任务' : '启用任务'}>
            {task.enabled ? <Pause size={14} /> : <RefreshCw size={14} />}
          </button>
          <button onClick={() => onEdit(task)} className="p-1.5 rounded hover:bg-slate-700 text-yellow-400" title="编辑">
            <Edit3 size={14} />
          </button>
          <button onClick={() => onDelete(task.id)} className="p-1.5 rounded hover:bg-slate-700 text-red-400" title="删除">
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  )
}


// ── Cron 解析工具 ──────────────────────────────────────────────
function parseCronConfig(cfg) {
  /** 从 schedule_config 中解析出编辑器需要的字段。
   *  支持两种格式：
   *    1) 结构化: { type:'cron', hour:9, minute:0, day_of_week:'1-5' }
   *    2) 原始cron: { type:'cron', cron:'0 9,21 * * *' }
   *  返回 { hour, minute, day_of_week } 或 null
   */
  if (!cfg || typeof cfg !== 'object') return null
  if (cfg.hour !== undefined || cfg.minute !== undefined) {
    return { hour: cfg.hour, minute: cfg.minute ?? 0, day_of_week: cfg.day_of_week ?? '*' }
  }
  if (cfg.cron && typeof cfg.cron === 'string') {
    const parts = cfg.cron.trim().split(/\s+/)
    if (parts.length === 5) {
      return {
        minute: parts[0] === '*' ? '0' : parts[0],
        hour: parts[1] === '*' ? '*' : parts[1],
        day_of_week: parts[4] || '*',
      }
    }
  }
  return null
}

// ── Schedule Editor (替代原始 JSON 编辑) ──────────────────────────
function ScheduleEditor({ value, onChange, isAdmin }) {
  // value: { type: 'interval'|'cron', minutes?: number, hour?: number, minute?: number, day_of_week?: string }
  // 优先从 cron 字符串反解
  const parsed = parseCronConfig(value)
  const initHour = parsed ? parsed.hour : (value?.hour ?? 9)
  const initMinute = parsed ? parsed.minute : (value?.minute ?? 0)
  const initDow = parsed ? parsed.day_of_week : (value?.day_of_week ?? '*')

  const defaultMode = isAdmin
    ? (value?.type || 'daily')
    : (value?.type === 'interval' ? 'daily' : (value?.type || 'daily'))

  const [mode, setMode] = useState(defaultMode)
  const [minutes, setMinutes] = useState(value?.minutes || value?.interval_minutes || 60)
  const [hour, setHour] = useState(typeof initHour === 'number' ? initHour : 9)
  const [minute, setMinute] = useState(typeof initMinute === 'number' ? initMinute : 0)
  const [dayOfWeek, setDayOfWeek] = useState(typeof initDow === 'number' ? String(initDow) : initDow)
  const [cronHour, setCronHour] = useState(
    Array.isArray(initHour) ? initHour.join(',') : String(initHour)
  )
  const [cronMinute, setCronMinute] = useState(String(initMinute))
  const [cronDayOfWeek, setCronDayOfWeek] = useState(String(initDow))

  const apply = (newMode) => {
    let cfg = {}
    if (newMode === 'interval') {
      cfg = { type: 'interval', minutes: Math.max(60, minutes) }
    } else if (newMode === 'daily') {
      cfg = { type: 'cron', hour, minute, day_of_week: '*' }
    } else if (newMode === 'workday') {
      cfg = { type: 'cron', hour, minute, day_of_week: '1-5' }
    } else if (newMode === 'cron') {
      const hrs = cronHour.split(',').map(h => h.trim()).filter(Boolean)
      cfg = { type: 'cron', hour: hrs.length === 1 ? parseInt(hrs[0]) || 0 : hrs.map(h => parseInt(h) || 0), minute: parseInt(cronMinute) || 0, day_of_week: cronDayOfWeek }
    }
    onChange(cfg)
    setMode(newMode)
  }

  useEffect(() => { apply(mode) }, [minutes, hour, minute, dayOfWeek, cronHour, cronMinute, cronDayOfWeek])

  const adminPresets = [
    { label: '每1小时', mode: 'interval', minutes: 60 },
    { label: '每2小时', mode: 'interval', minutes: 120 },
    { label: '每4小时', mode: 'interval', minutes: 240 },
    { label: '每6小时', mode: 'interval', minutes: 360 },
    { label: '每12小时', mode: 'interval', minutes: 720 },
  ]

  const commonPresets = [
    { label: '工作日9点', mode: 'workday', hour: 9, minute: 0 },
    { label: '工作日14点', mode: 'workday', hour: 14, minute: 0 },
    { label: '每天9点', mode: 'daily', hour: 9, minute: 0 },
    { label: '每天21点', mode: 'daily', hour: 21, minute: 0 },
  ]

  const inputCls = "bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-sky-500 w-full"
  const labelCls = "block text-xs text-slate-400 mb-1"

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {isAdmin && adminPresets.map(p => (
          <button key={p.label} type="button"
            onClick={() => { setMode(p.mode); setMinutes(p.minutes); apply(p.mode) }}
            className={clsx("px-2 py-1 rounded text-xs border transition-colors",
              mode === p.mode ? 'bg-sky-500 border-sky-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-slate-500')}>
            {p.label}
          </button>
        ))}
        {commonPresets.map(p => (
          <button key={p.label} type="button"
            onClick={() => { setMode(p.mode); setHour(p.hour || 9); setMinute(p.minute || 0); apply(p.mode) }}
            className={clsx("px-2 py-1 rounded text-xs border transition-colors",
              mode === p.mode ? 'bg-sky-500 border-sky-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-slate-500')}>
            {p.label}
          </button>
        ))}
        <button type="button"
          onClick={() => apply('cron')}
          className={clsx("px-2 py-1 rounded text-xs border", mode === 'cron' ? 'bg-sky-500 border-sky-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300')}>
          自定义Cron
        </button>
      </div>

      {isAdmin && mode === 'interval' && (
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className={labelCls}>间隔（分钟，最小60）</label>
            <input type="number" value={minutes} min={60} max={1440}
              onChange={e => setMinutes(Math.max(60, parseInt(e.target.value) || 60))}
              className={inputCls} />
          </div>
          <div className="text-xs text-slate-500 mt-4">
            ≈ {minutes >= 60 ? `${Math.floor(minutes/60)}小时${minutes%60 ? minutes%60+'分' : ''}` : `${minutes}分钟`}
          </div>
        </div>
      )}

      {(mode === 'daily' || mode === 'workday') && (
        <div className="flex gap-3">
          <div className="flex-1">
            <label className={labelCls}>小时 (0-23)</label>
            <input type="number" value={hour} min={0} max={23}
              onChange={e => setHour(parseInt(e.target.value) || 0)}
              className={inputCls} />
          </div>
          <div className="flex-1">
            <label className={labelCls}>分钟 (0-59)</label>
            <input type="number" value={minute} min={0} max={59}
              onChange={e => setMinute(parseInt(e.target.value) || 0)}
              className={inputCls} />
          </div>
        </div>
      )}

      {mode === 'cron' && (
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={labelCls}>分钟 (0-59)</label>
            <input value={cronMinute} onChange={e => setCronMinute(e.target.value)} className={inputCls} placeholder="0" />
          </div>
          <div>
            <label className={labelCls}>小时 (0-23, 逗号分隔)</label>
            <input value={cronHour} onChange={e => setCronHour(e.target.value)} className={inputCls} placeholder="9,14,21" />
          </div>
          <div>
            <label className={labelCls}>星期 (0-6 或 1-5)</label>
            <input value={cronDayOfWeek} onChange={e => setCronDayOfWeek(e.target.value)} className={inputCls} placeholder="1-5" />
          </div>
          <div className="col-span-3 text-xs text-slate-500">
            当前: <code className="text-sky-400">{cronMinute} {cronHour} * * {cronDayOfWeek}</code>
            &nbsp; = 每周{cronDayOfWeek === '1-5' ? '工作日' : cronDayOfWeek} {cronHour}点{cronMinute}分
          </div>
        </div>
      )}
    </div>
  )
}


// ── Task Form Modal ──────────────────────────────────────────────
export function TaskFormModal({ task, defaultType, onClose, onSaved, allowedTypes, submitFn, userMode }) {
  const isEdit = !!task
  const [form, setForm] = useState({
    name: task?.name || '',
    module: task?.module || '',
    task_type: task?.task_type || defaultType || 'crawler',
    schedule_type: task?.schedule_type || 'interval',
    schedule_config: (() => {
      const cfg = task?.schedule_config
      if (cfg && typeof cfg === 'object' && cfg.type) {
        // 如果有 cron 字段但没有 hour/minute，反解出来
        if (cfg.type === 'cron' && cfg.cron && cfg.hour === undefined) {
          const parsed = parseCronConfig(cfg)
          if (parsed) return { type: 'cron', ...parsed }
        }
        return cfg
      }
      if (task?.schedule_type === 'cron') {
        const parsed = parseCronConfig(cfg)
        if (parsed) return { type: 'cron', ...parsed }
        return { type: 'cron', hour: cfg?.hour || 9, minute: cfg?.minute || 0, day_of_week: cfg?.day_of_week || '1-5' }
      }
      return { type: 'interval', minutes: cfg?.minutes || cfg?.interval_minutes || 60 }
    })(),
    script: task?.script || '',
    description: task?.description || '',
    tags: Array.isArray(task?.tags) ? task.tags.join(', ') : (task?.tags || 'crawler'),
    enabled: task?.enabled !== undefined ? task.enabled : true,
    // Report-specific fields
    report_template_id: '',
    report_sources: ['hot_topics', 'policy', 'exchange', 'financial', 'rss'],
    rss_source_ids: [],
    custom_prompt: '',
    trend_reference: true,
    use_harness: true,
    use_preferences: false,
    push_channel_ids: [],
    // Model selection for analysis/report tasks
    model: task?.schedule_config?.model || task?.script && (() => {
      try { return JSON.parse(task.script).model || '' } catch { return '' }
    })() || '',
  })

  // Parse existing report config from script field
  useEffect(() => {
    if (task?.task_type === 'report' && task?.script) {
      const script = task.script
      try {
        if (script.startsWith('{')) {
          const cfg = JSON.parse(script)
          setForm(prev => ({
            ...prev,
            report_template_id: cfg.template_id || '',
            report_sources: cfg.sources || ['hot_topics', 'policy', 'exchange', 'financial', 'rss'],
            rss_source_ids: cfg.rss_source_ids || [],
            custom_prompt: cfg.prompt || '',
            trend_reference: cfg.trend_reference !== false,
            use_harness: cfg.use_harness !== false,
            use_preferences: cfg.use_preferences === true,
            push_channel_ids: cfg.push_channel_ids || [],
            model: cfg.model || prev.model,
          }))
          if (userMode && cfg.user_source_ids) {
            setSelectedUserSourceIds(cfg.user_source_ids)
          }
        }
      } catch {}
    }
  }, [])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [previewScript, setPreviewScript] = useState(null)
  const [availableModels, setAvailableModels] = useState([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [selectedSourceIds, setSelectedSourceIds] = useState(() => {
    if (task?.task_type === 'crawler' && task?.script?.startsWith('{')) {
      try {
        const cfg = JSON.parse(task.script)
        if (cfg.type === 'rss' && Array.isArray(cfg.source_ids)) {
          return cfg.source_ids
        }
      } catch {}
    }
    return []
  })
  const [showSourcePicker, setShowSourcePicker] = useState(false)
  const [showReportRssPicker, setShowReportRssPicker] = useState(false)
  const [sourceNames, setSourceNames] = useState({})
  // User mode: personal data sources
  const [userSources, setUserSources] = useState([])
  const [selectedUserSourceIds, setSelectedUserSourceIds] = useState(() => {
    if (userMode && task?.task_type === 'crawler' && task?.script?.startsWith('{')) {
      try {
        const cfg = JSON.parse(task.script)
        if (cfg.type === 'user_rss' && Array.isArray(cfg.user_source_ids)) {
          return cfg.user_source_ids
        }
      } catch {}
    }
    return []
  })
  const [showOptimizeInput, setShowOptimizeInput] = useState(false)
  const [optimizeInstruction, setOptimizeInstruction] = useState('')
  const [optimizing, setOptimizing] = useState(false)
  const [pushChannels, setPushChannels] = useState([])

  const handleOptimize = async () => {
    if (!form.custom_prompt?.trim() || !optimizeInstruction.trim()) return
    setOptimizing(true)
    try {
      const res = await api.post('/api/v1/prompt/optimize', {
        prompt: form.custom_prompt,
        instruction: optimizeInstruction,
      })
      const optimized = res.data?.data?.optimized
      if (optimized) {
        handleChange('custom_prompt', optimized)
        setShowOptimizeInput(false)
        setOptimizeInstruction('')
      }
    } catch (e) {
      alert('优化失败: ' + (e.response?.data?.error?.message || e.message))
    } finally {
      setOptimizing(false)
    }
  }

  // Fetch available models from API
  const fetchModels = async () => {
    setFetchingModels(true)
    try {
      const res = await api.get('/api/v1/chat/models')
      const list = res.data?.data || []
      setAvailableModels(list)
    } catch { /* ignore */ } finally {
      setFetchingModels(false)
    }
  }

  // Fetch models when task_type changes to analysis/report
  useEffect(() => {
    if (form.task_type === 'analysis' || form.task_type === 'report') {
      if (availableModels.length === 0) fetchModels()
    }
  }, [form.task_type])

  // Fetch push channels when task_type is report
  useEffect(() => {
    if (form.task_type === 'report' && pushChannels.length === 0) {
      api.get('/api/v1/push-channels').then(r => {
        setPushChannels((r.data?.data || {}).channels || [])
      }).catch(() => {})
    }
  }, [form.task_type])

  // Load source names for displaying chips (crawler + report)
  useEffect(() => {
    const needLoad = (form.task_type === 'crawler' && selectedSourceIds.length > 0)
      || (form.task_type === 'report' && (form.rss_source_ids?.length > 0 || form.report_sources?.includes('rss')))
    if (!needLoad && Object.keys(sourceNames).length > 0) return
    if (!needLoad) return
    api.get('/api/v1/rss-sources').then(r => {
      const srcs = r.data?.data?.sources || []
      const map = {}
      srcs.forEach(s => { map[s.id] = s.name })
      setSourceNames(map)
    }).catch(() => {})
  }, [form.task_type, selectedSourceIds.length, form.rss_source_ids?.length])

  // Load user personal sources in user mode
  useEffect(() => {
    if (!userMode || (form.task_type !== 'crawler' && form.task_type !== 'report')) return
    api.get('/api/v1/user-sources').then(r => {
      setUserSources(r.data?.data || [])
    }).catch(() => {})
  }, [userMode, form.task_type])

  const handleChange = (key, val) => setForm(prev => ({ ...prev, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.module.trim()) {
      setError('任务名称和模块为必填项')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      // 构建 schedule_config，确保 cron 格式输出标准 cron 字符串
      const cfg = form.schedule_config

      // 非管理员（个人用户）：不允许 interval 模式
      if (userMode && cfg.type === 'interval') {
        return setError('个人用户仅支持小时级或天/周级定时任务')
      }

      // 管理员 interval：最小 60 分钟
      if (cfg.type === 'interval' && (cfg.minutes || cfg.interval_minutes || 0) < 60) {
        return setError('定时任务间隔不能小于 60 分钟')
      }

      let scheduleCfg = { ...cfg }
      // 结构化 cron 字段 → 原始 cron 字符串
      if (cfg.type === 'cron' && !cfg.cron) {
        const h = Array.isArray(cfg.hour) ? cfg.hour.join(',') : (cfg.hour ?? '*')
        const m = cfg.minute ?? '0'
        const dow = cfg.day_of_week ?? '*'
        scheduleCfg = { type: 'cron', cron: `${m} ${h} * * ${dow}` }
      }
      // interval 格式统一用 interval_minutes
      if (cfg.type === 'interval') {
        scheduleCfg = { type: 'interval', interval_minutes: cfg.minutes || cfg.interval_minutes || 60 }
      }

      const payload = {
        ...form,
        schedule_config: scheduleCfg,
        schedule_type: cfg.type || 'cron',
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      }
      delete payload.report_template_id
      delete payload.report_sources
      delete payload.custom_prompt
      delete payload.trend_reference
      delete payload.use_harness
      delete payload.model

      if (form.task_type === 'report') {
        // 序列化报告配置到 script 字段
        const reportCfg = {}
        if (form.report_template_id) reportCfg.template_id = form.report_template_id
        if (form.custom_prompt) reportCfg.prompt = form.custom_prompt
        if (form.report_sources) reportCfg.sources = form.report_sources
        if (form.rss_source_ids?.length) reportCfg.rss_source_ids = form.rss_source_ids
        if (userMode && selectedUserSourceIds.length > 0) reportCfg.user_source_ids = selectedUserSourceIds
        if (userMode && form.use_preferences) reportCfg.use_preferences = true
        if (form.push_channel_ids?.length) reportCfg.push_channel_ids = form.push_channel_ids
        if (form.trend_reference !== undefined) reportCfg.trend_reference = form.trend_reference
        if (form.use_harness !== undefined) reportCfg.use_harness = form.use_harness
        if (form.model) reportCfg.model = form.model
        payload.script = Object.keys(reportCfg).length > 0 ? JSON.stringify(reportCfg) : ''
      }

      if (form.task_type === 'crawler') {
        if (userMode) {
          // User mode: serialize personal data sources
          if (selectedUserSourceIds.length > 0) {
            payload.script = JSON.stringify({ type: 'user_rss', user_source_ids: selectedUserSourceIds })
          } else {
            payload.script = JSON.stringify({ type: 'user_rss' })
          }
        } else if (selectedSourceIds.length > 0) {
          payload.script = JSON.stringify({ type: 'rss', source_ids: selectedSourceIds })
        }
      }
      if (submitFn) {
        await submitFn(payload, isEdit, task)
      } else if (isEdit) {
        await api.put(`/api/v1/tasks/${task.id}`, payload)
      } else {
        await api.post('/api/v1/tasks', payload)
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
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-800">
          <h3 className="text-white font-semibold">{isEdit ? '编辑任务' : '新建任务'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {error && <div className="bg-red-900/30 text-red-400 text-sm rounded-lg px-3 py-2">{error}</div>}

          <div>
            <label className={labelCls}>任务名称 *</label>
            <input value={form.name} onChange={e => handleChange('name', e.target.value)}
              className={inputCls} placeholder="如：热点平台数据采集" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>模块名 *</label>
              <input value={form.module} onChange={e => handleChange('module', e.target.value)}
                className={inputCls} placeholder="如：hot_topics" />
            </div>
            <div>
              <label className={labelCls}>任务类型</label>
              <select value={form.task_type} onChange={e => handleChange('task_type', e.target.value)} className={inputCls}>
                {TASK_TYPE_OPTIONS.filter(o => !allowedTypes || allowedTypes.includes(o.value)).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>

          {/* Schedule Editor */}
          <div>
            <label className={labelCls}>执行周期（点击预设或自定义）</label>
            <ScheduleEditor value={form.schedule_config} onChange={cfg => handleChange('schedule_config', cfg)} isAdmin={!userMode} />
          </div>

          {/* Model selection for analysis tasks */}
          {form.task_type === 'analysis' && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={labelCls}>模型</label>
                <button type="button" onClick={fetchModels} disabled={fetchingModels}
                  className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 disabled:opacity-50">
                  {fetchingModels ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                  刷新
                </button>
              </div>
              {availableModels.length > 0 ? (
                <select value={form.model || ''} onChange={e => handleChange('model', e.target.value)} className={inputCls}>
                  <option value="">默认模型</option>
                  {availableModels.map(m => (
                    <option key={m.id} value={m.id}>{m.display_name || m.id}</option>
                  ))}
                </select>
              ) : (
                <input value={form.model || ''} onChange={e => handleChange('model', e.target.value)}
                  className={inputCls} placeholder="glm-5.1 (可选，留空用全局配置)" />
              )}
            </div>
          )}

          {/* Report-specific fields */}
          {form.task_type === 'report' && (
            <div className="space-y-3 p-4 bg-slate-900/60 rounded-lg border border-slate-700/50">
              <div className="text-xs text-slate-400 font-medium uppercase tracking-wide">报告配置</div>

              <div>
                <label className={labelCls}>报告模板（选择后自动加载提示词）</label>
                <select value={form.report_template_id || ''}
                  onChange={async e => {
                    const val = e.target.value
                    handleChange('report_template_id', val)
                    if (!val) return
                    // 从 API 加载模板提示词到自定义提示词框
                    try {
                      const res = await api.get(`/api/v1/report-templates/${val}`)
                      const tmpl = res.data?.data
                      if (tmpl?.prompt_template) {
                        handleChange('custom_prompt', tmpl.prompt_template)
                      }
                    } catch {
                      // 模板不存在，不填充
                    }
                  }}
                  className={inputCls}>
                  <option value="">不使用模板</option>
                  <option value="template:insight">深度洞察报告</option>
                  <option value="template:daily">每日洞察日报</option>
                  <option value="template:quick">快速简报</option>
                  <option value="template:heartbeat">系统心跳报告</option>
                </select>
              </div>

              {userMode && (
                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input type="checkbox"
                    checked={form.use_preferences}
                    onChange={e => handleChange('use_preferences', e.target.checked)}
                    className="accent-sky-500"
                  />
                  使用我的偏好（按兴趣标签过滤数据）
                </label>
              )}

                <div>
                <label className={labelCls}>数据源（留空则使用全部）</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {[
                    { key: 'hot_topics', label: '热点平台' },
                    { key: 'policy', label: '政策' },
                    { key: 'exchange', label: '交易所公告' },
                    { key: 'financial', label: '财经数据' },
                    { key: 'rss', label: 'RSS 数据源' },
                  ].map(src => (
                    <label key={src.key} className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800 px-2.5 py-1 rounded-md border border-slate-600 cursor-pointer hover:border-sky-500">
                      <input type="checkbox"
                        checked={form.report_sources?.includes(src.key) ?? true}
                        onChange={e => {
                          const srcs = form.report_sources || ['hot_topics','policy','exchange','financial','rss']
                          const next = e.target.checked
                            ? [...new Set([...srcs, src.key])]
                            : srcs.filter(s => s !== src.key)
                          handleChange('report_sources', next)
                        }}
                        className="accent-sky-500"
                      />
                      {src.label}
                    </label>
                  ))}
                </div>
                {/* RSS 细化选择 */}
                {form.report_sources?.includes('rss') && (
                  <div className="mt-2">
                    <button type="button" onClick={() => setShowReportRssPicker(true)}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white hover:border-sky-500 transition-colors text-left flex items-center gap-2">
                      <Rss size={14} className="text-sky-400 shrink-0" />
                      <span className="flex-1">
                        {form.rss_source_ids?.length > 0
                          ? `已细化 ${form.rss_source_ids.length} 个 RSS 源`
                          : '点击细化选择 RSS 数据源（留空则使用全部）'}
                      </span>
                      <span className="text-xs text-sky-400">选择</span>
                    </button>
                    {form.rss_source_ids?.length > 0 && sourceNames && Object.keys(sourceNames).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {form.rss_source_ids.slice(0, 15).map(id => (
                          <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-500/10 text-sky-400 text-xs rounded border border-sky-500/30">
                            {sourceNames[id] || `#${id}`}
                            <button type="button" onClick={() => {
                              handleChange('rss_source_ids', form.rss_source_ids.filter(i => i !== id))
                            }} className="hover:text-red-400"><X size={10} /></button>
                          </span>
                        ))}
                        {form.rss_source_ids.length > 15 && (
                          <span className="text-xs text-slate-500 px-2 py-0.5">+{form.rss_source_ids.length - 15} 个</span>
                        )}
                      </div>
                    )}
                  </div>
                )}
                </div>
              {userMode && (
                <div>
                  <label className={labelCls}>我的数据源</label>
                  {userSources.length === 0 ? (
                    <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-3 text-sm text-slate-500">
                      暂无个人数据源，请先在「我的RSS」中添加
                    </div>
                  ) : (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {userSources.map(src => {
                        const checked = selectedUserSourceIds.includes(src.id)
                        return (
                          <label key={src.id}
                            className={clsx("flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm",
                              checked ? "bg-sky-500/10 border-sky-500/30 text-white" : "bg-slate-900 border-slate-600 text-slate-400 hover:border-slate-500")}>
                            <input type="checkbox" checked={checked}
                              onChange={() => {
                                setSelectedUserSourceIds(prev =>
                                  checked ? prev.filter(id => id !== src.id) : [...prev, prev.id]
                                )
                              }}
                              className="accent-sky-500" />
                            <span className="flex-1 truncate">{src.display_name || src.source_id}</span>
                            <span className="text-xs text-slate-600">{src.type}</span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                  {selectedUserSourceIds.length > 0 && (
                    <div className="text-xs text-slate-500 mt-1">已选择 {selectedUserSourceIds.length} 个数据源</div>
                  )}
                </div>
              )}

              {/* 提示词编辑 + AI 优化 */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className={labelCls + " mb-0"}>Prompt</label>
                  <button type="button" disabled={optimizing || !form.custom_prompt?.trim()}
                    onClick={() => setShowOptimizeInput(true)}
                    className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 disabled:opacity-40 disabled:cursor-not-allowed">
                    {optimizing ? <Loader2 size={12} className="animate-spin" /> : <Edit3 size={12} />}
                    AI 优化
                  </button>
                </div>
                <textarea value={form.custom_prompt || ''}
                  onChange={e => handleChange('custom_prompt', e.target.value)}
                  rows={8}
                  className={inputCls + " font-mono text-xs leading-relaxed"}
                  placeholder={"你是一个专业的投资分析助手。请根据{hot_topics}生成一份..."}
                />
                {showOptimizeInput && (
                  <div className="mt-2 flex gap-2">
                    <input
                      value={optimizeInstruction}
                      onChange={e => setOptimizeInstruction(e.target.value)}
                      className={inputCls + " flex-1"}
                      placeholder="如：改成生活娱乐风格、增加数据分析维度..."
                      autoFocus
                      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleOptimize() } }}
                    />
                    <button type="button" onClick={handleOptimize}
                      disabled={optimizing || !optimizeInstruction.trim()}
                      className="px-3 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 disabled:opacity-50 whitespace-nowrap">
                      {optimizing ? '优化中...' : '执行'}
                    </button>
                    <button type="button" onClick={() => { setShowOptimizeInput(false); setOptimizeInstruction('') }}
                      className="px-3 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">
                      取消
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input type="checkbox"
                    checked={form.trend_reference !== false}
                    onChange={e => handleChange('trend_reference', e.target.checked)}
                    className="accent-sky-500"
                  />
                  趋势参考（对比历史报告）
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input type="checkbox"
                    checked={form.use_harness !== false}
                    onChange={e => handleChange('use_harness', e.target.checked)}
                    className="accent-sky-500"
                  />
                  使用 AI Harness 模式
                </label>
              </div>

              {/* Model selection for report tasks */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-slate-400">模型</label>
                  <button type="button" onClick={fetchModels} disabled={fetchingModels}
                    className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 disabled:opacity-50">
                    {fetchingModels ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                    刷新
                  </button>
                </div>
                {availableModels.length > 0 ? (
                  <select value={form.model || ''} onChange={e => handleChange('model', e.target.value)} className={inputCls}>
                    <option value="">默认模型</option>
                    {availableModels.map(m => (
                      <option key={m.id} value={m.id}>{m.display_name || m.id}</option>
                    ))}
                  </select>
                ) : (
                  <input value={form.model || ''} onChange={e => handleChange('model', e.target.value)}
                    className={inputCls} placeholder="glm-5.1 (可选)" />
                )}
              </div>

              {/* Push channel selection */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">推送渠道（报告生成后自动推送）</label>
                {pushChannels.length === 0 ? (
                  <div className="text-xs text-slate-500 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2">
                    暂无推送渠道，请先在「推送渠道」中配置
                  </div>
                ) : (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    <label className="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                      <input type="checkbox"
                        checked={(form.push_channel_ids || []).includes('_email')}
                        onChange={() => {
                          const ids = form.push_channel_ids || []
                          handleChange('push_channel_ids',
                            ids.includes('_email') ? ids.filter(id => id !== '_email') : [...ids, '_email'])
                        }}
                        className="accent-sky-500" />
                      <span className="text-sm text-slate-200">邮件推送</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-sky-500/10 text-sky-400">默认</span>
                    </label>
                    {pushChannels.filter(c => c.enabled).map(c => (
                      <label key={c.id} className="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-slate-700/50 cursor-pointer">
                        <input type="checkbox"
                          checked={(form.push_channel_ids || []).includes(c.id)}
                          onChange={() => {
                            const ids = form.push_channel_ids || []
                            handleChange('push_channel_ids',
                              ids.includes(c.id) ? ids.filter(id => id !== c.id) : [...ids, c.id])
                          }}
                          className="accent-sky-500" />
                        <span className="text-sm text-slate-200">{c.name}</span>
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
                          {c.channel_label || c.channel_type}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Crawler task: data source picker */}
          {form.task_type === 'crawler' && !userMode && (
          <div>
            <label className={labelCls}>数据源</label>
            <button type="button" onClick={() => setShowSourcePicker(true)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white hover:border-sky-500 transition-colors text-left flex items-center gap-2">
              <Rss size={14} className="text-sky-400 shrink-0" />
              <span className="flex-1">
                {selectedSourceIds.length > 0
                  ? `已选择 ${selectedSourceIds.length} 个数据源`
                  : '点击选择数据源...'}
              </span>
              <span className="text-xs text-sky-400">选择</span>
            </button>
            {selectedSourceIds.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {selectedSourceIds.slice(0, 20).map(id => (
                  <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-500/10 text-sky-400 text-xs rounded border border-sky-500/30">
                    {sourceNames[id] || `#${id}`}
                    <button type="button" onClick={() => {
                      setSelectedSourceIds(prev => prev.filter(i => i !== id))
                    }} className="hover:text-red-400">
                      <X size={10} />
                    </button>
                  </span>
                ))}
                {selectedSourceIds.length > 20 && (
                  <span className="text-xs text-slate-500 px-2 py-0.5">+{selectedSourceIds.length - 20} 个</span>
                )}
              </div>
            )}
          </div>
          )}

          {/* Crawler task (user mode): personal data sources */}
          {form.task_type === 'crawler' && userMode && (
          <div>
            <label className={labelCls}>我的数据源</label>
            {userSources.length === 0 ? (
              <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-3 text-sm text-slate-500">
                暂无个人数据源，请先在「我的RSS」中添加
              </div>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {userSources.map(src => {
                  const checked = selectedUserSourceIds.includes(src.id)
                  return (
                    <label key={src.id}
                      className={clsx("flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm",
                        checked ? "bg-sky-500/10 border-sky-500/30 text-white" : "bg-slate-900 border-slate-600 text-slate-400 hover:border-slate-500")}>
                      <input type="checkbox" checked={checked}
                        onChange={() => {
                          setSelectedUserSourceIds(prev =>
                            checked ? prev.filter(id => id !== src.id) : [...prev, src.id]
                          )
                        }}
                        className="accent-sky-500" />
                      <span className="flex-1 truncate">{src.display_name || src.source_id}</span>
                      <span className="text-xs text-slate-600">{src.type}</span>
                    </label>
                  )
                })}
              </div>
            )}
            {selectedUserSourceIds.length > 0 && (
              <div className="text-xs text-slate-500 mt-1">已选择 {selectedUserSourceIds.length} 个数据源</div>
            )}
          </div>
          )}

          {/* Non-crawler, non-report tasks: script path */}
          {form.task_type !== 'report' && form.task_type !== 'crawler' && (
          <div>
            <label className={labelCls}>脚本路径</label>
            <div className="flex gap-2">
              <input value={form.script} onChange={e => handleChange('script', e.target.value)}
                className={inputCls + " font-mono flex-1"} placeholder="scripts/cron_wrappers/run_xxx.sh" />
              {form.script && (
                <button type="button" onClick={() => {
                  const fname = form.script.split('/').pop()
                  setPreviewScript(fname)
                }} className="px-3 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600" title="预览脚本">
                  <Eye size={16} />
                </button>
              )}
            </div>
          </div>
          )}

          {form.task_type === 'report' && (
          <div>
            <label className={labelCls}>Module（报告输出标识）</label>
            <input value={form.module} onChange={e => handleChange('module', e.target.value)}
              className={inputCls} placeholder="report" />
          </div>
          )}

          <div>
            <label className={labelCls}>描述</label>
            <input value={form.description} onChange={e => handleChange('description', e.target.value)}
              className={inputCls} placeholder="任务功能描述" />
          </div>

          <div>
            <label className={labelCls}>标签 (逗号分隔)</label>
            <input value={form.tags} onChange={e => handleChange('tags', e.target.value)}
              className={inputCls} placeholder="crawler, hot_topics" />
          </div>

          {isEdit && (
            <div className="flex items-center gap-2">
              <label className={labelCls + " mb-0"}>启用状态</label>
              <button type="button" onClick={() => handleChange('enabled', !form.enabled)}
                className={clsx("relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                  form.enabled ? 'bg-sky-500' : 'bg-slate-600')}>
                <span className={clsx("inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform",
                  form.enabled ? 'translate-x-4.5' : 'translate-x-1')} />
              </button>
              <span className="text-xs text-slate-400">{form.enabled ? '已启用' : '已暂停'}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">取消</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 disabled:opacity-50">
              {submitting ? '保存中...' : (isEdit ? '保存' : '创建')}
            </button>
          </div>
        </form>
      </div>
      <ScriptPreviewModal filename={previewScript} category="shell" onClose={() => setPreviewScript(null)} />
      {showSourcePicker && (
        <DataSourcePicker
          selectedIds={selectedSourceIds}
          onConfirm={(ids) => { setSelectedSourceIds(ids); setShowSourcePicker(false) }}
          onClose={() => setShowSourcePicker(false)}
        />
      )}
      {showReportRssPicker && (
        <DataSourcePicker
          selectedIds={form.rss_source_ids || []}
          onConfirm={(ids) => { handleChange('rss_source_ids', ids); setShowReportRssPicker(false) }}
          onClose={() => setShowReportRssPicker(false)}
        />
      )}
    </div>
  )
}


export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editTask, setEditTask] = useState(null)
  const [runningIds, setRunningIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('crawler')
  const [scopeTab, setScopeTab] = useState('platform')
  const pollRef = useRef(null)
  const navigate = useNavigate()

  const load = () => {
    api.get('/api/v1/tasks').then(r => {
      const d = r.data?.data || []
      setTasks(d)
      localStorage.setItem('intelhub_tasks_cache', JSON.stringify(d))
    }).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => {
    // Read cache first
    try {
      const c = localStorage.getItem('intelhub_tasks_cache')
      if (c) { setTasks(JSON.parse(c)); setLoading(false) }
    } catch { /* ignore */ }
    load()
  }, [])

  // 根据 Scope + Tab 过滤任务
  const tabConfig = TASK_TABS.find(t => t.key === activeTab) || TASK_TABS[0]
  const scopedTasks = scopeTab === 'platform' ? tasks.filter(t => !t.user_id) : tasks.filter(t => t.user_id)
  const filtered = scopedTasks.filter(t => tabConfig.types.includes(t.task_type))
  // Scope 计数
  const scopeCounts = {
    platform: tasks.filter(t => !t.user_id).length,
    user: tasks.filter(t => t.user_id).length,
  }
  // Tab 计数（基于当前 scope）
  const tabCounts = {}
  TASK_TABS.forEach(tab => {
    tabCounts[tab.key] = scopedTasks.filter(t => tab.types.includes(t.task_type)).length
  })

  useEffect(() => {
    if (runningIds.size === 0) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    if (pollRef.current) return
    pollRef.current = setInterval(() => {
      const ids = Array.from(runningIds)
      Promise.all(ids.map(id => api.get(`/api/v1/tasks/${id}/status`).catch(() => null)))
        .then(results => {
          const done = new Set()
          results.forEach((r, i) => {
            const st = r?.data?.data?.status
            if (st === 'done' || st === 'failed' || st === 'timeout') done.add(ids[i])
          })
          if (done.size > 0) {
            setRunningIds(prev => { const n = new Set(prev); done.forEach(id => n.delete(id)); return n })
            load()
          }
        })
    }, 1500)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [runningIds])

  const handleRun = async (id) => {
    setRunningIds(prev => new Set(prev).add(id))
    try { await api.post(`/api/v1/tasks/${id}/run`) }
    catch { setRunningIds(prev => { const n = new Set(prev); n.delete(id); return n }) }
  }
  const handleToggle = async (id, enabled) => { await api.put(`/api/v1/tasks/${id}`, { enabled }); load() }
  const handleDelete = async (id) => { if (confirm('确定删除此任务?')) { await api.delete(`/api/v1/tasks/${id}`); load() } }
  const handleClick = (id) => { navigate(`/tasks/${id}`) }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">任务管理</h2>
          <p className="text-xs text-slate-500 mt-1">
            {tasks.filter(t => t.enabled).length} 个任务已启用 · APScheduler Worker 调度
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700 flex items-center gap-2">
            <RefreshCw size={14} /> 刷新
          </button>
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm hover:bg-sky-600 flex items-center gap-2">
            <Plus size={14} /> 新建任务
          </button>
        </div>
      </div>

      {/* Scope 栏：平台 / 用户 */}
      <div className="flex items-center gap-2">
        {[
          { key: 'platform', label: '平台任务' },
          { key: 'user', label: '用户任务' },
        ].map(s => (
          <button key={s.key} onClick={() => setScopeTab(s.key)}
            className={clsx("px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              scopeTab === s.key
                ? "bg-indigo-600 text-white"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            )}>
            {s.label} ({scopeCounts[s.key] || 0})
          </button>
        ))}
      </div>

      {/* Tab 栏：任务类型 */}
      <div className="flex items-center gap-2">
        {TASK_TABS.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={clsx("px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "bg-sky-600 text-white"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            )}>
            {tab.label} ({tabCounts[tab.key] || 0})
          </button>
        ))}
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800/80">
              <th className="text-left py-3 px-3 text-xs font-semibold text-slate-400">任务</th>
              <th className="text-left py-3 px-3 text-xs font-semibold text-slate-400">执行周期 / 下次执行</th>
              <th className="text-left py-3 px-3 text-xs font-semibold text-slate-400">成功/失败</th>
              <th className="text-left py-3 px-3 text-xs font-semibold text-slate-400">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <TaskRow
                key={t.id} task={t} isRunning={runningIds.has(t.id)}
                showUser={scopeTab === 'user'}
                onRun={handleRun} onToggle={handleToggle}
                onDelete={handleDelete} onEdit={setEditTask} onClick={handleClick}
              />
            ))}
            {filtered.length === 0 && !loading && (
              <tr><td colSpan={4} className="py-8 text-center text-slate-500">暂无{tabConfig.label}任务</td></tr>
            )}
          </tbody>
        </table>
        {loading && <div className="p-8 text-center text-slate-500">加载中...</div>}
      </div>

      {showCreate && <TaskFormModal defaultType={activeTab === 'system' ? 'knowledge' : activeTab} onClose={() => setShowCreate(false)} onSaved={load} />}
      {editTask && <TaskFormModal task={editTask} onClose={() => setEditTask(null)} onSaved={load} />}
    </div>
  )
}
