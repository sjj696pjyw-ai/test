from ..models import db, Competitor, Product, PriceHistory, ProductLink
from ..utils.site_parser import SiteParser
from datetime import datetime, timedelta


class PriceUpdateService:
    """Service for handling price updates from competitor sites"""
    
    MIN_UPDATE_INTERVAL_MINUTES = 3  # Minimum time between updates
    
    @staticmethod
    def can_update_competitor(competitor):
        """Check if competitor can be updated (rate limiting)"""
        if not competitor.last_price_update:
            return True, None
        
        now = datetime.utcnow()
        time_since_update = now - competitor.last_price_update
        minutes_remaining = PriceUpdateService.MIN_UPDATE_INTERVAL_MINUTES - (time_since_update.total_seconds() / 60)
        
        if minutes_remaining > 0:
            return False, f"Обновление доступно через {int(minutes_remaining)} мин."
        
        return True, None
    
    @staticmethod
    def update_competitor_prices(competitor_id):
        """
        Update prices for a single competitor.
        Returns dict with status, updated_count, errors, etc.
        """
        competitor = Competitor.query.get(competitor_id)
        if not competitor:
            print(f"[DEBUG] Competitor {competitor_id} not found in database")
            return {
                'success': False,
                'error': 'Конкурент не найден',
                'status': 'error'
            }
        
        # Check rate limit
        can_update, error_msg = PriceUpdateService.can_update_competitor(competitor)
        if not can_update:
            print(f"[DEBUG] Competitor {competitor_id} is rate limited: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'status': 'rate_limited'
            }
        
        # Check if selectors are configured (skip for user site without selectors - use current price)
        if not competitor.title_selector or not competitor.price_selector:
            # For user site without selectors, just record current price as history
            if competitor.is_user_site:
                products = Product.query.filter_by(competitor_id=competitor_id).all()
                for product in products:
                    # Record current price to history
                    price_history = PriceHistory(
                        product_id=product.id,
                        price=product.price,
                        currency=product.currency
                    )
                    db.session.add(price_history)
                
                competitor.last_price_update = datetime.utcnow()
                competitor.update_status = 'success'
                db.session.commit()
                
                return {
                    'success': True,
                    'status': 'success',
                    'competitor_id': competitor_id,
                    'competitor_domain': competitor.domain,
                    'updated_count': len(products),
                    'is_user_site': True
                }

            print(f"[DEBUG] Competitor {competitor_id} has no selectors configured")
            return {
                'success': False,
                'error': 'Селекторы не настроены',
                'status': 'no_selectors'
            }
        
        # Build URL from domain
        url = competitor.domain
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        print(f"[DEBUG] Updating prices for competitor {competitor_id}, domain: {competitor.domain}, url: {url}")
        print(f"[DEBUG] Selectors - title: {competitor.title_selector}, price: {competitor.price_selector}")
        
        # Parse the site
        parser = SiteParser()
        html = parser.get_page(url)
        
        if not html:
            print(f"[DEBUG] Failed to get HTML from {url}")
            competitor.update_status = 'error'
            competitor.update_error_message = 'Сайт не отвечает или недоступен'
            db.session.commit()
            
            return {
                'success': False,
                'error': 'Сайт не отвечает',
                'status': 'site_unavailable',
                'competitor_id': competitor_id,
                'competitor_domain': competitor.domain
            }
        
        print(f"[DEBUG] Got HTML, length: {len(html)}")
        
        # Parse products
        products_data = parser.parse_products(
            html, 
            competitor.title_selector, 
            competitor.price_selector
        )
        
        print(f"[DEBUG] Parsed {len(products_data)} products")
        
        if not products_data:
            competitor.update_status = 'partial'
            competitor.update_error_message = 'Товары не найдены по селекторам'
            db.session.commit()
            
            return {
                'success': False,
                'error': 'Товары не найдены',
                'status': 'no_products',
                'competitor_id': competitor_id,
                'competitor_domain': competitor.domain
            }
        
        # Match and update existing products or create new ones
        updated_count = 0
        created_count = 0
        not_found_count = 0
        price_changes = []
        
        existing_products = {p.name.strip().lower(): p for p in Product.query.filter_by(competitor_id=competitor_id).all()}
        
        for prod_data in products_data:
            product_name = prod_data['name'].strip()
            product_name_key = product_name.lower()
            
            if product_name_key in existing_products:
                # Update existing product
                product = existing_products[product_name_key]
                old_price = product.price
                new_price = prod_data['price']
                
                # Record price history for linked user product (before updating competitor price)
                # This ensures we capture the current state before any changes
                PriceUpdateService._record_linked_user_product_price(product.id)
                
                if old_price != new_price:
                    # Record price history for competitor product
                    price_history = PriceHistory(
                        product_id=product.id,
                        price=old_price,
                        currency=product.currency
                    )
                    db.session.add(price_history)
                    
                    # Update price
                    product.price = new_price
                    price_changes.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'old_price': old_price,
                        'new_price': new_price
                    })
                
                updated_count += 1
            else:
                # Create new product
                product = Product(
                    competitor_id=competitor_id,
                    name=product_name,
                    price=prod_data['price'],
                    currency=prod_data.get('currency', 'RUB')
                )
                db.session.add(product)
                created_count += 1
        
        # Mark products that weren't found in the latest parse as potentially unavailable
        found_names = {p['name'].strip().lower() for p in products_data}
        for name, product in existing_products.items():
            if name not in found_names:
                not_found_count += 1
                # We don't delete, just track that it wasn't found
        
        # Update competitor status
        competitor.last_price_update = datetime.utcnow()
        competitor.update_status = 'success' if not_found_count == 0 else 'partial'
        competitor.update_error_message = None if competitor.update_status == 'success' else f'{not_found_count} товаров не найдено'
        
        db.session.commit()
        
        return {
            'success': True,
            'status': competitor.update_status,
            'competitor_id': competitor_id,
            'competitor_domain': competitor.domain,
            'updated_count': updated_count,
            'created_count': created_count,
            'not_found_count': not_found_count,
            'price_changes': price_changes,
            'last_update': competitor.last_price_update.isoformat()
        }
    
    @staticmethod
    def _record_linked_user_product_price(competitor_product_id):
        """
        Record price history for user product linked to this competitor product.
        Called when competitor's price changes.
        """
        # Find all product links where this competitor product is linked
        product_links = ProductLink.query.filter_by(competitor_product_id=competitor_product_id).all()
        
        for link in product_links:
            user_product = link.user_product
            if user_product:
                # Record current user product price to history
                price_history = PriceHistory(
                    product_id=user_product.id,
                    price=user_product.price,
                    currency=user_product.currency
                )
                db.session.add(price_history)
    
    @staticmethod
    def update_analysis_prices(analysis_id):
        """
        Update prices for all competitors in an analysis.
        Returns dict with overall status and per-competitor results.
        """
        competitors = Competitor.query.filter_by(analysis_id=analysis_id).all()
        
        if not competitors:
            return {
                'success': False,
                'error': 'Конкуренты не найдены',
                'results': []
            }
        
        results = []
        success_count = 0
        partial_count = 0
        error_count = 0
        rate_limited_count = 0
        skipped_count = 0  # конкуренты без настроенных селекторов — это не ошибка

        for competitor in competitors:
            result = PriceUpdateService.update_competitor_prices(competitor.id)
            results.append(result)

            status = result.get('status')
            if status == 'success':
                success_count += 1
            elif status == 'partial':
                partial_count += 1
            elif status == 'rate_limited':
                rate_limited_count += 1
            elif status == 'no_selectors':
                skipped_count += 1
            else:
                error_count += 1

        # Сколько конкурентов реально обновилось
        updated = success_count + partial_count

        # Determine overall status
        if updated == 0:
            if error_count > 0:
                overall_status = 'error'
            elif rate_limited_count > 0:
                overall_status = 'rate_limited'
            else:
                overall_status = 'success'  # обновлять было нечего (только без селекторов)
        else:
            if error_count == 0 and rate_limited_count == 0:
                overall_status = 'success' if partial_count == 0 else 'partial'
            else:
                overall_status = 'partial'

        # Сообщение про рейт-лимит (берём из первого ограниченного конкурента)
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
    def get_price_history(product_id, days=30):
        """Get price history for a product"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        history = PriceHistory.query.filter(
            PriceHistory.product_id == product_id,
            PriceHistory.recorded_at >= cutoff_date
        ).order_by(PriceHistory.recorded_at.desc()).all()
        
        return [h.to_dict() for h in history]
    
    @staticmethod
    def get_analysis_price_dynamics(analysis_id, days=30):
        """
        Get price dynamics for all linked products in an analysis.
        Returns data suitable for chart rendering.
        """
        from ..models import ProductLink
        
        product_links = ProductLink.query.filter_by(analysis_id=analysis_id).all()
        
        dynamics = []
        
        for link in product_links:
            user_product = link.user_product
            competitor_product = link.competitor_product
            
            if not user_product or not competitor_product:
                continue
            
            # Get price history for both products
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            user_history = PriceHistory.query.filter(
                PriceHistory.product_id == user_product.id,
                PriceHistory.recorded_at >= cutoff_date
            ).order_by(PriceHistory.recorded_at.asc()).all()
            
            competitor_history = PriceHistory.query.filter(
                PriceHistory.product_id == competitor_product.id,
                PriceHistory.recorded_at >= cutoff_date
            ).order_by(PriceHistory.recorded_at.asc()).all()
            
            # Combine history points
            all_dates = set()
            for h in user_history + competitor_history:
                date_key = h.recorded_at.date().isoformat()
                all_dates.add(date_key)
            
            all_dates = sorted(all_dates)
            
            # Add current prices as latest point
            current_date = datetime.utcnow().date().isoformat()
            if current_date not in all_dates:
                all_dates.append(current_date)
            
            series_data = {
                'product_name': user_product.name,
                'user_site': True,  # Mark as user's product (green)
                'user_product_id': user_product.id,  # Add user product ID for filtering
                'competitor_name': competitor_product.name,
                'competitor_domain': competitor_product.competitor.domain,
                'product_url': competitor_product.url,
                'data_points': []
            }
            
            for date_str in all_dates:
                user_price = None
                competitor_price = None

                # Берём самую свежую запись истории за этот день (а не первую/старую),
                # чтобы при нескольких изменениях за день показывалась актуальная цена
                user_day = [h for h in user_history if h.recorded_at.date().isoformat() == date_str]
                if user_day:
                    user_price = max(user_day, key=lambda h: h.recorded_at).price

                competitor_day = [h for h in competitor_history if h.recorded_at.date().isoformat() == date_str]
                if competitor_day:
                    competitor_price = max(competitor_day, key=lambda h: h.recorded_at).price

                # Для текущего дня актуальна текущая цена товара: история хранит
                # прежние значения (записываются перед изменением), поэтому
                # сегодняшняя точка должна брать живую цену из товара.
                if date_str == current_date:
                    user_price = user_product.price
                    competitor_price = competitor_product.price

                if user_price is not None or competitor_price is not None:
                    series_data['data_points'].append({
                        'date': date_str,
                        'user_price': user_price,
                        'competitor_price': competitor_price
                    })
            
            dynamics.append(series_data)
        
        return dynamics
