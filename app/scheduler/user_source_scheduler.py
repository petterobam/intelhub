"""User source scheduler — fetches user content sources independently from main scheduler."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from app.utils.helpers import bj_now

logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='user-src')


def fetch_user_source(source):
    """Fetch a single user source, save results to user directory."""
    from app import db
    try:
        from crawlers.user_sources.dispatcher import get_adapter
        adapter = get_adapter(source.type)
        items = adapter.fetch(source.source_id, since=source.last_fetched)

        # Save to user directory
        out_dir = os.path.join(DATA_DIR, 'users', source.user_id, 'sources', source.id)
        os.makedirs(out_dir, exist_ok=True)
        ts = bj_now().strftime('%Y-%m-%dT%H-%M-%S')
        path = os.path.join(out_dir, f'{ts}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'source_id': source.id,
                'source_type': source.type,
                'items': items,
                'fetched_at': ts,
            }, f, ensure_ascii=False, indent=2)

        source.last_fetched = bj_now()
        source.item_count = len(items)
        source.status = 'active'
        source.last_error = None
        db.session.commit()
        logger.info(f"Fetched {len(items)} items from {source.type}:{source.source_id} for user {source.user_id}")
    except Exception as e:
        logger.error(f"Fetch failed for source {source.id}: {e}")
        source.status = 'error'
        source.last_error = str(e)[:500]
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def schedule_all_user_sources(scheduler):
    """Register a cron job to fetch all active user sources every 6 hours."""
    def _run():
        try:
            from flask import current_app
            with current_app.app_context():
                from app.models.user_source import UserSource
                sources = UserSource.query.filter_by(enabled=True).filter(
                    UserSource.status.in_(['active', 'error'])
                ).all()
                if not sources:
                    return
                logger.info(f"Fetching {len(sources)} user sources")
                for src in sources:
                    _executor.submit(fetch_user_source, src)
        except Exception as e:
            logger.error(f"User source scheduler error: {e}")

    scheduler.add_job(_run, 'cron', hour='*/6', minute=30, id='user_sources_fetch', replace_existing=True)
    logger.info("User source scheduler registered (every 6 hours at :30)")
