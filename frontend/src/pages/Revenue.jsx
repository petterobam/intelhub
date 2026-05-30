import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { DollarSign, TrendingUp, Calendar, Users, Filter } from 'lucide-react'
import clsx from 'clsx'

const STATUS_MAP = { paid: '已支付', pending: '待支付', failed: '失败', refunded: '已退款' }
const STATUS_COLORS = { paid: 'text-emerald-400', pending: 'text-yellow-400', failed: 'text-red-400', refunded: 'text-slate-400' }
const STATUS_BG = { paid: 'bg-emerald-500/20 text-emerald-400', pending: 'bg-yellow-500/20 text-yellow-400', failed: 'bg-red-500/20 text-red-400', refunded: 'bg-slate-500/20 text-slate-400' }
const TIER_NAMES = { v1: 'V1', v2: 'V2', v3: 'V3', v4: 'V4' }

function fmt(yuan) {
  if (!yuan) return '¥0.00'
  return '¥' + (yuan / 100).toFixed(2)
}

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
  const max = Math.max(...data.map(d => d.amount), 1)

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-white font-semibold mb-4">收入趋势（近 30 天）</h3>
      <div className="flex items-end gap-[3px] h-40">
        {data.map((d, i) => {
          const pct = (d.amount / max) * 100
          const isToday = i === data.length - 1
          return (
            <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group relative">
              <div
                className={clsx(
                  "w-full rounded-t transition-all duration-200 min-h-[2px]",
                  isToday ? "bg-sky-500" : "bg-sky-500/40 hover:bg-sky-500/60"
                )}
                style={{ height: `${Math.max(pct, 1)}%` }}
              />
              {/* tooltip */}
              <div className="absolute bottom-full mb-2 hidden group-hover:block z-10">
                <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-lg">
                  <div className="text-slate-400">{d.date}</div>
                  <div className="text-white font-medium">{fmt(d.amount)}</div>
                  <div className="text-slate-500">{d.count} 笔</div>
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
    </div>
  )
}

function DistBlock({ title, data }) {
  const entries = Object.entries(data)
  if (!entries.length) return null
  const total = entries.reduce((s, [, v]) => s + (v.amount || 0), 0)

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-white font-semibold mb-4">{title}</h3>
      <div className="space-y-3">
        {entries.map(([key, val]) => {
          const pct = total ? ((val.amount || 0) / total * 100) : 0
          return (
            <div key={key}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-300">{TIER_NAMES[key] || key}</span>
                <span className="text-slate-400">{fmt(val.amount)} <span className="text-slate-600 text-xs">({val.count}笔)</span></span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-sky-500/60 rounded-full transition-all" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Revenue() {
  const [stats, setStats] = useState(null)
  const [orders, setOrders] = useState({ items: [], total: 0 })
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState({ status: '', provider: '' })
  const [loading, setLoading] = useState(true)
  const [showCreateOrder, setShowCreateOrder] = useState(false)
  const [orderForm, setOrderForm] = useState({ user_email: '', tier: 'v2' })
  const [orderSubmitting, setOrderSubmitting] = useState(false)

  useEffect(() => { loadStats() }, [])
  useEffect(() => { loadOrders() }, [page, filter])

  const loadStats = async () => {
    try {
      const res = await api.get('/api/v1/payments/admin/stats')
      setStats(res.data?.data || res.data || {})
    } catch { }
    setLoading(false)
  }

  const loadOrders = async () => {
    try {
      const params = new URLSearchParams({ page, per_page: 15 })
      if (filter.status) params.set('status', filter.status)
      if (filter.provider) params.set('provider', filter.provider)
      const res = await api.get(`/api/v1/payments/admin/orders?${params}`)
      const d = res.data?.data || res.data || {}
      setOrders({ items: d.items || [], total: d.total || 0 })
    } catch { }
  }

  const totalPages = Math.ceil(orders.total / 15)

  const handleCreateOrder = async () => {
    if (!orderForm.user_email.trim()) return alert('请输入用户邮箱')
    setOrderSubmitting(true)
    try {
      await api.post('/api/v1/payments/admin/create-order', orderForm)
      setShowCreateOrder(false)
      setOrderForm({ user_email: '', tier: 'v2' })
      loadStats()
      loadOrders()
    } catch (e) {
      alert(e.response?.data?.error || e.message)
    } finally {
      setOrderSubmitting(false)
    }
  }

  if (loading) return <div className="text-slate-400">加载中...</div>

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-white tracking-tight">收益统计</h2>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={DollarSign} label="累计收入" value={fmt(stats?.total_revenue)} sub={`${stats?.total_count || 0} 笔`} color="sky" />
        <StatCard icon={Calendar} label="本月收入" value={fmt(stats?.monthly_revenue)} sub={`${stats?.monthly_count || 0} 笔`} color="blue" />
        <StatCard icon={TrendingUp} label="今日收入" value={fmt(stats?.today_revenue)} sub={`${stats?.today_count || 0} 笔`} color="emerald" />
        <StatCard icon={Users} label="付费用户" value={stats?.paid_users || 0} color="purple" />
      </div>

      {/* 趋势图 */}
      <TrendChart data={stats?.daily_trend} />

      {/* 分布 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DistBlock title="档位分布" data={stats?.tier_distribution || {}} />
        <DistBlock title="渠道分布" data={stats?.provider_distribution || {}} />
      </div>

      {/* 订单流水 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <h3 className="text-white font-semibold">订单流水</h3>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowCreateOrder(true)}
              className="text-xs bg-sky-500/20 text-sky-400 px-3 py-1.5 rounded-lg hover:bg-sky-500/30 transition-colors font-medium">
              + 手动添加订单
            </button>
            <Filter size={14} className="text-slate-500" />
            <select value={filter.status} onChange={e => { setFilter(f => ({ ...f, status: e.target.value })); setPage(1) }}
              className="bg-slate-900 border border-slate-600 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-sky-500">
              <option value="">全部状态</option>
              {Object.entries(STATUS_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={filter.provider} onChange={e => { setFilter(f => ({ ...f, provider: e.target.value })); setPage(1) }}
              className="bg-slate-900 border border-slate-600 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-sky-500">
              <option value="">全部渠道</option>
              <option value="alipay">支付宝</option>
              <option value="stripe">Stripe</option>
              <option value="xunhupay">虎皮椒</option>
              <option value="manual">手动</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-700">
                <th className="text-left px-5 py-3 font-medium">订单号</th>
                <th className="text-left px-3 py-3 font-medium">用户</th>
                <th className="text-left px-3 py-3 font-medium">档位</th>
                <th className="text-left px-3 py-3 font-medium">金额</th>
                <th className="text-left px-3 py-3 font-medium">渠道</th>
                <th className="text-left px-3 py-3 font-medium">状态</th>
                <th className="text-left px-3 py-3 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {orders.items.map(o => (
                <tr key={o.id} className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors">
                  <td className="px-5 py-3 text-slate-400 font-mono text-xs">{o.id}</td>
                  <td className="px-3 py-3 text-slate-300 truncate max-w-[180px]">{o.user_email || '-'}</td>
                  <td className="px-3 py-3 text-slate-300">{TIER_NAMES[o.tier] || o.tier}</td>
                  <td className="px-3 py-3 text-white font-medium">{fmt(o.amount)}</td>
                  <td className="px-3 py-3 text-slate-400">
                    {o.provider === 'alipay' ? '支付宝' : o.provider === 'stripe' ? 'Stripe' : o.provider === 'xunhupay' ? '虎皮椒' : o.provider === 'manual' ? '手动' : o.provider}
                  </td>
                  <td className="px-3 py-3">
                    <span className={clsx("text-xs px-2 py-0.5 rounded", STATUS_BG[o.status] || 'bg-slate-600 text-slate-300')}>
                      {STATUS_MAP[o.status] || o.status}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-slate-500 text-xs">
                    {o.paid_at ? new Date(o.paid_at).toLocaleString('zh-CN') : new Date(o.created_at).toLocaleString('zh-CN')}
                  </td>
                </tr>
              ))}
              {orders.items.length === 0 && (
                <tr><td colSpan={7} className="text-center py-10 text-slate-500">暂无订单</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-500">共 {orders.total} 条</span>
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

      {/* Manual order creation modal */}
      {showCreateOrder && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-6 w-96">
            <h3 className="text-white font-semibold mb-4">手动添加订单</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">用户邮箱 *</label>
                <input type="text" value={orderForm.user_email}
                  onChange={e => setOrderForm(f => ({ ...f, user_email: e.target.value }))}
                  placeholder="user@example.com"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500" />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">会员档位 *</label>
                <select value={orderForm.tier}
                  onChange={e => setOrderForm(f => ({ ...f, tier: e.target.value }))}
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500">
                  <option value="v1">V1 - ¥9/月</option>
                  <option value="v2">V2 - ¥29/月</option>
                  <option value="v3">V3 - ¥59/月</option>
                  <option value="v4">V4 - ¥99/月</option>
                </select>
              </div>
              <p className="text-xs text-slate-500">订单将以"已支付"状态创建，并立即激活用户会员。</p>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={handleCreateOrder} disabled={orderSubmitting}
                className="flex-1 bg-sky-500/20 text-sky-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-sky-500/30 transition-colors disabled:opacity-50">
                {orderSubmitting ? '创建中...' : '创建订单'}
              </button>
              <button onClick={() => { setShowCreateOrder(false); setOrderForm({ user_email: '', tier: 'v2' }) }}
                className="flex-1 bg-slate-700 text-slate-300 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-600 transition-colors">
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
