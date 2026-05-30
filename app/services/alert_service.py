"""Alert Service — 任务失败告警

告警策略:
  1. 查询管理员标记 is_alert=True 的推送渠道
  2. 无告警渠道时 fallback 发邮件到管理员邮箱
  3. 同一任务 1 小时内不重复告警（内存去重）
  4. 复用现有 FORMATTERS / SENDERS 发送
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

_alert_dedup = {}
_DEDUP_TTL = timedelta(hours=1)


def send_task_alert(task, result, run_status, worker_id):
    """任务执行失败时发送告警"""
    from app.utils.helpers import bj_now

    task_id = task.id
    now = bj_now()

    last_alert = _alert_dedup.get(task_id)
    if last_alert and (now - last_alert) < _DEDUP_TTL:
        logger.info(f"Alert dedup: skipping alert for task {task_id}")
        return

    _alert_dedup[task_id] = now

    task_name = getattr(task, 'name', task_id)
    stderr = (result.get('stderr', '') or '')[:500]
    exit_code = result.get('exit_code', -1)

    title = f"IntelHub 任务告警: {task_name}"
    summary = (
        f"<p><strong>任务名称:</strong> {task_name}</p>"
        f"<p><strong>任务 ID:</strong> {task_id}</p>"
        f"<p><strong>Worker:</strong> {worker_id}</p>"
        f"<p><strong>状态:</strong> {run_status}</p>"
        f"<p><strong>退出码:</strong> {exit_code}</p>"
        f"<p><strong>时间:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')}</p>"
    )
    if stderr:
        summary += f"<p><strong>错误:</strong></p><pre style='color:#f87171'>{stderr}</pre>"

    try:
        _dispatch_alert(title, summary)
        logger.info(f"Alert sent for task {task_id} ({task_name})")
    except Exception as e:
        logger.warning(f"Alert dispatch failed for {task_id}: {e}")


def _dispatch_alert(title, summary_html):
    """通过管理员告警渠道发送告警"""
    from app.models.push_channel import PushChannel
    from app.models.user import User
    from app.services.push_channels import FORMATTERS, SENDERS

    admin_ids = [u.id for u in User.query.filter_by(role='admin').all()]
    alert_channels = PushChannel.query.filter(
        PushChannel.user_id.in_(admin_ids),
        PushChannel.is_alert == True,
        PushChannel.enabled == True,
    ).all()

    if alert_channels:
        for ch in alert_channels:
            formatter = FORMATTERS.get(ch.channel_type)
            sender = SENDERS.get(ch.channel_type)
            if not formatter or not sender:
                continue
            try:
                message = formatter(summary_html, "", "alert")
                ok, err = sender(ch.get_config(), message)
                if not ok:
                    logger.warning(f"Alert send failed on {ch.channel_type}/{ch.id}: {err}")
            except Exception as e:
                logger.warning(f"Alert send error on {ch.channel_type}/{ch.id}: {e}")
    else:
        _send_fallback_email(title, summary_html, admin_ids)


def _send_fallback_email(title, summary_html, admin_ids):
    """Fallback: 无告警渠道时发邮件给管理员"""
    from app.models.user import User
    from app.services.email_sender import EmailSender

    admins = User.query.filter(User.id.in_(admin_ids)).all()
    emails = [u.email for u in admins if u.email]
    if not emails:
        logger.warning("No admin emails found for alert fallback")
        return

    sender = EmailSender()
    if not sender.is_configured():
        logger.warning("SMTP not configured, alert fallback skipped")
        return

    html = _build_alert_email(title, summary_html)
    sender.send_batch(emails, title, html)


def _build_alert_email(title, body_html):
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="600" cellpadding="0" cellspacing="0">
      <tr><td style="background:#1e293b;border-radius:12px;padding:24px;">
        <h1 style="color:#f87171;font-size:18px;margin:0 0 16px;">{title}</h1>
        <div style="color:#e2e8f0;font-size:14px;line-height:1.6;">{body_html}</div>
      </td></tr>
      <tr><td style="text-align:center;padding:16px 0;">
        <p style="color:#475569;font-size:11px;">IntelHub Alert System</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""
