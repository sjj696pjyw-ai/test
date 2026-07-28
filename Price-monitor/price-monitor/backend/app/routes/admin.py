"""Служебные эндпоинты для запуска прогона сбора на хосте.

Доступ — по секретному токену из переменной окружения ADMIN_TOKEN, который
передаётся заголовком X-Admin-Token. Если переменная не задана, эндпоинты
выключены полностью (чтобы случайно не открыть их в проде).

Зачем: у хостинга нет shell-доступа в контейнер, а прогон нужно делать именно
на сервере — там другой канал и мощности. Дёргаем curl-ом со своей машины.
"""
import hmac
import logging
import os
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ..services import bench_service

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def require_admin_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get('ADMIN_TOKEN')
        if not expected:
            return jsonify({'error': 'Админские эндпоинты отключены (нет ADMIN_TOKEN)'}), 404
        got = request.headers.get('X-Admin-Token', '')
        # сравнение постоянного времени — не даём подобрать токен по таймингам
        if not hmac.compare_digest(got, expected):
            logger.warning('[ADMIN] отказ в доступе: неверный токен, ip=%s',
                           request.headers.get('X-Forwarded-For', request.remote_addr))
            return jsonify({'error': 'Доступ запрещён'}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route('/bench', methods=['POST'])
@require_admin_token
def start_bench():
    """Запускает массовый прогон сбора в фоне и сразу отвечает."""
    data = request.get_json(silent=True) or {}
    only = data.get('only') or None
    if isinstance(only, str):
        only = [only]

    started = bench_service.start_background(current_app._get_current_object(), only=only)
    if not started:
        return jsonify({'message': 'Прогон уже идёт', 'state': bench_service.get_state()}), 409
    return jsonify({
        'message': 'Прогон запущен. Следите за логами или запросите /api/admin/bench/state',
        'state': bench_service.get_state(),
    }), 202


@admin_bp.route('/bench/state', methods=['GET'])
@require_admin_token
def bench_state():
    """Идёт ли прогон и сколько сайтов уже обработано."""
    return jsonify(bench_service.get_state()), 200


@admin_bp.route('/bench/last', methods=['GET'])
@require_admin_token
def bench_last():
    """Последний сохранённый отчёт целиком."""
    path = bench_service.latest_report_path()
    if not path:
        return jsonify({'error': 'Отчётов пока нет'}), 404
    return jsonify(bench_service.load_report(path)), 200


@admin_bp.route('/bench/summary', methods=['GET'])
@require_admin_token
def bench_summary():
    """Короткая сводка последнего отчёта — удобно смотреть прямо в терминале."""
    path = bench_service.latest_report_path()
    if not path:
        return jsonify({'error': 'Отчётов пока нет'}), 404
    report = bench_service.load_report(path)
    problem_names = {reg['name'] for reg in report.get('regressions', [])}
    lines = []
    for r in report.get('rows', []):
        status = bench_service.verdict(r)
        hint = f' из ~{r["total_hint"]}' if r.get('total_hint') else ''
        lines.append(
            f'{status.upper():5} {r["name"][:32]:32} {r["count"]:>6} товаров{hint}  '
            f'{str(r["method"] or "-"):12} {r["elapsed"]:>6}с  '
            f'тир: {r.get("tier") or "—"}'
            + (f'  ошибка: {r["error"][:60]}' if r.get('error') else '')
        )
        # для проблемных сайтов сразу показываем трассу — не надо лезть в логи
        if status != 'ok' or r['name'] in problem_names:
            for step in r.get('trace', []):
                details = ' '.join(f'{k}={v}' for k, v in step.items() if k != 'step')
                lines.append(f'      └ {step.get("step")}: {details}')
    return jsonify({
        'started_at': report.get('started_at'),
        'summary': report.get('summary'),
        'regressions': report.get('regressions', []),
        'lines': lines,
    }), 200
