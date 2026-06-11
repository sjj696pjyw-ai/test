import time
from datetime import datetime
from ..models import db, Analysis, Competitor, Product, ProductLink, PriceHistory
from ..utils import SiteParser


# Короткоживущий кэш собранных товаров: «Проверить селекторы» уже собирает
# товары — переиспользуем их при «Сохранить и собрать», чтобы не скрейпить заново.
_COLLECT_CACHE = {}
_COLLECT_TTL = 180  # секунды


def _collect_cache_key(competitor_id, url, title_selector, price_selector):
    return (competitor_id, url or '', title_selector or '', price_selector or '')


def _collect_cache_get(key):
    entry = _COLLECT_CACHE.get(key)
    if entry and (time.time() - entry[0]) < _COLLECT_TTL:
        return entry[1]
    return None


def _collect_cache_set(key, products):
    # чистим протухшие записи, чтобы кэш не разрастался
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
            print(f"[ERROR] Failed to delete analysis {analysis_id}: {e}")
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
    def parse_competitor_site(competitor_id, url, title_selector, price_selector):
        # Если только что собирали те же товары при проверке селекторов —
        # переиспользуем результат (сохранение становится почти мгновенным).
        cache_key = _collect_cache_key(competitor_id, url, title_selector, price_selector)
        products = _collect_cache_get(cache_key)
        if products is None:
            print(f"[СБОР] старт: {url}")
            parser = SiteParser()
            # Собираем товары со всех страниц каталога (обход пагинации по URL)
            products = parser.parse_products_paginated(url, title_selector, price_selector)
            print(f"[СБОР] готово: {url} — товаров {len(products) if products else 0}")
        else:
            print(f"[DEBUG] Сбор: переиспользую {len(products)} товаров из кэша проверки")

        if not products:
            return []

        competitor = Competitor.query.get(competitor_id)
        if competitor:
            competitor.title_selector = title_selector
            competitor.price_selector = price_selector
            # Указанная ссылка становится текущим сайтом (заменяет прежнюю)
            if url:
                competitor.domain = url
            # Момент сбора = момент актуальности цен (показывается «Цены актуальны на…»)
            competitor.last_price_update = datetime.utcnow()
            competitor.update_status = 'success'

        # Обновляем существующие товары по имени на месте, а не создаём дубли.
        # Иначе связи (ProductLink) продолжают указывать на старый товар со
        # старой ценой, и в сводном отчёте/графике цена моих товаров не меняется.
        existing = {
            p.name.strip().lower(): p
            for p in Product.query.filter_by(competitor_id=competitor_id).all()
        }

        saved_products = []
        for prod in products:
            name = prod['name'].strip()
            key = name.lower()
            new_price = prod['price']

            if key in existing:
                product = existing[key]
                old_price = product.price
                if old_price != new_price:
                    # Фиксируем прежнюю цену в истории и обновляем текущую
                    db.session.add(PriceHistory(
                        product_id=product.id,
                        price=old_price,
                        currency=product.currency
                    ))
                    product.price = new_price
            else:
                product = Product(
                    competitor_id=competitor_id,
                    name=name,
                    price=new_price,
                    currency=prod.get('currency', 'RUB')
                )
                db.session.add(product)

            saved_products.append(product)

        db.session.commit()

        return saved_products

    @staticmethod
    def verify_selectors(competitor_id, url, title_selector, price_selector):
        parser = SiteParser()
        # Базу грузим БЕЗ прокрутки — способ сбора определяется по тирам внутри
        # parse_products_paginated (пагинация → showall → прокрутка).
        first_html = parser.get_page(url, scroll_selector=title_selector, scroll=False)

        if not first_html:
            return {'valid': False, 'name_count': 0, 'price_count': 0, 'product_count': 0}

        # Базовые счётчики и примеры — по первой странице
        result = parser.verify_selectors(first_html, title_selector, price_selector)

        # Реальный итог — по всем страницам (обход пагинации с дедупом),
        # первую страницу переиспользуем, чтобы не грузить её повторно.
        all_products = parser.parse_products_paginated(
            url, title_selector, price_selector, first_html=first_html
        )
        # Кэшируем собранные товары, чтобы «Сохранить и собрать» не скрейпил заново
        _collect_cache_set(
            _collect_cache_key(competitor_id, url, title_selector, price_selector),
            all_products
        )
        total = len(all_products)
        page1_count = result.get('product_count', total)
        result['product_count'] = total
        result['page1_product_count'] = page1_count

        # Счётчики «совпадений названий/цен» — итоговое (дедупнутое) число
        # собранных товаров, чтобы совпадали с «Будет собрано».
        result['name_count'] = total
        result['price_count'] = total

        if total > page1_count:
            # Это НЕ предупреждение, а просто факт многостраничного каталога —
            # отдаём отдельным нейтральным полем, не трогая mismatch_warning.
            result['pagination_note'] = (
                f'Каталог многостраничный: на первой странице {page1_count} товаров, '
                f'со всех страниц будет собрано {total}.'
            )

        return result
