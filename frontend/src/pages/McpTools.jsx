import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Cpu, RefreshCw, Globe, User } from 'lucide-react'

function ToolTable({ tools, scope }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-800 text-left text-slate-400">
          <th className="px-4 py-3 font-medium">工具名</th>
          <th className="px-4 py-3 font-medium">描述</th>
          <th className="px-4 py-3 font-medium">参数</th>
          <th className="px-4 py-3 font-medium w-24 text-center">范围</th>
          <th className="px-4 py-3 font-medium w-16 text-center">状态</th>
        </tr>
      </thead>
      <tbody>
        {tools.map((t, i) => (
          <tr key={t.name} className={i % 2 === 0 ? 'bg-slate-900/50' : 'bg-slate-800/30'}>
            <td className="px-4 py-3">
              <code className="text-sky-400 text-xs bg-sky-500/10 px-1.5 py-0.5 rounded">{t.name}</code>
            </td>
            <td className="px-4 py-3 text-slate-300 max-w-md">
              <span className="line-clamp-2">{t.description || '-'}</span>
            </td>
            <td className="px-4 py-3 text-slate-400 text-xs">
              {t.params && Object.keys(t.params).length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {Object.entries(t.params).map(([k, v]) => (
                    <span key={k} className="bg-slate-700 px-1.5 py-0.5 rounded">
                      {k}: <span className="text-amber-400">{v}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-slate-600">无参数</span>
              )}
            </td>
            <td className="px-4 py-3 text-center">
              <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                t.scope === 'personal'
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-sky-500/15 text-sky-400'
              }`}>
                {t.scope === 'personal' ? <User size={10} /> : <Globe size={10} />}
                {t.scope === 'personal' ? '个人' : '平台'}
              </span>
            </td>
            <td className="px-4 py-3 text-center">
              <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                可用
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function McpTools() {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchTools = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/api/v1/chat/mcp-tools')
      setTools(res.data?.data || [])
    } catch (e) {
      setError(e.response?.data?.error || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchTools() }, [])

  const platformTools = tools.filter(t => t.scope !== 'personal')
  const personalTools = tools.filter(t => t.scope === 'personal')

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Cpu size={24} className="text-sky-400" />
          <h1 className="text-xl font-bold text-white">MCP 工具管理</h1>
          <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
            {platformTools.length} 平台 + {personalTools.length} 个人
          </span>
        </div>
        <button onClick={fetchTools} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-300 text-sm px-4 py-3 rounded-lg mb-4">{error}</div>
      )}

      {loading && tools.length === 0 ? (
        <div className="text-slate-500 text-sm py-12 text-center">加载中...</div>
      ) : (
        <>
          {/* Platform tools */}
          {platformTools.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <Globe size={16} className="text-sky-400" />
                <h2 className="text-sm font-semibold text-slate-300">平台数据工具</h2>
                <span className="text-xs text-slate-500">{platformTools.length} 个</span>
              </div>
              <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
                <ToolTable tools={platformTools} scope="platform" />
              </div>
            </div>
          )}

          {/* Personal tools */}
          {personalTools.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <User size={16} className="text-emerald-400" />
                <h2 className="text-sm font-semibold text-slate-300">个人数据工具</h2>
                <span className="text-xs text-slate-500">{personalTools.length} 个</span>
                <span className="text-xs text-slate-600 bg-slate-800 px-2 py-0.5 rounded">仅返回当前用户的数据</span>
              </div>
              <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
                <ToolTable tools={personalTools} scope="personal" />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
