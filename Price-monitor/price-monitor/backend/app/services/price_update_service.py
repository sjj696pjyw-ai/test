import logging
from datetime import datetime, timedelta

from ..models import Analysis, Competitor, PriceHistory, Product, ProductLink, db
from ..utils.site_parser import SiteParser
from .product_upsert import upsert_competitor_products

logger = logging.getLogger(__name__)

class PriceUpdateService:
    """Класс обновления цен товаров для сайтов"""

    MIN_UPDATE_INTERVAL_MINUTES = 3

    @staticmethod
    def can_update_competitor(competitor):
        """Проверяем - можем ли обновить сейчас (Проверка лимита времени)"""
        if not competitor.last_price_update:
            return True, None

        now = datetime.utcnow()
        time_since_update = now - competitor.last_price_update
        minutes_remaining = PriceUpdateService.MIN_UPDATE_INTERVAL_MINUTES - (time_since_update.total_seconds() / 60)

        if minutes_remaining > 0:
            return False, f"Слишком частые запросы. Обновление доступно через {int(minutes_remaining)} мин."

        return True, None

    @staticmethod
    def _collect_products_parallel(competitors, respect_rate_limit=True):
        """
        ПАРАЛЛЕЛЬНО собирает товары по КАТАЛОГАМ конкурентов (полный сбор:
        пагинация/прокрутка), только сеть/скрейпинг — БЕЗ обращения к БД,
        безопасно для потоков. Возвращает {catalog_id: products|None}.
        Запись в БД делается отдельно, последовательно (SQLite — один писатель).
        """
        import os as _os
        from concurrent.futures import ThreadPoolExecutor

        from ..models import Catalog

        targets = []
        for c in competitors:
            cats = Catalog.query.filter_by(competitor_id=c.id).all()
            has_selectors = any(cat.title_selector and cat.price_selector for cat in cats)
            # Свой сайт без селекторов не скрапим — он обновится снимком цен.
            if c.is_user_site and not has_selectors:
                continue
            if respect_rate_limit:
                can_update, _ = PriceUpdateService.can_update_competitor(c)
                if not can_update:
                    continue
            for cat in cats:
                url = cat.url or c.domain
                if not url.startswith(('http://', 'https://')):
                    url = f'https://{url}'
                targets.append((cat.id, url, cat.title_selector, cat.price_selector, cat.feed_url))

        if not targets:
            return {}

        def scrape(task):
            cat_id, url, title, price, feed_url = task
            try:
                logger.info(f"[СБОР] старт: {url}")
                sp = SiteParser()
                # по готовым селекторам — как раньше; иначе авто-извлечение
                # (кэш фида читаем; запись кэша из потока не делаем)
                if title and price:
                    prods = sp.parse_products_paginated(url, title, price)
                else:
                    prods, _, _ = sp.collect_products(url, feed_url=feed_url)
                logger.info(f"[СБОР] готово: {url} — товаров {len(prods) if prods else 0}")
                return cat_id, prods
            except Exception as e:
                logger.error(f"[СБОР] ошибка: {url} — {e}")
                return cat_id, None

        use_selenium = _os.environ.get('PARSER_USE_SELENIUM', '1') != '0'
        default_cap = 3 if use_selenium else 8
        try:
            worker_cap = int(_os.environ.get('COLLECT_MAX_WORKERS', default_cap))
        except (TypeError, ValueError):
            worker_cap = default_cap
        worker_cap = max(1, worker_cap)
        out = {}
        with ThreadPoolExecutor(max_workers=min(worker_cap, len(targets))) as ex:
            for cat_id, prods in ex.map(scrape, targets):
                out[cat_id] = prods
        return out

    @staticmethod
    def _update_one_catalog(competitor, catalog, prefetched_products=None, use_prefetched=False):
        """Обновляет цены одного каталога. Возвращает dict со status и счётчиками.
        use_prefetched=True — товары уже собраны (prefetched_products, может быть
        None при ошибке сбора); иначе скрапим здесь."""
        if use_prefetched:
            products_data = prefetched_products
        else:
            url = catalog.url or competitor.domain
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            parser = SiteParser()
            if catalog.title_selector and catalog.price_selector:
                first_html = parser.get_page(url, scroll_selector=catalog.title_selector, scroll=False)
                if not first_html:
                    catalog.update_status = 'error'
                    catalog.update_error_message = 'Сайт не отвечает или недоступен'
                    return {'status': 'site_unavailable', 'updated_count': 0,
                            'created_count': 0, 'not_found_count': 0, 'price_changes': []}
                products_data = parser.parse_products_paginated(
                    url, catalog.title_selector, catalog.price_selector, first_html=first_html
                )
            else:
                products_data, _, feed_cache = parser.collect_products(url, feed_url=catalog.feed_url)
                if feed_cache is not None:
                    catalog.feed_url = feed_cache

        if not products_data:
            catalog.update_status = 'partial'
            catalog.update_error_message = 'Товары не найдены'
            return {'status': 'no_products', 'updated_count': 0,
                    'created_count': 0, 'not_found_count': 0, 'price_changes': []}

        upsert_result = upsert_competitor_products(
            competitor.id,
            products_data,
            on_existing=lambda product: PriceUpdateService._record_linked_user_product_price(product.id),
            catalog_id=catalog.id,
        )
        catalog.last_price_update = datetime.utcnow()
        nf = upsert_result['not_found_count']
        catalog.update_status = 'success' if nf == 0 else 'partial'
        catalog.update_error_message = None if nf == 0 else f'{nf} товаров не найдено'
        return {
            'status': catalog.update_status,
            'updated_count': upsert_result['updated_count'],
            'created_count': upsert_result['created_count'],
            'not_found_count': nf,
            'price_changes': upsert_result['price_changes'],
        }

    @staticmethod
    def update_competitor_prices(competitor_id, prefetched_by_catalog=None,
                                 respect_rate_limit=True):
        """
        Обновление цен конкурента по ВСЕМ его каталогам.
        prefetched_by_catalog — {catalog_id: products|None} из параллельного сбора;
            если передан, скрейпинг пропускается, идёт только запись в БД.
        respect_rate_limit — учитывать лимит «раз в 3 минуты».
        Возвращает dict с полями status, updated_count, etc.
        """
        from ..models import Catalog
        from ..services.analysis_service import CatalogService

        competitor = Competitor.query.get(competitor_id)
        if not competitor:
            logger.debug(f"[DEBUG] Competitor {competitor_id} not found in database")
            return {'success': False, 'error': 'Конкурент не найден', 'status': 'error'}

        if respect_rate_limit:
            can_update, error_msg = PriceUpdateService.can_update_competitor(competitor)
            if not can_update:
                logger.debug(f"[DEBUG] Competitor {competitor_id} is rate limited: {error_msg}")
                return {'success': False, 'error': error_msg, 'status': 'rate_limited'}

        catalogs = Catalog.query.filter_by(competitor_id=competitor_id).all()
        if not catalogs:
            # старый конкурент без каталога — создаём основной
            catalogs = [CatalogService.ensure_primary_catalog(competitor)]

        has_selectors = any(c.title_selector and c.price_selector for c in catalogs)
        use_prefetched = prefetched_by_catalog is not None

        # Свой сайт без селекторов не скрапим — снимок текущих цен в историю.
        if competitor.is_user_site and not has_selectors:
            return PriceUpdateService._snapshot_user_site_prices(competitor)

        updated_count = created_count = not_found_count = 0
        price_changes = []
        statuses = []
        for cat in catalogs:
            res = PriceUpdateService._update_one_catalog(
                competitor, cat,
                prefetched_products=(prefetched_by_catalog or {}).get(cat.id),
                use_prefetched=use_prefetched,
            )
            statuses.append(res['status'])
            updated_count += res['updated_count']
            created_count += res['created_count']
            not_found_count += res['not_found_count']
            price_changes.extend(res['price_changes'])

        # сводный статус конкурента
        if any(s in ('success', 'partial') for s in statuses):
            overall = 'success' if all(s == 'success' for s in statuses) else 'partial'
        elif any(s == 'site_unavailable' for s in statuses):
            overall = 'site_unavailable'
        else:
            overall = 'no_products'

        competitor.last_price_update = datetime.utcnow()
        competitor.update_status = overall
        competitor.update_error_message = (
            None if overall == 'success'
            else (f'{not_found_count} товаров не найдено' if overall == 'partial'
                  else 'Товары не найдены')
        )
        db.session.commit()

        success = overall in ('success', 'partial')
        return {
            'success': success,
            'status': overall,
            'competitor_id': competitor_id,
            'competitor_domain': competitor.domain,
            'updated_count': updated_count,
            'created_count': created_count,
            'not_found_count': not_found_count,
            'price_changes': price_changes,
            'last_update': competitor.last_price_update.isoformat(),
        }

    @staticmethod
    def _snapshot_user_site_prices(competitor):
        """Свой сайт без скрапинга: фиксируем текущие цены товаров в истории.

        Используется, когда у своего сайта нет ни селекторов, ни авто-собранных
        данных — каталог заведён владельцем, и мы просто снимаем его цены в
        историю на сегодняшнюю дату.
        """
        products = Product.query.filter_by(competitor_id=competitor.id).all()
        if not products:
            logger.debug(f"[DEBUG] Свой сайт {competitor.id}: нет товаров — пропуск")
            return {
                'success': False,
                'status': 'no_products',
                'competitor_id': competitor.id,
                'competitor_domain': competitor.domain,
                'is_user_site': True,
            }
        for product in products:
            db.session.add(PriceHistory(
                product_id=product.id,
                price=product.price,
                currency=product.currency,
            ))
        competitor.last_price_update = datetime.utcnow()
        competitor.update_status = 'success'
        db.session.commit()
        return {
            'success': True,
            'status': 'success',
            'competitor_id': competitor.id,
            'competitor_domain': competitor.domain,
            'updated_count': len(products),
            'is_user_site': True,
        }

    @staticmethod
    def _record_linked_user_product_price(competitor_product_id):
        """
        Record price history for user product linked to this competitor product.
        Called when competitor's price changes.
        """
        product_links = ProductLink.query.filter_by(competitor_product_id=competitor_product_id).all()

        for link in product_links:
            user_product = link.user_product
            if user_product:
                price_history = PriceHistory(
                    product_id=user_product.id,
                    price=user_product.price,
                    currency=user_product.currency
                )
                db.session.add(price_history)

    @staticmethod
    def update_analysis_prices(analysis_id, respect_rate_limit=True):
        """
        Обновление всех цен в анализе.
        respect_rate_limit — для ручного обновления True (лимит раз в 3 мин),
            для системного (ночного) — False.
        Возвращает dict с статусом и результатами.
        """
        competitors = Competitor.query.filter_by(analysis_id=analysis_id).all()

        if not competitors:
            return {
                'success': False,
                'error': 'Конкуренты не найдены',
                'results': []
            }

        if respect_rate_limit:
            wait_minutes = []
            for c in competitors:
                ok, _ = PriceUpdateService.can_update_competitor(c)
                if not ok and c.last_price_update:
                    remaining = PriceUpdateService.MIN_UPDATE_INTERVAL_MINUTES - (
                        (datetime.utcnow() - c.last_price_update).total_seconds() / 60
                    )
                    wait_minutes.append(remaining)
            if wait_minutes:
                wait = max(1, int(round(max(wait_minutes))))
                msg = f'Обновление цен доступно раз в 3 минуты. Попробуйте через {wait} мин.'
                return {
                    'success': False,
                    'status': 'rate_limited',
                    'overall_status': 'rate_limited',
                    'rate_limited_message': msg,
                    'error': msg,
                    'results': []
                }

        collected = PriceUpdateService._collect_products_parallel(competitors, respect_rate_limit=respect_rate_limit)

        results = []
        success_count = 0
        partial_count = 0
        error_count = 0
        rate_limited_count = 0
        skipped_count = 0

        for competitor in competitors:
            result = PriceUpdateService.update_competitor_prices(
                competitor.id, prefetched_by_catalog=collected,
                respect_rate_limit=respect_rate_limit
            )
            results.append(result)

            status = result.get('status')
            dom = result.get('competitor_domain', competitor.domain)
            if status == 'success':
                success_count += 1
                logger.info(f"[ОБНОВЛЕНИЕ] {dom}: ✓ обновлено "
                      f"(обновлено {result.get('updated_count', 0)}, создано {result.get('created_count', 0)})")
            elif status == 'partial':
                partial_count += 1
                logger.warning(f"[ОБНОВЛЕНИЕ] {dom}: ⚠ частично — {result.get('error') or 'часть товаров не найдена'}")
            elif status == 'rate_limited':
                rate_limited_count += 1
                logger.info(f"[ОБНОВЛЕНИЕ] {dom}: пропуск — рейт-лимит")
            elif status == 'no_selectors':
                skipped_count += 1
                logger.info(f"[ОБНОВЛЕНИЕ] {dom}: пропуск — селекторы не настроены")
            else:
                error_count += 1
                logger.error(f"[ОБНОВЛЕНИЕ] {dom}: ✗ НЕ УДАЛОСЬ ({status}) — {result.get('error') or 'неизвестная ошибка'}")

        updated = success_count + partial_count

        if updated == 0:
            if error_count > 0:
                overall_status = 'error'
            elif rate_limited_count > 0:
                overall_status = 'rate_limited'
            else:
                overall_status = 'success'
        else:
            if error_count == 0 and rate_limited_count == 0:
                overall_status = 'success' if partial_count == 0 else 'partial'
            else:
                overall_status = 'partial'

        rate_limited_message = next(
            (r.get('error') for r in results if r.get('status') == 'rate_limited' and r.get('error')),
            None
        )

        return {
            'success': overall_status != 'error',
            'overall_status': overall_status,
            'analysis_id': analysis_id,
            'total_competitors': len(competitors),
            'success_count': success_count,
            'partial_count': partial_count,
            'error_count': error_count,
            'rate_limited_count': rate_limited_count,
            'rate_limited_message': rate_limited_message,
            'skipped_count': skipped_count,
            'results': results
        }

    @staticmethod
    def get_user_events(user_id, date_from=None, date_to=None):
        """
        Лента событий изменения цен по СВЯЗАННЫМ товарам конкурентов
        во всех анализах пользователя. date_from/date_to — объекты date (включительно).
        """
        def situational(direction, new_comp, old_comp, user_price):
            if user_price is None:
                return ''
            if direction == 'decreased':
                if new_comp < user_price:
                    return 'Конкурент теперь дешевле вас.'
                if new_comp == user_price:
                    return 'Цена сравнялась с вашей.'
                return 'Конкурент приближается к вашей цене.'
            if old_comp <= user_price < new_comp:
                return 'Теперь вы выгоднее конкурента.'
            if new_comp > user_price:
                return 'Вы по-прежнему выгоднее конкурента.'
            return 'Конкурент всё ещё дешевле вас.'

        events = []
        analyses = Analysis.query.filter_by(user_id=user_id).all()
        for analysis in analyses:
            links = ProductLink.query.filter_by(analysis_id=analysis.id).all()
            for link in links:
                cp = link.competitor_product
                up = link.user_product
                if not cp:
                    continue
                history = PriceHistory.query.filter_by(product_id=cp.id) \
                    .order_by(PriceHistory.recorded_at.asc()).all()
                n = len(history)
                for i in range(n):
                    old_price = history[i].price
                    new_price = history[i + 1].price if i + 1 < n else cp.price
                    if old_price is None or new_price is None or old_price == new_price:
                        continue
                    ts = history[i].recorded_at
                    d = ts.date()
                    if date_from and d < date_from:
                        continue
                    if date_to and d > date_to:
                        continue
                    direction = 'decreased' if new_price < old_price else 'increased'
                    events.append({
                        'analysis_id': analysis.id,
                        'analysis_name': analysis.name or f'Анализ #{analysis.id}',
                        'competitor_domain': (cp.competitor.domain if cp.competitor else ''),
                        'product_name': cp.name,
                        'old_price': old_price,
                        'new_price': new_price,
                        'direction': direction,
                        'situational': situational(direction, new_price, old_price, up.price if up else None),
                        'date': ts.isoformat(),
                    })
        events.sort(key=lambda e: e['date'], reverse=True)
        return events

    @staticmethod
    def update_all_analyses_prices():
        """Системное обновление цен по ВСЕМ анализам всех клиентов (для ночного
        планировщика). Игнорирует лимит «раз в 3 минуты». Возвращает сводку."""
        analyses = Analysis.query.all()
        total = len(analyses)
        ok = 0
        failed = 0
        logger.info(f"[SCHEDULER] Старт ночного обновления цен: анализов {total}")
        for a in analyses:
            try:
                PriceUpdateService.update_analysis_prices(a.id, respect_rate_limit=False)
                ok += 1
            except Exception as e:
                failed += 1
                logger.error(f"[SCHEDULER] Анализ {a.id}: ошибка обновления — {e}")
        logger.info(f"[SCHEDULER] Готово: обработано {ok}/{total}, с ошибками {failed}")
        return {'total': total, 'ok': ok, 'failed': failed}

    @staticmethod
    def update_user_analyses_prices(user_id):
        """Обновляет цены по всем анализам пользователя, собирает статусы."""
        FAILED = ('no_selectors', 'no_products', 'site_unavailable', 'error')

        analyses = Analysis.query.filter_by(user_id=user_id).all()
        comp_results = []
        problem_ids = []
        for a in analyses:
            r = PriceUpdateService.update_analysis_prices(a.id)
            comp = r.get('results', [])
            comp_results.extend(comp)
            working = sum(1 for cr in comp
                          if (cr.get('status') in ('success', 'partial') and not cr.get('is_user_site'))
                          or cr.get('status') == 'rate_limited')
            could_not = sum(1 for cr in comp if cr.get('status') in FAILED)
            if working == 0 and could_not > 0:
                problem_ids.append(a.id)

        any_problem = len(problem_ids) > 0
        any_rate_limited = any(cr.get('status') == 'rate_limited' for cr in comp_results)

        real_updates_total = sum(1 for cr in comp_results
                                 if cr.get('status') in ('success', 'partial') and not cr.get('is_user_site'))
        skipped_no_selectors = sum(1 for cr in comp_results if cr.get('status') == 'no_selectors')
        need_selectors = real_updates_total == 0 and skipped_no_selectors > 0 and not any_rate_limited

        return {
            'any_rate_limited': any_rate_limited,
            'any_problem': any_problem,
            'problem_analysis_ids': problem_ids,
            'need_selectors': need_selectors,
        }

    @staticmethod
    def get_price_history(product_id, days=30):
        """Получает историю цены для продукта"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        history = PriceHistory.query.filter(
            PriceHistory.product_id == product_id,
            PriceHistory.recorded_at >= cutoff_date
        ).order_by(PriceHistory.recorded_at.desc()).all()

        return [h.to_dict() for h in history]

    @staticmethod
    def get_analysis_price_dynamics(analysis_id, days=30):
        """
        Получает динамику цен для связанных товаров в анализе.
        Возвращает данные для отрисовки графика.
        """
        from ..models import ProductLink

        product_links = ProductLink.query.filter_by(analysis_id=analysis_id).all()

        dynamics = []

        for link in product_links:
            user_product = link.user_product
            competitor_product = link.competitor_product

            if not user_product or not competitor_product:
                continue

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            user_history = PriceHistory.query.filter(
                PriceHistory.product_id == user_product.id,
                PriceHistory.recorded_at >= cutoff_date
            ).order_by(PriceHistory.recorded_at.asc()).all()

            competitor_history = PriceHistory.query.filter(
                PriceHistory.product_id == competitor_product.id,
                PriceHistory.recorded_at >= cutoff_date
            ).order_by(PriceHistory.recorded_at.asc()).all()

            all_dates = set()
            for h in user_history + competitor_history:
                date_key = h.recorded_at.date().isoformat()
                all_dates.add(date_key)

            all_dates = sorted(all_dates)

            current_date = datetime.utcnow().date().isoformat()
            if current_date not in all_dates:
                all_dates.append(current_date)

            series_data = {
                'product_name': user_product.name,
                'user_site': True,
                'user_product_id': user_product.id,
                'competitor_name': competitor_product.name,
                'competitor_domain': competitor_product.competitor.domain,
                'product_url': competitor_product.url,
                'data_points': []
            }

            def effective(history, current_price, date_str):
                n = len(history)
                if n == 0:
                    return current_price
                if date_str < history[0].recorded_at.date().isoformat():
                    return history[0].price
                val = history[0].price
                for i in range(n):
                    if history[i].recorded_at.date().isoformat() <= date_str:
                        val = history[i + 1].price if i + 1 < n else current_price
                    else:
                        break
                return val

            for date_str in all_dates:
                series_data['data_points'].append({
                    'date': date_str,
                    'user_price': effective(user_history, user_product.price, date_str),
                    'competitor_price': effective(competitor_history, competitor_product.price, date_str)
                })

            dynamics.append(series_data)

        return dynamics
