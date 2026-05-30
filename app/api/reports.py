"""报告 API - 扫描 reports/ 目录下所有报告文件"""
from flask import Blueprint, request, Response
from app.utils.helpers import standard_response
import os, json, glob, threading, uuid
from datetime import datetime

bp = Blueprint('reports', __name__, url_prefix='/api/v1/reports')

# ── 生成任务状态跟踪 ──────────────────────────────────────────────────
_generate_jobs = {}  # {job_id: {status, progress, message, result, started_at}}

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'reports'
)


VALID_TYPES = {'insight', 'heartbeat', 'aggregate', 'agent', 'daily'}


def _classify_report(fname, subdir=None):
    """从所在子目录推断报告类型，fallback 到文件名前缀"""
    if subdir and subdir.lower() in VALID_TYPES:
        return subdir.lower()
    name = fname.lower()
    if 'insight' in name:
        return 'insight'
    elif 'heartbeat' in name:
        return 'heartbeat'
    elif 'aggregate' in name:
        return 'aggregate'
    elif 'resonance' in name:
        return 'resonance'
    elif 'trend' in name:
        return 'trend'
    elif 'agent-report' in name or 'agent' in name:
        return 'agent'
    return 'other'


def _base_name(fname):
    """去掉扩展名得到基础名，如 insight-2026-05-09T10-48-02"""
    if fname.endswith('.json'):
        return fname[:-5]
    elif fname.endswith('.md'):
        return fname[:-3]
    return fname


def _extract_summary(fname, data):
    """从 JSON 数据提取摘要"""
    if not isinstance(data, dict):
        return None

    parts = []

    # 通用字段
    if 'generated_at' in data:
        parts.append(f"生成于 {data['generated_at'][:19]}")
    if 'total_items' in data:
        parts.append(f"{data['total_items']} 条目")

    # insight 类型
    health = data.get('health', {})
    if health:
        status = health.get('status', '')
        parts.append(f"健康: {status}")

    trends = data.get('trends', [])
    if trends:
        parts.append(f"{len(trends)} 趋势")

    resonance = data.get('resonance', {})
    if isinstance(resonance, dict) and 'total' in resonance:
        parts.append(f"{resonance['total']} 共振点")

    # heartbeat 类型
    if 'health_score' in data:
        parts.append(f"健康分 {data['health_score']}")
    if 'alerts' in data:
        alerts = data['alerts']
        critical = sum(1 for a in alerts if 'CRITICAL' in str(a))
        warning = sum(1 for a in alerts if 'WARNING' in str(a))
        if critical: parts.append(f"{critical} 严重")
        if warning: parts.append(f"{warning} 警告")

    # aggregate 类型
    if 'platforms' in data and isinstance(data.get('platforms'), list):
        parts.append(f"{len(data['platforms'])} 平台")

    return ' | '.join(parts) if parts else None


def _md_summary(content):
    """从 Markdown 内容提取摘要"""
    lines = content.strip().split('\n')
    # 找第一行有意义的文字
    for line in lines[:5]:
        line = line.strip().strip('#').strip()
        if line and len(line) > 5:
            return line[:120]
    return content[:120]


def _report_to_list_item(report, task_map=None):
    """将 Report ORM 对象转为前端列表条目"""
    fp = report.file_path or ''
    name = os.path.splitext(os.path.basename(fp))[0] if fp else report.id
    subdir = os.path.basename(os.path.dirname(fp)) if fp and os.path.dirname(fp) != REPORTS_DIR else None

    has_json = False
    has_md = False
    if fp:
        if fp.endswith('.json') and os.path.isfile(fp):
            has_json = True
        if fp.endswith('.md') and os.path.isfile(fp):
            has_md = True
        if not has_json:
            candidate = os.path.splitext(fp)[0] + '.json'
            if os.path.isfile(candidate):
                has_json = True
        if not has_md:
            candidate = os.path.splitext(fp)[0] + '.md'
            if os.path.isfile(candidate):
                has_md = True

    task_name = ''
    if report.task_id and task_map and report.task_id in task_map:
        task_name = task_map[report.task_id]

    return {
        'id': report.id,
        'title': report.title or name,
        'name': name,
        'mtime': report.generated_at.isoformat() if report.generated_at else '',
        'type': report.report_type,
        'subdir': subdir,
        'has_json': has_json,
        'has_md': has_md,
        'summary': report.summary or '',
        'task_id': report.task_id,
        'task_name': task_name,
    }


