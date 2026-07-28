#!/usr/bin/env python3
"""Массовый прогон сбора товаров по реальным сайтам (CLI).

Логика живёт в app/services/bench_service.py — тот же код используется
админским эндпоинтом, поэтому прогон на хосте и локально даёт одинаковый
результат.

Запуск:
    python scripts/bench_collect.py                    # весь набор + сравнение с прошлым
    python scripts/bench_collect.py --only e2e4 mokry  # только совпадающие по имени/URL
    python scripts/bench_collect.py --no-compare

Код возврата 1, если найдены регрессии — удобно для cron/CI.
"""
import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# ВАЖНО: те же переменные окружения, что и у приложения (main.py делает то же).
# Без этого парсер вёл бы себя иначе, чем в проде: PARSER_USE_SELENIUM,
# CHROME_BIN, CHROMEDRIVER_PATH, LOG_LEVEL и прочее просто не подхватились бы.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    load_dotenv()
except ImportError:
    pass

from app.logging_config import configure_logging  # noqa: E402
from app.services import bench_service as bs  # noqa: E402

# то же логирование, что и в проде: видны [ТРАССА] и [СБОР]
configure_logging()


def print_report(report):
    rows = report['rows']
    print('\n' + '=' * 104)
    print(f'{"САЙТ":30} {"ТОВАРОВ":>8} {"ОЖИД":>6} {"СПОСОБ":14} {"ВРЕМЯ":>7} {"СО ССЫЛ":>8}  СТАТУС')
    print('-' * 104)
    for r in rows:
        v = bs.verdict(r)
        exp = r['expect_min'] if r['expect_min'] else '-'
        print(f'{r["name"][:30]:30} {r["count"]:>8} {str(exp):>6} '
              f'{str(r["method"] or "-"):14} {r["elapsed"]:>6}с {r["with_url"]:>8}  '
              f'{v.upper():5}')
        if r['error']:
            print(f'{"":30}   ошибка: {r["error"][:80]}')
    s = report['summary']
    print('-' * 104)
    print(f'Итого: {s["total"]} сайтов — OK {s["ok"]}, WARN {s["warn"]}, FAIL {s["fail"]}; '
          f'общее время {s["elapsed"]}с')

    print('\nПРИМЕРЫ РАЗОБРАННЫХ ТОВАРОВ')
    print('-' * 104)
    for r in rows:
        if not r['samples']:
            continue
        span = ''
        if r['price_min'] is not None:
            span = (f'  [цены: {r["price_min"]:.0f} … {r["price_max"]:.0f}, '
                    f'медиана {r["price_median"]:.0f}]')
        print(f'\n{r["name"]}{span}')
        for smp in r['samples']:
            link = ' ←ссылка' if smp['url'] else ''
            print(f'   {str(smp["price"]):>10}  {smp["name"]}{link}')

    if report.get('comparison'):
        print(f'\nСРАВНЕНИЕ С ПРЕДЫДУЩИМ ПРОГОНОМ ({report.get("baseline")})')
        print('-' * 104)
        for c in report['comparison']:
            if c.get('before') is None:
                print(f'{c["name"][:34]:34} {c["note"]}')
                continue
            d = c['delta']
            sign = '+' if d > 0 else ''
            print(f'{c["name"][:34]:34} {c["before"]:>6} → {c["after"]:<6} ({sign}{d})'
                  + (f'   {c["note"]}' if c['note'] else ''))


def main():
    ap = argparse.ArgumentParser(description='Прогон сбора товаров по реальным сайтам')
    ap.add_argument('--sites', help='JSON со списком сайтов')
    ap.add_argument('--only', nargs='*', help='только сайты, чьё имя/URL содержит подстроку')
    ap.add_argument('--no-compare', action='store_true', help='не сравнивать с предыдущим')
    args = ap.parse_args()

    sites = bs.load_sites(args.sites)
    print(f'Прогон {len(sites)} сайтов. Это занимает минуты — сбор идёт по-настоящему.\n')

    def progress(done, total, row):
        status = row['error'] or f'{row["count"]} товаров ({row["method"] or "нет"})'
        print(f'[{done}/{total}] {row["name"]}: {status}, {row["elapsed"]}с')

    report = bs.run_all(sites_path=args.sites, only=args.only,
                        compare_with_last=not args.no_compare, on_progress=progress)
    print_report(report)
    print(f'\nОтчёт сохранён: {report["saved_to"]}')

    if report['regressions']:
        print('\nНАЙДЕНЫ РЕГРЕССИИ:')
        for reg in report['regressions']:
            print(f'  • {reg["name"]}: {reg["note"]}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
