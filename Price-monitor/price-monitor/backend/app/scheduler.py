"""Планировщик фоновых задач (APScheduler).

Ночью в 19:30 UTC обновляет цены по всем анализам всех клиентов.

Особенности:
- gunicorn запускается с несколькими воркерами, и планировщик стартует в каждом.
  Чтобы ночное обновление не запустилось несколько раз, используем атомарную
  файловую блокировку «на сегодня»: задачу выполнит только тот воркер, который
  первым создаст файл-замок с датой запуска.
- Включается переменной окружения ENABLE_SCHEDULER=1.
"""
import os
import tempfile
from datetime import datetime


def _lock_dir():
    """Каталог для файлов-замков. На проде — постоянный том (рядом с БД),
    иначе временный каталог."""
    for d in (os.environ.get('SCHEDULER_LOCK_DIR'), '/data',
              os.path.join(os.getcwd(), 'instance')):
        if d and os.path.isdir(d) and os.access(d, os.W_OK):
            return d
    return tempfile.gettempdir()


def _claim_daily_run(job_name):
    """Атомарно «занимает» сегодняшний запуск задачи. True — этот процесс должен
    выполнить задачу; False — её уже забрал другой воркер/инстанс."""
    date = datetime.utcnow().strftime('%Y-%m-%d')
    path = os.path.join(_lock_dir(), f'.sched-{job_name}-{date}.lock')
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, datetime.utcnow().isoformat().encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception as e:
        # При проблемах с файловой системой — лучше не запускать (избежать дублей)
        print(f"[SCHEDULER] не удалось взять замок ({e}); пропуск")
        return False


def _nightly_price_update(app):
    """Ночная задача: обновить цены по всем анализам всех клиентов."""
    with app.app_context():
        if not _claim_daily_run('nightly_prices'):
            print("[SCHEDULER] Ночное обновление уже запущено другим воркером — пропуск")
            return
        try:
            from app.services.price_update_service import PriceUpdateService
            PriceUpdateService.update_all_analyses_prices()
        except Exception as e:
            print(f"[SCHEDULER] Ночное обновление: критическая ошибка — {e}")


def start_scheduler(app):
    """Запускает фоновый планировщик (если включён через ENABLE_SCHEDULER=1)."""
    if os.environ.get('ENABLE_SCHEDULER', '0') != '1':
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception as e:
        print(f"[SCHEDULER] APScheduler недоступен ({e}); планировщик не запущен")
        return None

    scheduler = BackgroundScheduler(timezone='UTC')
    scheduler.add_job(
        func=lambda: _nightly_price_update(app),
        trigger=CronTrigger(hour=19, minute=30, timezone='UTC'),
        id='nightly_price_update',
        replace_existing=True,
        misfire_grace_time=3600,  # если процесс был занят — допускаем запуск в течение часа
        coalesce=True,            # пропущенные срабатывания не копим
    )
    scheduler.start()
    print("[SCHEDULER] Запущен. Ночное обновление цен: каждый день в 19:30 UTC.")
    return scheduler
