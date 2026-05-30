import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Settings, Send, Trash2, ChevronDown, ChevronRight, Bot, User, Loader2, Key, Globe } from 'lucide-react'
import { api } from '../api/client'
import clsx from 'clsx'

// ── SSE Event Types ──────────────────────────────────────────────

function SSEEventBlock({ event }) {
  const [open, setOpen] = useState(false)

  if (event.type === 'thinking') {
    return (
      <div className="my-1">
        <button onClick={() => setOpen(!open)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="italic">Thinking...</span>
        </button>
        {open && (
          <pre className="mt-1 text-xs text-slate-500 bg-slate-900/50 rounded p-2 whitespace-pre-wrap max-h-60 overflow-y-auto">
            {event.content}
          </pre>
        )}
      </div>
    )
  }

  if (event.type === 'tool_call') {
    return (
      <div className="my-1">
        <button onClick={() => setOpen(!open)}
          className="flex items-center gap-1 text-xs text-amber-500 hover:text-amber-300 transition-colors">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span>Tool: {event.tool_name}</span>
        </button>
        {open && (
          <pre className="mt-1 text-xs text-slate-400 bg-slate-900/50 rounded p-2 whitespace-pre-wrap max-h-40 overflow-y-auto">
            {JSON.stringify(event.tool_args, null, 2)}
          </pre>
        )}
      </div>
    )
  }

  if (event.type === 'tool_result') {
    return (
      <div className="my-1">
        <button onClick={() => setOpen(!open)}
          className="flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-400 transition-colors">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span>Result{event.tool_name ? ` (${event.tool_name})` : ''}</span>
        </button>
        {open && (
          <pre className="mt-1 text-xs text-slate-400 bg-slate-900/50 rounded p-2 whitespace-pre-wrap max-h-40 overflow-y-auto">
            {event.result}
          </pre>
        )}
      </div>
    )
  }

  return null
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? 'bg-sky-500/20 text-sky-400' : 'bg-violet-500/20 text-violet-400'
      }`}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className={`max-w-[75%] ${isUser ? 'text-right' : 'text-left'}`}>
        {!isUser && msg.events && msg.events.length > 0 && (
          <div className="mb-2 ml-1">
            {msg.events.map((evt, i) => (
              <SSEEventBlock key={i} event={evt} />
            ))}
          </div>
        )}
        <div className={`inline-block rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? 'bg-sky-500/20 text-sky-100' : 'bg-slate-800 text-slate-200'
        }`}>
          {isUser ? (
            <span>{msg.content}</span>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-pre:my-1">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StreamingBubble({ content, events }) {
  return (
    <div className="flex gap-3 flex-row mb-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-violet-500/20 text-violet-400">
        <Bot size={16} />
      </div>
      <div className="max-w-[75%] text-left">
        <div className="inline-block rounded-2xl px-4 py-2.5 bg-slate-800 text-slate-200 text-sm">
          {events && events.length > 0 && (
            <div className="mb-2">
              {events.map((evt, i) => (
                <SSEEventBlock key={i} event={evt} />
              ))}
            </div>
          )}
          {content ? (
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-pre:my-1">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              <span className="inline-block w-2 h-4 bg-violet-400 animate-pulse ml-0.5" />
            </div>
          ) : (
            <span className="flex items-center gap-2 text-slate-400">
              <Loader2 size={14} className="animate-spin" />
              <span>思考中...</span>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Settings Modal ──────────────────────────────────────────────

function SettingsModal({ open, onClose, config, onSave }) {
  const user = api.getUser() || {}
  const isAdmin = user.role === 'admin'
  const isMember = user.is_member
  const hasUserConfig = config?.has_user_config

  const [viewMode, setViewMode] = useState(hasUserConfig ? 'custom' : 'global')
  const [form, setForm] = useState({ api_key: '', base_url: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open && config) {
      if (isAdmin) {
        setForm({
          api_key: config.has_key ? '••••••••' : '',
          base_url: config.base_url || '',
        })
      } else if (hasUserConfig) {
        setForm({ api_key: '••••••••', base_url: config.base_url || '' })
        setViewMode('custom')
      } else {
        setForm({ api_key: '', base_url: '' })
        setViewMode('global')
      }
    }
  }, [open, config])

  if (!open) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {}
      if (form.api_key && form.api_key !== '••••••••') {
        payload.api_key = form.api_key
      }
      payload.base_url = form.base_url || ''
      await api.post('/api/v1/chat/config', payload)
      onSave()
      onClose()
    } catch (e) {
      alert('保存失败: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleClearCustom = async () => {
    if (!confirm('确认清除自定义配置，切换到全局配置？')) return
    setSaving(true)
    try {
      await api.post('/api/v1/chat/config', { clear_custom: true })
      onSave()
      onClose()
    } catch (e) {
      alert('操作失败: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"

  // ── Admin: edit global config ──
  if (isAdmin) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-100">全局 LLM 配置</h2>
            <button onClick={onClose} className="text-slate-500 hover:text-white text-lg">&times;</button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">API Key</label>
              <input type="password" value={form.api_key}
                onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                placeholder="sk-ant-..." className={inputCls} />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Base URL</label>
              <input type="text" value={form.base_url}
                onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                placeholder="https://open.bigmodel.cn/api/anthropic" className={inputCls} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-6">
            <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white">取消</button>
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 text-sm bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Non-admin member: global / custom toggle ──
  if (isMember) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-100">AI 对话设置</h2>
            <button onClick={onClose} className="text-slate-500 hover:text-white text-lg">&times;</button>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center bg-slate-900 rounded-lg p-1 mb-4">
            <button onClick={() => setViewMode('global')}
              className={clsx("flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm transition-colors",
                viewMode === 'global' ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white")}>
              <Globe size={14} /> 全局配置
            </button>
            <button onClick={() => setViewMode('custom')}
              className={clsx("flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm transition-colors",
                viewMode === 'custom' ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white")}>
              <Key size={14} /> 自定义
            </button>
          </div>

          {viewMode === 'global' ? (
            <div className="space-y-3">
              {config?.configured ? (
                <>
                  <div className="bg-slate-900 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Base URL</span>
                      <span className="text-slate-200 font-mono text-xs">{config.base_url || '-'}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">状态</span>
                      <span className="text-emerald-400 text-xs">已配置</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">全局配置由管理员维护，你无法修改。如需使用自己的 API Key，请切换到"自定义"。</p>
                  <button onClick={() => setViewMode('custom')}
                    className="w-full px-4 py-2 text-sm bg-sky-500/20 text-sky-400 rounded-lg hover:bg-sky-500/30 transition-colors">
                    配置自定义 API Key
                  </button>
                </>
              ) : (
                <div className="text-center py-4">
                  <p className="text-slate-400 text-sm mb-2">全局配置未就绪</p>
                  <p className="text-xs text-slate-500 mb-3">请联系管理员配置全局 API Key，或使用自己的 Key。</p>
                  <button onClick={() => setViewMode('custom')}
                    className="px-4 py-2 text-sm bg-sky-500/20 text-sky-400 rounded-lg hover:bg-sky-500/30">
                    配置自定义 API Key
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">配置你自己的 API Key，将使用你的配额而非全局配置。</p>
              <div>
                <label className="block text-sm text-slate-400 mb-1">API Key</label>
                <input type="password" value={form.api_key}
                  onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                  placeholder={hasUserConfig ? '已配置，留空保持不变' : 'sk-ant-...'} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Base URL</label>
                <input type="text" value={form.base_url}
                  onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                  placeholder="https://open.bigmodel.cn/api/anthropic" className={inputCls} />
              </div>
              <div className="flex items-center justify-between pt-2">
                {hasUserConfig && (
                  <button onClick={handleClearCustom} disabled={saving}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors">
                    清除自定义配置
                  </button>
                )}
                <div className="flex gap-3 ml-auto">
                  <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white">取消</button>
                  <button onClick={handleSave} disabled={saving}
                    className="px-4 py-2 text-sm bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
                    {saving ? '保存中...' : '保存'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Non-member: only custom config ──
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">配置个人 API Key</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white text-lg">&times;</button>
        </div>
        <p className="text-xs text-slate-400 mb-4">配置你自己的 API Key 以使用 AI 对话功能。如需使用平台共享配额，请联系管理员开通会员。</p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">API Key</label>
            <input type="password" value={form.api_key}
              onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
              placeholder={hasUserConfig ? '已配置，留空保持不变' : 'sk-ant-...'} className={inputCls} />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Base URL</label>
            <input type="text" value={form.base_url}
              onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
              placeholder="https://open.bigmodel.cn/api/anthropic" className={inputCls} />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-white">取消</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main Chat Component ──────────────────────────────────────────

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState('')
  const [streamEvents, setStreamEvents] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [config, setConfig] = useState(null)
  const [showSettings, setShowSettings] = useState(false)
  const [sessions, setSessions] = useState([])
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState(() => {
    try { return localStorage.getItem('intelhub_chat_model') || '' } catch { return '' }
  })
  const [chatMode, setChatMode] = useState(() => {
    try { return localStorage.getItem('intelhub_chat_mode') || '' } catch { return '' }
  })
  const messagesEndRef = useRef(null)
  const abortRef = useRef(null)

  const user = api.getUser() || {}
  const isAdmin = user.role === 'admin'
  const isMember = user.is_member

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, streamContent, streamEvents, scrollToBottom])

  // Persist selections
  useEffect(() => {
    if (selectedModel) localStorage.setItem('intelhub_chat_model', selectedModel)
    else localStorage.removeItem('intelhub_chat_model')
  }, [selectedModel])

  useEffect(() => {
    localStorage.setItem('intelhub_chat_mode', chatMode)
  }, [chatMode])

  // Load config and sessions on mount
  useEffect(() => {
    try {
      const cachedConfig = localStorage.getItem('intelhub_chat_config')
      if (cachedConfig) setConfig(JSON.parse(cachedConfig))
      const cachedSessions = localStorage.getItem('intelhub_chat_sessions')
      if (cachedSessions) setSessions(JSON.parse(cachedSessions))
    } catch { /* ignore */ }
    loadConfig()
    loadSessions()
  }, [])

  // Auto-init chatMode and fetch models when config loads
  useEffect(() => {
    if (!config) return
    // Init chatMode based on config source
    if (!chatMode) {
      const mode = config.source === 'user' ? 'custom' : 'global'
      setChatMode(mode)
    }
    // Auto-fetch models
    if (config.configured) {
      api.get('/api/v1/chat/models').then(r => {
        setModels(r.data?.data || [])
      }).catch(() => {})
    }
  }, [config?.configured])

  const loadConfig = async () => {
    try {
      const res = await api.get('/api/v1/chat/config')
      const data = res.data.data
      setConfig(data)
      localStorage.setItem('intelhub_chat_config', JSON.stringify(data))
    } catch { /* ignore */ }
  }

  const loadSessions = async () => {
    try {
      const res = await api.get('/api/v1/chat/sessions')
      const data = res.data.data || []
      setSessions(data)
      localStorage.setItem('intelhub_chat_sessions', JSON.stringify(data))
    } catch { /* ignore */ }
  }

  // Effective configured state considering chatMode
  const isConfigured = config?.configured
  const effectiveConfigured = isAdmin ? isConfigured
    : chatMode === 'custom' ? !!config?.has_user_config
    : isConfigured

  const handleSend = async () => {
    const text = input.trim()
    if (!text || streaming) return

    if (!effectiveConfigured) {
      setShowSettings(true)
      return
    }

    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput('')
    setStreaming(true)
    setStreamContent('')
    setStreamEvents([])

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const BASE = import.meta.env.VITE_API_BASE || ''
      const headers = { 'Content-Type': 'application/json' }
      const token = api.getToken()
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(`${BASE}/api/v1/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          model: selectedModel || config?.model || undefined,
          max_turns: 10,
          use_global: chatMode === 'global',
        }),
        signal: ctrl.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error?.message || `HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''
      let events = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const evt = JSON.parse(raw)

            switch (evt.type) {
              case 'content':
                fullContent += evt.content
                setStreamContent(fullContent)
                break
              case 'thinking':
                if (events.length > 0 && events[events.length - 1].type === 'thinking') {
                  events[events.length - 1] = {
                    ...events[events.length - 1],
                    content: events[events.length - 1].content + evt.content,
                  }
                } else {
                  events = [...events, evt]
                }
                setStreamEvents([...events])
                break
              case 'tool_call':
                events = [...events, evt]
                setStreamEvents([...events])
                break
              case 'tool_result':
                if (events.length > 0 && events[events.length - 1].type === 'tool_result' && events[events.length - 1].tool_name === (evt.tool_name || '')) {
                  events[events.length - 1] = {
                    ...events[events.length - 1],
                    result: (events[events.length - 1].result || '') + (evt.result || ''),
                  }
                } else {
                  events = [...events, evt]
                }
                setStreamEvents([...events])
                break
              case 'session':
                setSessionId(evt.session_id)
                break
              case 'error':
                setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${evt.content}` }])
                break
              case 'done':
                if (fullContent) {
                  setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: fullContent,
                    events: events,
                  }])
                }
                setStreamContent('')
                setStreamEvents([])
                setStreaming(false)
                loadSessions()
                break
            }
          } catch { /* skip malformed JSON */ }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages(prev => [...prev, { role: 'assistant', content: `连接失败: ${e.message}` }])
      }
      setStreaming(false)
      setStreamContent('')
      setStreamEvents([])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setSessionId(null)
    setStreamContent('')
    setStreamEvents([])
    setStreaming(false)
    if (abortRef.current) abortRef.current.abort()
  }

  const handleDeleteSession = async (sid) => {
    try {
      await api.delete(`/api/v1/chat/sessions/${sid}`)
      loadSessions()
    } catch { /* ignore */ }
  }

  const handleLoadSession = async (sess) => {
    setSessionId(sess.session_id)
    setStreamContent('')
    setStreamEvents([])
    setStreaming(false)
    try {
      const res = await api.get(`/api/v1/chat/sessions/${sess.session_id}`)
      const data = res.data?.data
      if (data?.messages) {
        setMessages(data.messages.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        })))
      } else {
        setMessages([])
      }
    } catch {
      setMessages([])
    }
  }

  return (
    <div className="flex" style={{ height: 'calc(100vh - 3rem)' }}>
      {/* Sidebar: sessions list */}
      <div className="w-56 bg-slate-900/50 border-r border-slate-800 flex flex-col flex-shrink-0">
        <div className="p-3">
          <button onClick={handleNewChat}
            className="w-full px-3 py-2 text-sm bg-sky-500/10 text-sky-400 rounded-lg hover:bg-sky-500/20 transition-colors border border-sky-500/20">
            + 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2">
          {sessions.length === 0 && (
            <p className="text-xs text-slate-600 text-center mt-4">暂无历史对话</p>
          )}
          {sessions.map(s => (
            <div key={s.session_id} className="group flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-slate-800 cursor-pointer mb-0.5"
                 onClick={() => handleLoadSession(s)}>
              <span className="flex-1 text-xs text-slate-400 truncate">{s.title}</span>
              <button
                onClick={e => { e.stopPropagation(); handleDeleteSession(s.session_id) }}
                className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-slate-100">AI 对话</h2>

            {/* Config source indicator */}
            {isAdmin ? (
              <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400">全局配置</span>
            ) : isMember && isConfigured ? (
              <div className="flex items-center bg-slate-800 rounded-full p-0.5">
                <button onClick={() => setChatMode('global')}
                  className={clsx("px-3 py-0.5 rounded-full text-xs transition-colors",
                    chatMode === 'global' ? "bg-slate-600 text-white" : "text-slate-400 hover:text-white")}>
                  全局
                </button>
                <button onClick={() => {
                  setChatMode('custom')
                  if (!config?.has_user_config) setShowSettings(true)
                }}
                  className={clsx("px-3 py-0.5 rounded-full text-xs transition-colors",
                    chatMode === 'custom' ? "bg-slate-600 text-white" : "text-slate-400 hover:text-white")}>
                  自定义
                </button>
              </div>
            ) : config?.has_user_config ? (
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">个人配置</span>
            ) : (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">未配置</span>
            )}
          </div>
          <button onClick={() => setShowSettings(true)}
            className="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800">
            <Settings size={18} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 && !streaming && (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <Bot size={48} className="mb-4 text-slate-600" />
              <p className="text-lg mb-2">IntelHub AI 助手</p>
              <p className="text-sm text-slate-600 max-w-md text-center">
                {effectiveConfigured
                  ? '可以问我关于投资情报、数据采集、系统状态等问题。我会使用工具获取实时数据来回答你。'
                  : '请先配置你自己的 API Key，或联系管理员开通会员。'}
              </p>
              {!effectiveConfigured && (
                <button onClick={() => setShowSettings(true)}
                  className="mt-4 px-4 py-2 text-sm bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors">
                  配置 API Key
                </button>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {streaming && (
            <StreamingBubble content={streamContent} events={streamEvents} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="px-6 py-4 border-t border-slate-800 flex-shrink-0">
          <div className="flex gap-2 items-end">
            {/* Model selector */}
            {models.length > 0 && (
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-sky-500 shrink-0"
                style={{ maxHeight: '42px' }}>
                <option value="">{config?.model || '默认模型'}</option>
                {models.map(m => (
                  <option key={m.id} value={m.id}>{m.display_name || m.id}</option>
                ))}
              </select>
            )}
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={effectiveConfigured ? '输入消息... (Enter 发送, Shift+Enter 换行)' : '请先配置 API Key'}
              disabled={!effectiveConfigured || streaming}
              rows={1}
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 resize-none disabled:opacity-50"
              style={{ minHeight: '42px', maxHeight: '120px' }}
              onInput={e => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
              }}
            />
            <button
              onClick={handleSend}
              disabled={!effectiveConfigured || streaming || !input.trim()}
              className="p-2.5 bg-sky-500 text-white rounded-xl hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0">
              {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>

      {/* Settings modal */}
      <SettingsModal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        config={config}
        onSave={() => loadConfig()}
      />
    </div>
  )
}
