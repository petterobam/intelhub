import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import { Upload, Link, Trash2, FileText, Crown, Loader2, CheckCircle, AlertCircle, X, HardDrive } from 'lucide-react'
import clsx from 'clsx'

const TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']
const ALLOWED_EXTS = ['.pdf', '.txt', '.md', '.docx']

export default function Uploads() {
  const user = api.getUser() || {}
  const tierIdx = TIER_ORDER.indexOf(user.tier || 'free')
  const isV5 = tierIdx >= TIER_ORDER.indexOf('v5')

  const [files, setFiles] = useState([])
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState(null)
  const [urlInput, setUrlInput] = useState('')
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const [fRes, qRes] = await Promise.all([
        api.get('/api/v1/uploads'),
        api.get('/api/v1/uploads/quota'),
      ])
      setFiles(fRes.data?.data || [])
      setQuota(qRes.data?.data || null)
    } catch { }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (!isV5) { setLoading(false); return }
    load()
  }, [load, isV5])

  // Poll for pending/parsing files
  useEffect(() => {
    if (!isV5) return
    const hasPending = files.some(f => f.status === 'pending' || f.status === 'parsing' || f.status === 'fetching')
    if (!hasPending) return
    const timer = setTimeout(load, 3000)
    return () => clearTimeout(timer)
  }, [files, isV5, load])

  const showMsg = (text, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 4000)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTS.includes(ext)) {
      showMsg(`不支持的文件类型: ${ext}`, false)
      return
    }
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post('/api/v1/uploads', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      showMsg(`${file.name} 上传成功，解析中...`)
      load()
    } catch (e) {
      showMsg(e.response?.data?.error?.message || e.message, false)
    }
    e.target.value = ''
  }

  const handleUrlFetch = async () => {
    if (!urlInput.trim()) return
    try {
      await api.post('/api/v1/uploads/url', { url: urlInput.trim() })
      showMsg('URL 抓取已启动')
      setUrlInput('')
      load()
    } catch (e) {
      showMsg(e.response?.data?.error?.message || e.message, false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此文件？')) return
    try {
      await api.delete(`/api/v1/uploads/${id}`)
      showMsg('已删除')
      load()
    } catch (e) { showMsg(e.message, false) }
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTS.includes(ext)) {
      showMsg(`不支持的文件类型: ${ext}`, false)
      return
    }
    const formData = new FormData()
    formData.append('file', file)
    try {
      await api.post('/api/v1/uploads', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      showMsg(`${file.name} 上传成功，解析中...`)
      load()
    } catch (e) {
      showMsg(e.response?.data?.error?.message || e.message, false)
    }
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + 'B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
  }

  const statusConfig = {
    pending: { label: '等待', color: 'text-slate-400', bg: 'bg-slate-700/50' },
    parsing: { label: '解析中', color: 'text-blue-400', bg: 'bg-blue-500/10' },
    fetching: { label: '抓取中', color: 'text-blue-400', bg: 'bg-blue-500/10' },
    ready: { label: '已就绪', color: 'text-green-400', bg: 'bg-green-500/10' },
    error: { label: '错误', color: 'text-red-400', bg: 'bg-red-500/10' },
  }

  if (loading) return <div className="text-slate-400 py-8 text-center"><Loader2 className="animate-spin inline mr-2" />加载中...</div>

  if (!isV5) {
    return (
      <div className="text-center py-16">
        <Crown size={48} className="mx-auto text-slate-600 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">需要升级</h2>
        <p className="text-slate-400 text-sm">文件上传功能需要 V5 等级</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 w-full">
      <div>
        <h2 className="text-2xl font-bold text-white">文件上传</h2>
        <p className="text-xs text-slate-500 mt-1">上传 PDF/TXT/MD/DOCX 或抓取网页，自动纳入个人知识库</p>
      </div>

      {msg && (
        <div className={clsx("flex items-center gap-2 px-4 py-2 rounded-lg text-sm",
          msg.ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
          {msg.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {msg.text}
        </div>
      )}

      {/* Upload area */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5 space-y-4">
        <div
          className="border-2 border-dashed border-slate-600 rounded-xl p-8 text-center cursor-pointer hover:border-sky-500 transition-colors"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
        >
          <Upload size={32} className="mx-auto text-slate-500 mb-3" />
          <p className="text-sm text-slate-400">拖拽文件到此处，或点击选择</p>
          <p className="text-xs text-slate-600 mt-1">支持 {ALLOWED_EXTS.join(', ')}，最大 10MB</p>
          <input ref={fileInputRef} type="file" accept={ALLOWED_EXTS.join(',')} onChange={handleFileUpload} className="hidden" />
        </div>

        <div className="flex gap-2">
          <input value={urlInput} onChange={e => setUrlInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleUrlFetch()}
            placeholder="输入网页 URL 抓取内容..."
            className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500" />
          <button onClick={handleUrlFetch} disabled={!urlInput.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-sky-500/20 text-sky-400 rounded-lg text-sm hover:bg-sky-500/30 disabled:opacity-50">
            <Link size={14} /> 抓取
          </button>
        </div>
      </div>

      {/* Quota */}
      {quota && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <HardDrive size={14} />
              存储空间
            </div>
            <span className="text-xs text-slate-400">{quota.storage_used_mb} / {quota.storage_limit_mb} MB</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div className="bg-sky-500 h-2 rounded-full transition-all"
              style={{ width: `${Math.min(100, (quota.storage_used / quota.storage_limit) * 100)}%` }} />
          </div>
        </div>
      )}

      {/* File list */}
      <div className="space-y-2">
        {files.map(f => {
          const sc = statusConfig[f.status] || statusConfig.pending
          return (
            <div key={f.id} className="bg-slate-800 rounded-xl border border-slate-700 p-4 flex items-center gap-3">
              <FileText size={20} className="text-slate-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">{f.filename}</div>
                <div className="flex items-center gap-3 mt-1">
                  <span className={clsx('text-xs px-1.5 py-0.5 rounded', sc.bg, sc.color)}>
                    {(f.status === 'parsing' || f.status === 'fetching') && <Loader2 size={10} className="inline animate-spin mr-1" />}
                    {sc.label}
                  </span>
                  {f.size > 0 && <span className="text-xs text-slate-600">{formatSize(f.size)}</span>}
                  {f.char_count > 0 && <span className="text-xs text-slate-600">{f.char_count} 字</span>}
                  {f.status === 'ready' && <span className="text-xs text-green-500/60">已纳入知识库</span>}
                </div>
                {f.status === 'error' && f.parse_error && (
                  <div className="text-xs text-red-400 mt-1 truncate" title={f.parse_error}>{f.parse_error}</div>
                )}
              </div>
              <button onClick={() => handleDelete(f.id)} className="text-slate-500 hover:text-red-400 shrink-0">
                <Trash2 size={15} />
              </button>
            </div>
          )
        })}
        {files.length === 0 && (
          <div className="text-center text-slate-500 py-12">暂无上传文件</div>
        )}
      </div>
    </div>
  )
}
