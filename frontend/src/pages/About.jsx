import { Link } from 'react-router-dom'
import {
  Flame, Rss, FileText, BookOpen, MessageSquare, Clock, Mail, Zap,
  Search, Layers, Globe, Brain, Wrench, ArrowRight, Sparkles,
  MessageCircle
} from 'lucide-react'

const CAPABILITIES = [
  { icon: Globe, title: '情报广场', desc: '全网数据聚合，多源情报一站浏览', color: 'text-orange-400', bg: 'bg-orange-500/10' },
  { icon: Rss, title: '自定义数据源', desc: 'RSS / B站 / YouTube 灵活接入', color: 'text-purple-400', bg: 'bg-purple-500/10' },
  { icon: FileText, title: 'AI 智能报告', desc: '自动分析与深度洞察', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  { icon: BookOpen, title: '知识库', desc: '文档管理与向量检索', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  { icon: MessageSquare, title: 'AI 对话', desc: '上下文感知智能问答', color: 'text-sky-400', bg: 'bg-sky-500/10' },
  { icon: Clock, title: '任务自动化', desc: '定时调度与脚本执行', color: 'text-amber-400', bg: 'bg-amber-500/10' },
  { icon: Mail, title: '订阅推送', desc: '邮件、Webhook 多渠道推送', color: 'text-pink-400', bg: 'bg-pink-500/10' },
  { icon: Zap, title: 'MCP 工具', desc: '标准化接口连接外部 AI', color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
]

const VISIONS = [
  {
    icon: Globe,
    title: '广度聚合',
    subtitle: '当前阶段',
    color: 'from-sky-500/20 to-blue-500/10',
    borderColor: 'border-sky-500/20',
    current: true,
    items: [
      '多源数据实时采集与统一浏览',
      '按任务分类筛选，AI 生成报告',
      'AI 自动生成分析报告与洞察摘要',
      '邮件、Webhook 多渠道主动推送',
    ],
  },
  {
    icon: Search,
    title: '深度情报',
    subtitle: '从数据到洞察',
    color: 'from-blue-500/20 to-sky-500/10',
    borderColor: 'border-blue-500/20',
    items: [
      '事件追踪 — 自动构建事件时间线',
      '事件衍射 — 分析影响面与舆情扩散',
      '趋势分析 — 识别信号与拐点预判',
      '周期报告 — 日/周/月自动汇总追踪',
    ],
  },
  {
    icon: Layers,
    title: '泛内容挖掘',
    subtitle: '不止于媒体，发现隐藏的需求',
    color: 'from-purple-500/20 to-violet-500/10',
    borderColor: 'border-purple-500/20',
    items: [
      '从评论、提问、求助中采集大众真实声音',
      '分析社会需求痛点与消费趋势',
      '识别尚未被满足的细分市场机会',
      '构建"非媒体信息"的独特情报优势',
    ],
  },
  {
    icon: Brain,
    title: '专家 AI Agent',
    subtitle: '智能情报分析师',
    color: 'from-emerald-500/20 to-teal-500/10',
    borderColor: 'border-emerald-500/20',
    items: [
      '融合广度、深度与泛内容三源',
      '构建领域知识图谱与认知网络',
      '主动发现关联、预警风险、推荐机会',
      '从工具进化为真正的"数字分析师"',
    ],
  },
  {
    icon: Wrench,
    title: '开放生态',
    subtitle: '让知识流动',
    color: 'from-amber-500/20 to-orange-500/10',
    borderColor: 'border-amber-500/20',
    items: [
      '知识库通过 MCP/Skill 开放给外部 AI',
      '情报能力可被第三方应用直接调用',
      '共建共享的情报网络，打破信息孤岛',
      '开发者友好的 API 与插件体系',
    ],
  },
  {
    icon: MessageCircle,
    title: '用户共建',
    subtitle: '与用户一起成长',
    color: 'from-pink-500/20 to-rose-500/10',
    borderColor: 'border-pink-500/20',
    items: [
      '收集用户反馈驱动产品迭代',
      '社区需求投票与优先级排序',
      '开放路线图透明规划',
      '与用户共建 IntelHub 的未来',
    ],
  },
]

export default function About() {
  return (
    <div className="max-w-4xl mx-auto space-y-16">
      {/* Hero */}
      <div className="text-center pt-4">
        <div className="inline-flex items-center gap-3 mb-5">
          <span className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500/20 to-amber-500/10 border border-orange-500/20 flex items-center justify-center">
            <Flame size={24} className="text-orange-400" />
          </span>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Intel<span className="text-blue-400">Hub</span>
          </h1>
        </div>
        <p className="text-lg text-slate-300 leading-relaxed max-w-xl mx-auto">
          把全网信息变成<span className="text-blue-400 font-medium">可行动的情报</span>
        </p>
        <p className="text-sm text-slate-500 mt-3 max-w-md mx-auto">
          自动采集 · 智能分析 · 主动推送
        </p>
      </div>

      {/* Current capabilities */}
      <section>
        <div className="text-center mb-8">
          <h2 className="text-xl font-bold text-white">当前能力</h2>
          <p className="text-sm text-slate-500 mt-1">从数据采集到智能分析，一站式情报闭环</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {CAPABILITIES.map(c => {
            const Icon = c.icon
            return (
              <div key={c.title}
                className="bg-[#111a2e]/70 rounded-xl border border-[#1a2540]/80 p-4 hover:border-[#2a3f5f]/80 hover:bg-[#141e34] transition-all duration-200">
                <div className={`w-9 h-9 rounded-lg ${c.bg} flex items-center justify-center mb-3`}>
                  <Icon size={18} className={c.color} />
                </div>
                <h3 className="text-sm font-semibold text-white mb-1">{c.title}</h3>
                <p className="text-[11px] text-slate-500 leading-relaxed">{c.desc}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* Future vision */}
      <section>
        <div className="text-center mb-8">
          <h2 className="text-xl font-bold text-white">演进方向</h2>
          <p className="text-sm text-slate-500 mt-1">从信息聚合平台到智能情报中枢</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {VISIONS.map(v => {
            const Icon = v.icon
            return (
              <div key={v.title}
                className={`bg-gradient-to-br ${v.color} rounded-xl border ${v.borderColor} p-5 relative`}>
                {v.current && (
                  <span className="absolute top-3 right-3 text-[10px] px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-400 font-medium">当前</span>
                )}
                <div className="flex items-center gap-3 mb-1">
                  <Icon size={20} className="text-white/80" />
                  <h3 className="text-base font-bold text-white">{v.title}</h3>
                </div>
                <p className="text-xs text-slate-400 mb-4">{v.subtitle}</p>
                <ul className="space-y-2">
                  {v.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-white/20 mt-1.5 shrink-0" />
                      <span className="text-[12px] text-slate-300 leading-relaxed whitespace-nowrap">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </section>

      {/* CTA */}
      <div className="text-center pb-8">
        <div className="bg-gradient-to-r from-blue-500/10 via-sky-500/10 to-purple-500/10 rounded-xl border border-[#1a2540] p-8">
          <Sparkles size={28} className="text-blue-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white mb-2">开始使用 IntelHub</h3>
          <p className="text-sm text-slate-400 mb-5">一键启动，立刻拥有你的情报中心</p>
          <Link to="/plaza"
            className="inline-flex items-center gap-2 bg-sky-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-sky-600 transition-colors whitespace-nowrap">
            开始使用 <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  )
}
