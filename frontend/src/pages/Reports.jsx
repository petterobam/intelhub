import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { api } from '../api/client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  FileText, Clock, RefreshCw, TrendingUp, Database, Activity,
  BarChart3, Heart, Zap, Layers, AlertTriangle, CheckCircle2,
  XCircle, Flame, Tag, ChevronDown, ChevronRight, Sparkles, Shield, Sun,
  Wand2, Loader2, FileJson, Send
} from 'lucide-react'
import clsx from 'clsx'
import PushReportModal from '../components/PushReportModal'

// ── 平台/机构名称映射 ──────────────────────────────────────────────
const PLATFORM_NAMES = {
  // 社交/资讯平台
  weibo: '微博', douyin: '抖音', zhihu: '知乎', bilibili: '哔哩哔哩',
  '36kr': '36氪', huxiu: '虎嗅', toutiao: '今日头条', xiaohongshu: '小红书',
  kuaishou: '快手', baidu: '百度', sina: '新浪', sohu: '搜狐',
  netease: '网易', ifeng: '凤凰网', guanche: '观察者网', ths: '同花顺',
  eastmoney: '东方财富', cls: '财联社', wallstreetcn: '华尔街见闻',
  // 政府/监管机构
  pbc: '央行', csrc: '证监会', ndrc: '发改委', saf: '外汇局',
  mof: '财政部', moc: '商务部', miit: '工信部', mohrss: '人社部',
  pbo: '央行营管部', cbirc: '银保监会', circ: '保监会',
  gov: '国务院', statecouncil: '国务院', drc: '国务院发展研究中心',
  // 交易所
  sse: '上交所', szse: '深交所', bse: '北交所',
  shfe: '上海期货交易所', dce: '大连商品交易所', czce: '郑商所',
  ine: '上海国际能源交易中心', cffex: '中金所',
  // 其他
  ai_chips: 'AI芯片', ev: '新能源汽车', capital_markets: '资本市场',
  energy_cloud: '能源云', consumption_mayday: '五一消费',
  financial_highlight: '金融亮点', exchange_notes: '交易所动态',
  sector_snapshot: '板块快照', trending_weibo: '微博热搜',
  policy_highlights: '政策要点', hot_topics: '热点话题',
  market_data: '市场数据', risk_alerts: '风险警示',
  opportunities: '投资机会', modules: '模块数据',
}

function platformName(key) {
  if (!key) return key
  const lower = key.toLowerCase().replace(/^top_/, '')
  return PLATFORM_NAMES[lower] || key.replace(/^top_/, '').replace(/_/g, ' ')
}

// ── 类型元数据 ─────────────────────────────────────────────────────
const TYPE_META = {
  insight:   { label: '洞察报告', icon: Sparkles,   color: 'text-blue-400',   bg: 'bg-blue-900/30' },
  heartbeat: { label: '心跳检测', icon: Heart,      color: 'text-green-400',  bg: 'bg-green-900/30' },
  aggregate: { label: '数据聚合', icon: Layers,     color: 'text-purple-400', bg: 'bg-purple-900/30' },
  resonance: { label: '共振分析', icon: Activity,   color: 'text-orange-400', bg: 'bg-orange-900/30' },
  trend:     { label: '趋势分析', icon: TrendingUp,  color: 'text-cyan-400',  bg: 'bg-cyan-900/30' },
  agent:     { label: 'Agent 报告', icon: BarChart3, color: 'text-pink-400', bg: 'bg-pink-900/30' },
  personal_daily: { label: '偏好日报', icon: Sun,   color: 'text-orange-400', bg: 'bg-orange-900/30' },
  other:     { label: '其他', icon: FileText,        color: 'text-slate-400', bg: 'bg-slate-800/30' },
}

