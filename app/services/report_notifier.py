"""ReportNotifier — 报告后置消费: AI 汇总 + 邮件推送

流程:
  1. 读取报告 MD 文件
  2. 调用 LLM 生成邮件友好 HTML 摘要
  3. 查询订阅该报告类型的活跃订阅者
  4. 批量发送邮件
"""

import json
import logging
import os
import threading
from datetime import datetime
from app.utils.helpers import bj_now

logger = logging.getLogger(__name__)


def notify_report(report_path: str, report_type: str, async_mode: bool = True, title: str = None, app=None):
    """报告生成后的通知入口。

    Args:
        report_path: 报告文件路径 (.md 或 .json)
        report_type: 'insight' | 'agent' | 'heartbeat'
        async_mode: True 则在后台线程执行
        title: 可选的自定义推送标题（含任务名）
        app: 可选的 Flask app 实例（避免重复 create_app）
    """
    if async_mode:
        t = threading.Thread(target=_do_notify, args=(report_path, report_type, title, app), daemon=True)
        t.start()
    else:
        _do_notify(report_path, report_type, title, app)


def _do_notify(report_path: str, report_type: str, title: str = None, app=None):
    """实际执行通知逻辑"""
    try:
        if app is None:
            from flask import current_app
            try:
                app = current_app._get_current_object()
            except RuntimeError:
                from app import create_app
                app = create_app()
        with app.app_context():
            _notify_inner(report_path, report_type, title=title)
    except Exception as e:
        logger.error("Report notifier failed: %s", e, exc_info=True)


def _notify_inner(report_path: str, report_type: str, title: str = None):
    # 1. Read report content
    content = _read_report(report_path)
    if not content:
        logger.warning("No report content to notify: %s", report_path)
        return

    # 1.1 从 DB 取报告标题
    report_title = _get_report_title(report_path)

    # 1.2 查找任务名，构建含任务名的推送标题
    push_title = title  # 优先使用调用方传入的 title
    if not push_title:
        task_name = _get_task_name_for_report(report_path, report_type)
        if task_name:
            if report_title:
                push_title = f'{task_name} · {report_title}'
            else:
                push_title = f'{task_name} · {bj_now().strftime("%Y-%m-%d")}'
        else:
            push_title = report_title  # fallback to DB report title

    # 2. 存储报告 HTML（前端 marked.js 渲染）
    html_filename = _save_report_html(report_path, content)

    # 3. 构建在线访问链接
    site_url = _get_site_url()
    view_link = ''
    if site_url and html_filename:
        view_link = f'{site_url}/api/v1/reports/html/{html_filename}'

    # 4. LLM 生成 Markdown 摘要
    summary_md = _generate_email_summary(content, report_type)

    # 4.1 将 MD 摘要存盘，关联到 Report 记录
    summary_md_path = _save_summary_md(report_path, summary_md)
    if summary_md_path:
        _link_summary_to_report(report_path, summary_md_path)

    # 4.2 MD → HTML 用于邮件内容
    summary_html = _md_to_simple_html(summary_md) if summary_md else ''

    html_body = _build_email_body(summary_html, view_link, report_type)
    subject = _build_subject(report_type)

    # 5. Find subscribers — 按 task_id 精准匹配
    from app.models.subscription import Subscription
    from app.models.report import Report

    # 优先从 Report 记录取 task_id（最可靠）
    task_id = None
    report_record = Report.query.filter(
        (Report.file_path == report_path) |
        (Report.file_path == os.path.splitext(report_path)[0] + '.json')
    ).first()
    if report_record and report_record.task_id:
        task_id = report_record.task_id

    if not task_id:
        logger.info("No task_id found for report_path=%s, skip notification", report_path)
        return

    subs = Subscription.query.filter_by(enabled=True, task_id=task_id).all()

    if not subs:
        logger.info("No subscribers for report type: %s", report_type)
        return

    # 6. 多渠道推送（summary_html 用于邮件，summary_md 用于 IM）
    from app.services.push_channels import PushDispatcher
    dispatcher = PushDispatcher()
    result = dispatcher.dispatch(summary_html, view_link, report_type, subs, raw_md=content, summary_md=summary_md, title=push_title, report_path=report_path)
    logger.info("Report notification: %s (sent=%d, failed=%d, skipped=%d)", report_type, result['sent'], result['failed'], result.get('skipped', 0))
    for d in result.get('details', []):
        if d.get('status') != 'sent':
            logger.error("  push detail: sub=%s channel=%s error=%s", d.get('sub_id'), d.get('channel'), d.get('error'))


def _get_report_title(report_path):
    """从 DB 查询报告标题"""
    try:
        from app.models.report import Report
        report = Report.query.filter(
            (Report.file_path == report_path) |
            (Report.file_path == os.path.splitext(report_path)[0] + '.json')
        ).first()
        if report and report.title:
            return report.title
    except Exception:
        pass
    return ''


