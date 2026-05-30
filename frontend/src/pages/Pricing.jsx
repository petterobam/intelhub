import { useState, useEffect } from "react"
import { api } from "../api/client"
import { Check, X, Crown, Zap, Star, Sparkles } from "lucide-react"
import clsx from "clsx"

const TIER_ORDER = ["free", "v1", "v2", "v3", "v4"]

const TIERS = [
  {
    key: "free",
    name: "Free",
    price: "免费",
    period: "",
    desc: "体验基础功能",
    icon: Zap,
    color: "slate",
    features: [
      { text: "查看情报广场与系统报告", included: true },
      { text: "订阅报告推送", included: true },
      { text: "AI 对话 (每日 10 次)", included: true },
      { text: "个人任务管理", included: false, hint: "V2" },
      { text: "个人数据源", included: false, hint: "V3" },
      { text: "个人知识库", included: false, hint: "V4" },
    ],
  },
  {
    key: "v1",
    name: "V1",
    price: "¥9",
    period: "/月",
    desc: "轻度使用",
    icon: Zap,
    color: "blue",
    features: [
      { text: "Free 全部功能", included: true },
      { text: "个人偏好设置", included: true },
      { text: "自定义报告模板", included: true },
      { text: "AI 无限对话", included: false, hint: "V3" },
      { text: "个人数据源", included: false, hint: "V3" },
    ],
  },
  {
    key: "v2",
    name: "V2",
    price: "¥29",
    period: "/月",
    desc: "个人任务自动化",
    icon: Star,
    color: "sky",
    highlight: true,
    features: [
      { text: "V1 全部功能", included: true },
      { text: "个人任务 (≤3 个)", included: true },
      { text: "AI 对话 (每日 100 次)", included: true },
      { text: "个人数据源", included: false, hint: "V3" },
      { text: "个人知识库", included: false, hint: "V4" },
    ],
  },
  {
    key: "v3",
    name: "V3",
    price: "¥59",
    period: "/月",
    desc: "数据自由",
    icon: Sparkles,
    color: "purple",
    features: [
      { text: "V2 全部功能", included: true },
      { text: "AI 无限对话", included: true },
      { text: "个人数据源 (≤15)", included: true },
      { text: "RSS / B站 / YouTube", included: true },
      { text: "任务上限提升至 8 个", included: true },
      { text: "个人知识库", included: false, hint: "V4" },
    ],
  },
  {
    key: "v4",
    name: "V4",
    price: "¥99",
    period: "/月",
    desc: "旗舰全能",
    icon: Crown,
    color: "orange",
    features: [
      { text: "V3 全部功能", included: true },
      { text: "个人知识库", included: true },
      { text: "文件上传与管理", included: true },
      { text: "数据源上限 50 个", included: true },
      { text: "任务上限 20 个", included: true },
      { text: "优先技术支持", included: true },
    ],
  },
]

const COLOR_MAP = {
  slate: {
    border: "border-slate-700",
    bg: "bg-slate-800",
    btn: "bg-slate-700 text-slate-300 hover:bg-slate-600",
  },
  blue: {
    border: "border-blue-700",
    bg: "bg-blue-900/20",
    btn: "bg-blue-500/20 text-blue-400 hover:bg-blue-500/30",
  },
  sky: {
    border: "border-sky-500",
    bg: "bg-sky-900/20",
    btn: "bg-sky-500 text-white hover:bg-sky-600",
  },
  purple: {
    border: "border-purple-700",
    bg: "bg-purple-900/20",
    btn: "bg-purple-500/20 text-purple-400 hover:bg-purple-500/30",
  },
  orange: {
    border: "border-orange-500",
    bg: "bg-gradient-to-br from-orange-900/20 to-amber-900/20",
    btn: "bg-gradient-to-r from-orange-500 to-amber-500 text-white hover:from-orange-600 hover:to-amber-600",
  },
}