// ── Markdown 暗色渲染器 ─────────────────────────────────────────────
function MarkdownRenderer({ content }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none
      prose-headings:text-slate-200 prose-headings:font-semibold
      prose-h1:text-xl prose-h1:border-b prose-h1:border-slate-700 prose-h1:pb-2
      prose-h2:text-lg prose-h2:mt-6
      prose-h3:text-base prose-h3:mt-4
      prose-p:text-slate-300 prose-p:leading-relaxed
      prose-a:text-sky-400 prose-a:no-underline hover:prose-a:underline
      prose-strong:text-slate-200
      prose-code:text-pink-300 prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
      prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700
      prose-li:text-slate-300
      prose-table:border prose-table:border-slate-700
      prose-th:bg-slate-800 prose-th:text-slate-200 prose-th:px-3 prose-th:py-2
      prose-td:border-t prose-td:border-slate-700 prose-td:px-3 prose-td:py-2
      prose-blockquote:border-l-sky-500 prose-blockquote:text-slate-400
      prose-hr:border-slate-700
    ">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

// ── 智能数组渲染器 ──────────────────────────────────────────────────
// 纯字符串数组 → 标签堆叠
// 对象数组 (≤3 key) → 标签卡片, name/title 放前
// 对象数组 (>3 key) → 表格
const TAG_COLORS = ['text-sky-300', 'text-emerald-300', 'text-amber-300', 'text-rose-300', 'text-violet-300', 'text-teal-300']

function SmartArray({ items, max = 20 }) {
  if (!items || items.length === 0) return null
  const arr = items.slice(0, max)

  // 纯字符串数组
  if (arr.every(x => typeof x === 'string')) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {arr.map((s, i) => (
          <span key={i} className="px-2 py-1 bg-slate-700/50 rounded text-xs text-slate-300">{s}</span>
        ))}
        {items.length > max && <span className="text-xs text-slate-500 px-1">...+{items.length - max}</span>}
      </div>
    )
  }

  // 对象数组
  if (arr.every(x => typeof x === 'object' && x !== null && !Array.isArray(x))) {
    const allKeys = [...new Set(arr.flatMap(Object.keys))]
    const titleKey = allKeys.find(k => ['name', 'title', 'word', 'label'].includes(k.toLowerCase()))
    const restKeys = allKeys.filter(k => k !== titleKey)

    // 超过 3 个 key → 表格
    if (allKeys.length > 3) {
      return (
        <div className="overflow-x-auto rounded-lg border border-slate-700/50">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-800/80">
                {allKeys.map(k => (
                  <th key={k} className="px-3 py-2 text-left text-slate-400 font-medium whitespace-nowrap">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {arr.map((item, i) => (
                <tr key={i} className="border-t border-slate-700/30 hover:bg-slate-700/20">
                  {allKeys.map(k => (
                    <td key={k} className="px-3 py-2 text-slate-300 max-w-xs">
                      {item[k] != null ? (
                        typeof item[k] === 'object' ? <JsonValue value={item[k]} /> : String(item[k])
                      ) : '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    // ≤3 key → 标签卡片
    return (
      <div className="flex flex-wrap gap-1.5">
        {arr.map((item, i) => {
          const title = titleKey ? String(item[titleKey] ?? '') : ''
          const extras = restKeys.filter(k => item[k] != null && item[k] !== '').map((k, ki) => {
            const v = item[k]
            if (typeof v === 'object' && v !== null) {
              return (
                <span key={k} className={`text-[10px] ${TAG_COLORS[ki % TAG_COLORS.length]} inline-flex flex-col gap-0.5`}>
                  <JsonValue value={v} />
                </span>
              )
            }
            return (
              <span key={k} className={`text-[10px] ${TAG_COLORS[ki % TAG_COLORS.length]}`}>
                {String(v)}
              </span>
            )
          })
          return (
            <span key={i} className="px-2 py-1 bg-slate-700/50 rounded text-xs text-slate-300 flex items-center gap-1.5 max-w-full">
              {title && <span className="font-medium text-slate-200 truncate">{title}</span>}
              {extras.length > 0 && <span className="flex items-center gap-1 flex-shrink-0">{extras}</span>}
            </span>
          )
        })}
        {items.length > max && <span className="text-xs text-slate-500 px-1">...+{items.length - max}</span>}
      </div>
    )
  }

  // 混合类型兜底
  return (
    <div className="flex flex-wrap gap-1.5">
      {arr.map((item, i) => (
        <span key={i} className="px-2 py-1 bg-slate-700/50 rounded text-xs text-slate-300">
          {typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean' ? String(item)
            : typeof item === 'object' && item !== null ? <JsonValue value={item} />
            : String(item)}
        </span>
      ))}
    </div>
  )
}

// ── 递归 JSON 值渲染器 ───────────────────────────────────────────────
function JsonValue({ value }) {
  if (value === null || value === undefined) return <span className="text-slate-500">-</span>
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return <span>{String(value)}</span>
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-500 text-xs">[]</span>
    return <SmartArray items={value} />
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    if (entries.length === 0) return <span className="text-slate-500 text-xs">{'{}'}</span>
    return (
      <div className="space-y-1.5 pl-3 border-l border-slate-700/40">
        {entries.map(([k, v]) => (
          <div key={k}>
            {typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' || v === null || v === undefined ? (
              <div className="flex items-baseline gap-2 text-xs">
                <span className="text-slate-500 flex-shrink-0">{platformName(k)}</span>
                <span className="text-slate-300">{v !== null && v !== undefined ? String(v) : '-'}</span>
              </div>
            ) : (
              <div>
                <div className="text-xs text-slate-500 mb-0.5">{platformName(k)}</div>
                <JsonValue value={v} />
              </div>
            )}
          </div>
        ))}
      </div>
    )
  }
  return <span>{String(value)}</span>
}

// ── 报告卡片 ────────────────────────────────────────────────────────
function ReportCard({ report, selected, onClick }) {
  const meta = TYPE_META[report.type] || TYPE_META.other
  const Icon = meta.icon
  const mtime = new Date(report.mtime).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })

  return (
    <div
      onClick={onClick}
      className={clsx(
        "border rounded-lg p-3 cursor-pointer transition-all hover:border-sky-500/40",
        selected ? "bg-slate-700/60 border-sky-500/50" : "bg-slate-800/40 border-slate-700/50"
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 flex-shrink-0 ${meta.color}`} />
        <span className="text-sm text-white font-medium truncate">{report.title || report.name}</span>
      </div>
      {report.summary && (
        <p className="text-xs text-slate-400 mb-1 truncate">{report.summary}</p>
      )}
      {report.user_email && (
        <div className="text-[10px] text-emerald-400/80 mb-0.5 truncate">
          {report.user_display_name ? (
            <>{report.user_display_name} <span className="text-emerald-500/50">{report.user_email}</span></>
          ) : report.user_email}
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1">
          {report.task_name && !report.user_email && (
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-700/50 text-slate-400">
              {report.task_name}
            </span>
          )}
          <span className={clsx("px-1.5 py-0.5 rounded text-[10px]", meta.bg, meta.color)}>
            {meta.label}
          </span>
          <span className="flex items-center gap-0.5">
            {report.has_json && <FileJson className="w-3 h-3 text-amber-400" title="JSON" />}
            {report.has_md && <FileText className="w-3 h-3 text-sky-400" title="MD" />}
          </span>
        </div>
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {mtime}
        </span>
      </div>
    </div>
  )
}

// ── Section 标题组件 ─────────────────────────────────────────────────
function Section({ title, icon: Icon, iconColor, children, collapsible, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="mb-5">
      <div
        className={clsx("flex items-center gap-2 mb-3", collapsible && "cursor-pointer")}
        onClick={() => collapsible && setOpen(!open)}
      >
        {Icon && <Icon className={`w-4 h-4 ${iconColor || 'text-slate-400'}`} />}
        <h4 className="text-sm font-semibold text-slate-300 flex-1">{title}</h4>
        {collapsible && (
          open ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />
        )}
      </div>
      {open && children}
    </div>
  )
}

// ── Insight 详情面板 ─────────────────────────────────────────────────
function InsightDetail({ data }) {
  const inner = data.data || data
  const coreData = inner.data || inner
  const hotTopics = coreData.hot_topics || {}
  const marketData = coreData.market_data || {}
  const opportunities = coreData.opportunities || []
  const riskAlerts = coreData.risk_alerts || []
  const policyHighlights = coreData.policy_highlights || {}

  return (
    <>
      {(opportunities.length > 0 || riskAlerts.length > 0) && (
        <div className="grid grid-cols-2 gap-3 mb-5">
          {opportunities.length > 0 && (
            <div className="bg-green-900/15 border border-green-700/30 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-green-400" />
                <span className="text-sm font-semibold text-green-300">投资机会 ({opportunities.length})</span>
              </div>
              <SmartArray items={opportunities} />
            </div>
          )}
          {riskAlerts.length > 0 && (
            <div className="bg-red-900/15 border border-red-700/30 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <span className="text-sm font-semibold text-red-300">风险警示 ({riskAlerts.length})</span>
              </div>
              <SmartArray items={riskAlerts} />
            </div>
          )}
        </div>
      )}

      {Object.keys(hotTopics).length > 0 && (
        <Section title="热点话题" icon={Flame} iconColor="text-orange-400" collapsible defaultOpen={true}>
          <div className="space-y-3">
            {Object.entries(hotTopics).map(([platform, items]) => {
              const arr = Array.isArray(items) ? items : [items]
              return (
                <div key={platform}>
                  <div className="text-xs text-slate-500 mb-1 flex items-center gap-1">
                    <Tag className="w-3 h-3" />
                    {platformName(platform)}
                  </div>
                  <SmartArray items={arr} />
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {Object.keys(marketData).length > 0 && (
        <Section title="市场数据" icon={BarChart3} iconColor="text-cyan-400" collapsible defaultOpen={true}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {Object.entries(marketData).map(([key, val]) => (
              <div key={key} className="bg-slate-700/30 rounded-lg p-3">
                <div className="text-xs text-cyan-400 font-medium mb-2">{platformName(key)}</div>
                {typeof val === 'object' && val !== null && !Array.isArray(val) ? (
                  <div className="space-y-1">
                    {Object.entries(val).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">{platformName(k)}</span>
                        <span className="text-slate-200 font-medium">
                          {Array.isArray(v) ? <SmartArray items={v} max={5} /> : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : Array.isArray(val) ? (
                  <SmartArray items={val} />
                ) : (
                  <div className="text-sm text-slate-200">{String(val)}</div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {Object.keys(policyHighlights).length > 0 && (
        <Section title="政策要点" icon={Shield} iconColor="text-indigo-400" collapsible defaultOpen={false}>
          <div className="space-y-2">
            {Object.entries(policyHighlights).map(([source, items]) => {
              const arr = Array.isArray(items) ? items : [items]
              return (
                <div key={source}>
                  <div className="text-xs text-slate-500 mb-1 flex items-center gap-1">
                    <Shield className="w-3 h-3" />
                    {platformName(source)}
                  </div>
                  <SmartArray items={arr} />
                </div>
              )
            })}
          </div>
        </Section>
      )}
    </>
  )
}

// ── Heartbeat 详情面板 ───────────────────────────────────────────────
function HeartbeatDetail({ data }) {
  const inner = data.data || data
  const coreData = inner.data || inner
  const trending = coreData.trending_weibo || []
  const policyHighlights = coreData.policy_highlights || []
  const sectorSnapshot = coreData.sector_snapshot || {}
  const exchangeNotes = coreData.exchange_notes || {}
  const financialHighlight = coreData.financial_highlight || {}

  return (
    <>
      {Object.keys(sectorSnapshot).length > 0 && (
        <Section title="板块快照" icon={Activity} iconColor="text-cyan-400" collapsible defaultOpen={true}>
          <div className="space-y-3">
            {Object.entries(sectorSnapshot).map(([name, info]) => (
              <div key={name}>
                <div className="text-xs text-slate-500 mb-1">{platformName(name)}</div>
                {Array.isArray(info) ? (
                  <SmartArray items={info} />
                ) : (
                  <div className="text-sm text-slate-200">
                    {typeof info === 'string' ? info : info?.summary || info?.trend || JSON.stringify(info)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {trending.length > 0 && (
        <Section title="微博热搜" icon={Flame} iconColor="text-red-400" collapsible defaultOpen={false}>
          <div className="flex flex-wrap gap-1.5">
            {trending.slice(0, 20).map((t, i) => (
              <span key={i} className="px-2 py-1 bg-red-900/20 border border-red-700/30 rounded text-xs text-red-200 flex items-center gap-1">
                <span className="text-[10px] text-red-400 font-mono">#{i + 1}</span>
                {t.word || t.title || t}
                {t.hot && <span className="text-[10px] text-slate-500">{Number(t.hot).toLocaleString()}</span>}
              </span>
            ))}
          </div>
        </Section>
      )}

      {policyHighlights.length > 0 && (
        <Section title="政策要点" icon={Shield} iconColor="text-indigo-400" collapsible defaultOpen={false}>
          <SmartArray items={policyHighlights} />
        </Section>
      )}

      {Object.keys(exchangeNotes).length > 0 && (
        <Section title="交易所动态" icon={FileText} iconColor="text-amber-400" collapsible defaultOpen={false}>
          <div className="space-y-2">
            {Object.entries(exchangeNotes).map(([exchange, info]) => (
              <div key={exchange} className="p-2 bg-amber-900/10 border border-amber-700/20 rounded text-xs text-amber-200">
                <span className="font-medium text-amber-300">{platformName(exchange)}</span>
                <span className="ml-2">{typeof info === 'string' ? info : info?.summary || info?.status || JSON.stringify(info)}</span>
                {typeof info === 'object' && info?.categories && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {info.categories.map((c, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-slate-700/40 rounded text-[10px] text-slate-400">{c}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {Object.keys(financialHighlight).length > 0 && (
        <Section title="金融亮点" icon={TrendingUp} iconColor="text-yellow-400" collapsible defaultOpen={false}>
          <div className="bg-yellow-900/10 border border-yellow-700/20 rounded-lg p-3">
            {financialHighlight.name && <div className="text-sm font-medium text-yellow-200 mb-1">{financialHighlight.name}</div>}
            {financialHighlight.notes && <div className="text-xs text-yellow-200/70">{financialHighlight.notes}</div>}
            {financialHighlight.metrics && typeof financialHighlight.metrics === 'object' && (
              <div className="flex flex-wrap gap-2 mt-2">
                {Object.entries(financialHighlight.metrics).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 bg-slate-700/50 rounded text-[10px] text-slate-300">
                    {platformName(k)}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Section>
      )}
    </>
  )
}

// ── Aggregate 详情面板 ───────────────────────────────────────────────
function AggregateDetail({ data }) {
  const inner = data.data || data
  const modules = inner.modules || {}

  return (
    <>
      {inner.generated_at && (
        <div className="text-xs text-slate-500 mb-4">聚合时间: {inner.generated_at}</div>
      )}
      {Object.keys(modules).length > 0 ? (
        <Section title="模块数据" icon={Layers} iconColor="text-purple-400">
          <div className="space-y-3">
            {Object.entries(modules).map(([modName, modData]) => (
              <div key={modName}>
                <div className="text-xs text-slate-500 mb-1">{platformName(modName)}</div>
                <JsonValue value={modData} />
              </div>
            ))}
          </div>
        </Section>
      ) : (
        <div className="text-sm text-slate-500">无聚合模块数据</div>
      )}
    </>
  )
}

// ── JSON 结构化预览面板 ──────────────────────────────────────────────
function JsonStructuredPreview({ data, reportType }) {
  if (reportType === 'insight') return <InsightDetail data={data} />
  if (reportType === 'heartbeat') return <HeartbeatDetail data={data} />
  if (reportType === 'aggregate') return <AggregateDetail data={data} />

  return (
    <details open>
      <summary className="text-sm text-slate-400 cursor-pointer hover:text-slate-200 mb-2">结构化数据</summary>
      <pre className="bg-slate-900/60 rounded-lg p-4 text-xs text-slate-400 overflow-x-auto max-h-[40vh] overflow-y-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  )
}

// ── 从 MD 内容提取标题 ──────────────────────────────────────────────
function extractMdTitle(content) {
  if (!content) return null
  const lines = content.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('# ')) {
      const title = trimmed.replace(/^#+\s*/, '').trim()
      if (title.length > 2) return title
    }
  }
  return null
}

// ── 从 JSON 提取标题 ────────────────────────────────────────────────
function extractJsonTitle(data) {
  if (!data) return null
  const inner = data.data || data
  return inner.title || null
}

// ── 主详情面板（合并 JSON + MD）────────────────────────────────────
function ReportDetail({ report, detail, onClose, onPush }) {
  if (!report) return null

  const meta = TYPE_META[report.type] || TYPE_META.other
  const Icon = meta.icon

  const jsonData = detail?.json || report.data || null
  const mdContent = detail?.md || report.md || ''
  const hasJson = detail?.has_json ?? report.has_json
  const hasMd = detail?.has_md ?? report.has_md

  // 优先用 MD 标题，其次 JSON 标题，最后用文件名
  const displayTitle = extractMdTitle(mdContent) || extractJsonTitle(jsonData) || report.name

  return (
    <div className="p-6">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className={clsx("p-2 rounded-lg", meta.bg)}>
            <Icon className={`w-5 h-5 ${meta.color}`} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{displayTitle}</h3>
            <span className="text-xs text-slate-500">
              {meta.label} · {new Date(report.mtime).toLocaleString('zh-CN')}
              {detail?.size && ` · ${(detail.size / 1024).toFixed(1)}KB`}
              {' '}·
              {hasJson && <span className="text-amber-400 ml-1">JSON</span>}
              {hasJson && hasMd && <span className="text-slate-500 mx-1">+</span>}
              {hasMd && <span className="text-sky-400">MD</span>}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onPush}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-500/20 text-sky-400 rounded-lg text-sm hover:bg-sky-500/30 transition-colors" title="推送此报告">
            <Send size={14} /> 推送
          </button>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xl px-2">×</button>
        </div>
      </div>

      {/* JSON 结构化预览（上方） */}
      {hasJson && jsonData && (
        <div className={clsx(hasMd && "border-b border-slate-700/50 pb-5 mb-5")}>
          <JsonStructuredPreview data={jsonData} reportType={report.type} />

          {['insight', 'heartbeat', 'aggregate'].includes(report.type) && (
            <details className="mt-4">
              <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300 flex items-center gap-1">
                <ChevronRight className="w-3 h-3" /> 查看原始 JSON
              </summary>
              <pre className="mt-2 bg-slate-900/60 rounded-lg p-4 text-xs text-slate-400 overflow-x-auto max-h-[40vh] overflow-y-auto">
                {JSON.stringify(jsonData, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* MD 明细渲染（下方） */}
      {hasMd && mdContent && (
        <div>
          {hasJson && (
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-sky-400" />
              <span className="text-sm font-medium text-slate-300">详细报告</span>
            </div>
          )}
          <MarkdownRenderer content={mdContent} />
        </div>
      )}

      {!hasJson && !hasMd && (
        <div className="text-sm text-slate-500">暂无内容</div>
      )}
    </div>
  )
}

// ── 生成进度弹窗 ────────────────────────────────────────────────────
function GenerateModal({ job, onClose, onComplete }) {
  const isRunning = job?.status === 'running' || job?.status === 'queued'
  const isDone = job?.status === 'done'
  const isError = job?.status === 'error'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-[420px] shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          {isRunning && <Loader2 className="w-5 h-5 text-sky-400 animate-spin" />}
          {isDone && <CheckCircle2 className="w-5 h-5 text-green-400" />}
          {isError && <XCircle className="w-5 h-5 text-red-400" />}
          <h3 className="text-lg font-semibold text-white">
            {isRunning ? '正在生成报告...' : isDone ? '生成完成' : '生成失败'}
          </h3>
        </div>

        <div className="mb-4">
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>{job?.message || '准备中...'}</span>
            <span>{job?.progress || 0}%</span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={clsx(
                "h-full rounded-full transition-all duration-500",
                isError ? "bg-red-500" : isDone ? "bg-green-500" : "bg-sky-500"
              )}
              style={{ width: `${job?.progress || 0}%` }}
            />
          </div>
        </div>

        {isDone && job?.result && (
          <div className="bg-green-900/20 border border-green-700/30 rounded-lg p-3 mb-4 text-xs text-green-200">
            <p>文件: {job.result.filename || job.result.md_filename || '-'}</p>
            {job.result.md_filename && <p>MD: {job.result.md_filename}</p>}
            <p>耗时: {((new Date() - new Date(job.started_at)) / 1000).toFixed(1)}s</p>
          </div>
        )}
        {isError && (
          <div className="bg-red-900/20 border border-red-700/30 rounded-lg p-3 mb-4 text-xs text-red-200">
            {job?.message}
          </div>
        )}

        <div className="flex justify-end gap-2">
          {isDone && (
            <button onClick={() => { onClose(); onComplete() }}
              className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm hover:bg-sky-500">
              查看报告
            </button>
          )}
          <button onClick={onClose}
            className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600">
            {isDone ? '关闭' : '后台运行'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 主页面（固定布局，三区域独立滚动）──────────────────────────────
export default function Reports() {
  const [reports, setReports] = useState([])
  const [taskGroups, setTaskGroups] = useState([])
  const [personalGroups, setPersonalGroups] = useState([])
  const [activeTab, setActiveTab] = useState(null)  // null=全部平台, task_id, '_personal:{type_key}'
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const [showGenMenu, setShowGenMenu] = useState(false)
  const [genJob, setGenJob] = useState(null)
  const [showGenModal, setShowGenModal] = useState(false)
  const [reportTasks, setReportTasks] = useState([])
  const [pushReport, setPushReport] = useState(null)
  const pollRef = useRef(null)

  const CACHE_KEY = 'intelhub_reports_cache'

  useEffect(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY)
      if (cached) {
        const parsed = JSON.parse(cached)
        setReports(parsed.reports || [])
        setTaskGroups(parsed.task_groups || [])
        setPersonalGroups(parsed.personal_groups || [])
        if (parsed.reports?.length > 0 && selected === null) setSelected(0)
        setLoading(false)
      }
    } catch { }

    api.get('/api/v1/reports?limit=9999')
      .then(d => {
        const payload = d.data?.data || {}
        const list = payload.reports || []
        setReports(list)
        setTaskGroups(payload.task_groups || [])
        setPersonalGroups(payload.personal_groups || [])
        if (list.length > 0 && selected === null) setSelected(0)
        setLoading(false)
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({
            reports: list,
            task_groups: payload.task_groups || [],
            personal_groups: payload.personal_groups || [],
            ts: Date.now(),
          }))
        } catch { }
      })
      .catch(() => { if (reports.length === 0) setLoading(false) })
  }, [refreshKey])

  // All reports for the active tab
  const filtered = useMemo(() => {
    if (!activeTab) return reports
    // Personal group: _personal:{type_key}
    if (activeTab.startsWith('_personal:')) {
      const typeKey = activeTab.slice('_personal:'.length)
      const pg = personalGroups.find(g => g.type_key === typeKey)
      return pg ? pg.reports : []
    }
    // Platform task group or orphan
    return reports.filter(r => activeTab === '_orphan' ? !r.task_id : r.task_id === activeTab)
  }, [reports, personalGroups, activeTab])

  useEffect(() => {
    if (selected === null) { setDetail(null); return }
    const r = filtered[selected]
    if (!r) return

    const detailCacheKey = r.id
      ? `intelhub_report_${r.id}`
      : `intelhub_report_${r.name}_${r.subdir || ''}`

    // 先读缓存
    try {
      const cached = localStorage.getItem(detailCacheKey)
      if (cached) setDetail(JSON.parse(cached))
    } catch { }

    // 优先用 report ID，否则回退文件名
    const fetchUrl = r.id
      ? `/api/v1/reports/by-id/${r.id}`
      : (() => {
          const params = new URLSearchParams()
          if (r.subdir) params.set('subdir', r.subdir)
          const qs = params.toString() ? `?${params.toString()}` : ''
          return `/api/v1/reports/detail/${r.name}${qs}`
        })()

    api.get(fetchUrl)
      .then(d => {
        const data = d.data?.data
        setDetail(data)
        try { localStorage.setItem(detailCacheKey, JSON.stringify(data)) } catch { }
      })
      .catch(() => {
        setDetail(prev => prev || { json: r.data, md: r.content_preview || null, has_json: r.has_json, has_md: r.has_md })
      })
  }, [selected, refreshKey, filtered])

  const handleGenerate = useCallback(async (reportType, taskId) => {
    setShowGenMenu(false)
    try {
      const payload = { report_type: reportType }
      if (taskId) payload.task_id = taskId
      const resp = await api.post('/api/v1/reports/generate', payload)
      const jobData = resp.data?.data
      if (!jobData?.job_id) return
      setGenJob({ ...jobData, started_at: new Date().toISOString() })
      setShowGenModal(true)

      const poll = setInterval(async () => {
        try {
          const statusResp = await api.get(`/api/v1/reports/generate/${jobData.job_id}`)
          const status = statusResp.data?.data
          setGenJob(prev => ({ ...prev, ...status }))
          if (status?.status === 'done' || status?.status === 'error') {
            clearInterval(poll)
          }
        } catch { clearInterval(poll) }
      }, 1500)
      pollRef.current = poll
    } catch (e) {
      console.error('Generate failed:', e)
    }
  }, [])

  const sel = selected !== null ? filtered[selected] : null

  return (
    <div className="h-full flex flex-col">
      {/* 顶部工具栏（固定） */}
      <div className="flex-shrink-0 pb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-white">报告中心</h2>
            <p className="text-xs text-slate-500 mt-1">
              {reports.length} 个平台报告 · {personalGroups.reduce((s, g) => s + g.report_count, 0)} 个个人报告
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={() => {
                  setShowGenMenu(!showGenMenu)
                  if (!showGenMenu && reportTasks.length === 0) {
                    api.get('/api/v1/tasks?type=report&enabled=true&limit=20').then(r => {
                      setReportTasks(r.data?.data?.tasks || [])
                    }).catch(() => {})
                  }
                }}
                className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm hover:bg-sky-500 flex items-center gap-2"
              >
                <Wand2 className="w-4 h-4" /> 生成报告
              </button>
              {showGenMenu && (
                <div className="absolute right-0 mt-2 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-40 w-56 py-1">
                  <div className="px-3 py-1.5 text-[11px] text-slate-500 font-semibold">选择任务生成</div>
                  {reportTasks.map(t => (
                    <button
                      key={t.id}
                      onClick={() => handleGenerate('insight', t.id)}
                      className="w-full px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2"
                    >
                      <Sparkles className="w-4 h-4 text-blue-400" />
                      {t.name}
                    </button>
                  ))}
                  <div className="border-t border-slate-700 my-1" />
                  {[
                    { type: 'heartbeat', label: '心跳检测', icon: Heart, color: 'text-green-400' },
                    { type: 'aggregate', label: '数据聚合', icon: Layers, color: 'text-purple-400' },
                  ].map(item => (
                    <button
                      key={item.type}
                      onClick={() => handleGenerate(item.type)}
                      className="w-full px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2"
                    >
                      <item.icon className={`w-4 h-4 ${item.color}`} />
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={() => {
                // 清除报告缓存后刷新
                Object.keys(localStorage).filter(k => k.startsWith('intelhub_report_')).forEach(k => localStorage.removeItem(k))
                localStorage.removeItem('intelhub_reports_cache')
                setRefreshKey(k => k + 1); setSelected(null); setDetail(null)
              }}
              className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700 flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> 刷新
            </button>
          </div>
        </div>

        {/* 分组筛选：平台任务 + 个人报告类型 */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* 平台：全部 */}
          <button
            onClick={() => { setActiveTab(null); setSelected(null); setDetail(null) }}
            className={clsx("px-3 py-1.5 rounded-lg text-xs transition-colors",
              !activeTab ? "bg-sky-600 text-white" : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            )}
          >
            全部平台 ({reports.length})
          </button>
          {taskGroups.map(g => (
            <button
              key={g.task_id}
              onClick={() => { setActiveTab(g.task_id); setSelected(null); setDetail(null) }}
              className={clsx("px-3 py-1.5 rounded-lg text-xs transition-colors flex items-center gap-1",
                activeTab === g.task_id ? "bg-sky-600 text-white" : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
              )}
            >
              {g.task_name} ({g.report_count})
            </button>
          ))}
          {/* 分隔 */}
          {personalGroups.length > 0 && (
            <span className="text-slate-600 mx-1">|</span>
          )}
          {/* 个人报告类型分组 */}
          {personalGroups.map(g => (
            <button
              key={g.type_key}
              onClick={() => { setActiveTab(`_personal:${g.type_key}`); setSelected(null); setDetail(null) }}
              className={clsx("px-3 py-1.5 rounded-lg text-xs transition-colors flex items-center gap-1",
                activeTab === `_personal:${g.type_key}` ? "bg-orange-600 text-white" : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
              )}
            >
              {g.group_name} ({g.report_count})
            </button>
          ))}
        </div>
      </div>

      {/* 主体：左右布局（撑满剩余空间，各自独立滚动） */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* 左侧列表 */}
        <div className="w-72 flex-shrink-0 overflow-y-auto space-y-2 pr-1">
          {filtered.length === 0 && !loading && (
            <div className="text-center text-slate-500 py-12">
              <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>暂无报告</p>
              <p className="text-xs mt-1">运行采集任务后自动生成</p>
            </div>
          )}
          {filtered.map((r, i) => (
            <div key={r.id || r.name + r.mtime} className="relative group/card">
              <ReportCard
                report={r}
                selected={selected === i}
                onClick={() => setSelected(i)}
              />
              <button
                onClick={e => { e.stopPropagation(); setPushReport(r) }}
                className="absolute top-2 right-2 p-1 rounded text-slate-600 hover:text-sky-400 hover:bg-slate-700 opacity-0 group-hover/card:opacity-100 transition-all" title="推送">
                <Send size={13} />
              </button>
            </div>
          ))}
        </div>

        {/* 右侧详情 */}
        <div className="flex-1 overflow-y-auto bg-slate-800/40 border border-slate-700/50 rounded-xl">
          {!sel && (
            <div className="flex items-center justify-center h-full text-slate-500">
              <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p>选择左侧报告查看详情</p>
              </div>
            </div>
          )}
          {sel && <ReportDetail report={sel} detail={detail} onClose={() => setSelected(null)} onPush={() => setPushReport(sel)} />}
        </div>
      </div>

      {/* 生成进度弹窗 */}
      {showGenModal && genJob && (
        <GenerateModal
          job={genJob}
          onClose={() => { setShowGenModal(false); if (pollRef.current) clearInterval(pollRef.current) }}
          onComplete={() => { setRefreshKey(k => k + 1); setSelected(0) }}
        />
      )}

      {/* 手动推送弹窗 */}
      {pushReport && (
        <PushReportModal
          report={pushReport}
          onClose={() => setPushReport(null)}
          onDone={() => setPushReport(null)}
          admin
        />
      )}
    </div>
  )
}
