"""Массовый прогон сбора товаров по реальным сайтам (ядро).

Используется и из CLI (scripts/bench_collect.py), и из админского эндпоинта,
чтобы прогон на хосте и локально давал одинаковый результат.
"""
import json
import logging
import os
import statistics
import threading
import time
from datetime import datetime

from ..utils import SiteParser

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SITES = os.path.join(BASE_DIR, 'scripts', 'bench_sites.json')
REPORTS_DIR = os.environ.get('BENCH_REPORTS_DIR') or os.path.join(BASE_DIR, 'scripts', 'reports')

# Состояние фонового прогона: чтобы не запускать второй параллельно и чтобы
# можно было спросить «идёт ли сейчас».
_state = {'running': False, 'started_at': None, 'done': 0, 'total': 0, 'last_report': None}
_lock = threading.Lock()


def load_sites(path=None):
    with open(path or DEFAULT_SITES, encoding='utf-8') as f:
        return json.load(f).get('sites', [])


def run_site(site):
    """Прогоняет один сайт. Никогда не бросает исключение наружу."""
    # Нормализация — как в проде (preview_products), иначе URL без схемы
    # обрабатывался бы иначе, чем при обычном добавлении товаров.
    raw = site['url']
    url = raw if raw.startswith(('http://', 'https://')) else f'https://{raw}'
    started = time.monotonic()
    parser = None
    row = {
        'name': site.get('name') or url,
        'url': url,
        'expect_min': site.get('expect_min'),
        'expect_method': site.get('expect_method'),
        'count': 0, 'method': None, 'elapsed': 0.0, 'with_url': 0,
        'error': None, 'samples': [], 'trace': [], 'total_hint': None, 'tier': None,
        'price_min': None, 'price_max': None, 'price_median': None,
    }
    try:
        parser = SiteParser()
        products, method, _feed = parser.collect_products(url)
        # трасса тиров: по ней видно, ПОЧЕМУ собрано столько товаров
        row['trace'] = list(getattr(parser, 'trace', []) or [])
        for step in row['trace']:
            if step.get('step') == 'страница_1':
                hint = step.get('всего_на_сайте')
                row['total_hint'] = hint if isinstance(hint, int) else None
            if step.get('step') == 'итог':
                row['tier'] = step.get('тир')
        row['count'] = len(products or [])
        row['method'] = method
        if products:
            row['with_url'] = sum(1 for p in products if p.get('url'))
            prices = [float(p['price']) for p in products
                      if isinstance(p.get('price'), (int, float))]
            if prices:
                row['price_min'] = min(prices)
                row['price_max'] = max(prices)
                row['price_median'] = statistics.median(prices)
            row['samples'] = [
                {'name': (p.get('name') or '')[:90], 'price': p.get('price'),
                 'url': (p.get('url') or '')[:120]}
                for p in products[:3]
            ]
    except Exception as e:
        row['error'] = f'{type(e).__name__}: {e}'[:300]
    finally:
        if parser is not None:
            try:
                parser.close()
            except Exception:
                pass
        row['elapsed'] = round(time.monotonic() - started, 1)
    return row


def verdict(row):
    if row['error'] or row['count'] == 0:
        return 'fail'
    if row['expect_min'] and row['count'] < row['expect_min']:
        return 'warn'
    if row['expect_method'] and row['method'] != row['expect_method']:
        return 'warn'
    return 'ok'


def compare(rows, baseline_rows):
    """Сравнение с предыдущим прогоном. Возвращает (строки сравнения, регрессии)."""
    prev = {r['url']: r for r in baseline_rows}
    lines, regressions = [], []
    for r in rows:
        p = prev.get(r['url'])
        if not p:
            lines.append({'name': r['name'], 'note': 'новый сайт в наборе',
                          'before': None, 'after': r['count']})
            continue
        d = r['count'] - p['count']
        notes = []
        if p['count'] > 0 and r['count'] == 0:
            notes.append('РЕГРЕСС: перестал парситься')
        elif p['count'] > 0 and d < 0 and abs(d) >= max(3, p['count'] * 0.1):
            notes.append(f'РЕГРЕСС: товаров меньше на {abs(d)}')
        if p['method'] and r['method'] and p['method'] != r['method']:
            notes.append(f'сменился способ: {p["method"]} → {r["method"]}')
        if p['elapsed'] > 3 and (r['elapsed'] - p['elapsed']) > max(10, p['elapsed']):
            notes.append(f'стало медленнее на {r["elapsed"] - p["elapsed"]:.0f}с')
        lines.append({'name': r['name'], 'before': p['count'], 'after': r['count'],
                      'delta': d, 'note': '; '.join(notes)})
        if any(n.startswith('РЕГРЕСС') for n in notes):
            regressions.append({'name': r['name'], 'note': '; '.join(notes)})
    return lines, regressions


