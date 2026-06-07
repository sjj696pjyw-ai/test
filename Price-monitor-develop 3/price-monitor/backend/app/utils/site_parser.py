import requests
from bs4 import BeautifulSoup
import time
import random
import re
from .helpers import get_default_headers


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

        # В ячейке цены может быть несколько чисел: старая (зачёркнутая) цена,
        # текущая цена и иногда мелкие числа вроде кэшбэка. Старая цена всегда
        # выше текущей, а порядок в разметке у разных сайтов разный, поэтому
        # нельзя просто брать первое число.
        price_matches = re.findall(r'[\d\s]+(?:[.,]\d+)?', price_str)
        nums = []
        for m in price_matches:
            cleaned = re.sub(r'[^\d.,]', '', m).replace(',', '.')
            try:
                val = float(cleaned)
            except ValueError:
                continue
            if 10 <= val <= 1_000_000_000:  # Защита от некорректных значений
                nums.append(val)

        if not nums:
            return None

        # Отбрасываем заведомо мелкие числа (кэшбэк и т.п.), затем берём
        # наименьшую из оставшихся — это текущая цена со скидкой.
        threshold = max(nums) * 0.3
        big = [n for n in nums if n >= threshold]
        return min(big) if big else min(nums)

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

            # Если сервер не указал кодировку в заголовке, requests по умолчанию
            # берёт ISO-8859-1, из-за чего UTF-8 страницы превращаются в «кракозябры».
            # Определяем реальную кодировку по содержимому страницы.
            header_charset = None
            content_type = response.headers.get('Content-Type', '')
            if 'charset=' in content_type.lower():
                header_charset = content_type.lower().split('charset=')[-1].split(';')[0].strip()

            if not header_charset or header_charset in ('iso-8859-1', 'latin-1'):
                response.encoding = response.apparent_encoding or 'utf-8'

            return response.text
        except Exception as e:
            print(f"Requests fetch error for {url}: {e}")
            return None

    def parse_products(self, html, name_selector, price_selector):
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
        
        max_len = max(len(name_elements), len(price_elements))
        print(f"[DEBUG] Will attempt to parse {max_len} products (names: {len(name_elements)}, prices: {len(price_elements)})")

        for i in range(max_len):
            name = name_elements[i].get_text(strip=True) if i < len(name_elements) else ''
            price_text = price_elements[i].get_text(strip=True) if i < len(price_elements) else ''
            price = self._clean_price(price_text)
            
            if name and price is not None:
                products.append({
                    'name': name,
                    'price': price,
                    'currency': 'RUB'
                })
            elif name and price is None:
                print(f"[DEBUG] Product '{name}' has invalid price: '{price_text}'")

        print(f"[DEBUG] Successfully parsed {len(products)} valid products")
        return products

    def verify_selectors(self, html, name_selector, price_selector):
        if not html:
            return {'valid': False, 'name_count': 0, 'price_count': 0, 'sample_names': [], 'sample_prices': []}

        soup = BeautifulSoup(html, 'lxml')

        name_elements = self._try_selectors(soup, [name_selector])
        price_elements = self._try_selectors(soup, [price_selector])

        def is_percentage(text):
            return '%' in text or 'скидк' in text.lower()

        sample_names = [el.get_text(strip=True) for el in name_elements[:5] if el.get_text(strip=True)]
        sample_prices = [el.get_text(strip=True) for el in price_elements[:5] if el.get_text(strip=True) and not is_percentage(el.get_text(strip=True))]

        valid = len(name_elements) > 0 and len(price_elements) > 0
        mismatch = abs(len(name_elements) - len(price_elements)) > max(len(name_elements), len(price_elements)) * 0.3 if valid else False

        return {
            'valid': valid,
            'name_count': len(name_elements),
            'price_count': len(price_elements),
            'mismatch_warning': mismatch,
            'mismatch_message': f'Найдено названий: {len(name_elements)}, цен: {len(price_elements)}. Проверьте селекторы.' if mismatch else None,
            'sample_names': sample_names,
            'sample_prices': sample_prices,
        }
