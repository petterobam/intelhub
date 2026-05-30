"""PushChannels — 多渠道推送服务

支持: email / feishu / dingtalk / telegram
每种渠道有独立的格式化器和发送器。
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from app.utils.helpers import bj_now

logger = logging.getLogger(__name__)


# ── 格式化器 ──────────────────────────────────────────────────


def format_email(
    summary_html, view_link, report_type, raw_md=None, title=None, **kwargs
):
    """邮件格式：复用现有 HTML 模板"""
    from app.services.report_notifier import _build_email_body

    subject = title or _build_subject(report_type)
    return {
        "subject": f"[IntelHub] {subject}",
        "html_body": _build_email_body(summary_html, view_link, report_type),
    }


def _build_subject(report_type):
    from datetime import datetime

    labels = {
        "insight": "投资洞察报告",
        "agent": "Agent 分析报告",
        "heartbeat": "系统健康报告",
    }
    label = labels.get(report_type, "分析报告")
    return f"[IntelHub] {label} — {bj_now().strftime('%Y-%m-%d')}"


def format_feishu(
    summary_html, view_link, report_type, raw_md=None, title=None, summary_md=None
):
    """飞书格式：schema 2.0 卡片消息，markdown 渲染"""
    date_str = bj_now().strftime("%Y-%m-%d")

    # 优先使用原生 MD，避免 HTML→MD 来回转换丢失格式
    if summary_md:
        md = summary_md[:4000]
    else:
        md = _html_to_markdown(summary_html)[:4000] if summary_html else "新报告已生成"

    if view_link:
        md += f"\n\n[查看完整报告 →]({view_link})"

    card_title = f"IntelHub · {title or date_str}"

    card = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "config": {"update_multi": True},
            "header": {
                "title": {"tag": "plain_text", "content": card_title},
                "template": "blue",
            },
            "body": {
                "direction": "vertical",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": md,
                        "text_align": "left",
                        "text_size": "normal",
                    },
                ],
            },
        },
    }
    return card


def format_dingtalk(
    summary_html, view_link, report_type, raw_md=None, title=None, summary_md=None
):
    """钉钉格式：Markdown 消息"""
    from datetime import datetime

    date_str = bj_now().strftime("%Y-%m-%d")

    # 优先使用原生 MD
    if summary_md:
        text = summary_md[:3500]
    else:
        text = (
            _html_to_markdown(summary_html)[:3500] if summary_html else "新报告已生成"
        )
    link_line = f"\n\n[查看完整报告]({view_link})" if view_link else ""

    card_title = f"IntelHub · {title or date_str}"
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": card_title,
            "text": f"### {card_title}\n\n{text}{link_line}",
        },
    }


def format_telegram(
    summary_html, view_link, report_type, raw_md=None, title=None, **kwargs
):
    """Telegram 格式：HTML 消息"""

    date_str = bj_now().strftime("%Y-%m-%d")

    text = _html_to_text(summary_html)[:3500] if summary_html else "新报告已生成"
    link_line = f'\n\n<a href="{view_link}">查看完整报告</a>' if view_link else ""

    card_title = title or f"IntelHub · {date_str}"
    return {
        "text": f"<b>{card_title}</b>\n\n{text}{link_line}",
        "parse_mode": "HTML",
    }


def _html_to_markdown(html):
    """HTML → Markdown（飞书/钉钉/Telegram 兼容）"""
    if not html:
        return ""
    text = html
    # headings
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", text, flags=re.S)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", text, flags=re.S)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", text, flags=re.S)
    text = re.sub(r"<h4[^>]*>(.*?)</h4>", r"#### \1\n", text, flags=re.S)
    # bold / strong
    text = re.sub(r"<(?:strong|b)>(.*?)</(?:strong|b)>", r"**\1**", text, flags=re.S)
    # italic / em
    text = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", r"_\1_", text, flags=re.S)
    # list items
    text = re.sub(r"<li[^>]*>", "- ", text)
    # links
    text = re.sub(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.S
    )
    # blockquotes
    text = re.sub(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        lambda m: "> " + m.group(1).strip().replace("\n", "\n> "),
        text,
        flags=re.S,
    )
    # line breaks
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"</div>", "\n", text)
    # strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # strip leading whitespace on each line (prevents code-block rendering)
    text = re.sub(r"^( {4,}|\t+)", "", text, flags=re.M)
    # collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # decode common entities
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return text.strip()


def _html_to_text(html):
    """简单 HTML → 纯文本"""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


FORMATTERS = {
    "email": format_email,
    "feishu": format_feishu,
    "dingtalk": format_dingtalk,
    "telegram": format_telegram,
}


# ── 发送器 ────────────────────────────────────────────────────


def send_email(config, message):
    """邮件发送"""
    from app.services.email_sender import EmailSender

    sender = EmailSender()
    if not sender.is_configured():
        return False, "SMTP 未配置"
    to = config.get("email", "")
    if not to:
        return False, "缺少收件邮箱"
    ok = sender.send(to, message["subject"], message["html_body"])
    return ok, "" if ok else "发送失败"


def send_feishu(config, message):
    """飞书 Webhook 发送"""
    url = config.get("webhook_url", "")
    if not url:
        return False, "缺少 webhook_url"
    try:
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        logger.debug("Feishu request to %s, payload %d bytes", url[:60], len(data))
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        logger.info("Feishu response: %s", result)
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            return True, ""
        return False, result.get("msg", str(result))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        logger.error("Feishu HTTP %d: %s", e.code, body)
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        logger.error("Feishu send error: %s", e)
        return False, str(e)


def send_dingtalk(config, message):
    """钉钉 Webhook 发送（支持签名）"""
    url = config.get("webhook_url", "")
    if not url:
        return False, "缺少 webhook_url"
    secret = config.get("secret", "")
    try:
        if secret:
            ts = str(int(time.time() * 1000))
            sign_str = f"{ts}\n{secret}"
            hmac_code = hmac.new(
                secret.encode(), sign_str.encode(), hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            url = f"{url}&timestamp={ts}&sign={sign}"

        data = json.dumps(message).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("errcode") == 0:
            return True, ""
        return False, result.get("errmsg", str(result))
    except Exception as e:
        return False, str(e)


def send_telegram(config, message):
    """Telegram Bot API 发送"""
    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not bot_token or not chat_id:
        return False, "缺少 bot_token 或 chat_id"
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message["text"],
            "parse_mode": message.get("parse_mode", "HTML"),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("ok"):
            return True, ""
        return False, result.get("description", str(result))
    except Exception as e:
        return False, str(e)


SENDERS = {
    "email": send_email,
    "feishu": send_feishu,
    "dingtalk": send_dingtalk,
    "telegram": send_telegram,
}


# ── 分发器 ────────────────────────────────────────────────────


def _channel_key(channel_type, channel_config):
    """提取渠道可读标识用于去重"""
    if channel_type == "email":
        return channel_config.get("email", "")
    return channel_config.get("webhook_url", "") or channel_config.get("bot_token", "") or json.dumps(channel_config, sort_keys=True)


class PushDispatcher:
    """统一推送分发：按渠道类型分组推送"""

    def dispatch(
        self,
        summary_html,
        view_link,
        report_type,
        subscriptions,
        raw_md=None,
        title=None,
        summary_md=None,
        report_path=None,
    ):
        """分发报告通知到所有订阅渠道"""
        from app.models.push_channel import PushChannel
        from app.models.push_log import PushLog
        from app import db

        results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}

        all_channel_ids = set()
        for s in subscriptions:
            if s.channel_ids:
                all_channel_ids.update(s.channel_ids)
            elif s.channel_id:
                all_channel_ids.add(s.channel_id)

        channels = {}
        if all_channel_ids:
            for ch in PushChannel.query.filter(
                PushChannel.id.in_(all_channel_ids), PushChannel.enabled == True
            ).all():
                channels[ch.id] = ch

        sent_keys = set()

        for sub in subscriptions:
            # 解析 user_id：通过 email 查 users 表
            sub_user_id = None
            try:
                from app.models.user import User
                u = User.query.filter_by(email=sub.email).first()
                if u:
                    sub_user_id = u.id
            except Exception:
                pass

            sub_channels = []
            cids = list(dict.fromkeys(
                sub.channel_ids or (
                    [sub.channel_id]
                    if hasattr(sub, "channel_id") and sub.channel_id
                    else []
                )
            ))
            for cid in cids:
                if cid == "_email":
                    sub_channels.append(("email", {"email": sub.email}))
                elif cid in channels:
                    sub_channels.append(
                        (channels[cid].channel_type, channels[cid].get_config())
                    )
            if not sub_channels:
                sub_channels.append(("email", {"email": sub.email}))

            for channel_type, channel_config in sub_channels:
                dedup_key = (channel_type, json.dumps(channel_config, sort_keys=True))
                if dedup_key in sent_keys:
                    continue
                sent_keys.add(dedup_key)

                # 持久化去重：同一报告+渠道只发一次
                ch_key = _channel_key(channel_type, channel_config)
                if report_path and ch_key:
                    existing = PushLog.query.filter_by(
                        report_path=report_path,
                        channel_type=channel_type,
                        channel_key=ch_key,
                    ).first()
                    if existing:
                        logger.info("Push skipped (already sent): %s/%s for %s", channel_type, ch_key[:30], report_path)
                        results["skipped"] += 1
                        continue

                formatter = FORMATTERS.get(channel_type)
                if not formatter:
                    logger.warning("Unknown channel type: %s", channel_type)
                    continue
                try:
                    message = formatter(
                        summary_html, view_link, report_type,
                        raw_md=raw_md, title=title, summary_md=summary_md,
                    )
                except Exception as e:
                    logger.error("Format failed for %s: %s", channel_type, e)
                    continue

                sender = SENDERS.get(channel_type)
                if not sender:
                    continue
                try:
                    ok, err = sender(channel_config, message)
                    push_status = "sent" if ok else "failed"
                    if ok:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                        logger.error("Push failed: sub=%s channel=%s error=%s", sub.id, channel_type, err)
                    results["details"].append({"sub_id": sub.id, "channel": channel_type, "status": push_status, "error": err or ""})

                    # 写入 PushLog
                    if report_path and ch_key:
                        log = PushLog(
                            report_path=report_path,
                            channel_type=channel_type,
                            channel_key=ch_key,
                            user_id=sub_user_id,
                            status=push_status,
                            error=(err or "")[:512],
                        )
                        db.session.add(log)
                        db.session.commit()
                except Exception as e:
                    results["failed"] += 1
                    logger.error("Push exception: sub=%s channel=%s error=%s", sub.id, channel_type, e, exc_info=True)
                    results["details"].append({"sub_id": sub.id, "channel": channel_type, "status": "error", "error": str(e)})

                    if report_path and ch_key:
                        log = PushLog(
                            report_path=report_path,
                            channel_type=channel_type,
                            channel_key=ch_key,
                            user_id=sub_user_id,
                            status="error",
                            error=str(e)[:512],
                        )
                        db.session.add(log)
                        db.session.commit()

        logger.info("Push dispatch: sent=%d, failed=%d, skipped=%d", results["sent"], results["failed"], results["skipped"])
        return results

    def send_test(self, channel_type, channel_config):
        """发送测试消息"""
        test_summary = (
            "<p>这是一条来自 IntelHub 的测试消息，验证推送渠道配置是否正确。</p>"
        )
        formatter = FORMATTERS.get(channel_type)
        sender = SENDERS.get(channel_type)
        if not formatter or not sender:
            return False, f"不支持的渠道类型: {channel_type}"

        message = formatter(test_summary, "", "heartbeat")
        return sender(channel_config, message)

    def dispatch_to_channels(
        self, channel_ids, user_email, summary_html, view_link,
        report_type, raw_md=None, title=None, summary_md=None,
        report_path=None,
    ):
        """直接按 channel_ids 推送（无需 Subscription 对象）"""
        from app.models.push_channel import PushChannel
        from app.models.push_log import PushLog
        from app import db

        results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}
        if not channel_ids:
            return results

        real_ids = [cid for cid in channel_ids if cid != "_email"]
        channels = {}
        if real_ids:
            for ch in PushChannel.query.filter(
                PushChannel.id.in_(real_ids), PushChannel.enabled == True
            ).all():
                channels[ch.id] = ch

        sent_keys = set()
        for cid in channel_ids:
            if cid == "_email":
                channel_type, channel_config = "email", {"email": user_email}
            elif cid in channels:
                channel_type = channels[cid].channel_type
                channel_config = channels[cid].get_config()
            else:
                continue

            dedup_key = (channel_type, json.dumps(channel_config, sort_keys=True))
            if dedup_key in sent_keys:
                continue
            sent_keys.add(dedup_key)

            # 持久化去重
            ch_key = _channel_key(channel_type, channel_config)
            if report_path and ch_key:
                existing = PushLog.query.filter_by(
                    report_path=report_path,
                    channel_type=channel_type,
                    channel_key=ch_key,
                ).first()
                if existing:
                    logger.info("Push skipped (already sent): %s/%s for %s", channel_type, ch_key[:30], report_path)
                    results["skipped"] += 1
                    continue

            formatter = FORMATTERS.get(channel_type)
            if not formatter:
                continue
            try:
                message = formatter(
                    summary_html, view_link, report_type,
                    raw_md=raw_md, title=title, summary_md=summary_md,
                )
            except Exception as e:
                logger.error("Format failed for %s: %s", channel_type, e)
                continue

            sender = SENDERS.get(channel_type)
            if not sender:
                continue
            try:
                ok, err = sender(channel_config, message)
                push_status = "sent" if ok else "failed"
                if ok:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    logger.error("Push failed: channel=%s error=%s", channel_type, err)
                results["details"].append({"channel": channel_type, "status": push_status, "error": err or ""})

                if report_path and ch_key:
                    log = PushLog(
                        report_path=report_path,
                        channel_type=channel_type,
                        channel_key=ch_key,
                        status=push_status,
                        error=(err or "")[:512],
                    )
                    db.session.add(log)
                    db.session.commit()
            except Exception as e:
                results["failed"] += 1
                results["details"].append({"channel": channel_type, "status": "error", "error": str(e)})

                if report_path and ch_key:
                    log = PushLog(
                        report_path=report_path,
                        channel_type=channel_type,
                        channel_key=ch_key,
                        status="error",
                        error=str(e)[:512],
                    )
                    db.session.add(log)
                    db.session.commit()

        return results
