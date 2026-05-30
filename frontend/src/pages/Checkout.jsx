import { useState, useEffect } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { api } from "../api/client"
import { CheckCircle, XCircle, Loader2, ArrowLeft, QrCode } from "lucide-react"

export default function Checkout() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const status = params.get("status")
  const orderId = params.get("order")
  const qrCode = params.get("qr")
  const qrImageUrl = params.get("qr_img")
  const [orderInfo, setOrderInfo] = useState(null)
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    if (qrCode && orderId) {
      startPolling()
    } else if (status === "success" && orderId) {
      startPolling()
    }
  }, [status, orderId, qrCode])

  const startPolling = () => {
    if (polling) return
    setPolling(true)
    let attempts = 0
    const maxAttempts = 60

    const poll = async () => {
      try {
        const res = await api.post("/api/v1/payments/verify", { order_id: orderId })
        const data = res.data?.data || res.data || {}
        if (data.status === "paid") {
          setOrderInfo(data)
          setPolling(false)
          return
        }
      } catch { /* ignore */ }

      attempts++
      if (attempts < maxAttempts) {
        setTimeout(poll, 3000)
      } else {
        setPolling(false)
      }
    }

    poll()
  }

  if (status === "cancel") {
    return (
      <div className="max-w-md mx-auto mt-20 text-center">
        <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-8">
          <XCircle size={48} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">支付已取消</h2>
          <p className="text-sm text-slate-400 mb-6">你取消了本次支付，未产生任何费用。</p>
          <button
            onClick={() => navigate("/pricing")}
            className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 text-sm transition-colors"
          >
            返回会员方案
          </button>
        </div>
      </div>
    )
  }

  if (orderInfo) {
    return (
      <div className="max-w-md mx-auto mt-20 text-center">
        <div className="bg-[#111a2e] border border-emerald-500/20 rounded-xl p-8">
          <CheckCircle size={48} className="text-emerald-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">支付成功</h2>
          <p className="text-sm text-slate-400 mb-1">已激活 {orderInfo.tier?.toUpperCase()} 会员</p>
          {orderInfo.paid_at && (
            <p className="text-xs text-slate-500 mb-6">
              {new Date(orderInfo.paid_at).toLocaleString("zh-CN")}
            </p>
          )}
          <button
            onClick={() => { api.clearToken(); window.location.href = "/login" }}
            className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 text-sm transition-colors"
          >
            开始使用
          </button>
        </div>
      </div>
    )
  }

  // QR code mode (XunHuPay / etc.)
  if (qrCode && orderId) {
    return (
      <div className="max-w-sm mx-auto mt-16 text-center">
        <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-8">
          <QrCode size={40} className="text-sky-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-white mb-2">扫码支付</h2>
          <p className="text-xs text-slate-500 mb-5">请使用微信或支付宝扫描下方二维码完成支付</p>

          {qrImageUrl ? (
            <div className="bg-white rounded-lg p-3 mx-auto w-fit mb-5">
              <img src={qrImageUrl} alt="支付二维码" className="w-48 h-48" />
            </div>
          ) : (
            <div className="bg-white rounded-lg p-3 mx-auto w-fit mb-5">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrCode)}`}
                alt="支付二维码"
                className="w-48 h-48"
              />
            </div>
          )}

          {polling && (
            <div className="flex items-center justify-center gap-2 text-xs text-slate-400 mb-4">
              <Loader2 size={14} className="animate-spin" />
              等待支付确认...
            </div>
          )}

          <div className="flex gap-3 justify-center">
            <button
              onClick={startPolling}
              disabled={polling}
              className="px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 text-xs transition-colors disabled:opacity-50"
            >
              检查支付状态
            </button>
            <button
              onClick={() => navigate("/pricing")}
              className="px-3 py-1.5 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 text-xs transition-colors"
            >
              返回
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (polling) {
    return (
      <div className="max-w-md mx-auto mt-20 text-center">
        <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-8">
          <Loader2 size={48} className="text-blue-400 mx-auto mb-4 animate-spin" />
          <h2 className="text-xl font-bold text-white mb-2">确认支付中...</h2>
          <p className="text-sm text-slate-400">正在等待支付结果，请稍候</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto mt-20 text-center">
      <div className="bg-[#111a2e] border border-[#1a2540] rounded-xl p-8">
        <ArrowLeft size={48} className="text-slate-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">等待支付</h2>
        <p className="text-sm text-slate-400 mb-6">
          支付结果确认中，完成后会自动刷新。如已支付，请稍等片刻。
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={startPolling}
            className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 text-sm transition-colors"
          >
            检查支付状态
          </button>
          <button
            onClick={() => navigate("/pricing")}
            className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 text-sm transition-colors"
          >
            返回
          </button>
        </div>
      </div>
    </div>
  )
}
