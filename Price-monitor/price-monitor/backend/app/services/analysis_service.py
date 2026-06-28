import logging
import time
from datetime import datetime

from ..models import Analysis, Catalog, Competitor, Product, ProductLink, db
from ..utils import SiteParser, same_site
from .product_upsert import upsert_competitor_products

logger = logging.getLogger(__name__)

_COLLECT_CACHE = {}
_COLLECT_TTL = 180

def _collect_cache_key(competitor_id, url, title_selector, price_selector):
    return (competitor_id, url or '', title_selector or '', price_selector or '')

def _collect_cache_get(key):
    entry = _COLLECT_CACHE.get(key)
    if entry and (time.time() - entry[0]) < _COLLECT_TTL:
        return entry[1]
    return None

def _collect_cache_set(key, products):
    now = time.time()
    for k in [k for k, v in _COLLECT_CACHE.items() if now - v[0] >= _COLLECT_TTL]:
        _COLLECT_CACHE.pop(k, None)
    _COLLECT_CACHE[key] = (now, products)

class AnalysisService:
    @staticmethod
    def create_analysis(user_id, analysis_type, region, queries, user_site=None, name=None):
        analysis = Analysis(
            user_id=user_id,
            analysis_type=analysis_type,
            region=region,
            queries='\n'.join(queries) if isinstance(queries, list) else queries,
            user_site=user_site,
            name=name
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis

    @staticmethod
    def get_user_analyses(user_id):
        return Analysis.query.filter_by(user_id=user_id).order_by(Analysis.created_at.desc()).all()

    @staticmethod
    def get_analysis_by_id(analysis_id, user_id=None):
        query = Analysis.query.filter_by(id=analysis_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.first()

    @staticmethod
    def delete_analysis(analysis_id, user_id):
        analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()
        if not analysis:
            return False
        try:
            db.session.delete(analysis)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Failed to delete analysis {analysis_id}: {e}")
            return False

    @staticmethod
    def update_analysis_name(analysis_id, user_id, name):
        analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()
        if analysis:
            analysis.name = name
            db.session.commit()
            return analysis
        return None

class CompetitorService:
    @staticmethod
    def add_competitor(analysis_id, domain, competitor_type=None, position=None, is_user_site=False,
                       title_selector=None, price_selector=None):
        competitor = Competitor(
            analysis_id=analysis_id,
            domain=domain,
            competitor_type=competitor_type,
            position=position,
            is_user_site=is_user_site,
            title_selector=title_selector,
            price_selector=price_selector
        )
        db.session.add(competitor)
        db.session.commit()
        return competitor

    @staticmethod
    def get_competitors(analysis_id):
        return Competitor.query.filter_by(analysis_id=analysis_id).all()

    @staticmethod
    def update_selectors(competitor_id, title_selector, price_selector, url=None):
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            competitor.title_selector = title_selector
            competitor.price_selector = price_selector
            if url:
                competitor.domain = url
            db.session.commit()
            return competitor
        return None

    @staticmethod
    def delete_competitor(competitor_id):
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            db.session.delete(competitor)
            db.session.commit()
            return True
        return False

def _catalog_label(url):
    """Короткая метка каталога из URL (последний значимый сегмент пути)."""
    from urllib.parse import urlparse
    if not url:
        return 'Каталог'
    u = url if url.startswith(('http://', 'https://')) else f'https://{url}'
    path = urlparse(u).path.strip('/')
    if not path:
        return 'Главный каталог'
    return path.split('/')[-1] or path


class CatalogService:
    @staticmethod
    def get_catalogs(competitor_id):
        return Catalog.query.filter_by(competitor_id=competitor_id).order_by(Catalog.id.asc()).all()

    @staticmethod
    def update_selectors(catalog_id, title_selector, price_selector, url=None):
        catalog = Catalog.query.get(catalog_id)
        if not catalog:
            return None
        catalog.title_selector = title_selector
        catalog.price_selector = price_selector
        if url:
            catalog.url = url
        db.session.commit()
        return catalog

    @staticmethod
    def ensure_primary_catalog(competitor, url=None):
        """Возвращает основной (первый) каталог конкурента, создавая его при
        отсутствии — из domain/селекторов конкурента. Flush, но без commit."""
        cat = (Catalog.query.filter_by(competitor_id=competitor.id)
               .order_by(Catalog.id.asc()).first())
        if cat:
            return cat
        src = url or competitor.domain
        cat = Catalog(
            competitor_id=competitor.id,
            url=src,
            name=_catalog_label(src),
            title_selector=competitor.title_selector,
            price_selector=competitor.price_selector,
            feed_url=competitor.feed_url,
            last_price_update=competitor.last_price_update,
            update_status=competitor.update_status or 'pending',
        )
        db.session.add(cat)
        db.session.flush()
        return cat

    @staticmethod
    def delete_catalog(catalog_id):
        catalog = Catalog.query.get(catalog_id)
        if not catalog:
            return None
        competitor = Competitor.query.get(catalog.competitor_id)
        # последний каталог конкурента удалять нельзя — иначе товары осиротеют
        if competitor and competitor.catalogs.count() <= 1:
            return 'last'
        # товары каталога удаляем вместе с ним
        Product.query.filter_by(catalog_id=catalog_id).delete(synchronize_session=False)
        db.session.delete(catalog)
        db.session.commit()
        return True

    @staticmethod
    def add_catalog(competitor_id, url, title_selector=None, price_selector=None):
        """Добавляет новый каталог к существующему конкуренту.

        Возвращает dict со статусом:
          {'ok': True, 'catalog': Catalog, 'products': [...]}             — успех
          {'error': 'not_found'}                                          — нет конкурента
          {'error': 'different_site', 'expected': host, 'got': host}      — другой сайт
          {'error': 'no_products'}                                        — ничего не нашли
          {'error': 'duplicate'}                                          — товары уже есть
        """
        competitor = Competitor.query.get(competitor_id)
        if not competitor:
            return {'error': 'not_found'}

        normalized = url if url.startswith(('http://', 'https://')) else f'https://{url}'

        # 1) проверка того же сайта
        if not same_site(competitor.domain, normalized):
            from ..utils import host_of
            return {
                'error': 'different_site',
                'expected': host_of(competitor.domain),
                'got': host_of(normalized),
            }

        # 2) сбор товаров
        parser = SiteParser()
        try:
            products, method, feed_cache = parser.collect_products(
                normalized, title_selector, price_selector
            )
        except Exception as e:
            logger.error(f"[КАТАЛОГ] ошибка сбора {normalized}: {e}")
            return {'error': 'no_products'}
        finally:
            parser.close()

        if not products:
            return {'error': 'no_products'}

        # 3) дедуп: если ВСЕ найденные товары уже есть у конкурента по названию
        #    (цену не сравниваем — она могла измениться с прошлого сбора)
        existing = {
            p.name.strip().lower()
            for p in Product.query.filter_by(competitor_id=competitor_id).all()
        }
        found = {p['name'].strip().lower() for p in products}
        if found and found.issubset(existing):
            return {'error': 'duplicate'}

        # 4) создаём каталог и товары под ним
        catalog = Catalog(
            competitor_id=competitor_id,
            url=normalized,
            name=_catalog_label(normalized),
            title_selector=title_selector or None,
            price_selector=price_selector or None,
            feed_url=feed_cache if feed_cache is not None else None,
            last_price_update=datetime.utcnow(),
            update_status='success',
        )
        db.session.add(catalog)
        db.session.flush()  # нужен catalog.id

        result = upsert_competitor_products(competitor_id, products, catalog_id=catalog.id)
        db.session.commit()

        return {'ok': True, 'catalog': catalog, 'products': result['products']}


class ProductService:
    @staticmethod
    def get_competitor_products(competitor_id):
        return Product.query.filter_by(competitor_id=competitor_id).all()

    @staticmethod
    def get_catalog_products(catalog_id):
        return Product.query.filter_by(catalog_id=catalog_id).all()

class ProductLinkService:
    @staticmethod
    def link_products(analysis_id, user_product_id, competitor_product_id):
        existing = ProductLink.query.filter_by(
            analysis_id=analysis_id,
            user_product_id=user_product_id,
            competitor_product_id=competitor_product_id
        ).first()

        if existing:
            return existing

        link = ProductLink(
            analysis_id=analysis_id,
            user_product_id=user_product_id,
            competitor_product_id=competitor_product_id
        )
        db.session.add(link)
        db.session.commit()
        return link

    @staticmethod
    def unlink_products(link_id):
        link = ProductLink.query.get(link_id)
        if link:
            db.session.delete(link)
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_analysis_links(analysis_id):
        return ProductLink.query.filter_by(analysis_id=analysis_id).all()

class SiteParsingService:
    @staticmethod
    def preview_products(url, title_selector=None, price_selector=None, limit=100):
        """«Сухой» авто-сбор товаров по URL без записи в БД (для предпросмотра).

        Возвращает: {success, method, count, products: [{name, price, currency}]}.
        method — каким способом нашли (json-ld/microdata/embedded-json/selectors),
        либо None, если ничего не нашли.
        """
        normalized = url if url.startswith(('http://', 'https://')) else f'https://{url}'
        parser = SiteParser()
        try:
            products, method, _ = parser.collect_products(normalized, title_selector, price_selector)
        except Exception as e:
            logger.error(f"[ПРЕВЬЮ] ошибка: {url} — {e}")
            return {'success': False, 'error': 'Не удалось получить товары с сайта',
                    'method': None, 'count': 0, 'products': []}
        finally:
            parser.close()

        return {
            'success': bool(products),
            'method': method,
            'count': len(products),
            'products': [
                {'name': p['name'], 'price': p['price'],
                 'currency': p.get('currency', 'RUB'), 'url': p.get('url')}
                for p in products[:limit]
            ],
        }

    @staticmethod
    def parse_competitor_site(competitor_id, url, title_selector, price_selector):
        competitor = Competitor.query.get(competitor_id)
        feed_cache = None

        cache_key = _collect_cache_key(competitor_id, url, title_selector, price_selector)
        products = _collect_cache_get(cache_key)
        if products is None:
            logger.info(f"[СБОР] старт: {url}")
            parser = SiteParser()
            # YML-фид → авто-извлечение → селекторы (фолбэк); фид берём из кэша
            products, method, feed_cache = parser.collect_products(
                url, title_selector, price_selector,
                feed_url=(competitor.feed_url if competitor else None),
            )
            logger.info(
                f"[СБОР] готово: {url} — товаров {len(products) if products else 0}"
                f" (способ: {method or 'нет'})"
            )
        else:
            logger.debug(f"[DEBUG] Сбор: переиспользую {len(products)} товаров из кэша проверки")

        if not products:
            # даже если товаров нет — запоминаем результат поиска фида
            if competitor and feed_cache is not None:
                competitor.feed_url = feed_cache
                db.session.commit()
            return []

        catalog = None
        if competitor:
            # селекторы сохраняем только если заданы — авто-извлечению они не нужны
            if title_selector:
                competitor.title_selector = title_selector
            if price_selector:
                competitor.price_selector = price_selector
            if url:
                competitor.domain = url
            if feed_cache is not None:
                competitor.feed_url = feed_cache
            competitor.last_price_update = datetime.utcnow()
            competitor.update_status = 'success'

            # основной каталог конкурента — товары привязываем к нему
            catalog = CatalogService.ensure_primary_catalog(competitor, url=url)
            if title_selector:
                catalog.title_selector = title_selector
            if price_selector:
                catalog.price_selector = price_selector
            if url:
                catalog.url = url
            if feed_cache is not None:
                catalog.feed_url = feed_cache
            catalog.last_price_update = datetime.utcnow()
            catalog.update_status = 'success'

        result = upsert_competitor_products(
            competitor_id, products,
            catalog_id=(catalog.id if catalog else None),
        )

        db.session.commit()

        return result['products']

    @staticmethod
    def parse_catalog_site(catalog_id, url, title_selector, price_selector):
        """Пересобирает товары конкретного каталога (URL+селекторы каталога)."""
        catalog = Catalog.query.get(catalog_id)
        if not catalog:
            return []

        parser = SiteParser()
        products, method, feed_cache = parser.collect_products(
            url, title_selector, price_selector, feed_url=catalog.feed_url
        )
        parser.close()
        logger.info(f"[КАТАЛОГ {catalog_id}] собрано {len(products) if products else 0} "
                    f"(способ: {method or 'нет'})")

        if not products:
            if feed_cache is not None:
                catalog.feed_url = feed_cache
                db.session.commit()
            return []

        if title_selector:
            catalog.title_selector = title_selector
        if price_selector:
            catalog.price_selector = price_selector
        if url:
            catalog.url = url
        if feed_cache is not None:
            catalog.feed_url = feed_cache
        catalog.last_price_update = datetime.utcnow()
        catalog.update_status = 'success'

        result = upsert_competitor_products(
            catalog.competitor_id, products, catalog_id=catalog.id
        )
        db.session.commit()
        return result['products']

    @staticmethod
    def verify_selectors(competitor_id, url, title_selector, price_selector):
        parser = SiteParser()
        first_html = parser.get_page(url, scroll_selector=title_selector, scroll=False)

        if not first_html:
            return {'valid': False, 'name_count': 0, 'price_count': 0, 'product_count': 0}

        result = parser.verify_selectors(first_html, title_selector, price_selector)

        all_products = parser.parse_products_paginated(
            url, title_selector, price_selector, first_html=first_html
        )
        _collect_cache_set(
            _collect_cache_key(competitor_id, url, title_selector, price_selector),
            all_products
        )
        total = len(all_products)
        page1_count = result.get('product_count', total)
        result['product_count'] = total
        result['page1_product_count'] = page1_count

        result['name_count'] = total
        result['price_count'] = total

        if total > page1_count:
            result['pagination_note'] = (
                f'Каталог многостраничный: на первой странице {page1_count} товаров, '
                f'со всех страниц будет собрано {total}.'
            )

        return result
