import logging
import time
from datetime import datetime

from ..models import Analysis, Competitor, Product, ProductLink, db
from ..utils import SiteParser
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

class ProductService:
    @staticmethod
    def get_competitor_products(competitor_id):
        return Product.query.filter_by(competitor_id=competitor_id).all()

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

        result = upsert_competitor_products(competitor_id, products)

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
