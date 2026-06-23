import logging
import os
import sys

_CONFIGURED = False


def configure_logging():
    """Единая настройка логирования для всего приложения.

    Уровень берётся из переменных окружения:
      - LOG_LEVEL (DEBUG/INFO/WARNING/...), по умолчанию INFO;
      - DEBUG=1 принудительно включает уровень DEBUG.
    В проде по умолчанию INFO, поэтому отладочные сообщения не засоряют логи.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"):
        level_name = "DEBUG"
    else:
        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    else:
        root.handlers = [handler]

    _CONFIGURED = True