def _group_by_task(reports, task_map, report_tasks):
    """将报告按任务分组"""
    from collections import OrderedDict

    grouped = OrderedDict()
    for r in reports:
        tid = r.get('task_id') or '_orphan'
        if tid not in grouped:
            grouped[tid] = []
        grouped[tid].append(r)

    groups = []
    for task in report_tasks:
        task_reports = grouped.pop(task.id, [])
        groups.append({
            'task_id': task.id,
            'task_name': task.name,
            'report_count': len(task_reports),
            'reports': task_reports,
        })

    # 孤儿报告
    orphan_reports = []
    for tid, rpts in grouped.items():
        orphan_reports.extend(rpts)
    if orphan_reports:
        groups.append({
            'task_id': '_orphan',
            'task_name': '其他报告',
            'report_count': len(orphan_reports),
            'reports': orphan_reports,
        })

    return groups


def _scan_reports(report_type=None, limit=50):
    """[DEPRECATED] 扫描 reports/ 子目录，合并同名的 json+md 文件为一个报告条目。
    仅供 /latest、/types 兼容端点使用。
    根目录下的文件 fallback 到文件名前缀分类。
    """
    if not os.path.isdir(REPORTS_DIR):
        return []

    # 收集所有文件，按 (subdir, base_name) 分组
    # subdir 为 None 表示根目录下的文件
    groups = {}  # (subdir, base_name) -> {json_path, md_path, subdir}
    for f in glob.glob(os.path.join(REPORTS_DIR, '*', '*')) + glob.glob(os.path.join(REPORTS_DIR, '*')):
        if not (os.path.isfile(f) or os.path.islink(f)):
            continue
        fname = os.path.basename(f)
        if not fname.endswith(('.json', '.md')):
            continue

        # 确定子目录名
        parent = os.path.dirname(f)
        if parent == REPORTS_DIR:
            subdir = None
        else:
            subdir = os.path.basename(parent)

        base = _base_name(fname)
        # 跳过 -latest 链接
        if '-latest' in base:
            continue

        key = (subdir, base)
        if key not in groups:
            groups[key] = {'base': base, 'json_path': None, 'md_path': None, 'subdir': subdir}

        if fname.endswith('.json'):
            groups[key]['json_path'] = f
        elif fname.endswith('.md'):
            groups[key]['md_path'] = f

    # 按类型过滤 & 构建结果
    result = []
    for (subdir, base), info in groups.items():
        rtype = _classify_report(base, subdir)
        if report_type and rtype != report_type:
            continue

        primary = info['json_path'] or info['md_path']
        if not primary:
            continue

        mtime = datetime.fromtimestamp(os.path.getmtime(primary))

        entry = {
            'name': base,
            'display_name': os.path.basename(primary),
            'mtime': mtime.isoformat(),
            'size': os.path.getsize(primary),
            'type': rtype,
            'subdir': subdir,
            'has_json': info['json_path'] is not None,
            'has_md': info['md_path'] is not None,
        }

        if info['json_path']:
            try:
                with open(info['json_path'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                entry['data'] = data
                entry['summary'] = _extract_summary(base, data)
                entry['size'] = os.path.getsize(info['json_path'])
            except Exception:
                entry['data'] = None

        if info['md_path'] and not entry.get('summary'):
            try:
                with open(info['md_path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                entry['md_summary'] = _md_summary(content)
                if not entry.get('summary'):
                    entry['summary'] = entry['md_summary']
            except Exception:
                pass

        result.append(entry)

    result.sort(key=lambda x: x['mtime'], reverse=True)

    return result[:limit]


# ── API 路由 ────────────────────────────────────────────────────────
# 注意: 具名路由必须在 /<path:filename> 之前注册

@bp.route('', methods=['GET'])
def list_reports():
    """列出所有报告（按任务分组）。?task_id=xxx&limit=200"""
    from app import db
    from app.models.report import Report
    from app.models.task import ScheduledTask

    filter_task_id = request.args.get('task_id')
    limit = int(request.args.get('limit', 200))

    # ── 所有报告（按任务分组）──────────────────────────────────────
    q = Report.query
    if filter_task_id:
        q = q.filter_by(task_id=filter_task_id)
    rows = q.order_by(Report.generated_at.desc()).limit(limit).all()

    task_ids = {r.task_id for r in rows if r.task_id}
    task_map = {}
    for tid in task_ids:
        task = db.session.get(ScheduledTask, tid)
        if task:
            task_map[tid] = task.name

    report_tasks = ScheduledTask.query.filter_by(task_type='report', enabled=True)\
        .filter(ScheduledTask.is_auto == False).all()

    all_reports = [_report_to_list_item(r, task_map) for r in rows]
    task_groups = _group_by_task(all_reports, task_map, report_tasks)

    return standard_response({
        'reports': all_reports,
        'total': len(all_reports),
        'task_groups': task_groups,
    })


@bp.route('/latest', methods=['GET'])
def latest_reports():
    """兼容旧接口 - 返回最新报告"""
    all_reports = _scan_reports(limit=20)

    # 每种类型取最新的一个
    seen_types = set()
    latest = []
    for r in all_reports:
        if r['type'] not in seen_types:
            seen_types.add(r['type'])
            latest.append(r)

    return standard_response({
        'reports': latest,
        'all_reports_count': len(all_reports),
    })


@bp.route('/types', methods=['GET'])
def report_types():
    """返回所有报告类型及统计"""
    all_reports = _scan_reports()
    types = {}
    for r in all_reports:
        t = r['type']
        if t not in types:
            types[t] = {'count': 0, 'latest': None}
        types[t]['count'] += 1
        if not types[t]['latest']:
            types[t]['latest'] = r['mtime']
    return standard_response(types)


# ── 报告生成（必须在 /<path:filename> 之前） ─────────────────────────

@bp.route('/generate', methods=['POST'])
def generate_report():
    """触发报告生成（异步）
    
    Body JSON:
      report_type: "insight" | "heartbeat" | "aggregate"  (默认 insight)
      data_sources: ["hot_topics", "policy", "exchange", "financial"]
      prompt_template: "自定义提示词"
      use_harness: true/false
    """
    payload = request.get_json(silent=True) or {}
    report_type = payload.get('report_type', 'insight')
    data_sources = payload.get('data_sources', ['hot_topics', 'policy', 'exchange', 'financial'])
    prompt_template = payload.get('prompt_template', '')
    use_harness = payload.get('use_harness', True)
    task_id = payload.get('task_id') or _match_report_task(report_type)

    job_id = str(uuid.uuid4())[:8]
    _generate_jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'message': '任务已排队',
        'result': None,
        'started_at': bj_now().isoformat(),
        'report_type': report_type,
    }

    def _run():
        _generate_jobs[job_id]['status'] = 'running'
        _generate_jobs[job_id]['progress'] = 10
        _generate_jobs[job_id]['message'] = f'正在生成 {report_type} 报告...'

        try:
            os.makedirs(REPORTS_DIR, exist_ok=True)
            now_str = bj_now().strftime('%Y-%m-%dT%H-%M-%S')

            if report_type == 'aggregate':
                # 数据聚合
                _generate_jobs[job_id]['progress'] = 30
                _generate_jobs[job_id]['message'] = '聚合多平台数据...'
                from analysis.aggregate.aggregator import Aggregator
                agg = Aggregator()
                result = agg.aggregate()
                filename = f'aggregate-{now_str}.json'
                save_dir = os.path.join(REPORTS_DIR, 'aggregate')
                os.makedirs(save_dir, exist_ok=True)
                fpath = os.path.join(save_dir, filename)
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
                _generate_jobs[job_id].update(
                    status='done', progress=100,
                    message=f'聚合报告已生成: {filename}',
                    result={'filename': filename, 'type': 'aggregate'}
                )
                _notify_report_async(fpath, report_type)

            elif report_type == 'heartbeat':
                # 心跳检测
                _generate_jobs[job_id]['progress'] = 30
                _generate_jobs[job_id]['message'] = '执行心跳检测...'
                from analysis.heartbeat.heartbeat_analyzer import generate_heartbeat
                hb = generate_heartbeat()
                filename = f'heartbeat-{now_str}.json'
                save_dir = os.path.join(REPORTS_DIR, 'heartbeat')
                os.makedirs(save_dir, exist_ok=True)
                fpath = os.path.join(save_dir, filename)
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(hb, f, ensure_ascii=False, indent=2, default=str)
                _generate_jobs[job_id].update(
                    status='done', progress=100,
                    message=f'心跳报告已生成: {filename}',
                    result={'filename': filename, 'type': 'heartbeat'}
                )
                _notify_report_async(fpath, 'heartbeat')

            else:
                # insight 报告 (使用 ReportExecutor 或 analysis engine)
                _generate_jobs[job_id]['progress'] = 20
                _generate_jobs[job_id]['message'] = '采集数据并生成洞察报告...'
                
                # 尝试使用 analysis engine 的 insight generator
                try:
                    from analysis.reports.insight_generator import InsightGenerator
                    gen = InsightGenerator()
                    insight = gen.generate(data_sources=data_sources)
                    filename = f'insight-{now_str}.json'
                    save_dir = os.path.join(REPORTS_DIR, 'insight')
                    os.makedirs(save_dir, exist_ok=True)
                    fpath = os.path.join(save_dir, filename)
                    with open(fpath, 'w', encoding='utf-8') as f:
                        json.dump(insight, f, ensure_ascii=False, indent=2, default=str)

                    # 同时生成 MD 版本
                    if insight.get('md_content'):
                        md_filename = f'insight-{now_str}.md'
                        md_path = os.path.join(save_dir, md_filename)
                        with open(md_path, 'w', encoding='utf-8') as f:
                            f.write(insight['md_content'])
                        _generate_jobs[job_id]['result'] = {
                            'filename': filename, 'md_filename': md_filename, 'type': 'insight'
                        }
                        # 保存报告记录
                        _save_report_record(md_path, insight['md_content'], report_type='insight', task_id=task_id)
                    else:
                        _generate_jobs[job_id]['result'] = {'filename': filename, 'type': 'insight'}
                        # 保存报告记录（JSON 格式尝试提取内容）
                        try:
                            _save_report_record(fpath, json.dumps(insight, ensure_ascii=False)[:3000], report_type='insight', task_id=task_id)
                        except Exception:
                            pass
                    _generate_jobs[job_id].update(
                        progress=100, status='done',
                        message=f'洞察报告已生成: {filename}'
                    )
                    _notify_report_async(fpath, report_type)
                except ImportError:
                    # 回退到 ReportExecutor
                    from app.scheduler.report_executor import generate_report as _gen
                    result = _gen(
                        prompt_template=prompt_template or None,
                        data_sources=data_sources,
                        use_harness=use_harness,
                        task_id=task_id,
                    )
                    _generate_jobs[job_id].update(
                        progress=100,
                        status='done' if result.get('success') else 'error',
                        message=f"报告生成{'成功' if result.get('success') else '失败'}: {result.get('filename', '')}",
                        result=result
                    )
                    if result.get('success') and result.get('path'):
                        _notify_report_async(result['path'], 'agent')

        except Exception as e:
            _generate_jobs[job_id].update(
                status='error', progress=0,
                message=f'生成失败: {str(e)}',
                result={'error': str(e)}
            )

    thread = threading.Thread(target=_run)
    thread.start()

    return standard_response({
        'job_id': job_id,
        'status': 'queued',
        'message': '报告生成任务已提交',
    })


@bp.route('/generate/<job_id>', methods=['GET'])
def generate_status(job_id):
    """查询生成任务进度"""
    if job_id not in _generate_jobs:
        return standard_response({'error': 'Job not found'}), 404
    return standard_response(_generate_jobs[job_id])


def _find_report_file(filename, subdir=None):
    """在 REPORTS_DIR 中查找报告文件，优先按 subdir 查找"""
    # 指定子目录优先
    if subdir:
        fpath = os.path.join(REPORTS_DIR, subdir, filename)
        if os.path.isfile(fpath):
            return fpath
    # 根目录
    fpath = os.path.join(REPORTS_DIR, filename)
    if os.path.isfile(fpath):
        return fpath
    # 所有子目录中查找
    for f in glob.glob(os.path.join(REPORTS_DIR, '*', filename)):
        if os.path.isfile(f):
            return f
    return None


# ── 报告生成后通知订阅者 ──────────────────────────────────────────────

def _notify_report_async(report_path: str, report_type: str):
    """报告生成成功后异步通知订阅者"""
    try:
        from app.services.report_notifier import notify_report
        notify_report(report_path, report_type, async_mode=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Report notification trigger failed: %s", e)


# ── 单个报告详情（合并 json+md）────────────────────────────────────


@bp.route('/by-id/<report_id>', methods=['GET'])
def get_report_by_id(report_id):
    """通过 DB ID 获取报告详情，从 file_path 读取内容"""
    from app.models.report import Report
    report = Report.query.get(report_id)
    if not report:
        return standard_response({'error': '报告不存在'}), 404

    fp = report.file_path or ''
    name = os.path.splitext(os.path.basename(fp))[0] if fp else ''
    subdir = os.path.basename(os.path.dirname(fp)) if fp and os.path.dirname(fp) != REPORTS_DIR else None

    result = {
        'id': report.id,
        'name': name,
        'title': report.title,
        'type': report.report_type,
        'subdir': subdir,
        'json': None,
        'md': None,
        'mtime': report.generated_at.isoformat() if report.generated_at else '',
        'summary': report.summary,
        'has_json': False,
        'has_md': False,
    }

    # 读取 MD
    md_path = fp if fp.endswith('.md') and os.path.isfile(fp) else None
    if not md_path and fp:
        candidate = os.path.splitext(fp)[0] + '.md'
        if os.path.isfile(candidate):
            md_path = candidate
    if md_path:
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                result['md'] = f.read()
            result['has_md'] = True
        except Exception:
            pass

    # 读取 JSON
    json_path = fp if fp.endswith('.json') and os.path.isfile(fp) else None
    if not json_path and fp:
        candidate = os.path.splitext(fp)[0] + '.json'
        if os.path.isfile(candidate):
            json_path = candidate
    if json_path:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                result['json'] = json.load(f)
            result['has_json'] = True
            if not result['mtime']:
                result['mtime'] = datetime.fromtimestamp(os.path.getmtime(json_path)).isoformat()
        except Exception:
            pass

    return standard_response(result)


@bp.route('/detail/<path:base_name>', methods=['GET'])
def get_report_detail(base_name):
    """获取单个报告的完整内容，合并同名 json 和 md。
    支持查询参数 ?subdir=insight 指定子目录。
    """
    subdir = request.args.get('subdir')
    result = {
        'name': base_name,
        'type': _classify_report(base_name, subdir),
        'subdir': subdir,
        'json': None,
        'md': None,
    }

    # 尝试加载 JSON
    json_path = _find_report_file(base_name + '.json', subdir)
    if json_path:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                result['json'] = json.load(f)
            stat = os.stat(json_path)
            result['mtime'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            result['size'] = stat.st_size
            result['has_json'] = True
        except Exception as e:
            result['json_error'] = str(e)

    # 尝试加载 MD（完整内容，不截断）
    md_path = _find_report_file(base_name + '.md', subdir)
    if md_path:
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                result['md'] = f.read()
            if 'mtime' not in result:
                stat = os.stat(md_path)
                result['mtime'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                result['size'] = stat.st_size
            result['has_md'] = True
        except Exception as e:
            result['md_error'] = str(e)

    if result['json'] is None and result['md'] is None:
        return standard_response({'error': 'Report not found'}), 404

    result['summary'] = _extract_summary(base_name, result['json']) if result['json'] else None

    return standard_response(result)


# ── 报告 HTML 在线访问 ────────────────────────────────────────────────

@bp.route('/html/<path:html_name>', methods=['GET'])
def get_report_html(html_name):
    """直接返回报告 HTML 文件供浏览器访问"""
    html_dir = os.path.join(REPORTS_DIR, 'html')
    fpath = os.path.join(html_dir, html_name)
    if not os.path.isfile(fpath):
        return Response('<h1>404 Not Found</h1>', status=404, content_type='text/html')
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    return Response(content, status=200, content_type='text/html; charset=utf-8')


# ── 兼容旧的单文件路由 ────────────────────────────────────────────

@bp.route('/<path:filename>', methods=['GET'])
def get_report(filename):
    """获取单个报告文件的完整内容（兼容旧接口）"""
    fpath = _find_report_file(filename)
    if not fpath:
        return standard_response({'error': 'Report not found'}), 404

    # 推断子目录用于分类
    parent = os.path.dirname(fpath)
    subdir = os.path.basename(parent) if parent != REPORTS_DIR else None

    entry = {
        'name': filename,
        'mtime': datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
        'size': os.path.getsize(fpath),
        'type': _classify_report(filename, subdir),
    }

    if filename.endswith('.json'):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                entry['data'] = json.load(f)
            entry['summary'] = _extract_summary(filename, entry['data'])
        except Exception as e:
            entry['error'] = str(e)
    elif filename.endswith('.md'):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                entry['content'] = f.read()  # 完整内容
            entry['summary'] = _md_summary(entry['content'])
        except Exception as e:
            entry['error'] = str(e)

    return standard_response(entry)


def _save_report_record(path, content, report_type='agent', task_id=None):
    """保存报告数据库记录"""
    try:
        from app import db
        from app.models.report import Report
        from app.scheduler.report_executor import _extract_title, _extract_summary
        filename = os.path.basename(path)
        title = _extract_title(content, fallback=filename.replace('.md', ''))
        summary = _extract_summary(content)
        report = Report(
            title=title,
            report_type=report_type,
            file_path=path,
            summary=summary,
            task_id=task_id,
            scope='platform',
        )
        db.session.add(report)
        db.session.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to save report record: {e}")


@bp.route('/push', methods=['POST'])
def push_report():
    """手动推送报告到指定渠道

    Body:
      name: 报告 base_name (必须)
      subdir: 子目录 (可选)
      mode: 'all' | 'user' (必须)
      user_id: 目标用户 ID (mode='user' 时必须)
      channel_ids: 指定渠道 ID 列表 (可选, 不传则推该用户所有渠道)
    """
    from app.utils.auth import login_required
    from flask import g

    # 手动调用 login_required 逻辑
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return standard_response({'error': '未登录'}), 401
    try:
        from app.utils.auth import decode_token
        payload = decode_token(auth[7:])
    except Exception:
        return standard_response({'error': 'Token 无效'}), 401

    from app.models.user import User
    user = User.query.get(payload['sub'])
    if not user or not user.enabled:
        return standard_response({'error': '用户不存在'}), 401
    g.current_user = user

    data = request.get_json() or {}
    report_id = data.get('report_id', '')
    report_name = data.get('name', '')
    subdir = data.get('subdir', '')
    mode = data.get('mode', '')
    target_user_id = data.get('user_id', '')
    selected_channel_ids = data.get('channel_ids')

    if not (report_id or report_name) or not mode:
        return standard_response({'error': '参数不完整'}), 400

    # 优先用 report_id 从数据库查报告记录，其次用文件名查找
    report_title = ''
    report_type = ''
    report_path = ''
    content = ''

    if report_id:
        from app.models.report import Report
        report = Report.query.get(report_id)
        if not report:
            return standard_response({'error': '报告不存在'}), 404
        report_title = report.title
        report_type = report.report_type
        report_path = report.file_path or ''
    else:
        # 管理员报告中心：用文件名查找
        md_path = _find_report_file(report_name + '.md', subdir or None)
        json_path = _find_report_file(report_name + '.json', subdir or None)
        report_path = md_path or json_path or ''
        report_type = _classify_report(report_name, subdir or None)

    # 读取报告 MD 内容
    if report_path and os.path.isfile(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            pass
    elif report_path.endswith('.json'):
        md_path = report_path[:-5] + '.md'
        if os.path.isfile(md_path):
            report_path = md_path
            try:
                with open(md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                pass

    from app.services.report_notifier import _save_report_html, _get_site_url

    # 优先读存档摘要 MD，其次用报告 MD 转 HTML
    summary_md = _read_summary_md(report) if report_id else ''
    if summary_md:
        summary_html = _md_to_simple_html(summary_md)
    else:
        summary_html = _md_to_simple_html(content) if content else ''

    # 从内容提取标题（如果 DB 没给标题）
    if not report_title:
        report_title = _extract_report_title(content)

    # 查找或生成在线查看的 HTML 存档
    base_name = os.path.splitext(os.path.basename(report_path))[0] if report_path else report_name
    html_filename = _find_cached_html(base_name)
    if not html_filename and content:
        html_filename = _save_report_html(report_path, content)

    site_url = _get_site_url()
    view_link = f'{site_url}/api/v1/reports/html/{html_filename}' if site_url and html_filename else ''

    from app.models.subscription import Subscription
    from app.models.push_channel import PushChannel
    from app.services.push_channels import PushDispatcher

    dispatcher = PushDispatcher()

    if mode == 'all':
        task_id = _match_report_task(report_type)
        if task_id:
            subs = Subscription.query.filter_by(enabled=True, task_id=task_id).all()
        else:
            subs = Subscription.query.filter_by(enabled=True).all()
        if not subs:
            return standard_response({'sent': 0, 'failed': 0, 'message': '无活跃订阅者'})
        result = dispatcher.dispatch(summary_html, view_link, report_type, subs, title=report_title, summary_md=summary_md)
        return standard_response(result)

    elif mode == 'user':
        uid = target_user_id

        target_user = User.query.get(uid)
        if not target_user:
            return standard_response({'error': '用户不存在'}), 404

        channels = PushChannel.query.filter_by(user_id=uid, enabled=True).all()
        if selected_channel_ids:
            channels = [c for c in channels if c.id in selected_channel_ids]

        if not channels:
            return standard_response({'sent': 0, 'failed': 0, 'message': '该用户无可用渠道'})

        class _TempSub:
            def __init__(self, email, channel_ids):
                self.id = 'temp'
                self.email = email
                self.channel_id = None
                self.channel_ids = channel_ids

        temp = _TempSub(
            email=target_user.email,
            channel_ids=[c.id for c in channels]
        )
        result = dispatcher.dispatch(summary_html, view_link, report_type, [temp], title=report_title, summary_md=summary_md)
        return standard_response(result)

    return standard_response({'error': '无效 mode'}), 400


def _find_cached_html(report_name):
    """查找已存档的 HTML 文件（按名称前缀匹配最新的）"""
    import glob
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_dir = os.path.join(base_dir, 'reports', 'html')
    if not os.path.isdir(html_dir):
        return ''
    pattern = os.path.join(html_dir, f'{report_name}-*.html')
    files = sorted(glob.glob(pattern))
    if not files:
        return ''
    return os.path.basename(files[-1])


def _md_to_simple_html(md_text):
    """将 Markdown 内容转为 HTML（用于推送摘要）"""
    import markdown
    if not md_text:
        return ''
    return markdown.markdown(md_text, extensions=['extra', 'tables', 'nl2br'])


def _extract_report_title(md_text):
    """从 MD 内容提取第一个标题作为报告标题"""
    import re
    if not md_text:
        return ''
    m = re.search(r'^#\s+(.+)$', md_text, re.M)
    return m.group(1).strip() if m else ''


def _read_summary_md(report):
    """读取报告关联的摘要 MD 文件"""
    if not report or not report.summary_path:
        return ''
    if not os.path.isfile(report.summary_path):
        return ''
    try:
        with open(report.summary_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def _match_report_task(report_type):
    """根据 report_type 自动匹配一个启用的报告任务"""
    try:
        from app.models.task import ScheduledTask
        tasks = ScheduledTask.query.filter_by(task_type='report', enabled=True).all()
        # 关键词匹配
        type_keywords = {
            'insight': ['洞察', 'insight'],
            'heartbeat': ['心跳', 'heartbeat'],
            'aggregate': ['聚合', 'aggregate'],
            'agent': ['综合', 'agent', '简报'],
        }
        keywords = type_keywords.get(report_type, [])
        for t in tasks:
            for kw in keywords:
                if kw in (t.name or '').lower():
                    return t.id
        # 没匹配到就取第一个
        if tasks:
            return tasks[0].id
    except Exception:
        pass
    return None
