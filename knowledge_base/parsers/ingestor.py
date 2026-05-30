"""Ingestor — parse uploaded files and write to user KB."""

import json
import logging
import os
from datetime import datetime

from app.utils.helpers import bj_now

logger = logging.getLogger(__name__)


def ingest_upload(upload_id: str):
    """Parse uploaded file and ingest into user KB."""
    from app import db
    from app.models.user_upload import UserUpload
    from app.utils.user_dirs import user_kb_dir, assert_within_user_dir

    upload = db.session.get(UserUpload, upload_id)
    if not upload:
        return

    upload.status = 'parsing'
    db.session.commit()

    try:
        # Parse
        if upload.ext == 'url':
            from knowledge_base.parsers.url_parser import UrlParser
            result = UrlParser().fetch_and_parse(upload.source_url)
        else:
            from knowledge_base.parsers.dispatcher import get_parser
            parser = get_parser(upload.ext)
            result = parser.parse(upload.path)

        # Write to KB uploads directory
        kb_uploads_dir = os.path.join(user_kb_dir(upload.user_id), 'uploads')
        os.makedirs(kb_uploads_dir, exist_ok=True)
        assert_within_user_dir(upload.user_id, kb_uploads_dir)

        text = result['text'][:50000]
        truncated = len(result['text']) > 50000

        out_path = os.path.join(kb_uploads_dir, f'{upload_id}.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'upload_id': upload_id,
                'title': result['title'],
                'text': text,
                'char_count': result['char_count'],
                'truncated': truncated,
                'metadata': result['metadata'],
                'ingested_at': datetime.now().isoformat(),
            }, f, ensure_ascii=False)

        # Trigger KB rebuild
        try:
            from knowledge_base.user_kb_builder import UserKBBuilder
            UserKBBuilder().build(upload.user_id)
        except Exception as e:
            logger.warning(f"KB rebuild after ingest failed: {e}")

        upload.status = 'ready'
        upload.char_count = result['char_count']
        upload.ingested_at = bj_now()

    except Exception as e:
        logger.error(f"Ingest failed for upload {upload_id}: {e}")
        upload.status = 'error'
        upload.parse_error = str(e)[:500]

    db.session.commit()