export default function Pricing() {
  const user = api.getUser() || {}
  const currentIdx = TIER_ORDER.indexOf(user.tier || "free")
  const [loading, setLoading] = useState(null)
  const [providers, setProviders] = useState([])
  const [showModal, setShowModal] = useState(null) // { tier, providers }
  const [showCustomModal, setShowCustomModal] = useState(null)

  useEffect(() => {
    loadProviders()
  }, [])

  const loadProviders = async () => {
    try {
      const res = await api.get("/api/v1/payments/providers")
      const list = res.data?.data || res.data || []
      setProviders(list)
    } catch { /* ignore */ }
  }

  const createOrder = async (tier, provider) => {
    const providerObj = providers.find(p => p.id === provider)
    if (providerObj?.type === 'custom') {
      setShowCustomModal(providerObj)
      return true
    }
    const res = await api.post("/api/v1/payments/create-order", { tier, provider })
    const d = res.data?.data || res.data || {}
    if (d.checkout_url && (provider === 'xunhupay' || provider === 'alipay')) {
      const params = new URLSearchParams({
        order: d.order_id,
        qr: d.checkout_url,
        qr_img: d.qrcode_url || '',
      })
      window.location.href = `/checkout?${params}`
      return true
    }
    if (d.checkout_url) {
      window.location.href = d.checkout_url
      return true
    }
    return false
  }

  const handleUpgrade = async (tier) => {
    if (loading || !providers.length) return

    if (providers.length === 1) {
      setLoading(tier)
      try {
        if (await createOrder(tier, providers[0].id)) return
      } catch { /* ignore */ }
      setLoading(null)
      alert("创建订单失败，请稍后重试")
      return
    }

    setShowModal({ tier, providers })
  }

  const selectProvider = async (provider) => {
    const tier = showModal.tier
    setShowModal(null)
    setLoading(tier)
    try {
      if (await createOrder(tier, provider)) return
    } catch { /* ignore */ }
    setLoading(null)
    alert("创建订单失败，请稍后重试")
  }

  return (
    <div className="max-w-5xl mx-auto space-y-10">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white tracking-tight">会员方案</h2>
        <p className="text-sm text-slate-500 mt-2">选择适合你的方案，解锁更多能力</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {TIERS.map((tier) => {
          const idx = TIER_ORDER.indexOf(tier.key)
          const isCurrent = idx === currentIdx
          const isOwned = idx <= currentIdx
          const colors = COLOR_MAP[tier.color]
          const Icon = tier.icon

          return (
            <div
              key={tier.key}
              className={clsx(
                "rounded-xl border p-4 flex flex-col transition-all duration-200",
                isCurrent
                  ? `${colors.border} ${colors.bg} ring-1 ring-current`
                  : "border-[#1a2540]/80 bg-[#111a2e]/60 hover:border-[#2a3f5f]/80 hover:bg-[#141e34]",
                tier.highlight && !isCurrent && "ring-1 ring-blue-500/20",
              )}
            >
              <div className="flex items-center gap-2 mb-3">
                <Icon size={18} className={clsx("text-" + tier.color + "-400")} />
                <span className="text-sm font-bold text-white">{tier.name}</span>
              </div>

              <div className="mb-1.5">
                <span className="text-2xl font-bold text-white tracking-tight">{tier.price}</span>
                {tier.period && <span className="text-xs text-slate-500 ml-0.5">{tier.period}</span>}
              </div>
              <p className="text-xs text-slate-500 mb-4">{tier.desc}</p>

              <div className="flex-1 space-y-1.5 mb-4">
                {tier.features.map((f, i) => (
                  <div key={i} className="flex items-start gap-1.5">
                    {f.included ? (
                      <Check size={12} className="text-emerald-400/80 mt-0.5 shrink-0" />
                    ) : (
                      <X size={12} className="text-slate-700 mt-0.5 shrink-0" />
                    )}
                    <span className={clsx("text-[11px] leading-snug", f.included ? "text-slate-300" : "text-slate-600")}>
                      {f.text}
                      {f.hint && <span className="text-slate-700 ml-1">({f.hint})</span>}
                    </span>
                  </div>
                ))}
              </div>

              {isCurrent ? (
                <div className="text-center py-2 px-3 rounded-lg bg-blue-500/10 text-blue-400 text-xs font-medium">
                  当前方案
                </div>
              ) : isOwned ? (
                <div className="text-center py-2 px-3 rounded-lg bg-white/[0.03] text-slate-500 text-xs">
                  已拥有
                </div>
              ) : (
                <button
                  onClick={() => handleUpgrade(tier.key)}
                  disabled={loading === tier.key}
                  className={clsx(
                    "w-full py-2 px-3 rounded-lg text-xs font-medium transition-all duration-200",
                    colors.btn,
                    loading === tier.key && "opacity-50 cursor-not-allowed",
                  )}
                >
                  {loading === tier.key ? "跳转中..." : "升级"}
                </button>
              )}
            </div>
          )
        })}
      </div>

      <div className="text-center text-xs text-slate-600">
        价格均为人民币，实际收费以支付页面为准。如有疑问请联系管理员。
      </div>

      {/* Provider selection modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-6 w-80">
            <h3 className="text-white font-semibold mb-4">选择支付方式</h3>
            <div className="space-y-2">
              {showModal.providers.map(p => (
                <button key={p.id}
                  onClick={() => selectProvider(p.id)}
                  className="w-full text-left px-4 py-3 rounded-lg border border-slate-700 hover:border-sky-500/50 hover:bg-slate-700/20 transition-colors">
                  <div className="text-sm text-white font-medium">{p.name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {p.type === 'qrcode' ? '扫码支付' : p.type === 'custom' ? '联系客服' : '跳转支付'}
                  </div>
                </button>
              ))}
            </div>
            <button onClick={() => setShowModal(null)}
              className="mt-4 w-full text-center text-xs text-slate-500 hover:text-slate-300 transition-colors">
              取消
            </button>
          </div>
        </div>
      )}

      {/* Custom payment info modal */}
      {showCustomModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-6 w-80 text-center">
            <h3 className="text-white font-semibold mb-2">{showCustomModal.name}</h3>
            {showCustomModal.description && (
              <p className="text-sm text-slate-400 mb-4 whitespace-pre-line">{showCustomModal.description}</p>
            )}
            {showCustomModal.image_url && (
              <div className="flex justify-center mb-4">
                <div className="bg-white rounded-lg p-3">
                  <img src={showCustomModal.image_url} alt="支付引导" className="w-52 h-52 object-contain" />
                </div>
              </div>
            )}
            <button onClick={() => setShowCustomModal(null)}
              className="mt-2 w-full text-center text-xs text-slate-500 hover:text-slate-300 transition-colors">
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