def latest_report_path():
    if not os.path.isdir(REPORTS_DIR):
        return None
    files = sorted(f for f in os.listdir(REPORTS_DIR) if f.endswith('.json'))
    return os.path.join(REPORTS_DIR, files[-1]) if files else None


def load_report(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_report(report):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR,
                        f'bench_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def run_all(sites=None, sites_path=None, only=None, compare_with_last=True, on_progress=None):
    """Прогоняет набор сайтов и возвращает готовый отчёт (dict)."""
    sites = sites if sites is not None else load_sites(sites_path)
    if only:
        needles = [s.lower() for s in only]
        sites = [s for s in sites
                 if any(n in (s.get('name', '') + ' ' + s['url']).lower() for n in needles)]

    rows = []
    total = len(sites)
    logger.info(f'[БЕНЧ] старт прогона: сайтов {total}')
    for i, site in enumerate(sites, 1):
        row = run_site(site)
        rows.append(row)
        logger.info(
            f'[БЕНЧ] {i}/{total} {row["name"]}: '
            f'{"ОШИБКА " + row["error"] if row["error"] else str(row["count"]) + " товаров"} '
            f'({row["method"] or "нет"}), {row["elapsed"]}с'
        )
        if on_progress:
            on_progress(i, total, row)

    baseline_path = latest_report_path() if compare_with_last else None
    comparison, regressions = [], []
    if baseline_path and os.path.exists(baseline_path):
        base = load_report(baseline_path)
        comparison, regressions = compare(rows, base.get('rows', []))

    report = {
        'started_at': datetime.utcnow().isoformat() + 'Z',
        'rows': rows,
        'summary': {
            'total': len(rows),
            'ok': sum(1 for r in rows if verdict(r) == 'ok'),
            'warn': sum(1 for r in rows if verdict(r) == 'warn'),
            'fail': sum(1 for r in rows if verdict(r) == 'fail'),
            'elapsed': round(sum(r['elapsed'] for r in rows), 1),
        },
        'baseline': os.path.basename(baseline_path) if baseline_path else None,
        'comparison': comparison,
        'regressions': regressions,
    }
    path = save_report(report)
    report['saved_to'] = os.path.basename(path)

    s = report['summary']
    logger.info(f'[БЕНЧ] готово: OK {s["ok"]}, WARN {s["warn"]}, FAIL {s["fail"]}, '
                f'время {s["elapsed"]}с, отчёт {report["saved_to"]}')
    for reg in regressions:
        logger.warning(f'[БЕНЧ] РЕГРЕСС — {reg["name"]}: {reg["note"]}')
    return report


def get_state():
    with _lock:
        return dict(_state)


def start_background(app, only=None):
    """Запускает прогон в фоне (HTTP-запрос не должен ждать минуты).

    Возвращает False, если прогон уже идёт."""
    with _lock:
        if _state['running']:
            return False
        _state.update({'running': True, 'started_at': datetime.utcnow().isoformat() + 'Z',
                       'done': 0, 'total': 0, 'last_report': None})

    def progress(done, total, _row):
        with _lock:
            _state['done'] = done
            _state['total'] = total

    def worker():
        try:
            with app.app_context():
                report = run_all(only=only, on_progress=progress)
            with _lock:
                _state['last_report'] = report.get('saved_to')
        except Exception as e:
            logger.exception(f'[БЕНЧ] прогон упал: {e}')
        finally:
            with _lock:
                _state['running'] = False

    threading.Thread(target=worker, daemon=True, name='bench').start()
    return True
