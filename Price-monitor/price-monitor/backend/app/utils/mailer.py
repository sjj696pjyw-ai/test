"""Отправка писем через SMTP (Yandex Cloud Postbox или любой SMTP).

Параметры берутся из переменных окружения:
  SMTP_HOST      — напр. postbox.cloud.yandex.net
  SMTP_PORT      — 587 (STARTTLS, по умолчанию) или 465 (SSL)
  SMTP_USER      — ID API-ключа Postbox (логин SMTP)
  SMTP_PASSWORD  — секрет API-ключа
  MAIL_FROM      — подтверждённый адрес отправителя
  MAIL_FROM_NAME — имя отправителя (по умолчанию PriceMonitor)

Если SMTP не настроен (нет host/user/password/from) — письмо не отправляется,
а пишется в лог. Это удобно для локальной разработки: ссылку подтверждения/сброса
можно взять прямо из логов, не подключая реальный почтовый сервис.
"""
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _cfg():
    return {
        'host': os.environ.get('SMTP_HOST'),
        'port': int(os.environ.get('SMTP_PORT', '587') or 587),
        'user': os.environ.get('SMTP_USER'),
        'password': os.environ.get('SMTP_PASSWORD'),
        'sender': os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USER'),
        'sender_name': os.environ.get('MAIL_FROM_NAME', 'PriceMonitor'),
    }


def _strip_html(html):
    return re.sub(r'<[^>]+>', '', html).strip()


def send_email(to, subject, html, text=None):
    """Отправляет письмо. Возвращает True при успехе (или в dev-режиме)."""
    c = _cfg()
    if not (c['host'] and c['user'] and c['password'] and c['sender']):
        logger.warning(
            "[MAIL DEV] SMTP не настроен — письмо не отправлено. to=%s | %s\n%s",
            to, subject, text or _strip_html(html),
        )
        return True

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr((c['sender_name'], c['sender']))
    msg['To'] = to
    msg.set_content(text or _strip_html(html))
    msg.add_alternative(html, subtype='html')

    try:
        ctx = ssl.create_default_context()
        if c['port'] == 465:
            with smtplib.SMTP_SSL(c['host'], c['port'], context=ctx, timeout=20) as s:
                s.login(c['user'], c['password'])
                s.send_message(msg)
        else:
            with smtplib.SMTP(c['host'], c['port'], timeout=20) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(c['user'], c['password'])
                s.send_message(msg)
        logger.info("Письмо отправлено: to=%s | %s", to, subject)
        return True
    except Exception as e:
        logger.error("Отправка письма не удалась (to=%s): %s", to, e)
        return False


def _email_html(heading, paragraphs, button_text, link, note):
    """Простой адаптивный HTML-шаблон письма (table-based, инлайн-стили —
    для совместимости с почтовыми клиентами)."""
    body = "".join(
        f'<p style="margin:0 0 12px;color:#374151;font-size:15px;line-height:1.55">{p}</p>'
        for p in paragraphs
    )
    return f"""<!DOCTYPE html>
<html lang="ru"><body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden">
  <tr><td style="background:#2563eb;padding:20px 28px">
    <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:.3px">📈&nbsp; PriceMonitor</span>
  </td></tr>
  <tr><td style="padding:28px 28px 8px">
    <h1 style="margin:0 0 18px;color:#111827;font-size:20px;font-weight:700">{heading}</h1>
    {body}
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 6px"><tr>
      <td style="border-radius:10px;background:#2563eb">
        <a href="{link}" style="display:inline-block;padding:13px 26px;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;border-radius:10px">{button_text}</a>
      </td>
    </tr></table>
    <p style="margin:18px 0 0;color:#9ca3af;font-size:13px;line-height:1.5">{note}</p>
  </td></tr>
  <tr><td style="padding:18px 28px;background:#f9fafb;border-top:1px solid #e5e7eb">
    <p style="margin:0;color:#9ca3af;font-size:12px">PriceMonitor — мониторинг цен конкурентов</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


def confirmation_email(link):
    subject = "Подтвердите email — PriceMonitor"
    html = _email_html(
        "Подтвердите email",
        [
            "Спасибо за регистрацию в PriceMonitor.",
            "Нажмите кнопку ниже, чтобы подтвердить адрес и войти. Ссылка действует 24 часа.",
        ],
        "Подтвердить email",
        link,
        "Если вы не регистрировались, просто проигнорируйте это письмо.",
    )
    text = f"Подтвердите email, перейдя по ссылке (действует 24 часа):\n{link}"
    return subject, html, text


def reset_email(link):
    subject = "Сброс пароля — PriceMonitor"
    html = _email_html(
        "Сброс пароля",
        [
            "Вы запросили сброс пароля в PriceMonitor.",
            "Нажмите кнопку ниже, чтобы задать новый пароль. Ссылка действует 1 час.",
        ],
        "Сбросить пароль",
        link,
        "Если вы не запрашивали сброс, просто проигнорируйте это письмо.",
    )
    text = f"Сброс пароля, перейдите по ссылке (действует 1 час):\n{link}"
    return subject, html, text
