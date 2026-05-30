"""Payment API — 订单创建、回调、查询"""
from flask import Blueprint, request
from app.utils.helpers import standard_response, error_response, bj_now
from app.utils.auth import login_required, admin_required
from app import db
from flask import g
from sqlalchemy import func, text
from datetime import datetime, timedelta

bp = Blueprint('payments', __name__, url_prefix='/api/v1/payments')

TIER_PRICES = {
    'v1': 900,
    'v2': 2900,
    'v3': 5900,
    'v4': 9900,
}


def _activate_tier(user_id, tier):
    """支付成功后激活用户会员"""
    from app.models.user import User
    from datetime import timedelta
    user = User.query.get(user_id)
    if not user:
        return
    user.tier = tier
    user.is_member = True
    # 月付，有效期 31 天
    user.tier_expires_at = bj_now() + timedelta(days=31)
    db.session.commit()


@bp.route('/create-order', methods=['POST'])
@login_required
def create_order():
    """创建支付订单"""
    user = g.current_user
    data = request.get_json() or {}
    tier = data.get('tier', '')
    provider = data.get('provider', '')  # alipay / stripe

    if tier not in TIER_PRICES:
        return error_response(400, f'无效的档位: {tier}')
    if provider not in ('alipay', 'stripe', 'xunhupay'):
        return error_response(400, f'不支持的支付方式: {provider}')

    from app.models.order import Order
    order = Order(
        user_id=user.id,
        tier=tier,
        amount=TIER_PRICES[tier],
        currency='cny',
        provider=provider,
    )
    db.session.add(order)
    db.session.commit()

    # 调用支付商创建支付
    if provider == 'stripe':
        from app.services.payment_stripe import create_payment, is_configured
        if not is_configured():
            return error_response(503, 'Stripe 支付暂未配置')
        result, err = create_payment(order)
    elif provider == 'xunhupay':
        from app.services.payment_xunhupay import create_payment, is_configured
        if not is_configured():
            return error_response(503, '虎皮椒支付暂未配置')
        result, err = create_payment(order)
    else:
        from app.services.payment_alipay import create_payment, is_configured
        if not is_configured():
            return error_response(503, '支付宝暂未配置')
        result, err = create_payment(order)

    if err:
        order.status = 'failed'
        db.session.commit()
        return error_response(500, f'创建支付失败: {err}')

    # 保存支付商订单号
    if result.get('provider_id'):
        order.provider_id = result['provider_id']
        db.session.commit()

    return standard_response({
        'order_id': order.id,
        'checkout_url': result.get('checkout_url'),
        'qrcode_url': result.get('qrcode_url'),
        'amount': order.amount,
        'tier': order.tier,
        'provider': order.provider,
    })


@bp.route('/callback/alipay', methods=['POST'])
def alipay_callback():
    """支付宝异步通知"""
    data = request.form.to_dict()
    signature = data.pop('sign', None)
    data.pop('sign_type', None)

    from app.services.payment_alipay import verify_callback
    if not verify_callback(data, signature):
        return 'fail', 200

    trade_status = data.get('trade_status')
    if trade_status not in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
        return 'success', 200

    out_trade_no = data.get('out_trade_no')
    from app.models.order import Order
    order = Order.query.get(out_trade_no)
    if not order or order.status == 'paid':
        return 'success', 200

    order.status = 'paid'
    order.provider_id = data.get('trade_no', '')
    order.paid_at = bj_now()
    _activate_tier(order.user_id, order.tier)
    db.session.commit()

    return 'success', 200


