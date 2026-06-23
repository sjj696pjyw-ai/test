import logging
import os
import random
import re
import time
from collections import Counter
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .helpers import get_default_headers, setup_selenium_options

logger = logging.getLogger(__name__)

_SELENIUM_DISABLED = False

class SiteParser:
    def __init__(self, delay=1, use_selenium=None, scroll=True):
        self.delay = delay
        self.session = requests.Session()
        if use_selenium is None:
            use_selenium = os.environ.get('PARSER_USE_SELENIUM', '1') != '0'
        self.use_selenium = use_selenium
        self.scroll = scroll
        self._driver = None
        self._reuse_driver = False

    def _get_headers(self):
        return get_default_headers()

    def _clean_price(self, price_str):
        if not price_str:
            return None

        price_str = re.sub(r'-?\s*\d+([.,]\d+)?\s*%', ' ', price_str)
        price_str = re.sub(r'скидк\w*', ' ', price_str, flags=re.IGNORECASE)

        price_matches = re.findall(r'[\d\s]+(?:[.,]\d+)?', price_str)
        nums = []
        for m in price_matches:
            cleaned = re.sub(r'[^\d.,]', '', m).replace(',', '.')
            try:
                val = float(cleaned)
            except ValueError:
                continue
            if 10 <= val <= 1_000_000_000:
                nums.append(val)

        if not nums:
            return None

        threshold = max(nums) * 0.3
        big = [n for n in nums if n >= threshold]
        return min(big) if big else min(nums)

    def _try_selectors(self, soup, selectors):
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                return elements
        return []

    def get_page(self, url, scroll_selector=None, scroll=None):
        """
        Загружает HTML страницы. По умолчанию — через headless-браузер (Selenium):
        он выполняет JS и прокручивает страницу, подгружая ленивый контент, иначе
        на JS-сайтах товары/цены не отрисовываются. Если браузер недоступен или
        упал — прозрачно откатываемся на обычный requests.

        scroll_selector — селектор карточки товара; если задан, прокрутка идёт
        к последней карточке (надёжнее триггерит ленивую подгрузку, чем скролл
        просто в низ страницы).
        scroll — переопределяет прокрутку для конкретного вызова (например, на
        страницах серверной пагинации прокрутка не нужна — это сильно быстрее).
        """
        do_scroll = self.scroll if scroll is None else scroll
        if self.use_selenium and not _SELENIUM_DISABLED:
            html = self._get_page_selenium(url, scroll_selector, do_scroll)
            if html:
                return html
        return self._get_page_requests(url)

    def _build_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        setup_selenium_options(options)

        chrome_bin = os.environ.get('CHROME_BIN')
        if chrome_bin:
            options.binary_location = chrome_bin

        driver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        service = Service(executable_path=driver_path) if os.path.exists(driver_path) else Service()

        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        return driver

    def _get_page_selenium(self, url, scroll_selector=None, do_scroll=True):
        global _SELENIUM_DISABLED
        driver = None
        own_driver = False
        try:
            time.sleep(random.uniform(self.delay * 0.3, self.delay * 0.7))
            if self._reuse_driver:
                if self._driver is None:
                    self._driver = self._build_driver()
                driver = self._driver
            else:
                driver = self._build_driver()
                own_driver = True
            driver.get(url)
            time.sleep(1.0)
            if do_scroll:
                self._auto_scroll(driver, scroll_selector)
            return driver.page_source
        except Exception as e:
            msg = str(e)
            logger.error(f"Selenium fetch error for {url}: {msg}")
            if self._reuse_driver:
                self.close()

            low = msg.lower()
            transient = any(k in low for k in (
                'timed out', 'timeout', 'renderer', 'target crashed',
                'tab crashed', 'disconnected', 'no such window', 'connection refused',
            ))
            fatal = (
                isinstance(e, (ImportError, ModuleNotFoundError))
                or 'no module named' in low
                or 'cannot find chrome' in low
                or 'chrome binary' in low
                or 'chrome failed to start' in low
                or 'cannot find chromedriver' in low
                or 'executable needs to be in path' in low
                or 'unable to obtain' in low
            )
            if fatal and not transient:
                _SELENIUM_DISABLED = True
                logger.warning("[INFO] Selenium недоступен — переключаюсь на requests до перезапуска процесса.")
            return None
        finally:
            if own_driver and driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def close(self):
        """Закрывает переиспользуемый браузер, если он был открыт."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def _auto_scroll(self, driver, scroll_selector=None, max_rounds=25, pause=0.7, max_seconds=12.0):
        """Прокручивает страницу для ленивой подгрузки товаров.

        Если задан scroll_selector — на каждом шаге скроллит к ПОСЛЕДНЕЙ карточке
        товара (надёжнее цепляет IntersectionObserver, чем скролл в низ страницы).
        Когда прокрутка перестаёт подгружать новое — один раз пробует кнопку
        догрузки («Показать ещё»). Чтобы не крутить пустые циклы, кнопку на одном
        и том же состоянии страницы жмём не больше раза: если прогресса нет — стоп.
        """
        if not self.scroll:
            return
        last_marker = None
        stable = 0
        clicked_at = set()
        deadline = time.monotonic() + max_seconds
        for _ in range(max_rounds):
            if time.monotonic() > deadline:
                break
            count = 0
            if scroll_selector:
                try:
                    count = driver.execute_script(
                        "const e = document.querySelectorAll(arguments[0]);"
                        "if (e.length) { e[e.length - 1].scrollIntoView({block: 'end'}); }"
                        "return e.length;",
                        scroll_selector
                    ) or 0
                except Exception:
                    count = 0
            if not scroll_selector or count == 0:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            if scroll_selector:
                marker = count
            else:
                try:
                    marker = driver.execute_script("return document.body.scrollHeight")
                except Exception:
                    marker = None
            if marker == last_marker:
                stable += 1
                if stable >= 2:
                    if marker in clicked_at:
                        break
                    clicked_at.add(marker)
                    if self._click_load_more(driver):
                        stable = 0
                        time.sleep(pause)
                        continue
                    break
            else:
                stable = 0
                last_marker = marker

    def _click_load_more(self, driver):
        """Ищет и кликает кнопку догрузки товаров («Показать ещё» и т.п.).

        Кликает только кнопки-догрузки (добавляют товары к текущему списку), а не
        числовую пагинацию 1-2-3 — переход по номерам заменил бы уже загруженные
        товары в DOM. Возвращает True, если по чему-то кликнули.
        """
        try:
            has_pager = driver.execute_script(r"""
                for (const a of document.querySelectorAll('a[href]')) {
                    if (/[?&](PAGEN_\d+|page|p|PAGE)=\d+/.test(a.getAttribute('href') || '')) return true;
                }
                return false;
            """)
            if has_pager:
                return False
            return bool(driver.execute_script(r"""
                const phrases = ['показать ещё','показать еще','показать больше',
                    'загрузить ещё','загрузить еще','смотреть ещё','смотреть еще',
                    'ещё товары','еще товары','показать все','показать всё',
                    'show more','load more'];
                const els = document.querySelectorAll('a,button,[role="button"],span,div');
                for (const el of els) {
                    const t = (el.textContent || '').trim().toLowerCase();
                    if (!t || t.length > 40) continue;            // отсекаем крупные контейнеры
                    if (phrases.some(p => t.includes(p))) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {        // только видимые
                            el.scrollIntoView({block: 'center'});
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            """))
        except Exception:
            return False

    def _get_page_requests(self, url):
        try:
            time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
            headers = self._get_headers()
            response = self.session.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()

            header_charset = None
            content_type = response.headers.get('Content-Type', '')
            if 'charset=' in content_type.lower():
                header_charset = content_type.lower().split('charset=')[-1].split(';')[0].strip()

            if not header_charset or header_charset in ('iso-8859-1', 'latin-1'):
                response.encoding = response.apparent_encoding or 'utf-8'

            return response.text
        except Exception as e:
            logger.error(f"Requests fetch error for {url}: {e}")
            return None

    def _fetch_html_requests(self, url):
        """Быстрый GET без задержки (для параллельной загрузки страниц)."""
        try:
            headers = self._get_headers()
            response = self.session.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')
            charset = None
            if 'charset=' in content_type.lower():
                charset = content_type.lower().split('charset=')[-1].split(';')[0].strip()
            if not charset or charset in ('iso-8859-1', 'latin-1'):
                response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except Exception:
            return None

    def parse_products(self, html, name_selector, price_selector):
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        products = []

        name_selectors = [s.strip() for s in name_selector.split(',')] if ',' in name_selector else [name_selector]
        price_selectors = [s.strip() for s in price_selector.split(',')] if ',' in price_selector else [price_selector]

        logger.debug(f"[DEBUG] Trying name selectors: {name_selectors}")
        logger.debug(f"[DEBUG] Trying price selectors: {price_selectors}")

        name_elements = []
        for sel in name_selectors:
            elements = soup.select(sel)
            if elements:
                name_elements = elements
                logger.debug(f"[DEBUG] Found {len(elements)} name elements with selector '{sel}'")
                break

        price_elements = []
        for sel in price_selectors:
            elements = soup.select(sel)
            if elements:
                price_elements = elements
                logger.debug(f"[DEBUG] Found {len(elements)} price elements with selector '{sel}'")
                break

        if not name_elements:
            logger.warning(f"[WARNING] No name elements found with any of: {name_selectors}")
            all_classes = set()
            for tag in soup.find_all(class_=True):
                classes = tag.get('class', [])
                if isinstance(classes, list):
                    all_classes.update(classes)
            logger.debug(f"[DEBUG] Available classes (first 20): {list(all_classes)[:20]}")

        if not price_elements:
            logger.warning(f"[WARNING] No price elements found with any of: {price_selectors}")

        max_len = max(len(name_elements), len(price_elements))
        logger.debug(f"[DEBUG] Will attempt to parse {max_len} products (names: {len(name_elements)}, prices: {len(price_elements)})")

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
                logger.debug(f"[DEBUG] Product '{name}' has invalid price: '{price_text}'")

        logger.debug(f"[DEBUG] Successfully parsed {len(products)} valid products")
        return products

    def _detect_page_param(self, html):
        """Определяет имя параметра пагинации по ссылкам на странице.
        Возвращает, например, 'PAGEN_1' / 'page' / 'p', либо None."""
        if not html:
            return None
        found = re.findall(r'[?&]((?:PAGEN_\d+)|page|p|PAGE)=\d+', html)
        if not found:
            return None
        return Counter(found).most_common(1)[0][0]

    def _detect_max_page(self, html, param):
        """Максимальный номер страницы из ссылок пагинации (?param=N).
        Игнорируем абсурдно большие числа — это, скорее всего, ID/год, а не
        номер страницы пагинации."""
        if not html:
            return None
        nums = [int(n) for n in re.findall(rf'[?&]{re.escape(param)}=(\d+)', html)]
        nums = [n for n in nums if 1 <= n <= 200]
        return max(nums) if nums else None

    def _with_page_param(self, url, param, value):
        """Возвращает URL с заданным значением параметра страницы."""
        parts = urlparse(url)
        query = parse_qs(parts.query)
        query[param] = [str(value)]
        return urlunparse(parts._replace(query=urlencode(query, doseq=True)))

    def _tally_matches(self, html, name_selector, price_selector, stats):
        """Добавляет в stats число сырых совпадений селекторов на странице
        (для суммарных счётчиков «совпадений названий/цен» по всем страницам)."""
        soup = BeautifulSoup(html, 'lxml')
        stats['name_count'] = stats.get('name_count', 0) + len(soup.select(name_selector))
        stats['price_count'] = stats.get('price_count', 0) + len(soup.select(price_selector))

    @staticmethod
    def _dedup_key(p):
        """Ключ абсолютного дубля: одинаковое название И цена = тот же товар."""
        try:
            price = round(float(p['price']), 2)
        except (TypeError, ValueError):
            price = p.get('price')
        return (p['name'].strip().lower(), price)

    def _dedup_absolute(self, products):
        """Убирает абсолютные дубли (одинаковые название и цена)."""
        seen = set()
        out = []
        for p in products:
            k = self._dedup_key(p)
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return out

    def _showall_candidates(self, url, html):
        """URL-кандидаты «показать всё одной страницей»: найденный в разметке
        Bitrix-параметр SHOWALL_x, затем типовые query-параметры выдачи."""
        cands = []
        m = re.search(r'(SHOWALL_\d+)=1', html or '')
        if m:
            cands.append(self._with_page_param(url, m.group(1), 1))
        for param, val in (('SHOWALL_1', 1), ('showall', 1), ('show_all', 1),
                           ('limit', 100000), ('per_page', 100000),
                           ('count', 100000), ('page_size', 100000), ('pageSize', 100000)):
            u = self._with_page_param(url, param, val)
            if u not in cands:
                cands.append(u)
        return cands

    def parse_products_paginated(self, url, name_selector, price_selector,
                                 first_html=None, max_pages=50, stats=None):
        """Собирает товары по тирам:

        1) если на странице есть ссылки пагинации — обходим страницы по URL (без
           прокрутки) и дедупим абсолютные дубли;
        2) иначе пробуем «показать всё» / query-параметры выдачи;
        3) иначе — прокрутка (бесконечная подгрузка) как последнее средство.

        Если тир не дал прироста к базовой странице — переходим к следующему.
        """
        if first_html is not None:
            base_html = first_html
        else:
            base_html = self._fetch_html_requests(url)
            if not base_html or not self.parse_products(base_html, name_selector, price_selector):
                base_html = self.get_page(url, scroll_selector=name_selector, scroll=False)
        if not base_html:
            return []
        base_products = self.parse_products(base_html, name_selector, price_selector)

        def set_stats(html):
            if stats is not None:
                stats.clear()
                self._tally_matches(html, name_selector, price_selector, stats)

        param = self._detect_page_param(base_html)
        if param:
            products, seen = [], set()

            def add(items):
                added = 0
                for p in items:
                    k = self._dedup_key(p)
                    if k in seen:
                        continue
                    seen.add(k)
                    products.append(p)
                    added += 1
                return added

            scrolled_base = self.get_page(url, scroll_selector=name_selector, scroll=True)
            base_full = scrolled_base or base_html
            scrolled_products = self.parse_products(base_full, name_selector, price_selector)
            add(scrolled_products)
            is_spa = len(scrolled_products) > len(base_products)
            max_page = self._detect_max_page(base_full, param) or self._detect_max_page(base_html, param)

            limit = min(max_page, max_pages) if max_page else max_pages
            self._reuse_driver = True
            try:
                page, zero_streak = 2, 0
                while page <= limit:
                    u = self._with_page_param(url, param, page)
                    html = self._fetch_html_requests(u)
                    prods = self.parse_products(html, name_selector, price_selector) if html else []
                    added = add(prods) if prods else 0
                    if added == 0:
                        if is_spa:
                            bhtml = self.get_page(u, scroll_selector=name_selector, scroll=False)
                            bprods = self.parse_products(bhtml, name_selector, price_selector) if bhtml else []
                            if not prods and not bprods:
                                break
                            added = add(bprods) if bprods else 0
                        elif not prods:
                            break
                    if added:
                        zero_streak = 0
                    else:
                        zero_streak += 1
                        if zero_streak >= 3:
                            break
                    page += 1
            finally:
                self._reuse_driver = False
                self.close()
            logger.debug(f"[DEBUG] Пагинация: до стр. {page}, всего {len(products)}")

            return products

        for cand in self._showall_candidates(url, base_html):
            html = self.get_page(cand, scroll_selector=name_selector, scroll=False)
            if not html:
                continue
            prods = self.parse_products(html, name_selector, price_selector)
            if len(prods) > len(base_products):
                logger.debug(f"[DEBUG] Showall сработал: {cand} -> {len(prods)} товаров")
                set_stats(html)
                return self._dedup_absolute(prods)

        scrolled = self.get_page(url, scroll_selector=name_selector, scroll=True)
        final_html = scrolled or base_html
        prods = self.parse_products(final_html, name_selector, price_selector)
        if len(prods) <= len(base_products):
            set_stats(base_html)
            return self._dedup_absolute(base_products)
        set_stats(final_html)
        return self._dedup_absolute(prods)

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

        collectible = self.parse_products(html, name_selector, price_selector)
        product_count = len(collectible)
        raw_max = max(len(name_elements), len(price_elements))
        skipped = raw_max - product_count

        valid = product_count > 0
        mismatch = skipped > 0

        if mismatch:
            mismatch_message = (
                f'Найдено совпадений: названий {len(name_elements)}, цен {len(price_elements)}. '
                f'Будет собрано товаров: {product_count}'
                + (f' (пропущено {skipped} — без корректной цены или без пары название/цена).'
                   if skipped > 0 else '.')
            )
        else:
            mismatch_message = None

        return {
            'valid': valid,
            'product_count': product_count,
            'skipped_count': skipped,
            'name_count': len(name_elements),
            'price_count': len(price_elements),
            'mismatch_warning': mismatch,
            'mismatch_message': mismatch_message,
            'sample_names': sample_names,
            'sample_prices': sample_prices,
        }
