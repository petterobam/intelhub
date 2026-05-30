import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import { lazy, Suspense, useState } from 'react'
import { api } from './api/client'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import TaskDetail from './pages/TaskDetail'
import Crawlers from './pages/Crawlers'
import DataExplorer from './pages/DataExplorer'
import Reports from './pages/Reports'
import RssSources from './pages/RssSources'
import Health from './pages/Health'
import ScriptsTemplates from './pages/ScriptsTemplates'
import Knowledge from './pages/Knowledge'
import SettingsPage from './pages/Settings'
import Subscriptions from './pages/Subscriptions'
import Plaza from './pages/Plaza'
import PushChannels from './pages/PushChannels'
import McpTools from './pages/McpTools'
import PushStats from './pages/PushStats'
import About from './pages/About'
import { LayoutDashboard, Clock, Globe, Database, FileText, Heart, FileCode, MessageSquare, BookOpen, Settings as SettingsIcon, Mail, Rss, Layers, Activity, Send, Cpu, Flame, Menu, Info } from 'lucide-react'
import clsx from 'clsx'

const Chat = lazy(() => import('./pages/Chat'))

function NavLink({ to, icon: Icon, label }) {
  const loc = useLocation()
  const active = loc.pathname === to || (to !== '/' && loc.pathname.startsWith(to))
  return (
    <Link to={to} className={clsx(
      "flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all duration-200",
      active
        ? "bg-blue-500/10 text-blue-400 shadow-sm shadow-blue-500/5"
        : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
    )}>
      <Icon size={16} className={active ? "text-blue-400" : ""} />
      <span className="text-[13px] font-medium">{label}</span>
    </Link>
  )
}

const MENU = [
  {
    group: '情报中心', icon: Flame,
    items: [
      { to: '/plaza', icon: Flame, label: '情报广场' },
      { to: '/chat', icon: MessageSquare, label: 'AI 对话' },
    ]
  },
  {
    group: '数据采集', icon: Layers,
    items: [
      { to: '/crawlers', icon: Globe, label: '爬虫节点' },
      { to: '/tasks', icon: Clock, label: '任务管理' },
    ]
  },
  {
    group: '数据中心', icon: Database,
    items: [
      { to: '/data', icon: Database, label: '数据浏览' },
      { to: '/rss-sources', icon: Rss, label: 'RSS 管理' },
      { to: '/knowledge', icon: BookOpen, label: '知识库' },
      { to: '/reports', icon: FileText, label: '报告中心' },
    ]
  },
  {
    group: '系统运维', icon: Activity,
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/health', icon: Heart, label: '系统健康' },
      { to: '/scripts', icon: FileCode, label: '脚本与模板' },
      { to: '/subscriptions', icon: Mail, label: '订阅中心' },
      { to: '/push-channels', icon: Send, label: '推送渠道' },
      { to: '/settings', icon: SettingsIcon, label: '配置中心' },
      { to: '/push-stats', icon: Send, label: '推送统计' },
      { to: '/mcp-tools', icon: Cpu, label: 'MCP 工具' },
      { to: '/about', icon: Info, label: '关于平台' },
    ]
  },
]

function Sidebar({ onCloseMobile }) {
  const handleNavClick = () => {
    if (window.innerWidth < 768) onCloseMobile?.()
  }

  return (
    <aside className="w-60 bg-[#0d1322] flex-shrink-0 p-3 flex flex-col gap-1 h-full overflow-y-auto border-r border-[#1a2540]/60">
      <div className="px-3 py-4 mb-2">
        <h1 className="text-lg font-bold flex items-center gap-2.5 tracking-tight">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500/20 to-amber-500/10 border border-orange-500/20 flex items-center justify-center">
            <Flame size={16} className="text-orange-400" />
          </span>
          <span className="text-white">Intel<span className="text-blue-400">Hub</span></span>
        </h1>
        <p className="text-[11px] text-slate-500 mt-1.5 pl-[42px] tracking-wide">智能情报与投资分析平台</p>
      </div>
      <nav className="flex flex-col gap-0.5" onClick={handleNavClick}>
        {MENU.map(g => (
          <div key={g.group} className="mb-1">
            <div className="flex items-center gap-2 px-3 py-2 text-[10px] font-semibold text-slate-500/80 uppercase tracking-widest">
              <g.icon size={11} />
              {g.group}
            </div>
            {g.items.map(item => (
              <NavLink key={item.to} to={item.to} icon={item.icon} label={item.label} />
            ))}
          </div>
        ))}
      </nav>
      <div className="mt-auto pt-3 border-t border-[#1a2540]/60 mx-1">
        <div className="px-3 py-2">
          <div className="text-[11px] text-slate-500">管理员模式</div>
        </div>
      </div>
    </aside>
  )
}

function AppLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#0a0f1e]">
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}

      <div className={clsx(
        "fixed inset-y-0 left-0 z-40 transition-transform md:static md:translate-x-0",
        mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <Sidebar onCloseMobile={() => setMobileMenuOpen(false)} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="md:hidden flex items-center gap-3 px-4 py-3 bg-[#0d1322] border-b border-[#1a2540]/60 flex-shrink-0">
          <button onClick={() => setMobileMenuOpen(true)} className="text-slate-400 hover:text-white">
            <Menu size={22} />
          </button>
          <h1 className="text-lg font-bold flex items-center gap-2 tracking-tight">
            <Flame size={18} className="text-orange-400" />
            <span className="text-white">Intel<span className="text-blue-400">Hub</span></span>
          </h1>
        </div>

        <main className="flex-1 overflow-y-auto p-5 md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/crawlers" element={<Crawlers />} />
            <Route path="/data" element={<DataExplorer />} />
            <Route path="/rss-sources" element={<RssSources />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/scripts" element={<ScriptsTemplates />} />
            <Route path="/health" element={<Health />} />
            <Route path="/subscriptions" element={<Subscriptions />} />
            <Route path="/push-channels" element={<PushChannels />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/plaza" element={<Plaza />} />
            <Route path="/push-stats" element={<PushStats />} />
            <Route path="/mcp-tools" element={<McpTools />} />
            <Route path="/about" element={<About />} />
            <Route path="/chat" element={
              <Suspense fallback={<div className="text-slate-500 text-sm p-4">加载中...</div>}>
                <Chat />
              </Suspense>
            } />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  )
}
