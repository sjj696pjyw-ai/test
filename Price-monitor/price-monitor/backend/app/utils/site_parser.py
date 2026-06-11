import os
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from collections import Counter
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from .helpers import get_default_headers, setup_selenium_options


# Если запуск браузера однажды провалился (нет chromium/драйвера в окружении),
# выключаем Selenium для всего процесса и работаем через requests — чтобы не
# пытаться поднимать браузер на каждый запрос там, где его нет (например локалка).
_SELENIUM_DISABLED = False


class SiteParser:
    def __init__(self, delay=1, use_selenium=None, scroll=True):
        self.delay = delay
        self.session = requests.Session()
        # Selenium включён по умолчанию; отключается через env PARSER_USE_SELENIUM=0
        if use_selenium is None:
            use_selenium = os.environ.get('PARSER_USE_SELENIUM', '1') != '0'
        self.use_selenium = use_selenium
        self.scroll = scroll
        # Переиспользуемый браузер: при обходе пагинации держим один драйвер и
        # ходим по страницам переходами, а не поднимаем браузер на каждую.
        self._driver = None
        self._reuse_driver = False

    def _get_headers(self):
        return get_default_headers()

    def _clean_price(self, price_str):
        if not price_str:
            return None

        # Убираем токены скидки, а не отбрасываем весь товар: в ячейке цены со
        # скидкой попадаются куски вроде "-10%" и слово "скидка". Если оставить
        # "10" из "-10%", оно засоряет список чисел, поэтому вырезаем целиком.
        price_str = re.sub(r'-?\s*\d+([.,]\d+)?\s*%', ' ', price_str)
        price_str = re.sub(r'скидк\w*', ' ', price_str, flags=re.IGNORECASE)

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
                # один браузер на серию запросов (обход пагинации)
                if self._driver is None:
                    self._driver = self._build_driver()
                driver = self._driver
            else:
                driver = self._build_driver()
                own_driver = True
            driver.get(url)
            time.sleep(1.0)  # даём отрисоваться
            if do_scroll:
                self._auto_scroll(driver, scroll_selector)  # подгружаем ленивый контент
            return driver.page_source
        except Exception as e:
            msg = str(e)
            print(f"Selenium fetch error for {url}: {msg}")
            # Переиспользуемый драйвер мог «умереть» — сбрасываем, чтобы пересоздать
            if self._reuse_driver:
                self.close()
            # Браузер/драйвер вообще не поднимается — выключаем Selenium на весь
            # процесс и дальше работаем через requests.
            if any(k in msg.lower() for k in (
                'executable', 'no such file', 'cannot find', 'not found',
                'chromedriver', 'session not created', 'unable to', 'winerror',
                'module named', 'modulenotfound'
            )):
                _SELENIUM_DISABLED = True
                print("[INFO] Selenium недоступен — переключаюсь на requests до перезапуска процесса.")
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

    def _auto_scroll(self, driver, scroll_selector=None, max_rounds=25, pause=0.7):
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
        clicked_at = set()  # состояния, на которых уже жали «показать ещё»
        for _ in range(max_rounds):
            count = 0
            if scroll_selector:
                # скроллим к последней найденной карточке и заодно считаем их
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
            height = driver.execute_script("return document.body.scrollHeight")
            marker = (count, height)  # прогресс: число карточек + высота
            if marker == last_marker:
                stable += 1
                if stable >= 2:
                    # прокрутка ничего не даёт — один раз пробуем кнопку догрузки.
                    # Если на этом состоянии уже жали — прогресса нет, выходим.
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
            # Если на странице есть числовая пагинация (ссылки на страницы) — НЕ
            # кликаем «показать ещё»: на таких сайтах это обычно переход на след.
            # URL, который заменяет товары. Их соберёт обход пагинации по URL.
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

    # ------------------------------------------------------------------
    # Обход пагинации по URL (для сайтов с серверной пагинацией: страницы —
    # это отдельные адреса ?PAGEN_1=N / ?page=N / ?p=N).
    # ------------------------------------------------------------------
    def _detect_page_param(self, html):
        """Определяет имя параметра пагинации по ссылкам на странице.
        Возвращает, например, 'PAGEN_1' / 'page' / 'p', либо None."""
        if not html:
            return None
        # Ищем в href'ах параметры вида ?PAGEN_1=2, ?page=2, ?p=2, ?PAGE=2
        found = re.findall(r'[?&]((?:PAGEN_\d+)|page|p|PAGE)=\d+', html)
        if not found:
            return None
        # Берём самый часто встречающийся параметр (обычно это и есть пагинация)
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
        # Базовая страница для определения способа: сначала пробуем requests
        # (быстро, без браузера), и только если товаров нет — браузер.
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

        # ---- ТИР 1: серверная пагинация по ссылкам ----
        # Объединяем ДВА источника: прокрутку базовой страницы (покрывает то,
        # что догружает бесконечный скролл) И обход всех номеров страниц из
        # пагинации (там лежат товары, до которых скролл не достаёт). Дедуп по
        # абсолютным дублям. Это и даёт полный каталог на сайтах вроде rus-buket,
        # где скролл показывает 3 страницы, а остаток — на последней через кнопки.
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

            # ВАЖНО: у SPA серверная (requests) версия и JS-версия расходятся —
            # сервер по ?page может отдавать меньше товаров и меньше страниц, чем
            # видно в браузере (у rus-buket сервер = 3 стр./74, JS = 4 стр./104).
            # Поэтому базу берём С ПРОКРУТКОЙ (JS) и номер последней страницы тоже
            # из JS-страницы — иначе теряем товары, доступные только в браузере.
            scrolled_base = self.get_page(url, scroll_selector=name_selector, scroll=True)
            base_full = scrolled_base or base_html
            add(self.parse_products(base_full, name_selector, price_selector))
            max_page = self._detect_max_page(base_full, param) or self._detect_max_page(base_html, param)

            # Обход страниц ПО ПОРЯДКУ (без предварительного массового фетча):
            # для каждой сначала requests (быстро), если новых товаров нет —
            # браузерная версия (JS-only страницы). Стоп, если страница пустая в
            # обеих версиях (конец каталога) или 3 страницы подряд не дают новых
            # (фейковая пагинация: одни и те же товары на всех страницах).
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
                        # requests не дал новых — пробуем браузерную версию страницы
                        bhtml = self.get_page(u, scroll_selector=name_selector, scroll=False)
                        bprods = self.parse_products(bhtml, name_selector, price_selector) if bhtml else []
                        if not prods and not bprods:
                            break  # страница пуста в обеих версиях — конец каталога
                        added = add(bprods) if bprods else 0
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
            print(f"[DEBUG] Пагинация: до стр. {page}, всего {len(products)}")

            # Пагинация на странице есть — отдаём её результат (даже если это одна
            # страница). Тиры showall/прокрутка тут не нужны и только тормозят.
            return products

        # ---- ТИР 2: «показать всё» / query-параметры ----
        for cand in self._showall_candidates(url, base_html):
            html = self.get_page(cand, scroll_selector=name_selector, scroll=False)
            if not html:
                continue
            prods = self.parse_products(html, name_selector, price_selector)
            if len(prods) > len(base_products):
                print(f"[DEBUG] Showall сработал: {cand} -> {len(prods)} товаров")
                set_stats(html)
                return self._dedup_absolute(prods)

        # ---- ТИР 3: прокрутка (последнее средство) ----
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

        # Реальное число товаров, которое будет собрано: проходим тем же путём,
        # что и сбор (parse_products) — пары «название + валидная цена». Иначе
        # «найдено N» (сырые совпадения) расходится с «добавлено M», потому что
        # товары без корректной цены отбрасываются при сохранении.
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
            # Главный показатель — сколько товаров реально соберётся
            'product_count': product_count,
            'skipped_count': skipped,
            # Сырые совпадения селекторов (для диагностики)
            'name_count': len(name_elements),
            'price_count': len(price_elements),
            'mismatch_warning': mismatch,
            'mismatch_message': mismatch_message,
            'sample_names': sample_names,
            'sample_prices': sample_prices,
        }
