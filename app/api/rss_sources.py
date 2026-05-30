"""RSS 数据源 API — 内置 RSS 源管理（从 OPML 导入 + CRUD）"""
from flask import Blueprint, request
from app.utils.helpers import standard_response, error_response
from app import db
from app.models.rss_source import RssSource

bp = Blueprint('rss_sources', __name__, url_prefix='/api/v1/rss-sources')


@bp.route('', methods=['GET'])
def list_sources():
    """列出 RSS 源，支持 ?category=新闻&q=keyword"""
    query = RssSource.query
    cat = request.args.get('category')
    q = request.args.get('q', '').strip()
    if cat:
        query = query.filter_by(category=cat)
    if q:
        query = query.filter(
            db.or_(RssSource.name.contains(q), RssSource.url.contains(q), RssSource.slug.contains(q))
        )
    sources = query.order_by(RssSource.category, RssSource.name).all()
    return standard_response({
        'sources': [s.to_dict() for s in sources],
        'total': len(sources),
    })


@bp.route('/categories', methods=['GET'])
def categories():
    """返回所有分类及计数"""
    rows = db.session.query(
        RssSource.category, db.func.count(RssSource.id)
    ).group_by(RssSource.category).all()
    cats = {row[0]: row[1] for row in rows}
    return standard_response(cats)


@bp.route('', methods=['POST'])
def add_source():
    """手动添加 RSS 源"""
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    url = (payload.get('url') or '').strip()
    category = (payload.get('category') or '其他').strip()
    if not name or not url:
        return error_response(400, 'name 和 url 必填')
    existing = RssSource.query.filter_by(url=url).first()
    if existing:
        return error_response(409, '该 URL 已存在')

    slug = (payload.get('slug') or '').strip()
    if slug:
        if RssSource.query.filter_by(slug=slug).first():
            return error_response(409, '该别名已存在')
    else:
        slug = RssSource.make_unique_slug(name, url)

    src = RssSource(name=name, slug=slug, url=url, category=category,
                    description=payload.get('description', ''))
    db.session.add(src)
    db.session.commit()
    return standard_response(src.to_dict())


@bp.route('/<int:src_id>', methods=['PUT'])
def update_source(src_id):
    """编辑 RSS 源"""
    src = RssSource.query.get(src_id)
    if not src:
        return error_response(404, '未找到')
    payload = request.get_json(silent=True) or {}
    if 'name' in payload:
        src.name = payload['name'].strip() or src.name
    if 'slug' in payload:
        new_slug = payload['slug'].strip()
        if new_slug:
            dup = RssSource.query.filter(RssSource.slug == new_slug, RssSource.id != src_id).first()
            if dup:
                return error_response(409, '该别名已被其他源使用')
            src.slug = new_slug
    if 'url' in payload:
        new_url = payload['url'].strip()
        dup = RssSource.query.filter(RssSource.url == new_url, RssSource.id != src_id).first()
        if dup:
            return error_response(409, '该 URL 已被其他源使用')
        src.url = new_url
    if 'category' in payload:
        src.category = payload['category'].strip() or src.category
    if 'description' in payload:
        src.description = payload['description']
    if 'enabled' in payload:
        src.enabled = bool(payload['enabled'])
    db.session.commit()
    return standard_response(src.to_dict())


@bp.route('/<int:src_id>/toggle', methods=['PUT'])
def toggle_source(src_id):
    """切换 RSS 源启用状态"""
    src = RssSource.query.get(src_id)
    if not src:
        return error_response(404, '未找到')
    src.enabled = not src.enabled
    db.session.commit()
    return standard_response(src.to_dict())


@bp.route('/batch-delete', methods=['POST'])
def batch_delete():
    """批量删除 RSS 源"""
    payload = request.get_json(silent=True) or {}
    ids = payload.get('ids', [])
    if not ids:
        return error_response(400, 'ids 不能为空')
    deleted = RssSource.query.filter(RssSource.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return standard_response({'deleted': deleted})


@bp.route('/<int:src_id>', methods=['DELETE'])
def delete_source(src_id):
    """删除 RSS 源"""
    src = RssSource.query.get(src_id)
    if not src:
        return error_response(404, '未找到')
    db.session.delete(src)
    db.session.commit()
    return standard_response({'deleted': True})


@bp.route('/import-opml', methods=['POST'])
def import_opml():
    """从 OPML 种子数据导入（内嵌在 seed 脚本中，此接口供前端手动触发重导入）"""
    try:
        from scripts.seed_rss_sources import seed_from_url
        count = seed_from_url()
        return standard_response({'imported': count})
    except Exception as e:
        return error_response(500, f'导入失败: {e}')
