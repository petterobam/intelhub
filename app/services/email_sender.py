"""EmailSender — SMTP 邮件发送服务

从 DB 读取 SMTP 配置，使用 smtplib 发送邮件。
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Module-level singleton
_sender = None


def _get_sender():
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender


def send_daily_report(to, display_name, report_date, highlights, h5_url):
    """Send a personalized daily report email with highlights and H5 link."""
    sender = _get_sender()
    if not sender.is_configured():
        logger.warning("SMTP not configured, skip daily report to %s", to)
        return False

    subject = f'IntelHub 日报 - {report_date}'
    html = _build_daily_report_email(display_name, report_date, highlights, h5_url)
    return sender.send(to, subject, html)


def _build_daily_report_email(display_name, report_date, highlights, h5_url):
    """Build the daily report HTML email body."""
    highlights_html = ''
    for h in (highlights or []):
        platform = h.get('platform', '')
        text = h.get('text', '')
        url = h.get('url', '')
        highlights_html += f'''
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #1e293b;">
            <span style="display:inline-block;font-size:11px;color:#38bdf8;background:#0c4a6e;padding:2px 8px;border-radius:4px;margin-bottom:4px;">{platform}</span>
            <p style="margin:4px 0;font-size:14px;color:#e2e8f0;line-height:1.5;">{text}</p>
            {"<a href='" + url + "' style='font-size:12px;color:#7dd3fc;text-decoration:none;'>查看原文 →</a>" if url else ""}
          </td>
        </tr>'''

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
  <tr><td align="center" style="padding:32px 16px;">
    <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;">
      <!-- Header -->
      <tr><td style="text-align:center;padding:24px 0 20px;border-bottom:1px solid #1e293b;">
        <h1 style="margin:0;font-size:22px;color:#38bdf8;font-weight:700;">IntelHub</h1>
        <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">{display_name}，这是你的 {report_date} 日报</p>
      </td></tr>
      <!-- Highlights -->
      <tr><td style="padding:0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:12px;overflow:hidden;margin:20px 0;">
          <tr><td style="padding:12px 16px;background:#0f172a;"><h2 style="margin:0;font-size:14px;color:#f1f5f9;">今日要点</h2></td></tr>
          {highlights_html}
        </table>
      </td></tr>
      <!-- CTA -->
      <tr><td align="center" style="padding:24px 0;">
        <a href="{h5_url}" style="display:inline-block;background:#0ea5e9;color:#fff;text-decoration:none;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600;">查看完整报告</a>
      </td></tr>
      <!-- Footer -->
      <tr><td style="text-align:center;padding:24px 0;border-top:1px solid #1e293b;">
        <p style="margin:0;font-size:11px;color:#475569;">&copy; IntelHub · 智能投资情报平台</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>'''


class EmailSender:
    def __init__(self):
        self._load_config()

    def _load_config(self):
        try:
            from app.models.llm_config import LlmConfig
            self.host = LlmConfig.get('smtp_host', '')
            self.port = int(LlmConfig.get('smtp_port', '465') or '465')
            self.user = LlmConfig.get('smtp_user', '')
            self.password = LlmConfig.get('smtp_password', '')
            self.from_name = LlmConfig.get('smtp_from_name', 'IntelHub')
            self.use_tls = LlmConfig.get('smtp_use_tls', 'true').lower() == 'true'
        except Exception:
            self.host = ''
            self.port = 465
            self.user = ''
            self.password = ''
            self.from_name = 'IntelHub'
            self.use_tls = True

    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def _build_message(self, to: str, subject: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'{self.from_name} <{self.user}>'
        msg['To'] = to
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        return msg

    def send(self, to: str, subject: str, html_body: str) -> bool:
        if not self.is_configured():
            logger.warning("SMTP not configured, skip sending to %s", to)
            return False

        msg = self._build_message(to, subject, html_body)
        try:
            if self.use_tls and self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as srv:
                    srv.login(self.user, self.password)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as srv:
                    if self.use_tls:
                        srv.starttls()
                    srv.login(self.user, self.password)
                    srv.send_message(msg)
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to, e)
            return False

    def send_batch(self, recipients: list, subject: str, html_body: str) -> dict:
        results = {'sent': 0, 'failed': 0, 'errors': []}
        for addr in recipients:
            ok = self.send(addr, subject, html_body)
            if ok:
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(addr)
        return results

    def test_connection(self) -> tuple:
        """Test SMTP connection. Returns (ok, message)."""
        if not self.is_configured():
            return False, 'SMTP 未配置'
        try:
            if self.use_tls and self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=10) as srv:
                    srv.login(self.user, self.password)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=10) as srv:
                    if self.use_tls:
                        srv.starttls()
                    srv.login(self.user, self.password)
            return True, 'SMTP 连接成功'
        except Exception as e:
            return False, str(e)
