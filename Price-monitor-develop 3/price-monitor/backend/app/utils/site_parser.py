import requests
from bs4 import BeautifulSoup
import time
import random
import re
from .helpers import REAL_UA, get_default_headers


class SiteParser:
    def __init__(self, delay=1):
        self.delay = delay
        self.session = requests.Session()

    def _get_headers(self):
        return get_default_headers()

    def _clean_price(self, price_str):
        if not price_str:
            return None
        if '%' in price_str or 'скидк' in price_str.lower():
            return None
        
        # Если в строке несколько цен (например, "36 990 ₽43 990 ₽"), берём первую
        # Находим все числовые значения в строке
        price_matches = re.findall(r'[\d\s]+(?:[.,]\d+)?', price_str)
        if len(price_matches) > 1:
            # Берём первое найденное число (обычно это акционная/текущая цена)
            price_str = price_matches[0].strip()
        
        price_str = re.sub(r'[^\d.,]', '', price_str)
        price_str = price_str.replace(',', '.')
        try:
            val = float(price_str)
            if val < 10 or val > 1_000_000_000:  # Защита от некорректных значений
                return None
            return val
        except:
            return None

    def _try_selectors(self, soup, selectors):
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                return elements
        return []

    def get_page(self, url):
        """Get page HTML using only HTTP requests (no Selenium)"""
        return self._get_page_requests(url)

    def _get_page_requests(self, url):
        try:
            time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
            headers = self._get_headers()
            response = self.session.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Requests fetch error for {url}: {e}")
            return None

    def parse_products(self, html, name_selector, price_selector, sku_selector=None):
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        products = []

        # Split selectors by comma if multiple provided
        name_selectors = [s.strip() for s in name_selector.split(',')] if ',' in name_selector else [name_selector]
        price_selectors = [s.strip() for s in price_selector.split(',')] if ',' in price_selector else [price_selector]

        print(f"[DEBUG] Trying name selectors: {name_selectors}")
        print(f"[DEBUG] Trying price selectors: {price_selectors}")

        # Try each name selector until we find elements
        name_elements = []
        for sel in name_selectors:
            elements = soup.select(sel)
            if elements:
                name_elements = elements
                print(f"[DEBUG] Found {len(elements)} name elements with selector '{sel}'")
                break
        
        # Try each price selector until we find elements
        price_elements = []
        for sel in price_selectors:
            elements = soup.select(sel)
            if elements:
                price_elements = elements
                print(f"[DEBUG] Found {len(elements)} price elements with selector '{sel}'")
                break
        
        if not name_elements:
            print(f"[WARNING] No name elements found with any of: {name_selectors}")
            # Debug: show what classes are available
            all_classes = set()
            for tag in soup.find_all(class_=True):
                classes = tag.get('class', [])
                if isinstance(classes, list):
                    all_classes.update(classes)
            print(f"[DEBUG] Available classes (first 20): {list(all_classes)[:20]}")
        
        if not price_elements:
            print(f"[WARNING] No price elements found with any of: {price_selectors}")
        
        sku_elements = self._try_selectors(soup, [sku_selector]) if sku_selector else []

        max_len = max(len(name_elements), len(price_elements))
        print(f"[DEBUG] Will attempt to parse {max_len} products (names: {len(name_elements)}, prices: {len(price_elements)})")

        for i in range(max_len):
            name = name_elements[i].get_text(strip=True) if i < len(name_elements) else ''
            price_text = price_elements[i].get_text(strip=True) if i < len(price_elements) else ''
            price = self._clean_price(price_text)
            sku = sku_elements[i].get_text(strip=True) if i < len(sku_elements) else None

            if name and price is not None:
                products.append({
                    'name': name,
                    'price': price,
                    'currency': 'RUB',
                    'external_id': sku
                })
            elif name and price is None:
                print(f"[DEBUG] Product '{name}' has invalid price: '{price_text}'\")

        print(f"[DEBUG] Successfully parsed {len(products)} valid products")
        return products

    def verify_selectors(self, html, name_selector, price_selector, sku_selector=None):
        if not html:
            return {'valid': False, 'name_count': 0, 'price_count': 0, 'sample_names': [], 'sample_prices': []}

        soup = BeautifulSoup(html, 'lxml')

        name_elements = self._try_selectors(soup, [name_selector])
        price_elements = self._try_selectors(soup, [price_selector])
        sku_elements = self._try_selectors(soup, [sku_selector]) if sku_selector else []

        def is_percentage(text):
            return '%' in text or 'скидк' in text.lower()

        sample_names = [el.get_text(strip=True) for el in name_elements[:5] if el.get_text(strip=True)]
        sample_prices = [el.get_text(strip=True) for el in price_elements[:5] if el.get_text(strip=True) and not is_percentage(el.get_text(strip=True))]
        sample_skus = [el.get_text(strip=True) for el in sku_elements[:5] if el.get_text(strip=True)]

        valid = len(name_elements) > 0 and len(price_elements) > 0
        mismatch = abs(len(name_elements) - len(price_elements)) > max(len(name_elements), len(price_elements)) * 0.3 if valid else False

        return {
            'valid': valid,
            'name_count': len(name_elements),
            'price_count': len(price_elements),
            'sku_count': len(sku_elements),
            'mismatch_warning': mismatch,
            'mismatch_message': f'Найдено названий: {len(name_elements)}, цен: {len(price_elements)}. Проверьте селекторы.' if mismatch else None,
            'sample_names': sample_names,
            'sample_prices': sample_prices,
            'sample_skus': sample_skus
        }

    def test_selector(self, url, selector, selector_type='name'):
        html = self.get_page(url)
        if not html:
            return {'success': False, 'elements': [], 'count': 0}

        soup = BeautifulSoup(html, 'lxml')
        elements = soup.select(selector)

        sample_texts = [el.get_text(strip=True) for el in elements[:5] if el.get_text(strip=True)]

        return {
            'success': len(elements) > 0,
            'count': len(elements),
            'sample_texts': sample_texts
        }
