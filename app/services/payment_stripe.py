"""Stripe payment integration — Checkout Session"""
import logging
from app.utils.helpers import bj_now

logger = logging.getLogger(__name__)

# 档位价格映射（分）
TIER_PRICES = {
    'v1': 900,
    'v2': 2900,
    'v3': 5900,
    'v4': 9900,
}

TIER_NAMES = {
    'v1': 'V1 轻度使用',
    'v2': 'V2 个人任务',
    'v3': 'V3 数据自由',
    'v4': 'V4 旗舰全能',
}


def _get_config():
    """从 llm_config 表读取 Stripe 配置"""
    from app.models.llm_config import LlmConfig
    return {
        'api_key': LlmConfig.get('stripe_api_key') or '',
        'webhook_secret': LlmConfig.get('stripe_webhook_secret') or '',
    }


def is_configured():
    cfg = _get_config()
    return bool(cfg['api_key'])


def create_payment(order):
    """创建 Stripe Checkout Session，返回支付链接"""
    import stripe

    cfg = _get_config()
    stripe.api_key = cfg['api_key']

    tier = order.tier
    amount = TIER_PRICES.get(tier, 0)
    if amount == 0:
        return None, f'Invalid tier: {tier}'

    try:
        site_url = ''
        try:
            from app.models.llm_config import LlmConfig
            site_url = (LlmConfig.get('site_url') or '').rstrip('/')
        except Exception:
            pass

        session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card', 'alipay', 'wechat_pay'],
            line_items=[{
                'price_data': {
                    'currency': 'cny',
                    'product_data': {
                        'name': f'IntelHub {TIER_NAMES.get(tier, tier)} · 月度订阅',
                    },
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            metadata={
                'order_id': order.id,
                'user_id': order.user_id,
                'tier': tier,
            },
            success_url=f'{site_url}/checkout?status=success&order={order.id}',
            cancel_url=f'{site_url}/checkout?status=cancel&order={order.id}',
        )

        return {'checkout_url': session.url, 'provider_id': session.id}, None
    except Exception as e:
        logger.error('Stripe create_payment failed: %s', e)
        return None, str(e)


def verify_webhook(payload, sig_header):
    """验证 Stripe Webhook 签名，返回事件数据"""
    import stripe

    cfg = _get_config()
    stripe.api_key = cfg['api_key']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, cfg['webhook_secret']
        )
        return event, None
    except Exception as e:
        logger.error('Stripe webhook verify failed: %s', e)
        return None, str(e)
