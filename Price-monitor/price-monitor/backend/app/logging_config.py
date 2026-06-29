import contextvars
import datetime
import json
import logging
import os
import sys

_CONFIGURED = False

# Сквозной идентификатор запроса (request-id): пишется в каждую строку лога,
# чтобы можно было собрать все сообщения одного HTTP-запроса.
_request_id = contextvars.ContextVar("request_id", default="-")


def set_request_id(rid):
    return _request_id.set(rid)


def get_request_id():
    return _request_id.get()


def reset_request_id(token):
    try:
        _request_id.reset(token)
    except (ValueError, LookupError):
        pass


class RequestIdFilter(logging.Filter):
    """Добавляет request_id в каждую запись лога."""

    def filter(self, record):
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """Структурированный JSON-формат (LOG_FORMAT=json)."""

    def format(self, record):
        data = {
            "ts": datetime.datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure_logging():
    """Единая настройка логирования для всего приложения.

    Env:
      - LOG_LEVEL (DEBUG/INFO/WARNING/...), по умолчанию INFO;
      - DEBUG=1 — принудительно DEBUG;
      - LOG_FORMAT=json — структурированные JSON-логи (иначе текст).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"):
        level_name = "DEBUG"
    else:
        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if os.environ.get("LOG_FORMAT", "").lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    _CONFIGURED = True
