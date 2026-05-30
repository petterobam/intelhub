import { useState, useEffect } from 'react'
import { api } from '../api/client'

// ── 品牌 SVG 图标 ────────────────────────────────────────────────────

function GitHubIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

function GoogleIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  )
}

function MicrosoftIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
      <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
    </svg>
  )
}

function DiscordIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  )
}

function WeChatIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 01.213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 00.167-.054l1.903-1.114a.864.864 0 01.717-.098 10.16 10.16 0 002.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 01-1.162 1.178A1.17 1.17 0 014.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 01-1.162 1.178 1.17 1.17 0 01-1.162-1.178c0-.651.52-1.18 1.162-1.18zm3.307 4.28c-3.813 0-6.905 2.648-6.905 5.917 0 3.269 3.092 5.917 6.905 5.917a8.07 8.07 0 002.346-.348.67.67 0 01.558.076l1.463.857a.262.262 0 00.132.044c.128 0 .232-.108.232-.241 0-.06-.023-.117-.038-.174l-.3-1.133a.464.464 0 01.166-.515C21.138 19.453 22 17.842 22 16.188c0-3.269-3.092-5.917-6.905-5.917v-.001zM13.56 14.3c.499 0 .904.411.904.918a.911.911 0 01-.904.917.911.911 0 01-.903-.917c0-.507.404-.918.903-.918zm4.652 0c.499 0 .904.411.904.918a.911.911 0 01-.904.917.911.911 0 01-.903-.917c0-.507.404-.918.903-.918z" />
    </svg>
  )
}

function FeishuIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.882 19.225L11.28 3.017a.874.874 0 011.536.017l3.947 7.784-5.29 3.415a.5.5 0 00-.156.697l2.632 4.396H3.645a.874.874 0 01-.763-1.101zm12.074 1.101l-3.136-5.237 5.778-3.733 3.603 7.11a.874.874 0 01-.778 1.26h-5.467z" />
    </svg>
  )
}

// ── Provider 元信息 ──────────────────────────────────────────────────

const PROVIDER_META = {
  github: { name: 'GitHub', icon: GitHubIcon, primary: true, className: 'bg-slate-800 hover:bg-slate-700 text-white border-slate-600' },
  google: { name: 'Google', icon: GoogleIcon, primary: true, className: 'bg-white hover:bg-gray-100 text-gray-700 border-gray-300' },
  wechat: { name: '微信', icon: WeChatIcon, primary: false, className: 'bg-[#07C160]/15 hover:bg-[#07C160]/25 text-[#07C160] border-[#07C160]/30' },
  feishu: { name: '飞书', icon: FeishuIcon, primary: false, className: 'bg-[#3370ff]/15 hover:bg-[#3370ff]/25 text-[#6ba3ff] border-[#3370ff]/30' },
  microsoft: { name: 'Microsoft', icon: MicrosoftIcon, primary: false, className: 'bg-slate-800/40 hover:bg-slate-800/60 text-slate-300 border-slate-700/50' },
  discord: { name: 'Discord', icon: DiscordIcon, primary: false, className: 'bg-[#5865F2]/20 hover:bg-[#5865F2]/30 text-[#8b9bff] border-[#5865F2]/30' },
}

// ── OAuthButtons 组件 ─────────────────────────────────────────────────

export default function OAuthButtons() {
  const [providers, setProviders] = useState(null)

  useEffect(() => {
    api.get('/api/v1/oauth/providers')
      .then(res => setProviders(res.data?.data || {}))
      .catch(() => setProviders({}))
  }, [])

  // 还在加载或没有配置任何 provider
  if (!providers) return null
  const available = Object.keys(providers)
  if (available.length === 0) return null

  const primaryProviders = available.filter(k => PROVIDER_META[k]?.primary)
  const secondaryProviders = available.filter(k => !PROVIDER_META[k]?.primary)

  const handleClick = (provider) => {
    window.location.href = `/api/v1/oauth/${provider}`
  }

  return (
    <div className="space-y-3">
      {/* 主登录按钮: GitHub + Google */}
      {primaryProviders.length > 0 && (
        <div className="flex gap-2">
          {primaryProviders.map(key => {
            const meta = PROVIDER_META[key]
            const Icon = meta.icon
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleClick(key)}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium border transition-all ${meta.className}`}
              >
                <Icon size={18} />
                {meta.name}
              </button>
            )
          })}
        </div>
      )}

      {/* 分隔线 */}
      {primaryProviders.length > 0 && (
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-700/50" />
          <span className="text-xs text-slate-500">或使用邮箱</span>
          <div className="flex-1 h-px bg-slate-700/50" />
        </div>
      )}

      {/* 次要登录按钮: 微信 / 飞书 / Microsoft / Discord */}
      {secondaryProviders.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {secondaryProviders.map(key => {
            const meta = PROVIDER_META[key]
            const Icon = meta.icon
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleClick(key)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border transition-all ${meta.className}`}
              >
                <Icon size={14} />
                {meta.name}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
