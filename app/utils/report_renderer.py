"""Report renderer — renders Markdown report to H5 HTML page"""

import os
import uuid
from datetime import datetime

import markdown
from flask import current_app


def render_report_page(
    report_md: str,
    highlights: list,
    output_path: str,
    title: str = '智能日报',
) -> str:
    """Render report Markdown + highlights into an H5 HTML file.

    Args:
        report_md: Markdown content of the report
        highlights: list of {"platform": str, "text": str, "url": str}
        output_path: absolute file path to write HTML
        title: page title

    Returns:
        The relative path under static/ for URL generation
    """
    from flask import render_template

    content_html = markdown.markdown(
        report_md,
        extensions=['extra', 'nl2br', 'tables'],
    )

    now = bj_now()
    html = render_template('reports/daily.html',
        title=title,
        date=now.strftime('%Y-%m-%d %A'),
        year=now.year,
        highlights=highlights,
        content_html=content_html,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return os.path.relpath(output_path, current_app.static_folder)


def generate_access_token() -> str:
    return uuid.uuid4().hex