@bp.route('/callback/stripe', methods=['POST'])
def stripe_callback():
    """Stripe Webhook"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')

    from app.services.payment_stripe import verify_webhook
    event, err = verify_webhook(payload, sig_header)
    if err:
        return error_response(400, f'Webhook verification failed: {err}')

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.get('metadata', {}).get('order_id')
        if order_id:
            from app.models.order import Order
            order = Order.query.get(order_id)
            if order and order.status != 'paid':
                order.status = 'paid'
                order.provider_id = session.get('payment_intent', '')
                order.paid_at = bj_now()
                _activate_tier(order.user_id, order.tier)
                db.session.commit()

    return standard_response({'received': True})


@bp.route('/callback/xunhupay', methods=['POST'])
def xunhupay_callback():
    """虎皮椒支付结果通知（POST 请求）"""
    params = request.form.to_dict()
    from app.services.payment_xunhupay import verify_callback
    if not verify_callback(params):
        return 'sign error', 200

    status = params.get('status')
    if status != 'OD':
        return 'success', 200

    trade_order_id = params.get('trade_order_id')
    if not trade_order_id:
        return 'success', 200

    from app.models.order import Order
    order = Order.query.get(trade_order_id)
    if not order or order.status == 'paid':
        return 'success', 200

    order.status = 'paid'
    order.provider_id = params.get('open_order_id', '')
    order.paid_at = bj_now()
    _activate_tier(order.user_id, order.tier)
    db.session.commit()

    return 'success', 200


@bp.route('/providers', methods=['GET'])
def list_providers():
    """返回当前可用的支付渠道列表"""
    from app.models.llm_config import LlmConfig
    all_cfg = LlmConfig.get_all()

    providers = []

    # Stripe
    if (all_cfg.get('payment_stripe_enabled', 'true') != 'false'
            and all_cfg.get('stripe_api_key')):
        providers.append({'id': 'stripe', 'name': 'Stripe', 'type': 'redirect'})

    # Alipay
    if (all_cfg.get('payment_alipay_enabled', 'true') != 'false'
            and all_cfg.get('alipay_app_id')
            and all_cfg.get('alipay_private_key')
            and all_cfg.get('alipay_public_key')):
        providers.append({'id': 'alipay', 'name': '支付宝扫码', 'type': 'qrcode'})

    # XunHuPay (虎皮椒)
    if (all_cfg.get('payment_xunhupay_enabled', 'true') != 'false'
            and all_cfg.get('xunhupay_appid')
            and all_cfg.get('xunhupay_secret')):
        providers.append({'id': 'xunhupay', 'name': '微信/支付宝扫码', 'type': 'qrcode'})

    # Custom (线下/客服)
    if (all_cfg.get('payment_custom_enabled', 'true') != 'false'
            and all_cfg.get('custom_pay_image_url')):
        providers.append({
            'id': 'custom',
            'name': all_cfg.get('custom_pay_title', '联系客服'),
            'type': 'custom',
            'image_url': all_cfg.get('custom_pay_image_url', ''),
            'description': all_cfg.get('custom_pay_description', ''),
        })

    return standard_response(providers)


@bp.route('/verify', methods=['POST'])
@login_required
def verify_payment():
    """前端轮询检查支付结果"""
    user = g.current_user
    data = request.get_json() or {}
    order_id = data.get('order_id', '')

    from app.models.order import Order
    order = Order.query.filter_by(id=order_id, user_id=user.id).first()
    if not order:
        return error_response(404, '订单不存在')

    return standard_response({
        'order_id': order.id,
        'status': order.status,
        'tier': order.tier,
        'paid_at': order.paid_at.isoformat() if order.paid_at else None,
    })


@bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    """查看用户自己的订单记录"""
    user = g.current_user
    from app.models.order import Order
    orders = Order.query.filter_by(user_id=user.id)\
        .order_by(Order.created_at.desc()).limit(20).all()
    return standard_response([o.to_dict() for o in orders])


@bp.route('/admin/create-order', methods=['POST'])
@admin_required
def admin_create_order():
    """管理员手动创建已支付订单"""
    data = request.get_json() or {}
    user_email = (data.get('user_email') or '').strip()
    tier = data.get('tier', '')

    if not user_email:
        return error_response(400, '请输入用户邮箱')
    if tier not in TIER_PRICES:
        return error_response(400, f'无效的档位: {tier}')

    from app.models.user import User
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return error_response(404, f'用户不存在: {user_email}')

    from app.models.order import Order
    order = Order(
        user_id=user.id,
        tier=tier,
        amount=TIER_PRICES[tier],
        currency='cny',
        provider='manual',
        status='paid',
        paid_at=bj_now(),
    )
    db.session.add(order)
    _activate_tier(user.id, tier)
    db.session.commit()

    return standard_response({
        'order_id': order.id,
        'user_email': user_email,
        'tier': tier,
        'amount': order.amount,
    })


@bp.route('/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """管理员收益统计"""
    from app.models.order import Order
    now = bj_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 收入汇总（仅 paid）
    paid_base = db.session.query(func.sum(Order.amount), func.count(Order.id))\
        .filter(Order.status == 'paid')
    total_amount, total_count = paid_base.first()
    month_amount, month_count = paid_base.filter(Order.paid_at >= month_start).first()
    today_amount, today_count = paid_base.filter(Order.paid_at >= today_start).first()

    # 付费用户数（去重）
    paid_users = db.session.query(func.count(func.distinct(Order.user_id)))\
        .filter(Order.status == 'paid').scalar() or 0

    # 订单状态分布
    status_counts = {}
    for row in db.session.query(Order.status, func.count(Order.id))\
            .group_by(Order.status).all():
        status_counts[row[0]] = row[1]

    # 档位分布
    tier_distribution = {}
    for row in db.session.query(Order.tier, func.sum(Order.amount), func.count(Order.id))\
            .filter(Order.status == 'paid').group_by(Order.tier).all():
        tier_distribution[row[0]] = {'amount': row[1] or 0, 'count': row[2]}

    # 渠道分布
    provider_distribution = {}
    for row in db.session.query(Order.provider, func.sum(Order.amount), func.count(Order.id))\
            .filter(Order.status == 'paid').group_by(Order.provider).all():
        provider_distribution[row[0]] = {'amount': row[1] or 0, 'count': row[2]}

    # 最近 30 天每日趋势
    daily_trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_trend.append({'date': d, 'amount': 0, 'count': 0})

    trend_data = db.session.query(
        func.date(Order.paid_at), func.sum(Order.amount), func.count(Order.id)
    ).filter(Order.status == 'paid', Order.paid_at >= today_start - timedelta(days=29))\
     .group_by(func.date(Order.paid_at)).all()

    date_map = {row[0]: row for row in trend_data}
    for entry in daily_trend:
        row = date_map.get(entry['date'])
        if row:
            entry['amount'] = row[1] or 0
            entry['count'] = row[2]

    return standard_response({
        'total_revenue': total_amount or 0,
        'total_count': total_count or 0,
        'monthly_revenue': month_amount or 0,
        'monthly_count': month_count or 0,
        'today_revenue': today_amount or 0,
        'today_count': today_count or 0,
        'paid_users': paid_users,
        'status_counts': status_counts,
        'tier_distribution': tier_distribution,
        'provider_distribution': provider_distribution,
        'daily_trend': daily_trend,
    })


@bp.route('/admin/orders', methods=['GET'])
@admin_required
def admin_orders():
    """管理员订单流水"""
    from app.models.order import Order
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status = request.args.get('status', '')
    tier = request.args.get('tier', '')
    provider = request.args.get('provider', '')

    query = db.session.query(Order, db.session.bind)
    filters = []
    if status:
        filters.append(Order.status == status)
    if tier:
        filters.append(Order.tier == tier)
    if provider:
        filters.append(Order.provider == provider)

    query = Order.query
    if status:
        query = query.filter(Order.status == status)
    if tier:
        query = query.filter(Order.tier == tier)
    if provider:
        query = query.filter(Order.provider == provider)

    total = query.count()
    orders = query.order_by(Order.created_at.desc())\
        .offset((page - 1) * per_page).limit(per_page).all()

    # 批量取用户 email
    user_ids = list(set(o.user_id for o in orders))
    user_map = {}
    if user_ids:
        from app.models.user import User
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.email for u in users}

    items = []
    for o in orders:
        d = o.to_dict()
        d['user_email'] = user_map.get(o.user_id, '')
        items.append(d)

    return standard_response({
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
    })
