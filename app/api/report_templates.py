"""报告模板 API"""
from flask import Blueprint, request
from app import db
from app.models.report_template import ReportTemplate
from app.utils.helpers import standard_response, error_response

bp = Blueprint('report_templates', __name__, url_prefix='/api/v1/report-templates')


@bp.route('', methods=['GET'])
def list_templates():
    templates = ReportTemplate.query.order_by(ReportTemplate.updated_at.desc()).all()
    return standard_response([t.to_dict() for t in templates])


@bp.route('', methods=['POST'])
def create_template(data=None):
    if data is None:
        data = request.get_json()
    t = ReportTemplate(
        id=data.get('id') or data['name'][:8].lower().replace(' ', '-'),
        name=data['name'],
        description=data.get('description', ''),
        prompt_template=data['prompt_template'],
        data_sources=data.get('data_sources', []),
        trend_reference=data.get('trend_reference', True),
        max_items_per_source=data.get('max_items_per_source', 50),
        task_id=data.get('task_id'),
    )
    db.session.add(t)
    db.session.commit()
    return standard_response(t.to_dict()), 201


@bp.route('/<template_id>', methods=['GET'])
def get_template(template_id):
    t = db.session.get(ReportTemplate, template_id)
    if not t:
        return error_response(404, 'Template not found'), 404
    return standard_response(t.to_dict())


@bp.route('/<template_id>', methods=['PUT'])
def update_template(template_id):
    t = db.session.get(ReportTemplate, template_id)
    if not t:
        return error_response(404, 'Template not found'), 404
    data = request.get_json()
    for key in ['name', 'description', 'prompt_template', 'data_sources',
                'trend_reference', 'max_items_per_source', 'task_id']:
        if key in data:
            setattr(t, key, data[key])
    t.updated_at = db.func.now()
    db.session.commit()
    return standard_response(t.to_dict())


@bp.route('/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    t = db.session.get(ReportTemplate, template_id)
    if not t:
        return error_response(404, 'Template not found'), 404
    db.session.delete(t)
    db.session.commit()
    return standard_response({'deleted': template_id})


@bp.route('/<template_id>/preview', methods=['POST'])
def preview_template(template_id):
    """预览渲染后的提示词（不执行，只看填充效果）"""
    t = db.session.get(ReportTemplate, template_id)
    if not t:
        return error_response(404, 'Template not found'), 404
    # 用空上下文预览
    preview = t.render_prompt({
        'health': '[系统健康数据]',
        'previous_report': '[历史趋势对比]',
        'resonance': '[共振分析结果]',
        'trends': '[话题趋势]',
        'hot_topics': '[热点数据]',
        'policy_data': '[政策数据]',
        'exchange_data': '[交易所数据]',
        'financial_data': '[财经数据]',
        'date': '[当前日期]',
    })
    return standard_response({'preview': preview})
