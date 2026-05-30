"""爬虫 API"""
from flask import Blueprint, request
from app import db
from app.utils.helpers import standard_response, error_response
import uuid, os, json, glob, yaml
from datetime import datetime

bp = Blueprint('crawlers', __name__, url_prefix='/api/v1/crawlers')

@bp.route('', methods=['GET'])
def list_crawlers():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, 'crawlers', 'config', 'platforms.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    all_platforms = {}
    for category in ['hot_topics', 'policy', 'exchange', 'financial']:
        for pid, pdata in config.get(category, {}).items():
            all_platforms[pid] = {**pdata, 'category': category}
    return standard_response(all_platforms)

@bp.route('/<name>/status', methods=['GET'])
def crawler_status(name):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, 'data', 'raw')
    
    for subdir in ['hot_topics', 'policy', 'exchange', 'financial']:
        pattern = os.path.join(data_dir, subdir, f'{name}-*.json')
        files = glob.glob(pattern)
        if files:
            latest = max(files, key=os.path.getmtime)
            age = int((bj_now().timestamp() - os.path.getmtime(latest)) / 60)
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    item_count = len(data.get('items', [])) if isinstance(data, dict) else (len(data) if isinstance(data, list) else 0)
            except:
                item_count = 0
            return standard_response({
                'name': name, 'category': subdir, 'latest_file': os.path.basename(latest),
                'age_minutes': age, 'item_count': item_count,
                'status': 'fresh' if age < 120 else ('stale' if age < 360 else 'critical')
            })
    return standard_response({'name': name, 'status': 'not_found', 'message': 'No data found'})

@bp.route('/<name>/run', methods=['POST'])
def run_crawler(name):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 查找对应的 wrapper 脚本
    wrapper_map = {
        '36kr': 'run_hot_topics.sh', 'weibo': 'run_hot_topics.sh', 'zhihu': 'run_hot_topics.sh',
        'huanqiu': 'run_hot_topics.sh', 'huxiu': 'run_hot_topics.sh', 'eastmoney': 'run_hot_topics.sh',
        'paper': 'run_hot_topics.sh', 'wangyi': 'run_hot_topics.sh', 'douyin': 'run_hot_topics.sh',
    }
    script = wrapper_map.get(name, 'run_hot_topics.sh')
    script_path = os.path.join(base_dir, 'scripts', 'cron_wrappers', script)
    
    return standard_response({
        'message': f'Crawler {name} ready for Hermes Browser execution',
        'script': script,
        'note': 'Browser automation handled by Hermes Agent'
    })


# ── Crawler Node CRUD（数据库管理）──────────────────────────────

@bp.route('/nodes', methods=['GET'])
def list_crawler_nodes():
    """列出所有爬虫节点（DB中用户定义的 + 从platforms.yaml加载的）"""
    from app.models.crawler_node import CrawlerNode
    nodes = CrawlerNode.query.order_by(CrawlerNode.category, CrawlerNode.platform_id).all()

    # 也从 platforms.yaml 加载内置节点（只读）
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, 'crawlers', 'config', 'platforms.yaml')
    builtin = {}
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        for cat, platforms in config.items():
            for pid, pdata in (platforms or {}).items():
                builtin[pid] = {**pdata, 'category': cat, 'platform_id': pid, 'builtin': True, 'db_id': None}
    except Exception:
        pass

    # 合并：DB节点覆盖yaml节点（如果platform_id冲突）
    merged = {}
    for n in nodes:
        merged[n.platform_id] = {**n.to_dict(), 'builtin': False}
    # yaml内置节点（排除DB已覆盖的）
    for pid, pdata in builtin.items():
        if pid not in merged:
            merged[pid] = pdata

    return standard_response({'nodes': list(merged.values()), 'total': len(merged)})


@bp.route('/nodes/<node_id>', methods=['GET'])
def get_crawler_node(node_id):
    from app.models.crawler_node import CrawlerNode
    # 支持通过 db id 或 platform_id 查询
    node = db.session.get(CrawlerNode, node_id)
    if not node:
        node = CrawlerNode.query.filter_by(platform_id=node_id).first()
    if not node:
        return standard_response({'error': 'not_found'}), 404
    return standard_response(node.to_dict())


@bp.route('/nodes', methods=['POST'])
def create_crawler_node():
    """创建新爬虫节点"""
    from app.models.crawler_node import CrawlerNode
    data = request.get_json() or {}

    if not data.get('name') or not data.get('platform_id') or not data.get('category'):
        return standard_response({'error': 'name, platform_id, category required'}), 400

    existing = CrawlerNode.query.filter_by(platform_id=data['platform_id']).first()
    if existing:
        return standard_response({'error': 'platform_id already exists'}), 409

    node = CrawlerNode(
        id=str(uuid.uuid4())[:8],
        name=data['name'],
        platform_id=data['platform_id'],
        category=data['category'],
        url=data.get('url', ''),
        method=data.get('method', 'browser'),
        schedule=data.get('schedule', ''),
        priority=data.get('priority', 'medium'),
        enabled=data.get('enabled', True),
    )
    if data.get('config'):
        node.set_config(data['config'])
    db.session.add(node)
    db.session.commit()
    return standard_response(node.to_dict()), 201


@bp.route('/nodes/<node_id>', methods=['PUT'])
def update_crawler_node(node_id):
    """更新爬虫节点"""
    from app.models.crawler_node import CrawlerNode
    node = db.session.get(CrawlerNode, node_id)
    if not node:
        node = CrawlerNode.query.filter_by(platform_id=node_id).first()
    if not node:
        return standard_response({'error': 'not_found'}), 404

    data = request.get_json() or {}
    for key in ['name', 'platform_id', 'category', 'url', 'method', 'schedule', 'priority', 'enabled']:
        if key in data:
            setattr(node, key, data[key])
    if 'config' in data:
        node.set_config(data['config'])
    db.session.commit()
    return standard_response(node.to_dict())


@bp.route('/nodes/<node_id>', methods=['DELETE'])
def delete_crawler_node(node_id):
    """删除爬虫节点（只能删除用户创建的，builtin节点不能删）"""
    from app.models.crawler_node import CrawlerNode
    node = db.session.get(CrawlerNode, node_id)
    if not node:
        node = CrawlerNode.query.filter_by(platform_id=node_id).first()
    if not node:
        return standard_response({'error': 'not_found'}), 404
    db.session.delete(node)
    db.session.commit()
    return standard_response({'deleted': node_id})