def _get_task_name_for_report(report_path, report_type):
    """通过 report_path 或 report_type 反查任务名"""
    try:
        from app.models.report import Report
        from app.models.task import ScheduledTask
        # 优先通过 report 的 task_id 反查
        report = Report.query.filter(
            (Report.file_path == report_path) |
            (Report.file_path == os.path.splitext(report_path)[0] + '.json')
        ).first()
        if report and report.task_id:
            task = ScheduledTask.query.get(report.task_id)
            if task and task.name:
                return task.name
        # fallback: 通过 module 匹配
        tasks = ScheduledTask.query.filter_by(task_type='report', module=report_type).all()
        if tasks:
            return tasks[0].name
    except Exception:
        pass
    return None


def _save_summary_md(report_path, summary_md):
    """将 LLM 摘要 MD 直接存盘，返回文件路径"""
    if not summary_md:
        return ''
    md_content = summary_md.strip()
    if not md_content:
        return ''
    base = os.path.splitext(report_path)[0]
    summary_path = base + '-summary.md'
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info("Summary MD saved: %s", summary_path)
        return summary_path
    except Exception as e:
        logger.error("Failed to save summary MD: %s", e)
        return ''


def _link_summary_to_report(report_path, summary_path):
    """找到匹配的 Report 记录，更新 summary_path"""
    from app import db
    from app.models.report import Report
    try:
        report = Report.query.filter(
            (Report.file_path == report_path) |
            (Report.file_path == os.path.splitext(report_path)[0] + '.json')
        ).first()
        if report:
            report.summary_path = summary_path
            db.session.commit()
    except Exception as e:
        logger.error("Failed to link summary to report: %s", e)


def _read_report(path: str) -> str:
    """读取报告内容，优先 MD，其次 JSON"""
    if not path:
        return ''

    # If .json, try to find corresponding .md
    if path.endswith('.json'):
        # 1) 同名 .md
        md_path = path[:-5] + '.md'
        if os.path.isfile(md_path):
            path = md_path
        else:
            # 2) 从 JSON 内读 filename 字段找实际 MD
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                inner_name = data.get('filename', '')
                if inner_name and inner_name.endswith('.md'):
                    inner_path = os.path.join(os.path.dirname(path), inner_name)
                    if os.path.isfile(inner_path):
                        path = inner_path
            except Exception:
                pass

    if not os.path.isfile(path):
        return ''

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        logger.error("Failed to read report %s: %s", path, e)
        return ''


