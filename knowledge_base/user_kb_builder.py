"""UserKBBuilder — 从用户日报和订阅源数据构建个人知识库"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')


def _user_kb_dir(user_id):
    return os.path.join(DATA_DIR, 'users', user_id, 'kb')


def _user_reports_dir(user_id):
    return os.path.join(DATA_DIR, 'users', user_id, 'reports', 'daily')


def _user_sources_dir(user_id):
    return os.path.join(DATA_DIR, 'users', user_id, 'sources')


class UserKBBuilder:
    """从用户日报和订阅源数据构建个人知识库"""

    def build(self, user_id: str) -> dict:
        kb_dir = _user_kb_dir(user_id)
        os.makedirs(kb_dir, exist_ok=True)

        # 1. Load historical reports
        reports = self._load_reports(user_id)

        # 2. Load user source data
        source_items = self._load_source_items(user_id)

        # 3. Get user tags
        tags = self._get_user_tags(user_id)

        # 4. Load upload items
        upload_items = self._load_upload_items(user_id)

        # 5. Extract entities based on tags
        all_items = reports + source_items + upload_items
        entities = self._extract_entities(all_items, tags)

        # 5. Build timeline
        timeline = self._build_timeline(entities)

        # 6. Build topic index
        topics = self._build_topics(all_items)

        # 7. Write KB files
        self._write_kb(kb_dir, timeline, topics, entities, len(reports))

        return {
            'status': 'success',
            'entity_count': len(entities),
            'report_count': len(reports),
            'source_items': len(source_items),
        }

    def _load_reports(self, user_id):
        reports_dir = _user_reports_dir(user_id)
        if not os.path.isdir(reports_dir):
            return []
        items = []
        for f in sorted(os.listdir(reports_dir)):
            if not f.endswith('.md'):
                continue
            path = os.path.join(reports_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                date_str = f.replace('.md', '')
                # Parse sections from markdown
                lines = content.split('\n')
                current_section = ''
                for line in lines:
                    if line.startswith('## '):
                        current_section = line[3:].strip()
                    elif line.strip() and not line.startswith('#'):
                        items.append({
                            'title': current_section or line.strip()[:80],
                            'content': line.strip(),
                            'timestamp': date_str,
                            'date': date_str,
                            'source': 'daily_report',
                        })
            except Exception:
                continue
        return items

    def _load_source_items(self, user_id):
        import glob
        sources_dir = _user_sources_dir(user_id)
        if not os.path.isdir(sources_dir):
            return []
        items = []
        for source_id in os.listdir(sources_dir):
            source_dir = os.path.join(sources_dir, source_id)
            if not os.path.isdir(source_dir):
                continue
            files = sorted(glob.glob(os.path.join(source_dir, '*.json')), reverse=True)
            for f in files[:3]:
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    for item in data.get('items', []):
                        item['source'] = 'user_subscription'
                        items.append(item)
                except Exception:
                    continue
        return items

    def _get_user_tags(self, user_id):
        try:
            from app.models.user_profile import UserProfile
            profile = UserProfile.query.get(user_id)
            return profile.interest_tags if profile else []
        except Exception:
            return []

    def _extract_entities(self, items, tags):
        result = {}
        for tag in tags:
            kw = tag.get('value', '')
            if not kw:
                continue
            matched = []
            for i in items:
                text = (i.get('title', '') + ' ' + i.get('content', '')).lower()
                if kw.lower() in text:
                    matched.append(i)
            if matched:
                result[kw] = matched
        return result

    def _build_timeline(self, entities):
        timeline = {}
        for entity, items in entities.items():
            sorted_items = sorted(items, key=lambda x: x.get('timestamp', ''), reverse=True)
            timeline[entity] = sorted_items
        return timeline

    def _build_topics(self, items):
        topics = {}
        for item in items:
            date = item.get('date', item.get('timestamp', ''))[:10] if item.get('timestamp', item.get('date', '')) else ''
            if not date:
                continue
            if date not in topics:
                topics[date] = []
            topics[date].append({
                'title': item.get('title', '')[:100],
                'source': item.get('source', ''),
            })
        return topics

    def _write_kb(self, kb_dir, timeline, topics, entities, report_count):
        # Timeline
        timeline_dir = os.path.join(kb_dir, 'timeline')
        os.makedirs(timeline_dir, exist_ok=True)
        for entity, items in timeline.items():
            safe_name = entity.replace('/', '_').replace('\\', '_')
            with open(os.path.join(timeline_dir, f'{safe_name}.json'), 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

        # Topics
        topics_dir = os.path.join(kb_dir, 'topics')
        os.makedirs(topics_dir, exist_ok=True)
        with open(os.path.join(topics_dir, 'topic_index.json'), 'w', encoding='utf-8') as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)

        # Entities
        entity_list = []
        for entity, items in entities.items():
            entity_list.append({
                'name': entity,
                'item_count': len(items),
                'last_date': items[0].get('timestamp', '')[:10] if items else None,
            })
        with open(os.path.join(kb_dir, 'entities.json'), 'w', encoding='utf-8') as f:
            json.dump(entity_list, f, ensure_ascii=False, indent=2)

        # Index
        index = {
            'updated_at': datetime.now().isoformat(),
            'entity_count': len(entities),
            'report_count': report_count,
            'topic_count': len(topics),
        }
        with open(os.path.join(kb_dir, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _load_upload_items(self, user_id):
        """Load parsed upload file content."""
        uploads_dir = os.path.join(_user_kb_dir(user_id), 'uploads')
        if not os.path.isdir(uploads_dir):
            return []
        items = []
        for fname in os.listdir(uploads_dir):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(uploads_dir, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                paragraphs = [p for p in data.get('text', '').split('\n\n') if len(p.strip()) > 20]
                for p in paragraphs[:50]:
                    items.append({
                        'title': data.get('title', ''),
                        'content': p.strip(),
                        'timestamp': data.get('ingested_at', ''),
                        'date': (data.get('ingested_at', '') or '')[:10],
                        'source': 'upload',
                        '_upload_id': data.get('upload_id', ''),
                    })
            except Exception:
                continue
        return items
