import logging
import os
import random
import re
import time
from collections import Counter
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .api_sniffer import paginate_api
from .auto_extract import (
    auto_extract,
    count_price_nodes,
    looks_like_yml,
    parse_shopify_products,
    parse_yml,
    run_extractor,
    tier_counts,
)
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
        self._base_url = None  # для абсолютизации ссылок на карточки товаров
        self._last_fetch_error = None  # причина последней неудачи requests-фетча
        # Сайт отдаёт 403/429 на обычные запросы: страницы забираем браузером.
        self._requests_blocked = False
        self._tried_browser_session = False  # пробовали ли забрать cookies браузера
        self._browser_ua = None              # User-Agent браузера (к его cookies)
        self._used_browser_fetch = False     # логируем быстрый путь один раз
        # Трасса сбора: какие тиры отработали и с каким результатом. Нужна,
        # чтобы по итогам прогона было видно, ПОЧЕМУ собрано столько товаров,
        # а не только сколько (см. bench_service).
        self.trace = []

    def _trace(self, step, **fields):
        """Добавляет шаг в трассу сбора и дублирует его в лог."""
        entry = {'step': step}
        entry.update(fields)
        self.trace.append(entry)
        details = ' '.join(f'{k}={v}' for k, v in fields.items())
        logger.info(f'[ТРАССА] {step}: {details}')
        return entry

    def _get_headers(self):
        headers = dict(get_default_headers())
        # Если забрали cookies у браузера — ходим с его же User-Agent: анти-бот
        # часто привязывает выданную cookie именно к нему.
        if self._browser_ua:
            headers['User-Agent'] = self._browser_ua
        return headers

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

        # Ждём готовности DOM, а не полной загрузки картинок/шрифтов: товары
        # уже в разметке, а ожидание «всего» добавляло секунды на каждую страницу.
        options.page_load_strategy = 'eager'
        # Картинки нам не нужны — это заметно ускоряет тяжёлые каталоги.
        try:
            options.add_experimental_option(
                'prefs', {'profile.managed_default_content_settings.images': 2}
            )
        except Exception:
            pass

        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(20)
        return driver

    def _browser_fetch(self, url):
        """Запрашивает URL прямо из открытой вкладки браузера (fetch внутри страницы).

        Зачем: когда сайт режет обычные запросы, полная навигация браузером
        стоит ~9 секунд на страницу — каталог из 64 страниц не собрать никогда.
        Здесь запрос уходит из контекста самой страницы: те же cookies, тот же
        отпечаток (значит 403 не будет), но без рендеринга — около секунды.
        """
        driver = self._driver
        if driver is None:
            return None
        try:
            html = driver.execute_async_script(
                """
                const cb = arguments[arguments.length - 1];
                fetch(arguments[0], {credentials: 'include',
                                     headers: {'Accept': 'text/html'}})
                  .then(r => r.ok ? r.text() : null)
                  .then(t => cb(t))
                  .catch(() => cb(null));
                """,
                url,
            )
            return html or None
        except Exception as e:
            logger.debug(f'[DEBUG] fetch внутри браузера не удался: {e}')
            return None

    def _adopt_browser_session(self, driver):
        """Переносит cookies и User-Agent браузера в requests-сессию.

        Смысл: анти-бот выдаёт cookie после прохождения проверки в браузере.
        Скопировав её, дальше можно ходить обычными быстрыми запросами вместо
        того, чтобы поднимать браузер на каждую страницу каталога.
        """
        try:
            cookies = driver.get_cookies() or []
            for c in cookies:
                if not c.get('name'):
                    continue
                self.session.cookies.set(
                    c['name'], c.get('value', ''),
                    domain=c.get('domain') or None,
                    path=c.get('path') or '/',
                )
            ua = driver.execute_script('return navigator.userAgent;')
            if ua:
                self._browser_ua = ua
            if cookies:
                logger.debug(f'[DEBUG] перенесено cookies из браузера: {len(cookies)}')
            return len(cookies)
        except Exception as e:
            logger.debug(f'[DEBUG] не удалось перенести сессию браузера: {e}')
            return 0

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
            # Забираем cookies и User-Agent браузера в requests-сессию: защита от
            # ботов обычно ставит cookie после проверки, и с ней обычные запросы
            # начинают проходить. Без этого пришлось бы каждую страницу каталога
            # грузить браузером (~11с против ~1с) — на большом каталоге это часы.
            self._adopt_browser_session(driver)
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

    def _sniff_catalog_api(self, url):
        """Открывает каталог в браузере с перехватчиком сети, жмёт «Показать ещё»
        и возвращает запрос, которым сайт догружает товары.

        Нужно для SPA-каталогов без постраничных URL: поймав этот запрос, дальше
        весь каталог можно забрать напрямую, без браузера.
        Возвращает (call, products_from_first_call) или (None, []).
        """
        from . import api_sniffer

        driver = None
        own_driver = False
        try:
            if self._reuse_driver:
                if self._driver is None:
                    self._driver = self._build_driver()
                driver = self._driver
            else:
                driver = self._build_driver()
                own_driver = True

            if not api_sniffer.install_hook(driver):
                logger.warning("[ДИАГНОСТИКА API] перехватчик не установился (CDP недоступен)")
                return None, []

            driver.get(url)
            time.sleep(2.0)

            # ВАЖНО: чистим буфер после загрузки страницы. Иначе он забивается
            # запросами начальной загрузки, и запрос за следующей порцией
            # товаров (то, что нам нужно) в него уже не попадает.
            try:
                driver.execute_script("window.__pmNet = [];")
            except Exception:
                pass

            # клик по «Показать ещё» + скролл — чтобы сайт сходил за 2-й порцией
            clicked = self._click_load_more(driver)
            if not clicked:
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                except Exception:
                    pass
            time.sleep(3.0)
            # вторая попытка: часть сайтов реагирует только на повторный клик
            if not clicked:
                clicked = self._click_load_more(driver)
                if clicked:
                    time.sleep(2.5)

            # Оцениваем ВСЕ перехваченные вызовы по числу извлечённых товаров.
            # Фильтровать по виду URL нельзя: у нужного запроса адрес может
            # выглядеть как угодно, и мы его потеряем (так и было — из 53
            # вызовов фильтр оставлял 2 бесполезных).
            all_calls = api_sniffer.collect_calls(driver)
            calls = all_calls
            logger.info(
                f"[API] после клика перехвачено вызовов: {len(all_calls)}, "
                f"клик по «показать ещё»: {'да' if clicked else 'нет'}"
            )
            if not all_calls:
                logger.warning(
                    "[ДИАГНОСТИКА API] после клика сайт не сделал ни одного fetch/XHR — "
                    "товары догружаются другим способом (проверьте, сработал ли клик)"
                )
            return api_sniffer.find_product_api(calls)
        except Exception as e:
            logger.debug(f"[API] перехват не удался: {e}")
            return None, []
        finally:
            if own_driver and driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _fetch_api_text(self, url, method, headers, body):
        """Повтор перехваченного запроса напрямую (без браузера)."""
        try:
            hdrs = dict(self._get_headers())
            hdrs.update(headers or {})
            if method == 'POST':
                resp = self.session.post(url, headers=hdrs, data=body, timeout=20)
            else:
                resp = self.session.get(url, headers=hdrs, timeout=20)
            if resp.status_code != 200:
                return None
            return resp.text
        except Exception as e:
            logger.debug(f"[API] запрос не удался: {e}")
            return None

    def _auto_scroll(self, driver, scroll_selector=None, max_rounds=60, pause=0.4,
                     max_seconds=45.0, settle_timeout=3.0):
        """Прокручивает страницу для ленивой подгрузки товаров.

        Ожидание подгрузки адаптивное: после каждого скролла мы коротко опрашиваем
        число карточек и ждём прироста до settle_timeout секунд, прежде чем счесть,
        что подгрузка остановилась. Это важно для сайтов, где очередная порция
        прилетает XHR-ом медленнее фиксированной паузы — иначе скролл преждевременно
        решает, что товары кончились, и обрывается на первой порции.

        Если задан scroll_selector — скроллим к ПОСЛЕДНЕЙ карточке (надёжнее цепляет
        IntersectionObserver, чем скролл в низ страницы). Когда прироста нет даже за
        settle_timeout — один раз пробуем кнопку догрузки («Показать ещё»); если и
        она не помогает после пары застоев — выходим. Быстрые/короткие каталоги
        завершаются рано, полный бюджет тратится только на реально длинной подгрузке.
        """
        if not self.scroll:
            return

        def current_count():
            try:
                if scroll_selector:
                    return driver.execute_script(
                        "return document.querySelectorAll(arguments[0]).length;",
                        scroll_selector) or 0
                return driver.execute_script("return document.body.scrollHeight") or 0
            except Exception:
                return 0

        def scroll_step():
            moved = False
            if scroll_selector:
                try:
                    moved = bool(driver.execute_script(
                        "const e = document.querySelectorAll(arguments[0]);"
                        "if (e.length) { e[e.length - 1].scrollIntoView({block: 'end'}); return true; }"
                        "return false;",
                        scroll_selector))
                except Exception:
                    moved = False
            if not moved:
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                except Exception:
                    pass

        deadline = time.monotonic() + max_seconds
        poll = 0.3
        stalls = 0
        clicked = False
        last = current_count()

        for _ in range(max_rounds):
            if time.monotonic() > deadline:
                break
            scroll_step()

            # ждём прироста карточек короткими опросами (до settle_timeout)
            grew = False
            wait_until = min(time.monotonic() + settle_timeout, deadline)
            while time.monotonic() < wait_until:
                time.sleep(poll)
                cur = current_count()
                if cur > last:
                    last = cur
                    grew = True
                    break

            if grew:
                stalls = 0
                clicked = False
                continue

            # прироста нет — пробуем кнопку догрузки один раз, иначе считаем застой
            stalls += 1
            if not clicked and self._click_load_more(driver):
                clicked = True
                stalls = 0
                time.sleep(pause)
                continue
            if stalls >= 2:
                break

        logger.debug(f"[DEBUG] Автоскролл: итоговый маркер {last}")

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

    def _fetch_html_requests(self, url, attempts=2):
        """Быстрый GET с ретраем. Возвращает HTML или None; причину последней
        неудачи кладём в self._last_fetch_error (для диагностики)."""
        last = None
        for i in range(attempts):
            try:
                headers = self._get_headers()
                response = self.session.get(url, headers=headers, timeout=20, allow_redirects=True)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                charset = None
                if 'charset=' in content_type.lower():
                    charset = content_type.lower().split('charset=')[-1].split(';')[0].strip()
                if not charset or charset in ('iso-8859-1', 'latin-1'):
                    response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else None
                last = f"HTTP {code}"
                if code and code < 500 and code != 429:
                    break  # 4xx (кроме 429) — повтор не поможет
            except Exception as e:
                last = type(e).__name__  # Timeout / ConnectionError / SSLError ...
            if i + 1 < attempts:
                time.sleep(0.8)
        self._last_fetch_error = last
        logger.debug(f"[DEBUG] requests не получил {url}: {last}")
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
                item = {'name': name, 'price': price, 'currency': 'RUB'}
                url = self._extract_href(name_elements[i]) if i < len(name_elements) else None
                if url:
                    item['url'] = url
                products.append(item)
            elif name and price is None:
                logger.debug(f"[DEBUG] Product '{name}' has invalid price: '{price_text}'")

        logger.debug(f"[DEBUG] Successfully parsed {len(products)} valid products")
        return products

    def _extract_href(self, el):
        """Ссылка на карточку товара по элементу названия: сам <a>, ближайший
        родитель-<a> или вложенный <a>. Возвращает абсолютный URL или None."""
        a = None
        if el.name == 'a' and el.get('href'):
            a = el
        else:
            a = el.find_parent('a', href=True) or el.find('a', href=True)
        if not a or not a.get('href'):
            return None
        href = a['href'].strip()
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            return None
        if self._base_url:
            try:
                return urljoin(self._base_url, href)
            except ValueError:
                return href
        return href

    def _absolutize(self, products, base_url):
        """Делает относительные ссылки товаров абсолютными относительно base_url."""
        if not base_url:
            return products
        for p in products:
            u = p.get('url')
            if u and not u.startswith(('http://', 'https://')):
                try:
                    p['url'] = urljoin(base_url, u)
                except ValueError:
                    pass
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

    @staticmethod
    def _with_trailing_slash(url):
        """Добавляет завершающий слэш к пути, если его нет (и путь не файл).

        Нужно для каталогов, которые без слэша отдают 404 (типично для Bitrix).
        Не трогаем URL с query/фрагментом или с расширением в последнем сегменте
        (например .../item.html), чтобы не сломать корректные адреса.
        """
        parts = urlparse(url)
        if parts.query or parts.fragment:
            return url
        path = parts.path or '/'
        if path.endswith('/'):
            return url
        last = path.rsplit('/', 1)[-1]
        if '.' in last:  # похоже на файл (.html/.php/...) — не трогаем
            return url
        return urlunparse(parts._replace(path=path + '/'))

    def _tally_matches(self, html, name_selector, price_selector, stats):
        """Добавляет в stats число сырых совпадений селекторов на странице
        (для суммарных счётчиков «совпадений названий/цен» по всем страницам)."""
        soup = BeautifulSoup(html, 'lxml')
        stats['name_count'] = stats.get('name_count', 0) + len(soup.select(name_selector))
        stats['price_count'] = stats.get('price_count', 0) + len(soup.select(price_selector))

    @staticmethod
    def _product_key(p):
        """Ключ товара для дедупликации.

        Сначала пробуем устойчивые идентификаторы — артикул и ссылку на карточку:
        по ним товар определяется однозначно. Имя+цена берём только как запасной
        вариант, потому что в больших каталогах разные товары запросто совпадают
        по названию и цене (разные комплектации, цвета) и склеиваются в один.
        """
        ident = (p.get('external_id') or '').strip()
        if not ident:
            url = (p.get('url') or '').strip().lower()
            ident = url.split('#')[0].rstrip('/') if url else ''
        try:
            price = round(float(p['price']), 2)
        except (TypeError, ValueError):
            price = p.get('price')
        # Идентификатор + имя + цена. Идентификатор разводит разные товары с
        # одинаковыми именем и ценой; имя и цена сохраняют вариации одного
        # товара (разный вес/объём живут по одной ссылке).
        return (ident, p['name'].strip().lower(), price)

    @staticmethod
    def _dedup_key(p):
        """Совместимость: ключ абсолютного дубля."""
        return SiteParser._product_key(p)

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

        0) если на странице есть явная ссылка «показать всё» (Bitrix SHOWALL_x=1) —
           забираем все товары одним обычным GET (надёжнее всего, без браузера);
        1) иначе, если есть ссылки пагинации — обходим страницы по URL (без
           прокрутки) и дедупим абсолютные дубли;
        2) иначе пробуем «показать всё» / query-параметры выдачи;
        3) иначе — прокрутка (бесконечная подгрузка) как последнее средство.

        Если тир не дал прироста к базовой странице — переходим к следующему.
        """
        self._base_url = url  # ссылки на карточки делаем абсолютными от этого URL
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

        # Если переданный first_html не дал товаров (браузер мог вернуть страницу
        # ошибки/таймаут, как бывает на «тяжёлых» сайтах), берём базу через надёжный
        # requests — в нём обычно есть серверный рендер каталога со ссылками
        # пагинации и «показать всё».
        if not base_products:
            req_html = self._fetch_html_requests(url)
            req_products = self.parse_products(req_html, name_selector, price_selector) if req_html else []
            if len(req_products) > len(base_products):
                base_html, base_products = req_html, req_products

        # Явная ссылка «показать всё» (Bitrix SHOWALL_x=1) — самый надёжный путь:
        # один обычный GET отдаёт все товары серверным рендером, без headless-браузера
        # и без обхода страниц по URL. Пробуем её раньше нумерованной пагинации.
        showall = re.search(r'(SHOWALL_\d+)=1', base_html or '')
        if showall:
            showall_url = self._with_page_param(url, showall.group(1), 1)
            html = self._fetch_html_requests(showall_url)
            prods = self.parse_products(html, name_selector, price_selector) if html else []
            if len(prods) > len(base_products):
                logger.debug(f"[DEBUG] SHOWALL: {showall_url} -> {len(prods)} товаров")
                set_stats(html)
                return self._dedup_absolute(prods)

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

    def _fetch_full_html(self, url):
        """HTML каталога со всеми товарами для авто-извлечения.

        Берём обычным requests (надёжно и быстро, структурные данные лежат в
        серверном HTML), при пустом ответе — рендер браузером. Если на странице
        есть ссылка «показать всё» (Bitrix SHOWALL_x=1) — забираем страницу со
        всеми товарами, чтобы структурные данные охватили весь каталог.
        """
        source = 'requests'
        html = self._fetch_html_requests(url)
        if not html:
            # Многие каталоги (особенно на Bitrix) без завершающего слэша отдают
            # 404 — пробуем тот же адрес со слэшем, прежде чем идти в браузер.
            slashed = self._with_trailing_slash(url)
            if slashed != url:
                html = self._fetch_html_requests(slashed)
                if html:
                    url = slashed
                    source = 'requests-slash'
        if not html:
            html = self.get_page(url, scroll=False)
            source = 'selenium'
        if not html:
            return None, url, None
        m = re.search(r'(SHOWALL_\d+)=1', html)
        if m:
            all_html = self._fetch_html_requests(self._with_page_param(url, m.group(1), 1))
            if all_html:
                return all_html, url, source + '+showall'
        return html, url, source

    def _find_feed_candidates(self, base_url, html):
        """URL-кандидаты YML/price-фида: явные ссылки в HTML и robots.txt + пара
        типовых путей. Возвращает упорядоченный список без дублей (макс. 6)."""
        parts = urlparse(base_url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cands = []

        def add(u):
            if not u:
                return
            u = urljoin(base_url, u.strip())
            if u not in cands and urlparse(u).netloc == parts.netloc:
                cands.append(u)

        feedish = re.compile(r"(yml|yandex|market|price|export|feed)", re.IGNORECASE)
        # 1) явные ссылки в разметке (.yml/.xml, упоминающие фид)
        if html:
            for m in re.finditer(r'href=["\']([^"\']+\.(?:yml|xml)(?:\?[^"\']*)?)["\']', html, re.IGNORECASE):
                href = m.group(1)
                if href.lower().endswith('.yml') or feedish.search(href):
                    add(href)
        # 2) robots.txt — строки Sitemap и любые .yml
        robots = self._fetch_html_requests(f"{origin}/robots.txt")
        if robots:
            for m in re.finditer(r'(?:Sitemap:\s*|\b)(https?://\S+\.(?:yml|xml))', robots, re.IGNORECASE):
                u = m.group(1)
                if u.lower().endswith('.yml') or feedish.search(u):
                    add(u)
        # 3) типовые пути (коротко, чтобы не плодить 404)
        for p in ('/yml', '/yandex.xml', '/export/yml'):
            add(origin + p)
        return cands[:6]

    def _try_price_feed(self, url, html, cached_feed=None):
        """Тир 0: YML/price-фид с учётом кэша.

        cached_feed: None — не знаем (ищем), '' — фида нет (пропускаем), иначе URL
        фида (используем напрямую). Возвращает (products, feed_cache), где
        feed_cache — значение для записи в кэш (URL или ''), либо None если кэш
        менять не нужно.
        """
        # известно, что фида нет — не тратим запросы
        if cached_feed == '':
            return [], None
        # пробуем закэшированный URL
        if cached_feed:
            text = self._fetch_html_requests(cached_feed)
            if text and looks_like_yml(text):
                products = parse_yml(text)
                if products:
                    logger.debug(f"[DEBUG] YML-фид (кэш): {cached_feed} -> {len(products)} товаров")
                    return products, None  # кэш актуален, не меняем
            # фид пропал/переехал — переоткрываем ниже
        # поиск фида
        for cand in self._find_feed_candidates(url, html):
            text = self._fetch_html_requests(cand)
            if not text or not looks_like_yml(text):
                continue
            products = parse_yml(text)
            if products:
                logger.debug(f"[DEBUG] YML-фид: {cand} -> {len(products)} товаров")
                return products, cand  # запомнить найденный URL
        return [], ''  # проверили — фида нет

    def _try_shopify(self, url, html):
        """Тир: Shopify /products.json. Пробуем только если страница похожа на
        Shopify (иначе не плодим запросы). Возвращает товары или []."""
        h = (html or "").lower()
        if not any(s in h for s in ("cdn.shopify.com", "/cdn/shop/", "myshopify.com", "shopify.")):
            return []
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        bases = []
        m = re.search(r"/collections/([^/?#]+)", parts.path)
        if m:
            bases.append(f"{origin}/collections/{m.group(1)}/products.json")
        bases.append(f"{origin}/products.json")

        for base in bases:
            products = []
            for page in range(1, 11):  # до 2500 товаров
                text = self._fetch_html_requests(f"{base}?limit=250&page={page}")
                if not text:
                    break
                page_products = parse_shopify_products(text)
                if not page_products:
                    break
                products.extend(page_products)
                if len(page_products) < 250:
                    break
            if products:
                logger.debug(f"[DEBUG] Shopify products.json: {base} -> {len(products)} товаров")
                return products
        return []

    # ---- многостраничный сбор для авто-извлечения ----

    _PAGE_RE = re.compile(r'/p(\d+)/|/page/(\d+)/|[?&](?:PAGEN_\d+|page|p|PAGE)=(\d+)')

    @staticmethod
    def _page_template(href, k):
        """Шаблон URL страницы: заменяет номер k на плейсхолдер и в пути (/pK/,
        /page/K/), и в query (?PAGEN_x=K/?page=K). Поддерживает оба сразу."""
        ph = '\x00'
        t = re.sub(rf'(/p){k}(/)', rf'\g<1>{ph}\g<2>', href)
        t = re.sub(rf'(/page/){k}(/)', rf'\g<1>{ph}\g<2>', t)
        t = re.sub(rf'([?&](?:PAGEN_\d+|page|p|PAGE)=){k}(?=$|[&#])', rf'\g<1>{ph}', t)
        return t if ph in t else None

    def _page_urls_from_pagination(self, base_url, html, max_pages=50):
        """Список абсолютных URL страниц 2..max по ссылкам пагинации в HTML
        (и query, и путь). [] — пагинации нет."""
        if not html:
            return []
        pages = {}
        for m in re.finditer(r'href=["\']([^"\']+)["\']', html):
            href = m.group(1)
            found = self._PAGE_RE.search(href)
            if not found:
                continue
            num = int(next(g for g in found.groups() if g))
            if 1 <= num <= 200:
                pages.setdefault(num, href)
        if not pages:
            return []
        max_page = max(pages)
        if max_page < 2:
            return []
        k = min(p for p in pages if p >= 2)
        template = self._page_template(urljoin(base_url, pages[k]), k)
        if not template:
            return []
        host = urlparse(base_url).netloc
        urls = []
        for p in range(2, min(max_page, max_pages) + 1):
            u = template.replace('\x00', str(p))
            if urlparse(u).netloc == host:
                urls.append(u)
        return urls

    # Схемы постраничных URL для «слепого» перебора, когда ссылок пагинации нет
    # (SPA-пейджеры на <button>): (шаблон query, добавляется ли к пути).
    _PAGE_PATTERNS = (
        '?page=\x00',
        '?PAGEN_1=\x00',
        '?p=\x00',
        'page/\x00/',
    )

    @staticmethod
    def _total_products_hint(html):
        """Сколько всего товаров заявлено на странице каталога (если написано).

        Ищем «(1 582 товара)», «Найдено 1582 товара», «всего: 1582» и т.п.
        Возвращает int или None. Нужно, чтобы понять, что собрана лишь часть.
        """
        if not html:
            return None
        # Вырезаем script/style: там лежат общие счётчики сайта («более 185 000
        # товаров» в JSON-LD), которые не имеют отношения к текущему каталогу.
        cleaned = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', html)
        text = re.sub(r'<[^>]+>', ' ', cleaned).replace('\xa0', ' ')
        # число может быть с разделителями: 1 582, 1,582, 1.582
        num = r'\d{1,3}(?:[  ,.]\d{3})+|\d+'
        pat = re.compile(
            rf'(?:найдено|всего)\D{{0,12}}({num})'
            rf'|({num})\s*(?:товаров|товара|товар)\b',
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            raw = m.group(1) or m.group(2) or ''
            digits = re.sub(r'[^\d]', '', raw)
            if not digits:
                continue
            n = int(digits)
            if 1 <= n <= 1000000:
                return n  # первое упоминание в видимом тексте — счётчик каталога
        return None

    def _build_page_url(self, base_url, pattern, num):
        """Подставляет номер страницы в схему: query (?page=N) или путь (/page/N/)."""
        placeholder = '\x00'
        if pattern.startswith('?'):
            param = pattern[1:].split('=')[0]
            return self._with_page_param(base_url, param, num)
        # путь: /catalog/x/ + page/N/
        base = base_url.split('?')[0].split('#')[0]
        if not base.endswith('/'):
            base += '/'
        return base + pattern.replace(placeholder, str(num))

    def _fetch_catalog_page(self, url):
        """Забирает страницу каталога тем же способом, каким удалось забрать первую.

        Часть сайтов (напр. e2e4) отдаёт 403 на обычные HTTP-запросы, но пускает
        настоящий браузер. Раньше обход страниц ходил ТОЛЬКО через requests и на
        таких сайтах упирался в 403: пагинация не находилась, и сбор скатывался
        на медленный скролл. Теперь, если requests заблокирован, страницы берём
        браузером (без прокрутки — она тут не нужна).
        """
        if not self._requests_blocked:
            html = self._fetch_html_requests(url)
            if html:
                return html
            err = (self._last_fetch_error or '').lower()
            # 403/401/429 — признак блокировки обычных запросов, а не поломки
            if not any(code in err for code in ('403', '401', '429', 'forbidden')):
                return None

            if not self.use_selenium or _SELENIUM_DISABLED:
                return None

            # Прежде чем переходить на «браузер на каждую страницу» (медленно),
            # пробуем пройти проверку один раз браузером и забрать его cookies —
            # дальше обычные запросы обычно проходят.
            if not self._tried_browser_session:
                self._tried_browser_session = True
                self._reuse_driver = True
                probe = self.get_page(url, scroll=False)   # тут же переносим cookies
                if probe:
                    retry = self._fetch_html_requests(url)
                    if retry:
                        logger.info('[СБОР] cookies из браузера подошли — '
                                    'продолжаю быстрыми запросами')
                        self._trace('cookies_из_браузера', результат='подошли')
                        self._reuse_driver = False
                        self.close()
                        return retry
                    self._trace('cookies_из_браузера', результат='не помогли',
                                ошибка=self._last_fetch_error)
                    return probe   # страница у нас уже есть, не тратим ещё один заход

            self._requests_blocked = True
            # держим один браузер на все страницы: перезапуск Chrome на каждую
            # съел бы всё время обхода
            self._reuse_driver = True
            logger.warning(
                f'[СБОР] сайт блокирует обычные запросы ({self._last_fetch_error}) — '
                f'перехожу на браузер для остальных страниц'
            )
            self._trace('переход_на_браузер', причина=self._last_fetch_error)

        if not self.use_selenium or _SELENIUM_DISABLED:
            return None

        # Быстрый путь: тянем страницу через fetch внутри уже открытой вкладки
        # (~1с вместо ~9с на полную навигацию).
        if self._driver is not None:
            html = self._browser_fetch(url)
            if html:
                if not self._used_browser_fetch:
                    self._used_browser_fetch = True
                    self._trace('fetch_в_браузере', результат='работает',
                                размер_html=len(html))
                return html
            if not self._used_browser_fetch:
                self._trace('fetch_в_браузере', результат='не сработал, '
                            'обхожу навигацией (медленно)')
        # вкладки ещё нет (или fetch не сработал) — обычная навигация
        return self.get_page(url, scroll=False)

    def _trace_dedup_check(self, kept):
        """Решающая проверка дедупликации.

        Сайт отдал какое-то число РАЗНЫХ карточек — это число уникальных ссылок
        среди всего, что мы получили. Если сохранённых товаров не меньше, значит
        дедуп ничего не склеил и недобор целиком на стороне сайта. Если меньше —
        мы теряем товары сами, и это надо чинить.
        """
        unique_urls = len(getattr(self, '_all_urls', ()) or ())
        no_url = getattr(self, '_items_without_url', 0)
        if unique_urls:
            lost = unique_urls + (1 if no_url else 0) - kept
            verdict = ('дедуп ничего не потерял' if kept >= unique_urls
                       else f'ВНИМАНИЕ: потеряно ~{lost} — склеены разные карточки')
        else:
            verdict = 'ссылок на карточки нет — проверить нечем'
        self._trace('проверка_дедупа', уникальных_ссылок=unique_urls,
                    сохранено_товаров=kept, товаров_без_ссылки=no_url, вывод=verdict)

        collisions = getattr(self, '_name_price_collisions', 0)
        if collisions:
            # Совпало имя и цена, но ссылки разные. Сейчас такие товары НЕ
            # склеиваются; раньше на этом терялись позиции.
            self._trace('совпало_имя_и_цена_разные_ссылки', количество=collisions,
                        примеры=' | '.join(getattr(self, '_collision_examples', [])[:3]) or '—')

    def _walk_pages(self, url_for_page, method, add, start, max_pages, enough,
                    polite_delay=0.25, expected_per_page=0):
        """Обходит страницы каталога, накапливая товары.

        Ключевой момент: «страница не загрузилась» и «на странице нет новых
        товаров» — разные ситуации. Сетевую ошибку повторяем (сайт может
        придушивать частые запросы), и только реальное отсутствие новых товаров
        несколько раз подряд считаем концом каталога.

        Возвращает номер последней обработанной страницы.
        """
        empty_streak = 0      # страниц подряд без новых товаров
        fail_streak = 0       # страниц подряд, которые не удалось загрузить
        failed_pages = []     # какие страницы так и не загрузились
        fetched_total = 0     # сколько карточек всего пришло со страниц
        added_total = 0       # сколько из них оказались новыми
        short_pages = []      # страницы, отдавшие меньше товаров, чем первая
        dup_pages = []        # страницы с повторами (стр:сколько повторов)
        page = start
        stop_reason = 'дошли до конца диапазона'
        # Бюджет времени. Важно: gunicorn убивает воркер по своему таймауту
        # (сейчас 180с), поэтому обход обязан уложиться с запасом — иначе
        # пользователь получает 502, а не частичный результат.
        try:
            budget = float(os.environ.get('COLLECT_MAX_SECONDS', '110'))
        except (TypeError, ValueError):
            budget = 110.0
        deadline = time.monotonic() + budget
        while page <= max_pages:
            if enough():
                stop_reason = 'собрано всё, что заявлено на сайте'
                break
            if time.monotonic() > deadline:
                stop_reason = f'исчерпан бюджет времени ({budget:.0f}с)'
                break
            u = url_for_page(page)
            html = self._fetch_catalog_page(u)
            if not html:
                # даём сайту передохнуть и пробуем ещё раз
                time.sleep(1.5)
                html = self._fetch_catalog_page(u)
            if not html:
                fail_streak += 1
                failed_pages.append(page)
                if fail_streak >= 3:
                    stop_reason = (f'{fail_streak} страниц подряд не загрузились '
                                   f'(сайт ограничивает частоту запросов?)')
                    break
                page += 1
                continue

            fail_streak = 0
            items = run_extractor(method, html) or []
            added = add(items)
            fetched_total += len(items)
            added_total += added
            if len(items) < expected_per_page:
                short_pages.append(f'{page}:{len(items)}')
            if added < len(items):
                dup_pages.append(f'{page}:{len(items) - added}')
            if added == 0:
                empty_streak += 1
                if empty_streak >= 3:
                    stop_reason = 'три страницы подряд без новых товаров (конец каталога)'
                    break
            else:
                empty_streak = 0
            page += 1
            if polite_delay:
                time.sleep(polite_delay)
        else:
            stop_reason = f'достигнут лимит страниц ({max_pages})'

        self._trace('обход_страниц', до_страницы=page - 1, причина_остановки=stop_reason,
                    не_загрузились=(failed_pages[:10] or '—'),
                    последняя_ошибка=(self._last_fetch_error or '—'))
        # Куда делись товары: получено с страниц против реально новых. Большое
        # число повторов = сайт переупорядочивает каталог между запросами
        # (например, сортировка «по популярности»), и часть товаров не видна
        # ни на одной из запрошенных страниц.
        duplicates = fetched_total - added_total
        same_url = getattr(self, '_dup_same_url', 0)
        self._trace('учёт_товаров', получено_с_страниц=fetched_total,
                    новых=added_total, повторов=duplicates,
                    страниц_с_недобором=(', '.join(short_pages[:12]) or '—'),
                    повторы_по_страницам=(', '.join(dup_pages[:12]) or '—'))

        if same_url:
            logger.warning(
                f'[СБОР] тот же товар (та же ссылка) приходил повторно {same_url} раз '
                f'из {fetched_total} — сайт меняет порядок товаров между запросами. Примеры:'
            )
            for ex in getattr(self, '_dup_examples', [])[:5]:
                logger.warning(f'[СБОР]   {ex}')
        return page - 1

    def _probe_page_urls(self, base_url, method, base_keys, max_pages=200):
        """Фолбэк, когда href-пагинации нет: подбираем рабочую схему постраничных
        URL «вслепую».

        Для каждой схемы (?page=2, ?PAGEN_1=2, ?p=2, /page/2/) грузим страницу 2 и
        сравниваем состав товаров с первой. Схема считается рабочей, только если
        товары ОТЛИЧАЮТСЯ от первой страницы (иначе сайт просто игнорирует параметр
        и отдаёт ту же страницу). Возвращает (pattern, products_page2) или (None, []).
        """
        for pattern in self._PAGE_PATTERNS:
            url2 = self._build_page_url(base_url, pattern, 2)
            if url2 == base_url:
                continue
            html2 = self._fetch_catalog_page(url2)
            if not html2:
                # ВАЖНО: сетевой сбой здесь раньше молча отбраковывал рабочую
                # схему и весь сбор уходил на медленный скролл. Пробуем ещё раз.
                time.sleep(1.5)
                html2 = self._fetch_catalog_page(url2)
            if not html2:
                self._trace('подбор_схемы', схема=pattern, результат='страница не загрузилась',
                            ошибка=self._last_fetch_error)
                continue
            items = run_extractor(method, html2) or []
            if not items:
                self._trace('подбор_схемы', схема=pattern, результат='товары не извлеклись',
                            размер_html=len(html2))
                continue
            keys = {self._product_key(p) for p in items}
            # страница 2 должна давать преимущественно НОВЫЕ товары
            new = keys - base_keys
            if len(new) >= max(1, int(len(keys) * 0.5)):
                self._trace('подбор_схемы', схема=pattern, результат='ПОДОШЛА',
                            товаров=len(items), новых=len(new))
                return pattern, items
            self._trace('подбор_схемы', схема=pattern, результат='та же страница',
                        товаров=len(items), новых=len(new))
        return None, []

    @staticmethod
    def _looks_scrollable(html):
        """Есть ли на странице признаки догрузки (кнопка «показать ещё» / скролл)."""
        h = (html or '').lower()
        return any(s in h for s in (
            'показать ещё', 'показать еще', 'показать больше', 'show more', 'load more',
            'show-more', 'data-show-more', 'data-autoclick-show-more', 'load_more',
        ))

    def _auto_collect(self, url, base_html, html_source):
        """Авто-извлечение с обходом многостраничности.

        Тиры: базовая страница → (SHOWALL уже учтён в _fetch_full_html) →
        нумерованная пагинация по URL (requests) → показать ещё/скролл (браузер).
        Возвращает (products, method) с накоплением и дедупом по (имя, цена).
        """
        products, method = auto_extract(base_html)
        if not products:
            return [], None

        # key -> уже сохранённый товар: нужно, чтобы при повторе сравнить ссылку
        # на карточку и понять, тот же это товар или разные товары схлопнулись
        # одним ключом (имя+цена).
        seen, acc = {}, []
        # Счётчики для проверки самого дедупа (см. трассу «проверка_дедупа»):
        self._dup_same_url = 0        # тот же товар пришёл повторно
        self._dup_examples = []       # примеры повторов (имя + ссылка)
        self._all_urls = set()        # все встреченные ссылки на карточки
        self._all_name_price = {}     # (имя,цена) -> первая ссылка: ловим совпадения
        self._name_price_collisions = 0
        self._collision_examples = []
        self._items_without_url = 0

        def add(items):
            n = 0
            for p in items:
                url = (p.get('url') or '').strip().lower().split('#')[0].rstrip('/')
                if url:
                    self._all_urls.add(url)
                else:
                    self._items_without_url += 1

                # Отдельно (не влияя на дедуп) считаем, сколько товаров совпадают
                # по имени и цене, но ведут на РАЗНЫЕ карточки. Раньше такие
                # склеивались — теперь только фиксируем факт.
                np_key = (p['name'].strip().lower(), round(float(p['price']), 2))
                first_url = self._all_name_price.get(np_key)
                if first_url is None:
                    self._all_name_price[np_key] = url
                elif url and first_url and url != first_url:
                    self._name_price_collisions += 1
                    if len(self._collision_examples) < 5:
                        self._collision_examples.append(
                            f'«{p["name"][:42]}» {p["price"]}: …{first_url[-32:]} ≠ …{url[-32:]}'
                        )

                key = self._product_key(p)
                if key in seen:
                    self._dup_same_url += 1
                    if len(self._dup_examples) < 5:
                        self._dup_examples.append(f'«{p["name"][:42]}» {p["price"]} …{url[-34:]}')
                    continue
                seen[key] = p
                acc.append(p)
                n += 1
            return n

        add(products)
        page1_count = len(acc)
        total_hint = self._total_products_hint(base_html)
        self._trace('страница_1', способ=method, товаров=page1_count,
                    всего_на_сайте=(total_hint or 'не указано'),
                    источник_html=(html_source or '—'), размер_html=len(base_html or ''))

        # Если товаров подозрительно мало при большом числе «ценовых» узлов —
        # значит выбранный способ извлечения провалился (так buketopt отдаёт
        # 1 товар из json-ld). Показываем, что нашёл каждый способ.
        try:
            price_nodes = count_price_nodes(base_html)
            if price_nodes >= 10 and page1_count < price_nodes / 3:
                self._trace('мало_товаров', ценовых_узлов=price_nodes,
                            по_способам=tier_counts(base_html))
        except Exception as e:
            logger.debug(f'[DEBUG] диагностика способов не удалась: {e}')

        def enough():
            """Собрали всё, что заявлено на странице (если число известно)."""
            return bool(total_hint) and len(acc) >= total_hint

        # SHOWALL уже вернул весь каталог одной страницей — пагинация не нужна
        if html_source and 'showall' in html_source:
            self._trace('итог', тир='showall', товаров=len(acc))
            return acc, method

        # Тир 1: нумерованная пагинация по ссылкам в разметке
        page_urls = self._page_urls_from_pagination(url, base_html)
        if page_urls:
            last = self._walk_pages(
                lambda i: page_urls[i - 2],   # page_urls[0] — это страница 2
                method, add,
                start=2, max_pages=len(page_urls) + 1, enough=enough,
                expected_per_page=page1_count,
            )
            logger.info(
                f"[СБОР] пагинация по ссылкам ({method}): до стр. {last}, товаров {len(acc)}"
                + (f" из ~{total_hint}" if total_hint else "")
            )
            self._trace_dedup_check(len(acc))
            self._trace('итог', тир='пагинация по ссылкам', товаров=len(acc),
                        всего_на_сайте=(total_hint or '—'))
            return acc, method

        # Тир 2 (фолбэк): ссылок нет — подбираем схему постраничных URL «вслепую».
        # Нужен для SPA-каталогов, где пейджер сделан кнопками (Nuxt/React).
        base_keys = set(seen)
        pattern, page2 = self._probe_page_urls(url, method, base_keys)
        if pattern:
            add(page2)
            max_pages = 300
            if total_hint and page1_count:
                # с запасом: сколько страниц нужно, чтобы покрыть весь каталог
                max_pages = min(max_pages, int(total_hint / page1_count) + 5)
            last = self._walk_pages(
                lambda i: self._build_page_url(url, pattern, i),
                method, add,
                start=3, max_pages=max_pages, enough=enough,
                expected_per_page=page1_count,
            )
            logger.info(
                f"[СБОР] пагинация подбором «{pattern}» ({method}): до стр. {last}, "
                f"товаров {len(acc)}" + (f" из ~{total_hint}" if total_hint else "")
            )
            if total_hint and len(acc) < total_hint:
                logger.warning(
                    f"[СБОР] каталог собран не полностью: {len(acc)} из ~{total_hint} "
                    f"(остановились на стр. {last})"
                )
            self._trace_dedup_check(len(acc))
            self._trace('итог', тир=f'подбор схемы «{pattern}»', товаров=len(acc),
                        всего_на_сайте=(total_hint or '—'), до_страницы=last)
            return acc, method

        self._trace('подбор_схемы', результат='ни одна схема не подошла')

        # Тир 3: внутренний API каталога. Для SPA без постраничных URL это
        # единственный способ забрать весь каталог быстро: один раз ловим в
        # браузере запрос, которым сайт догружает товары, дальше повторяем его
        # напрямую с растущим номером страницы.
        if total_hint and total_hint > len(acc):
            call, api_products = self._sniff_catalog_api(url)
            if call:
                added_first = add(api_products)
                more = paginate_api(
                    call,
                    self._fetch_api_text,
                    page_size_hint=(page1_count or None),
                    stop_when=lambda n: bool(total_hint) and (len(acc) + n) >= total_hint,
                )
                add(more)
                logger.info(
                    f"[СБОР] через API сайта: товаров {len(acc)}"
                    + (f" из ~{total_hint}" if total_hint else "")
                )
                if not total_hint or len(acc) >= total_hint or added_first or more:
                    self._trace('итог', тир='внутренний API', товаров=len(acc),
                                всего_на_сайте=(total_hint or '—'))
                    return acc, method
            else:
                self._trace('внутренний_API', результат='источник товаров не найден')

        # Тир 4: показать ещё / бесконечный скролл — рендер браузером со скроллом.
        # Пробуем всегда (а не только когда HTML пришёл через requests), иначе
        # результат зависел от того, каким транспортом получена страница.
        if self._looks_scrollable(base_html) or (total_hint and total_hint > len(acc)):
            before = len(acc)
            scrolled = self.get_page(url, scroll=True)
            if scrolled:
                add(run_extractor(method, scrolled))
                logger.info(
                    f"[СБОР] догрузка скроллом ({method}): товаров {len(acc)}"
                    + (f" из ~{total_hint}" if total_hint else "")
                )
                self._trace('скролл', было=before, стало=len(acc), добавлено=len(acc) - before)
            else:
                self._trace('скролл', результат='браузер не отдал страницу',
                            ошибка=(self._last_fetch_error or '—'))

        if total_hint and len(acc) < total_hint:
            logger.warning(
                f"[СБОР] собрана часть каталога: {len(acc)} из ~{total_hint} — {url}"
            )

        self._trace('итог', тир='скролл/страница 1', товаров=len(acc),
                    всего_на_сайте=(total_hint or '—'))
        return acc, method

    def collect_products(self, url, name_selector=None, price_selector=None, feed_url=None):
        """Селектор-независимый сбор товаров по URL.

        Порядок: YML/price-фид → авто-извлечение (JSON-LD → microdata →
        встроенный JSON → DOM) → ручные селекторы (если заданы).

        feed_url — закэшированное значение фида (см. _try_price_feed).
        Возвращает (products, method, feed_cache), где feed_cache — значение для
        записи в кэш фида (URL / '' / None=не менять); method —
        'yml' / 'json-ld' / 'microdata' / 'embedded-json' / 'dom' / 'selectors' / None.
        """
        full_html, url, html_source = self._fetch_full_html(url)

        # тир 0: YML/price-фид — полный каталог одним XML, без рендера
        feed_products, feed_cache = self._try_price_feed(url, full_html, cached_feed=feed_url)
        if feed_products:
            feed_products = self._absolutize(feed_products, url)
            return self._dedup_absolute(feed_products), 'yml', feed_cache

        # Shopify /products.json (если сайт на Shopify)
        shopify = self._try_shopify(url, full_html)
        if shopify:
            shopify = self._absolutize(shopify, url)
            return self._dedup_absolute(shopify), 'shopify', feed_cache

        try:
            products, method = (self._auto_collect(url, full_html, html_source)
                                if full_html else ([], None))
        finally:
            # если переходили на браузерный обход — освобождаем Chrome
            if self._reuse_driver:
                self._reuse_driver = False
                self.close()
        if products:
            products = self._absolutize(products, url)
            products = self._dedup_absolute(products)
            self._log_auto_result(url, method, len(products), full_html)
            return products, method, feed_cache

        if name_selector and price_selector:
            prods = self.parse_products_paginated(url, name_selector, price_selector)
            if prods:
                return prods, 'selectors', feed_cache

        self._log_auto_failure(url, full_html, html_source, feed_cache, name_selector, price_selector)
        return [], None, feed_cache

    def _log_auto_result(self, url, method, n, html):
        """Лог успешного авто-сбора. Если товаров подозрительно мало при многих
        «ценовых» узлах на странице — пишем [ДИАГНОСТИКА] (вероятно частичный
        источник, напр. JSON-LD с одним товаром на странице-листинге)."""
        logger.debug(f"[DEBUG] Авто-извлечение ({method}): {n} товаров — {url}")
        # Диагностика не должна ломать успешный сбор — оборачиваем в try.
        try:
            if n < 5:
                pn = count_price_nodes(html)
                if pn >= max(8, n * 3):
                    logger.warning(
                        "[ДИАГНОСТИКА] подозрительно мало (%s): товаров=%d, ценовых узлов на "
                        "странице=%d | url=%s | тиры=%s",
                        method, n, pn, url, tier_counts(html),
                    )
        except Exception as e:
            logger.debug(f"[DEBUG] диагностика результата не удалась для {url}: {e}")

    def _log_auto_failure(self, url, html, html_source, feed_cache, name_selector, price_selector):
        """Диагностика неудачи авто-сбора — чтобы потом анализировать причины.

        Пишем одной greppable-строкой [ДИАГНОСТИКА]: как получили HTML и его
        размер, был ли фид, разбивку по HTML-тирам (сколько дал каждый) и число
        «ценовых» узлов. По ней видно, на каком шаге «отвалились»:
          - html=None/мелкий → сайт не отдал страницу (JS-рендер/блокировка);
          - price_nodes большое, а тиры 0 → проблема структуры/валюты (правим DOM);
          - json-ld=1 при многих price_nodes → битый/частичный JSON-LD;
          - всё 0 и price_nodes 0 → на странице нет цен (не та страница/каталог).
        """
        try:
            counts = tier_counts(html)
            feed_state = 'нет' if feed_cache == '' else ('кэш' if feed_cache is None else feed_cache)
            # если страницу вообще не получили — показываем причину фетча
            fetch_err = f" ошибка_фетча={self._last_fetch_error}" if not html and self._last_fetch_error else ""
            logger.warning(
                "[ДИАГНОСТИКА] авто-сбор пуст: url=%s | html=%s(%d)%s | фид=%s | "
                "селекторы=%s | тиры=%s",
                url,
                html_source,
                len(html or ''),
                fetch_err,
                feed_state,
                'да' if (name_selector and price_selector) else 'нет',
                counts,
            )
        except Exception as e:
            logger.warning(f"[ДИАГНОСТИКА] не удалось собрать диагностику для {url}: {e}")

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
