"""RssSource model — 平台内置 RSS 数据源（从 OPML 导入）"""
import re

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text

from app import db
from app.utils.helpers import bj_now


def _generate_slug(name: str, url: str) -> str:
    """从名称或 URL 生成英文别名

    优先取 URL 路径部分（跳过纯聚合域名如 plink.anyfeeder.com），
    其次取域名，最后回退到名称中的 ASCII 字符。
    """
    path = url.split('://', 1)[-1] if '://' in url else url
    parts = [p for p in path.split('/') if p]

    # parts[0] 是域名，parts[1:] 是路径段
    domain = parts[0].lower().replace('www.', '') if parts else ''
    # 常见聚合域名不算有效 slug
    aggregator_domains = {'plink.anyfeeder.com', 'feedx.net', 'rsshub.app'}
    if len(parts) > 1 and domain in aggregator_domains:
        # 聚合域名：取路径段拼接
        slug = '-'.join(parts[1:]).lower()
    elif domain and domain not in aggregator_domains:
        # 普通域名：取主域名部分
        slug = domain.split('.')[0]
    else:
        ascii_part = re.sub(r'[^a-zA-Z0-9]', '', name)
        slug = ascii_part.lower() if ascii_part else 'rss'

    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return slug or 'rss'


class RssSource(db.Model):
    __tablename__ = 'rss_sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    url = Column(String(512), nullable=False, unique=True)
    category = Column(String(64), nullable=False, default='其他')
    description = Column(String(512), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)

    @staticmethod
    def make_unique_slug(name: str, url: str) -> str:
        """生成不重复的 slug，冲突时追加数字后缀"""
        base = _generate_slug(name, url)
        slug = base
        n = 1
        while RssSource.query.filter_by(slug=slug).first():
            n += 1
            slug = f'{base}-{n}'
        return slug

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'url': self.url,
            'category': self.category,
            'description': self.description,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
