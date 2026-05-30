"""Personalized report generator — generates per-user daily reports filtered by interest tags."""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
REPORTS_DIR = os.path.join(PROJECT_DIR, 'reports')


def _load_aggregated_data(max_items=200):
    """Load the latest aggregated data from processed/ or raw/."""
    processed_dir = os.path.join(DATA_DIR, 'processed')
    if os.path.isdir(processed_dir):
        for f in sorted(os.listdir(processed_dir), reverse=True):
            if f.endswith('.json') and 'aggregat' in f.lower():
                path = os.path.join(processed_dir, f)
                try:
                    with open(path, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    if isinstance(data, list):
                        return data[:max_items]
                    if isinstance(data, dict):
                        items = data.get('items', data.get('data', []))
                        return items[:max_items]
                except Exception:
                    continue

    # Fallback: scan raw modules
    items = []
    raw_dir = os.path.join(DATA_DIR, 'raw')
    if not os.path.isdir(raw_dir):
        return items
    for module in os.listdir(raw_dir):
        module_path = os.path.join(raw_dir, module)
        if not os.path.isdir(module_path):
            continue
        for source in os.listdir(module_path):
            source_path = os.path.join(module_path, source)
            if not os.path.isdir(source_path):
                continue
            for f in os.listdir(source_path):
                if not f.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(source_path, f), 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                item.setdefault('_platform', source)
                                items.append(item)
                except Exception:
                    continue
    return items[:max_items]


def _load_data_by_sources(sources, max_items=200):
    """按数据源类型加载数据。sources 为 ["hot_topics", "policy", ...] 格式。
    不指定或为空则加载全部。"""
    if not sources:
        return _load_aggregated_data(max_items)

    raw_dir = os.path.join(DATA_DIR, 'raw')
    if not os.path.isdir(raw_dir):
        return _load_aggregated_data(max_items)

    items = []
    for source_type in sources:
        source_dir = os.path.join(raw_dir, source_type)
        if not os.path.isdir(source_dir):
            continue
        for subdir in os.listdir(source_dir):
            subdir_path = os.path.join(source_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue
            json_files = sorted(
                [f for f in os.listdir(subdir_path) if f.endswith('.json')],
                key=lambda f: os.path.getmtime(os.path.join(subdir_path, f)),
                reverse=True,
            )
            if not json_files:
                continue
            try:
                with open(os.path.join(subdir_path, json_files[0]), 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item.setdefault('_platform', subdir)
                            items.append(item)
                elif isinstance(data, dict):
                    for item in (data.get('items', data.get('data', []))):
                        if isinstance(item, dict):
                            item.setdefault('_platform', subdir)
                            items.append(item)
            except Exception:
                continue

    if not items:
        return _load_aggregated_data(max_items)
    return items[:max_items]


def _extract_highlights(items, max_count=5):
    """Extract top highlights from filtered items."""
    highlights = []
    for item in items[:max_count]:
        text = item.get('title', '') or item.get('content', '') or ''
        if len(text) > 150:
            text = text[:150] + '...'
        highlights.append({
            'platform': item.get('_platform', item.get('source', '未知')),
            'text': text,
            'url': item.get('url', item.get('link', '')),
        })
    return highlights


def generate_personal_report(user_id: str, app=None):
    """Generate a personalized daily report for a user.

    Must be called within a Flask app context.
    """
    from app import db
    from app.models.user import User
    from app.models.user_profile import UserProfile
    from app.models.report import Report
    from analysis.personalized.filter import filter_items_by_tags

    user = User.query.get(user_id)
    if not user or not user.enabled:
        logger.warning(f"User {user_id} not found or disabled, skipping")
        return None

    profile = UserProfile.query.get(user_id)
    if not profile or not profile.interest_tags:
        logger.info(f"User {user_id} has no interest tags, skipping")
        return None

    # Load data — platforms 现在是数据源类型 ["hot_topics", "policy", ...]
    selected_sources = profile.platforms or []
    items = _load_data_by_sources(selected_sources)

    # Load user source data (if any)
    user_source_items = _load_user_source_items(user_id)
    if user_source_items:
        items = items + user_source_items

    if not items:
        logger.warning("No aggregated data available")
        return None

    # Filter by user tags (不再传 platforms 过滤，已在加载时按类型筛选)
    filtered = filter_items_by_tags(items, profile.interest_tags)
    if not filtered:
        logger.info(f"No matching items for user {user_id}")
        return None

    # Keep top 50
    filtered = filtered[:50]
    highlights = _extract_highlights(filtered)

    # Generate report content via analysis engine (if available)
    today = datetime.now().strftime('%Y-%m-%d')
    tag_values = [t['value'] for t in profile.interest_tags]

    try:
        from analysis.engine import AnalysisEngine
        engine = AnalysisEngine()
        if engine.is_available():
            system_prompt = (
                f"你是一个专业的投资情报分析助手。用户关注的标签：{', '.join(tag_values)}。\n"
                "请根据提供的数据生成一份简洁的个人投资日报，重点关注用户感兴趣的内容。"
            )
            context = json.dumps(filtered[:30], ensure_ascii=False, indent=2)
            result = engine.analyze('personal_daily', system_prompt, context, max_turns=3)
            report_md = result.get('report', result.get('content', ''))
        else:
            report_md = _build_offline_report(filtered, tag_values, today)
    except Exception as e:
        logger.warning(f"Engine analysis failed, using offline: {e}")
        report_md = _build_offline_report(filtered, tag_values, today)

    # Save markdown
    user_report_dir = os.path.join(REPORTS_DIR, 'users', user_id, 'daily')
    os.makedirs(user_report_dir, exist_ok=True)
    md_path = os.path.join(user_report_dir, f'{today}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report_md)

    # Generate H5 page
    html_path = None
    access_token = None
    try:
        from app.utils.report_renderer import render_report_page, generate_access_token
        static_dir = os.path.join(PROJECT_DIR, 'static', 'reports', 'users', user_id)
        html_file = os.path.join(static_dir, f'{today}.html')
        html_path = render_report_page(report_md, highlights, html_file, title=f'{user.display_name or user.email} 的日报')
        access_token = generate_access_token()
    except Exception as e:
        logger.warning(f"H5 render failed: {e}")

    # Save to DB
    report = Report(
        title=f'个人日报 - {today}',
        report_type='personal_daily',
        file_path=os.path.relpath(md_path, PROJECT_DIR),
        user_id=user_id,
        scope='personal',
        html_path=html_path,
        access_token=access_token,
    )
    db.session.add(report)
    db.session.commit()

    logger.info(f"Personal report generated for user {user_id}: {md_path}")

    # Async KB build for v4+ users
    try:
        user_tier = user.effective_tier
        from app.utils.auth import TIER_ORDER
        if TIER_ORDER.index(user_tier) >= TIER_ORDER.index('v4'):
            import threading
            from knowledge_base.user_kb_builder import UserKBBuilder

            def _async_kb_build(uid):
                try:
                    UserKBBuilder().build(uid)
                except Exception as e:
                    logger.warning(f"User KB build failed for {uid}: {e}")

            threading.Thread(target=_async_kb_build, args=(user_id,), daemon=True).start()
    except Exception as e:
        logger.warning(f"KB build trigger failed: {e}")

    return {
        'report_path': md_path,
        'html_path': html_path,
        'highlights': highlights,
        'access_token': access_token,
        'report_id': report.id,
    }


def _build_offline_report(items, tag_values, date_str):
    """Build a simple markdown report without AI."""
    lines = [f'# 个人投资日报 - {date_str}', '']
    lines.append(f'关注标签: {", ".join(tag_values)}')
    lines.append(f'筛选条目: {len(items)} 条')
    lines.append('')

    for i, item in enumerate(items[:20], 1):
        title = item.get('title', '无标题')
        source = item.get('_platform', item.get('source', ''))
        matched = item.get('match_tags', [])
        lines.append(f'## {i}. {title}')
        if source:
            lines.append(f'来源: {source}')
        if matched:
            lines.append(f'匹配: {", ".join(matched)}')
        content = item.get('content', item.get('summary', ''))
        if content:
            # Truncate long content
            if len(content) > 500:
                content = content[:500] + '...'
            lines.append(f'\n{content}')
        lines.append('')

    return '\n'.join(lines)


def _load_user_source_items(user_id: str) -> list:
    """Load latest data from all user subscription sources."""
    import glob
    sources_dir = os.path.join(DATA_DIR, 'users', user_id, 'sources')
    if not os.path.isdir(sources_dir):
        return []
    items = []
    for source_id in os.listdir(sources_dir):
        source_dir = os.path.join(sources_dir, source_id)
        if not os.path.isdir(source_dir):
            continue
        files = sorted(glob.glob(os.path.join(source_dir, '*.json')), reverse=True)
        if not files:
            continue
        try:
            with open(files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data.get('items', []):
                item['_source'] = 'user_subscription'
                item['_source_id'] = source_id
                items.append(item)
        except Exception:
            continue
    return items
