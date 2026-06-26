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


def confirmation_email(link):
    subject = "Подтвердите email — PriceMonitor"
    html = (
        "<p>Спасибо за регистрацию в PriceMonitor.</p>"
        "<p>Подтвердите адрес электронной почты — ссылка действительна 24 часа:</p>"
        f'<p><a href="{link}">Подтвердить email</a></p>'
        f"<p>Или скопируйте ссылку: {link}</p>"
        "<p>Если вы не регистрировались, просто проигнорируйте это письмо.</p>"
    )
    text = f"Подтвердите email, перейдя по ссылке (действует 24 часа):\n{link}"
    return subject, html, text


def reset_email(link):
    subject = "Сброс пароля — PriceMonitor"
    html = (
        "<p>Вы запросили сброс пароля в PriceMonitor.</p>"
        "<p>Задать новый пароль — ссылка действительна 1 час:</p>"
        f'<p><a href="{link}">Сбросить пароль</a></p>'
        f"<p>Или скопируйте ссылку: {link}</p>"
        "<p>Если вы не запрашивали сброс, проигнорируйте это письмо.</p>"
    )
    text = f"Сброс пароля, перейдите по ссылке (действует 1 час):\n{link}"
    return subject, html, text
