import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Send, CheckCircle, XCircle, Filter, Mail, MessageSquare, Bell, Radio } from 'lucide-react'
import clsx from 'clsx'

const CHANNEL_MAP = { email: '邮件', feishu: '飞书', dingtalk: '钉钉', telegram: 'Telegram' }
const CHANNEL_ICONS = { email: Mail, feishu: MessageSquare, dingtalk: Bell, telegram: Radio }
const STATUS_BG = { sent: 'bg-emerald-500/20 text-emerald-400', failed: 'bg-red-500/20 text-red-400', error: 'bg-red-500/20 text-red-400' }
const STATUS_LABEL = { sent: '成功', failed: '失败', error: '异常' }

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex items-center gap-3 mb-3">
        <div className={clsx("p-2 rounded-lg", `bg-${color}-500/20`)}>
          <Icon size={20} className={clsx(`text-${color}-400`)} />
        </div>
        <span className="text-slate-400 text-sm">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  )
}

function TrendChart({ data }) {
  if (!data?.length) return null
  const max = Math.max(...data.map(d => d.total), 1)
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-white font-semibold mb-4">推送趋势（近 7 天）</h3>
      <div className="flex items-end gap-2 h-32">
        {data.map(d => {
          const pct = (d.total / max) * 100
          return (
            <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group relative">
              <div className="w-full relative rounded-t overflow-hidden min-h-[2px]"
                style={{ height: `${Math.max(pct, 2)}%` }}>
                <div className="absolute inset-0 bg-emerald-500/60" />
                {d.failed > 0 && (
                  <div className="absolute bottom-0 left-0 right-0 bg-red-500/70"
                    style={{ height: `${((d.failed / d.total) * 100)}%` }} />
                )}
              </div>
              <div className="absolute bottom-full mb-2 hidden group-hover:block z-10">
                <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-lg">
                  <div className="text-slate-400">{d.date.slice(5)}</div>
                  <div className="text-emerald-400">{d.sent} 成功</div>
                  {d.failed > 0 && <div className="text-red-400">{d.failed} 失败</div>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex justify-between mt-2 text-[10px] text-slate-600">
        <span>{data[0]?.date?.slice(5)}</span>
        <span>{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
      <div className="flex items-center gap-4 mt-3 text-[10px]">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-emerald-500/60" /> 成功</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-red-500/70" /> 失败</span>
      </div>
    </div>
  )
}

function ChannelSection({ title, data }) {
  const entries = Object.entries(data || {})
  if (!entries.length) return null
  const maxCount = Math.max(...entries.map(([, v]) => v.total), 1)
  return (
    <div>
      <h4 className="text-xs text-slate-500 font-medium mb-3">{title}</h4>
      <div className="space-y-3">
        {entries.map(([ct, v]) => {
          const Icon = CHANNEL_ICONS[ct] || Send
          return (
            <div key={ct}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="flex items-center gap-2 text-slate-300">
                  <Icon size={14} />{CHANNEL_MAP[ct] || ct}
                </span>
                <span className="text-slate-400 text-xs">
                  {v.total}
                  <span className="text-emerald-500 ml-1">{v.sent}成功</span>
                  {v.failed > 0 && <span className="text-red-400 ml-1">{v.failed}失败</span>}
                </span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500/50 rounded-full" style={{ width: `${(v.total / maxCount) * 100}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ChannelDist({ todayData, monthData }) {
  const hasToday = Object.keys(todayData || {}).length > 0
  const hasMonth = Object.keys(monthData || {}).length > 0
  if (!hasToday && !hasMonth) return null
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-white font-semibold mb-4">渠道分布</h3>
      {hasToday && <ChannelSection title="今日" data={todayData} />}
      {hasToday && hasMonth && <div className="border-t border-slate-700/50 my-4" />}
      {hasMonth && <ChannelSection title="本月" data={monthData} />}
    </div>
  )
}

function TopUsers({ users }) {
  if (!users?.length) return null
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-white font-semibold mb-4">活跃用户（本月）</h3>
      <div className="space-y-2">
        {users.map((u, i) => (
          <div key={i} className="flex items-center gap-3 text-sm py-1.5 border-b border-slate-700/50 last:border-0">
            <span className={clsx("text-xs font-bold w-4",
              i === 0 ? 'text-yellow-400' : i === 1 ? 'text-slate-300' : i === 2 ? 'text-orange-400' : 'text-slate-600'
            )}>{i + 1}</span>
            <div className="flex-1 min-w-0">
              {u.nickname && <span className="text-white font-medium mr-1.5">{u.nickname}</span>}
              <span className="text-slate-500 text-xs truncate">{u.email}</span>
            </div>
            <span className="text-slate-500 text-xs shrink-0">{u.count} 次</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PushStats() {
  const [stats, setStats] = useState(null)
  const [logs, setLogs] = useState({ items: [], total: 0 })
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState({ status: '', channel_type: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadStats() }, [])
  useEffect(() => { loadLogs() }, [page, filter])

  const loadStats = async () => {
    try {
      const res = await api.get('/api/v1/admin/push-stats')
      setStats(res.data?.data || res.data || {})
    } catch { /* ignore */ }
    setLoading(false)
  }

  const loadLogs = async () => {
    try {
      const params = new URLSearchParams({ page, per_page: 15 })
      if (filter.status) params.set('status', filter.status)
      if (filter.channel_type) params.set('channel_type', filter.channel_type)
      const res = await api.get(`/api/v1/admin/push-logs?${params}`)
      const d = res.data?.data || res.data || {}
      setLogs({ items: d.items || [], total: d.total || 0 })
    } catch { /* ignore */ }
  }

  const totalPages = Math.ceil(logs.total / 15)

  if (loading) return <div className="text-slate-400">加载中...</div>

  const today = stats?.today || { total: 0, sent: 0, failed: 0 }
  const month = stats?.month || { total: 0, sent: 0, failed: 0 }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-white tracking-tight">推送统计</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Send} label="今日推送" value={today.total} color="sky"
          sub={`${today.sent} 成功 · ${today.failed} 失败`} />
        <StatCard icon={CheckCircle} label="今日成功" value={today.sent} color="emerald" />
        <StatCard icon={XCircle} label="今日失败" value={today.failed} color="red" />
        <StatCard icon={Send} label="本月推送" value={month.total} color="blue"
          sub={`累计 ${stats?.total || 0} 次`} />
      </div>

      <TrendChart data={stats?.daily_trend_7d || []} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ChannelDist todayData={stats?.channel_dist_today} monthData={stats?.channel_dist} />
        <TopUsers users={stats?.top_users || []} />
      </div>

      {/* 推送明细 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <h3 className="text-white font-semibold">推送明细</h3>
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-slate-500" />
            <select value={filter.status} onChange={e => { setFilter(f => ({ ...f, status: e.target.value })); setPage(1) }}
              className="bg-slate-900 border border-slate-600 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-sky-500">
              <option value="">全部状态</option>
              <option value="sent">成功</option>
              <option value="failed">失败</option>
              <option value="error">异常</option>
            </select>
            <select value={filter.channel_type} onChange={e => { setFilter(f => ({ ...f, channel_type: e.target.value })); setPage(1) }}
              className="bg-slate-900 border border-slate-600 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-sky-500">
              <option value="">全部渠道</option>
              {Object.entries(CHANNEL_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-700">
                <th className="text-left px-5 py-3 font-medium">报告</th>
                <th className="text-left px-3 py-3 font-medium">用户</th>
                <th className="text-left px-3 py-3 font-medium">渠道</th>
                <th className="text-left px-3 py-3 font-medium">状态</th>
                <th className="text-left px-3 py-3 font-medium">错误</th>
                <th className="text-left px-3 py-3 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {logs.items.map(l => (
                <tr key={l.id} className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors">
                  <td className="px-5 py-3 text-slate-300 truncate max-w-[220px]" title={l.report_path}>
                    {l.report_name || '-'}
                  </td>
                  <td className="px-3 py-3">
                    <div className="max-w-[180px]">
                      {l.user_nickname && <div className="text-slate-200 text-xs truncate">{l.user_nickname}</div>}
                      <div className="text-slate-500 text-xs truncate">{l.user_email || l.channel_key || '-'}</div>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-slate-400">{CHANNEL_MAP[l.channel_type] || l.channel_type}</td>
                  <td className="px-3 py-3">
                    <span className={clsx("text-xs px-2 py-0.5 rounded", STATUS_BG[l.status] || 'bg-slate-600 text-slate-300')}>
                      {STATUS_LABEL[l.status] || l.status}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-slate-500 text-xs truncate max-w-[200px]" title={l.error}>
                    {l.error || '-'}
                  </td>
                  <td className="px-3 py-3 text-slate-500 text-xs">
                    {l.created_at ? new Date(l.created_at).toLocaleString('zh-CN') : ''}
                  </td>
                </tr>
              ))}
              {logs.items.length === 0 && (
                <tr><td colSpan={6} className="text-center py-10 text-slate-500">暂无推送记录</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-500">共 {logs.total} 条</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                className="px-3 py-1 rounded text-xs bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-40">
                上一页
              </button>
              <span className="px-3 py-1 text-xs text-slate-400">{page} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="px-3 py-1 rounded text-xs bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-40">
                下一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
