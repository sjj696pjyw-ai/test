import requests
from bs4 import BeautifulSoup
import time
import random
import re
from .helpers import REAL_UA, get_default_headers, setup_selenium_options

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class SiteParser:
    def __init__(self, delay=1):
        self.delay = delay
        self.session = requests.Session()
        self.driver = None

    def _get_headers(self):
        return get_default_headers()

    def _clean_price(self, price_str):
        if not price_str:
            return None
        if '%' in price_str or 'скидк' in price_str.lower():
            return None
        price_str = re.sub(r'[^\d.,]', '', price_str)
        price_str = price_str.replace(',', '.')
        try:
            val = float(price_str)
            if val < 10:
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
        if SELENIUM_AVAILABLE:
            html = self._get_page_selenium(url)
            if html and len(html) > 1000:
                return html
        html = self._get_page_requests(url)
        if html:
            return html
        return None

    def _get_page_requests(self, url):
        try:
            time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
            response = self.session.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Requests fetch error for {url}: {e}")
            return None

    def _get_page_selenium(self, url):
        try:
            if not self.driver:
                options = ChromeOptions()
                setup_selenium_options(options)
                self.driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=options
                )
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
                })
            self.driver.get(url)
            time.sleep(random.uniform(4, 6))

            try:
                self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight / 2)')
                time.sleep(1)
                self.driver.execute_script('window.scrollTo(0, 0)')
                time.sleep(0.5)
            except Exception:
                pass

            popup_selectors = [
                'button:contains("Закрыть")', 'button:contains("Close")',
                'button:contains("Принять")', 'button:contains("Accept")',
                'button:contains("Согласен")', 'button:contains("Продолжить")',
                'button:contains("Нет, спасибо")', 'button:contains("Не сейчас")',
                'button:contains("Отмена")', '[class*="close"]',
                '[class*="popup"] button', '[class*="modal"] button',
                '[class*="cookie"] button', '[aria-label*="close"]',
                '[aria-label*="Close"]', '[class*="notification"] button',
            ]
            for _ in range(2):
                for sel in popup_selectors:
                    try:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in els:
                            if el.is_displayed():
                                el.click()
                                time.sleep(0.5)
                    except Exception:
                        pass

            for _ in range(3):
                try:
                    btn_selectors = [
                        'button:contains("Показать ещё")', 'button:contains("Смотреть все")',
                        'button:contains("Смотреть всё")', 'button:contains("Показать все")',
                        '[class*="show-more"]', '[class*="load-more"]',
                        '[class*="pagination"] button', 'button:contains("Загрузить ещё")',
                        'a:contains("Далее")', 'a:contains("Вперед")', '[class*="next"]',
                    ]
                    found = False
                    for sel in btn_selectors:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                btn.click()
                                time.sleep(random.uniform(1, 2))
                                found = True
                                break
                        if found:
                            break
                    if not found:
                        break
                except Exception:
                    break

            return self.driver.page_source
        except Exception as e:
            print(f"Selenium fetch error for {url}: {e}")
            return None

    def parse_products(self, html, name_selector, price_selector, sku_selector=None):
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        products = []

        name_selectors = name_selector.split(',') if ',' in name_selector else [name_selector]
        price_selectors = price_selector.split(',') if ',' in price_selector else [price_selector]

        name_elements = self._try_selectors(soup, name_selectors)
        price_elements = self._try_selectors(soup, price_selectors)
        sku_elements = self._try_selectors(soup, [sku_selector]) if sku_selector else []

        max_len = max(len(name_elements), len(price_elements))

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

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
