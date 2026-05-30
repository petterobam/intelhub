"""XunHuPay (虎皮椒) payment integration — Native 扫码支付（微信 + 支付宝）"""
import hashlib
import logging
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import json

logger = logging.getLogger(__name__)

TIER_NAMES = {
    'v1': 'V1 轻度使用',
    'v2': 'V2 个人任务',
    'v3': 'V3 数据自由',
    'v4': 'V4 旗舰全能',
}

XUNHUPAY_API = 'https://api.xunhupay.com/payment/do.html'


def _get_config():
    from app.models.llm_config import LlmConfig
    return {
        'appid': LlmConfig.get('xunhupay_appid') or '',
        'secret': LlmConfig.get('xunhupay_secret') or '',
    }


def is_configured():
    cfg = _get_config()
    return bool(cfg['appid'] and cfg['secret'])


def _hash(params, secret):
    """MD5 签名：参数按 key ASCII 升序排列，拼接后追加 APPSECRET，取 MD5 32 位小写"""
    filtered = {k: v for k, v in params.items()
                if v != '' and v is not None and k != 'hash'}
    sorted_str = '&'.join(f'{k}={filtered[k]}' for k in sorted(filtered.keys()))
    raw = f'{sorted_str}{secret}'
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def create_payment(order):
    """创建虎皮椒扫码支付

    Args:
        order: Order 对象 (id, tier, amount)

    Returns:
        (result_dict, error_string)
    """
    cfg = _get_config()
    if not cfg['appid'] or not cfg['secret']:
        return None, '虎皮椒未配置'

    site_url = ''
    try:
        from app.models.llm_config import LlmConfig
        site_url = (LlmConfig.get('site_url') or '').rstrip('/')
    except Exception:
        pass

    title = f'IntelHub {TIER_NAMES.get(order.tier, order.tier)} 月度订阅'
    # total_fee 单位为元（虎皮椒要求），amount 存储单位为分
    total_fee_yuan = f'{order.amount / 100:.2f}'

    params = {
        'version': '1.1',
        'appid': cfg['appid'],
        'trade_order_id': order.id,
        'total_fee': total_fee_yuan,
        'title': title,
        'time': str(int(time.time())),
        'notify_url': f'{site_url}/api/v1/payments/callback/xunhupay',
        'return_url': f'{site_url}/checkout?order={order.id}',
        'nonce_str': uuid.uuid4().hex[:16],
    }

    params['hash'] = _hash(params, cfg['secret'])

    try:
        form_data = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(XUNHUPAY_API, data=form_data, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode('utf-8'))

        if result.get('errcode') == 0:
            return {
                'checkout_url': result.get('url_qrcode', '') or result.get('url', ''),
                'qrcode_url': result.get('url_qrcode', ''),
                'provider_id': result.get('openid', ''),
            }, None
        else:
            err_msg = result.get('errmsg', str(result))
            logger.error('XunHuPay create_payment failed: %s', err_msg)
            return None, err_msg
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')[:500]
        logger.error('XunHuPay HTTP %d: %s', e.code, body_text)
        return None, f'HTTP {e.code}: {body_text}'
    except Exception as e:
        logger.error('XunHuPay create_payment error: %s', e)
        return None, str(e)


def verify_callback(params):
    """验证虎皮椒回调签名

    Args:
        params: dict of callback parameters (including 'hash')

    Returns:
        bool — 签名是否合法
    """
    cfg = _get_config()
    if not cfg['secret']:
        return False

    received_hash = params.get('hash', '')
    if not received_hash:
        return False

    expected = _hash(params, cfg['secret'])
    return received_hash == expected