def _generate_email_summary(report_content: str, report_type: str) -> str:
    """调用 LLM 生成摘要 Markdown（核心洞察 + 数据亮点）"""
    try:
        from app.api.settings import _get_llm_env
        env, model, api_key = _get_llm_env()
        if not api_key:
            return ''

        base_url = env.get('ANTHROPIC_BASE_URL', '')

        truncated = report_content[:6000]

        prompt = (
            "你是一个邮件编辑助手。请根据以下投资研究报告，生成邮件摘要（Markdown格式）。\n\n"
            "要求:\n"
            "1. 输出纯 Markdown，不要用代码块包裹\n"
            "2. 使用 `##` 作为标题，有序列表编号核心洞察(3-5条)\n"
            "3. 用 Markdown 表格展示关键数据\n"
            "4. 只包含核心摘要，完整报告附在链接中\n"
            "5. 不要签名、前言、后记\n"
            "6. 第一个字符不要是 #\n"
            "7. 不要在末尾添加\"查看完整报告\"、\"点击查阅\"等链接文字，完整报告链接由系统自动附加\n\n"
            f"报告类型: {report_type}\n\n"
            f"报告内容:\n{truncated}"
        )

        # Use anthropic SDK directly
        try:
            import anthropic
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = anthropic.Anthropic(**kwargs)

            effective_model = model or 'claude-sonnet-4-20250514'
            resp = client.messages.create(
                model=effective_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return _clean_llm_output(resp.content[0].text)
        except ImportError:
            pass

        # Fallback: use OpenAI-compatible API
        try:
            import urllib.request
            url = f"{base_url.rstrip('/')}/v1/messages" if base_url else 'https://api.anthropic.com/v1/messages'
            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            body = json.dumps({
                'model': model or 'claude-sonnet-4-20250514',
                'max_tokens': 8192,
                'messages': [{'role': 'user', 'content': prompt}],
            }).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            resp = urllib.request.urlopen(req, timeout=180)
            data = json.loads(resp.read())
            return _clean_llm_output(data.get('content', [{}])[0].get('text', ''))
        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            return ''

    except Exception as e:
        logger.error("Failed to generate email HTML: %s", e)
        return ''


def _md_to_simple_html(md_text):
    """将 Markdown 内容转为 HTML（用于邮件摘要）"""
    if not md_text:
        return ''
    import markdown2
    return markdown2.markdown(md_text, extras=['tables', 'fenced-code-blocks'])


def _clean_llm_output(text: str) -> str:
    """清理 LLM 输出：剥离废话前缀、代码块标记"""
    import re
    text = text.strip()
    # 去除 ```markdown ... ``` 或 ``` ... ``` 包裹
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    # 剥离 LLM 前缀废话（如 "好的，以下是..."）
    lines = text.split('\n')
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith(('#', '```', '-', '*', '|', '>', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
            # likely preamble text, skip
            start = i + 1
        else:
            break
    if start > 0 and start < len(lines):
        text = '\n'.join(lines[start:])
    return text.strip()


def _get_site_url() -> str:
    """从 DB 读取站点域名"""
    try:
        from app.models.llm_config import LlmConfig
        return (LlmConfig.get('site_url') or '').rstrip('/')
    except Exception:
        return ''


def _save_report_html(report_path: str, md_content: str) -> str:
    """将 Markdown 报告存储为自渲染 HTML（使用 marked.js）"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        html_dir = os.path.join(base_dir, 'reports', 'html')
        os.makedirs(html_dir, exist_ok=True)

        basename = os.path.basename(report_path)
        name = os.path.splitext(basename)[0]
        date_str = bj_now().strftime('%Y%m%d-%H%M%S')
        html_filename = f'{name}-{date_str}.html'
        html_path = os.path.join(html_dir, html_filename)

        # JSON-escape markdown for safe embedding in JS
        import json as _json
        md_escaped = _json.dumps(md_content)

        full_page = (
            '<!DOCTYPE html>\n'
            '<html lang="zh-CN"><head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '<title>IntelHub Report</title>\n'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown-light.min.css">\n'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github.min.css">\n'
            '<style>\n'
            'body{margin:0;padding:0;background:#f7fafc;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}\n'
            '.container{max-width:860px;margin:24px auto;padding:40px;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08)}\n'
            '</style>\n'
            '</head><body>\n'
            '<div class="container">\n'
            '<article class="markdown-body" id="content"></article>\n'
            '</div>\n'
            '<script src="https://cdn.jsdelivr.net/npm/marked@15/marked.min.js"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/highlight.min.js"></script>\n'
            '<script>\n'
            'marked.setOptions({ gfm: true, breaks: false });\n'
            'document.getElementById("content").innerHTML = marked.parse(' + md_escaped + ');\n'
            '</script>\n'
            '</body></html>'
        )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(full_page)

        logger.info("Report HTML saved: %s", html_path)
        return html_filename
    except Exception as e:
        logger.error("Failed to save report HTML: %s", e)
        return ''


def _build_email_body(summary_html: str, view_link: str, report_type: str) -> str:
    """构建邮件内容：摘要 + 在线查看链接"""
    type_label = {'insight': '投资洞察', 'agent': '分析报告', 'heartbeat': '健康检测'}.get(report_type, '分析报告')
    date_str = bj_now().strftime('%Y-%m-%d')

    header = (
        '<div style="max-width:680px;margin:0 auto;font-family:-apple-system,sans-serif;padding:20px">'
        '<h1 style="color:#1a365d;border-bottom:2px solid #3182ce;padding-bottom:10px">'
        f'IntelHub {type_label} · {date_str}</h1>'
    )

    body = summary_html or '<p style="color:#2d3748">新报告已生成。</p>'

    footer = (
        '<hr style="margin:30px 0 10px;border-color:#e2e8f0">'
        '<p style="color:#a0aec0;font-size:12px">此邮件由 IntelHub 智能平台自动发送</p>'
        '</div>'
    )

    # 在线查看链接
    link_section = ''
    if view_link:
        link_section = (
            '<div style="margin:24px 0;text-align:center">'
            f'<a href="{view_link}" style="display:inline-block;background:#3182ce;color:#fff;padding:12px 28px;'
            'border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">'
            '查看完整报告 →</a>'
            f'<p style="margin:10px 0 0;color:#a0aec0;font-size:12px">'
            f'<a href="{view_link}" style="color:#a0aec0;word-break:break-all">{view_link}</a></p>'
            '</div>'
        )

    return header + body + link_section + footer


def _build_subject(report_type: str) -> str:
    type_labels = {
        'insight': '投资洞察报告',
        'agent': 'Agent 分析报告',
        'heartbeat': '系统健康报告',
    }
    label = type_labels.get(report_type, '分析报告')
    date_str = bj_now().strftime('%Y-%m-%d')
    return f'[IntelHub] {label} — {date_str}'
