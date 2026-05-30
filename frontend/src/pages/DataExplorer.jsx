import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown, Loader2, Database, FileText as ReportIcon, Play, Table } from 'lucide-react'
import clsx from 'clsx'


const TREE_WIDTH_KEY = 'data-explorer-tree-width'
const MIN_WIDTH = 200
const MAX_WIDTH = 600
const DEFAULT_WIDTH = 320

function getStoredWidth() {
  const v = localStorage.getItem(TREE_WIDTH_KEY)
  const n = v ? parseInt(v, 10) : DEFAULT_WIDTH
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, n || DEFAULT_WIDTH))
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'K'
  return (bytes / 1024 / 1024).toFixed(1) + 'M'
}

function formatTime(iso) {
  if (!iso) return ''
  return iso.replace('T', ' ').substring(0, 19)
}


// 树形节点 - 懒加载子目录
function TreeNode({ node, depth, selectedPath, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const [children, setChildren] = useState(node.children || null)
  const [loading, setLoading] = useState(false)
  const isDir = node.type === 'dir' || node.type === 'date_group'
  const isSelected = selectedPath === node.path
  const Icon = isDir ? (expanded ? FolderOpen : Folder) : FileText

  const treeApi = node.path?.startsWith('reports/') ? '/api/v1/data/report-tree' : '/api/v1/data/tree'

  const toggle = async (e) => {
    e.stopPropagation()
    if (!isDir) {
      onSelect(node.path)
      return
    }
    if (expanded) {
      setExpanded(false)
      return
    }
    if (node.type === 'date_group') {
      setExpanded(true)
      return
    }
    if (!children) {
      setLoading(true)
      try {
        const r = await api.get(`${treeApi}?path=${encodeURIComponent(node.path)}`)
        const items = r.data?.data?.children || []
        setChildren(items)
      } catch {
        setChildren([])
      } finally {
        setLoading(false)
      }
    }
    setExpanded(true)
  }

  const pad = depth * 16

  return (
    <div>
      <div
        onClick={toggle}
        className={clsx(
          'flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-colors text-sm',
          isSelected ? 'bg-sky-500/20 text-sky-400' : 'text-slate-300 hover:bg-slate-700'
        )}
        style={{ paddingLeft: pad + 8 }}
      >
        {isDir ? (
          loading ? (
            <Loader2 size={12} className="text-slate-500 shrink-0 animate-spin" />
          ) : expanded ? (
            <ChevronDown size={12} className="text-slate-500 shrink-0" />
          ) : (
            <ChevronRight size={12} className="text-slate-500 shrink-0" />
          )
        ) : (
          <span className="w-3" />
        )}
        <Icon size={14} className={clsx('shrink-0', isDir ? 'text-yellow-400' : 'text-sky-400')} />
        <span className="flex-1 truncate" title={node.name}>{node.name}</span>
        {!isDir && node.size != null && (
          <span className="text-xs text-slate-600 shrink-0">{formatSize(node.size)}</span>
        )}
        {node.type === 'dir' && !expanded && node.child_count != null && (
          <span className="text-xs text-slate-600 shrink-0">{node.child_count} 项</span>
        )}
        {node.type === 'date_group' && (
          <span className="text-xs text-slate-600 shrink-0">{node.count} 文件</span>
        )}
      </div>
      {isDir && expanded && children?.map((child, i) => (
        <TreeNode
          key={`${child.path || i}`}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}


function TreePanel({ apiEndpoint, icon, label, selectedPath, onSelect }) {
  const [tree, setTree] = useState(null)

  useEffect(() => {
    api.get(apiEndpoint).then(r => {
      setTree(r.data?.data)
    }).catch(() => {})
  }, [apiEndpoint])

  const handleSelect = useCallback((path) => {
    onSelect(path)
  }, [onSelect])

  return (
    <>
      <div className="sticky top-0 bg-slate-800 border-b border-slate-700 px-3 py-2 flex items-center gap-2">
        {icon}
        <span className="text-xs font-medium text-slate-400">{label}</span>
      </div>
      <div className="p-2">
        {tree ? tree.children?.map((child, i) => (
          <TreeNode
            key={`${child.path || i}`}
            node={child}
            depth={0}
            selectedPath={selectedPath}
            onSelect={handleSelect}
          />
        )) : (
          <div className="text-center py-8 text-slate-500"><Loader2 className="animate-spin inline mr-2" size={14} />加载中...</div>
        )}
      </div>
    </>
  )
}


export default function DataExplorer() {
  const [tab, setTab] = useState('data')
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [selectedPath, setSelectedPath] = useState(null)
  const [treeWidth, setTreeWidth] = useState(getStoredWidth)
  const dragging = useRef(false)
  const containerRef = useRef(null)

  // 拖拽调整宽度
  const onDragStart = useCallback((e) => {
    e.preventDefault()
    dragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMove = (ev) => {
      if (!dragging.current) return
      const container = containerRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      const newW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, ev.clientX - rect.left))
      setTreeWidth(newW)
    }
    const onUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      setTreeWidth(w => {
        localStorage.setItem(TREE_WIDTH_KEY, String(w))
        return w
      })
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [])

  const handleSelect = useCallback((path) => {
    setSelectedPath(path)
    setPreviewLoading(true)
    setPreview(null)
    const isReport = path.startsWith('reports/')
    const endpoint = isReport
      ? `/api/v1/data/report-preview?path=${encodeURIComponent(path)}`
      : `/api/v1/data/preview?path=${encodeURIComponent(path)}`
    api.get(endpoint).then(r => {
      setPreview(r.data?.data)
    }).catch(() => {
      setPreview(null)
    }).finally(() => setPreviewLoading(false))
  }, [])

  const switchTab = (t) => {
    if (t !== tab) {
      setTab(t)
      setSelectedPath(null)
      setPreview(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">数据浏览器</h2>
      </div>

      {/* 顶部 tab */}
      <div className="flex gap-1 bg-slate-800 rounded-lg p-1 w-fit">
        {[
          { key: 'data', label: '数据', icon: Database },
          { key: 'report', label: '报告', icon: ReportIcon },
        ].map(t => (
          <button key={t.key} onClick={() => switchTab(t.key)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              tab === t.key ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'
            )}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      <div ref={containerRef} className="flex h-[calc(100vh-240px)]">
        {/* 左侧目录树 */}
        <div
          className="bg-slate-800 rounded-l-xl border border-slate-700 border-r-0 overflow-auto shrink-0"
          style={{ width: treeWidth }}
        >
          {tab === 'data' ? (
            <TreePanel
              apiEndpoint="/api/v1/data/tree"
              icon={<Database size={14} className="text-sky-400" />}
              label="data/"
              selectedPath={selectedPath}
              onSelect={handleSelect}
            />
          ) : (
            <TreePanel
              apiEndpoint="/api/v1/data/report-tree"
              icon={<ReportIcon size={14} className="text-sky-400" />}
              label="reports/"
              selectedPath={selectedPath}
              onSelect={handleSelect}
            />
          )}
        </div>

        {/* 拖拽分割线 */}
        <div
          onMouseDown={onDragStart}
          className="w-1.5 shrink-0 cursor-col-resize bg-slate-700 hover:bg-sky-500/60 active:bg-sky-500 transition-colors relative z-10"
        />

        {/* 右侧预览 */}
        <div className="flex-1 bg-slate-800 rounded-r-xl border border-slate-700 border-l-0 overflow-auto min-w-0">
          {!selectedPath ? (
            <div className="flex items-center justify-center h-full text-slate-500">
              <div className="text-center">
                <FileText size={48} className="mx-auto mb-3 text-slate-700" />
                <p>点击左侧文件预览内容</p>
              </div>
            </div>
          ) : previewLoading ? (
            <div className="flex items-center justify-center h-full text-slate-500">
              <Loader2 className="animate-spin mr-2" size={20} /> 加载中...
            </div>
          ) : preview ? (
            preview.is_db ? (
              <DbConsole path={selectedPath} preview={preview} />
            ) : (
            <div className="flex flex-col h-full">
              <div className="border-b border-slate-700 px-4 py-3 flex items-center justify-between shrink-0">
                <div>
                  <h3 className="text-white font-medium text-sm">{preview.filename}</h3>
                  <p className="text-slate-500 text-xs mt-0.5">
                    {preview.path} | {formatSize(preview.size)} | {preview.is_json ? 'JSON' : preview.is_markdown ? 'Markdown' : 'Text'}
                    {preview.modified && ` | ${formatTime(preview.modified)}`}
                  </p>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-4">
                {preview.is_json ? (
                  <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
                    {JSON.stringify(preview.parsed, null, 2)}
                  </pre>
                ) : (
                  <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap">{preview.content || '(empty)'}</pre>
                )}
              </div>
            </div>
            )
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500">预览失败</div>
          )}
        </div>
      </div>
    </div>
  )
}


function DbConsole({ path, preview }) {
  const [tables, setTables] = useState([])
  const [selectedTable, setSelectedTable] = useState('')
  const [sql, setSql] = useState('')
  const [result, setResult] = useState(null)
  const [queryLoading, setQueryLoading] = useState(false)
  const [tablesLoading, setTablesLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setTablesLoading(true)
    api.get(`/api/v1/data/db-tables?path=${encodeURIComponent(path)}`).then(r => {
      setTables(r.data?.data?.tables || [])
    }).catch(() => {}).finally(() => setTablesLoading(false))
  }, [path])

  const executeQuery = useCallback((querySql) => {
    const s = querySql || sql
    if (!s.trim()) return
    setQueryLoading(true)
    setError('')
    setResult(null)
    api.post('/api/v1/data/db-query', { path, sql: s }).then(r => {
      const d = r.data?.data
      if (d?.error) {
        setError(d.error)
      } else {
        setResult(d)
      }
    }).catch(e => {
      setError(e.response?.data?.data?.error || e.message)
    }).finally(() => setQueryLoading(false))
  }, [path, sql])

  const selectTable = useCallback((tableName) => {
    setSelectedTable(tableName)
    const q = `SELECT * FROM ${tableName} LIMIT 100;`
    setSql(q)
    executeQuery(q)
  }, [executeQuery])

  const handleKeyDown = useCallback((e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      executeQuery()
    }
  }, [executeQuery])

  const cellCls = 'px-3 py-1.5 text-xs text-slate-300 whitespace-nowrap max-w-[300px] truncate'
  const headerCls = 'px-3 py-2 text-xs font-medium text-slate-400 uppercase tracking-wider whitespace-nowrap bg-slate-900/50 sticky top-0'

  return (
    <div className="flex flex-col h-full">
      {/* 文件信息头 */}
      <div className="border-b border-slate-700 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Database size={14} className="text-amber-400" />
          <h3 className="text-white font-medium text-sm">{preview.filename}</h3>
          <span className="text-slate-500 text-xs">{formatSize(preview.size)}</span>
          <span className="text-slate-500 text-xs">{tables.length} tables</span>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* 左侧表列表 */}
        <div className="w-44 shrink-0 border-r border-slate-700 overflow-auto">
          {tablesLoading ? (
            <div className="p-3 text-slate-500 text-xs"><Loader2 size={12} className="animate-spin inline mr-1" />加载表...</div>
          ) : tables.length === 0 ? (
            <div className="p-3 text-slate-500 text-xs">无表</div>
          ) : tables.map(t => (
            <button key={t.name} onClick={() => selectTable(t.name)}
              className={clsx(
                'w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors',
                selectedTable === t.name ? 'bg-sky-500/20 text-sky-400' : 'text-slate-300 hover:bg-slate-700'
              )}>
              <Table size={11} className="shrink-0 text-slate-500" />
              <span className="truncate text-xs">{t.name}</span>
              <span className="text-[10px] text-slate-600 ml-auto shrink-0">{t.row_count >= 0 ? t.row_count : '?'}</span>
            </button>
          ))}
        </div>

        {/* 右侧 SQL + 结果 */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* SQL 编辑器 */}
          <div className="border-b border-slate-700 shrink-0">
            <div className="flex items-center gap-2 px-3 pt-2">
              <span className="text-[10px] font-mono text-slate-500">SQL</span>
              <button onClick={() => executeQuery()} disabled={queryLoading || !sql.trim()}
                className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-sky-500/20 text-sky-400 hover:bg-sky-500/30 disabled:opacity-40 transition-colors">
                <Play size={10} /> {queryLoading ? '执行中...' : '执行'}
              </button>
            </div>
            <textarea
              value={sql}
              onChange={e => setSql(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              placeholder="SELECT * FROM table LIMIT 100;"
              className="w-full bg-transparent px-3 py-2 text-xs text-slate-200 font-mono resize-y focus:outline-none placeholder-slate-600"
            />
          </div>

          {/* 查询结果 */}
          <div className="flex-1 overflow-auto min-h-0">
            {error && (
              <div className="px-4 py-3 text-xs text-red-400 bg-red-500/5">{error}</div>
            )}
            {queryLoading && !result && (
              <div className="flex items-center justify-center py-8 text-slate-500 text-xs">
                <Loader2 size={14} className="animate-spin mr-2" />查询中...
              </div>
            )}
            {result && (
              <div>
                <div className="px-3 py-1 text-[10px] text-slate-500 border-b border-slate-700/50 bg-slate-900/30">
                  {result.row_count} rows{result.truncated ? ' (截断，最多 500)' : ''} · {result.columns.length} cols
                </div>
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      {result.columns.map(col => (
                        <th key={col} className={headerCls}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, ri) => (
                      <tr key={ri} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                        {row.map((cell, ci) => (
                          <td key={ci} className={clsx(cellCls, cell === null && 'text-slate-600 italic')}>
                            {cell === null ? 'NULL' : cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!result && !error && !queryLoading && (
              <div className="flex items-center justify-center h-full text-slate-600 text-xs">
                点击左侧表名或输入 SQL 查询
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
