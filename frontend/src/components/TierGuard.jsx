import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Crown, ArrowRight } from 'lucide-react'

const TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']
const TIER_NAMES = { free: 'Free', v1: 'V1', v2: 'V2', v3: 'V3', v4: 'V4', v5: 'V5' }

export default function TierGuard({ minTier, children }) {
  const user = api.getUser() || {}
  const tierIdx = TIER_ORDER.indexOf(user.tier || 'free')
  const minIdx = TIER_ORDER.indexOf(minTier)

  if (tierIdx >= minIdx) return children

  return <UpgradePrompt minTier={minTier} currentTier={user.tier || 'free'} />
}

function UpgradePrompt({ minTier, currentTier }) {
  const navigate = useNavigate()
  const tierName = { v2: 'V2 基础版', v3: 'V3 进阶版', v4: 'V4 专业版', v5: 'V5 旗舰版' }[minTier] || minTier

  return (
    <div className="max-w-lg mx-auto text-center py-20">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center mx-auto mb-5">
        <Crown size={32} className="text-amber-400" />
      </div>
      <h2 className="text-xl font-bold text-white mb-2">需要升级到 {tierName}</h2>
      <p className="text-sm text-slate-400 mb-6">
        当前等级为 <span className="text-white font-medium">{currentTier.toUpperCase()}</span>，此功能需要 <span className="text-amber-400 font-medium">{tierName}</span> 及以上
      </p>
      <button onClick={() => navigate('/pricing')}
        className="inline-flex items-center gap-2 bg-gradient-to-r from-amber-500 to-orange-500 text-white px-6 py-3 rounded-xl text-sm font-semibold hover:from-amber-600 hover:to-orange-600 transition-all shadow-lg shadow-amber-500/20">
        查看会员方案 <ArrowRight size={16} />
      </button>
    </div>
  )
}
