"""Alipay payment integration — 当面付（扫码支付）"""
import logging

logger = logging.getLogger(__name__)

TIER_NAMES = {
    'v1': 'V1 轻度使用',
    'v2': 'V2 个人任务',
    'v3': 'V3 数据自由',
    'v4': 'V4 旗舰全能',
}


def _ensure_pem(key, key_type='PRIVATE'):
    """确保密钥为 PEM 格式（兼容用户粘贴的纯 base64）"""
    if not key:
        return key
    key = key.strip()
    if key.startswith('-----'):
        return key
    header = f'-----BEGIN {key_type} KEY-----'
    footer = f'-----END {key_type} KEY-----'
    return f'{header}\n{key}\n{footer}'


def _get_config():
    """从 llm_config 表读取支付宝配置"""
    from app.models.llm_config import LlmConfig
    pk = LlmConfig.get('alipay_private_key') or ''
    pub = LlmConfig.get('alipay_public_key') or ''
    return {
        'app_id': LlmConfig.get('alipay_app_id') or '',
        'private_key': _ensure_pem(pk, 'RSA PRIVATE'),
        'alipay_public_key': _ensure_pem(pub, 'PUBLIC'),
    }


def is_configured():
    cfg = _get_config()
    return bool(cfg['app_id'] and cfg['private_key'] and cfg['alipay_public_key'])


def create_payment(order):
    """创建支付宝当面付（扫码支付），返回二维码内容 URL"""
    from alipay import AliPay

    cfg = _get_config()
    amount_yuan = order.amount / 100
    if amount_yuan == 0:
        return None, f'Invalid tier: {order.tier}'

    try:
        alipay = AliPay(
            appid=cfg['app_id'],
            app_private_key_string=cfg['private_key'],
            alipay_public_key_string=cfg['alipay_public_key'],
            sign_type='RSA2',
            debug=False,
        )

        site_url = ''
        try:
            from app.models.llm_config import LlmConfig
            site_url = (LlmConfig.get('site_url') or '').rstrip('/')
        except Exception:
            pass

        # 当面付 precreate — 返回二维码内容
        result = alipay.api_alipay_trade_precreate(
            out_trade_no=order.id,
            total_amount=str(amount_yuan),
            subject=f'IntelHub {TIER_NAMES.get(order.tier, order.tier)} · 月度订阅',
            notify_url=f'{site_url}/api/v1/payments/callback/alipay',
        )

        code = result.get('code')
        if code == '10000':
            qr_code = result.get('qr_code', '')
            return {
                'checkout_url': qr_code,
                'qrcode_url': qr_code,
                'provider_id': result.get('trade_no', ''),
            }, None
        else:
            err_msg = result.get('sub_msg') or result.get('msg') or str(result)
            logger.error('Alipay precreate failed: %s', err_msg)
            return None, err_msg
    except Exception as e:
        logger.error('Alipay create_payment failed: %s', e)
        return None, str(e)


def verify_callback(data, signature):
    """验证支付宝异步通知签名"""
    from alipay import AliPay

    cfg = _get_config()
    try:
        alipay = AliPay(
            appid=cfg['app_id'],
            app_private_key_string=cfg['private_key'],
            alipay_public_key_string=cfg['alipay_public_key'],
            sign_type='RSA2',
            debug=False,
        )
        return alipay.verify(data, signature)
    except Exception as e:
        logger.error('Alipay verify_callback failed: %s', e)
        return False
