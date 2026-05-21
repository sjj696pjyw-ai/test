import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, parse_qs, unquote
import time
import random
import re
from .helpers import extract_domain, get_default_headers, setup_selenium_options, is_excluded_domain

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# Маппинг регионов РФ для Яндекса
YANDEX_REGION_MAP = {
    '213': '213',  # Москва
    '2': '2',      # Санкт-Петербург
    '54': '54',    # Новосибирск
    '47': '47',    # Екатеринбург
    '43': '43',    # Нижний Новгород
    '120': '120',  # Казань
    '51': '51',    # Челябинск
    '24': '24',    # Красноярск
    '35': '35',    # Самара
    '39': '39',    # Ростов-на-Дону
    '38': '38',    # Уфа
    '59': '59',    # Пермь
    '28': '28',    # Воронеж
    '48': '48',    # Волгоград
    '50': '50',    # Краснодар
    '64': '64',    # Саратов
    '189': '189',  # Тюмень
    '30': '30',    # Тольятти
    '66': '66',    # Ижевск
    '75': '75',    # Барнаул
    '44': '44',    # Ульяновск
    '58': '58',    # Иркутск
    '57': '57',    # Хабаровск
    '192': '192',  # Владивосток
    '69': '69',    # Ярославль
    '68': '68',    # Махачкала
    '22': '22',    # Томск
    '26': '26',    # Оренбург
    '70': '70',    # Кемерово
    '49': '49',    # Рязань
}


class YandexParser:
    """
    Парсер поисковой выдачи Яндекса с усиленной антибот-защитой.
    
    Особенности:
    - Реалистичные заголовки и cookies
    - Рандомизированные задержки между запросами
    - Обход JavaScript-рендеринга через Selenium
    - Обработка капчи и блокировок
    - Гео-таргетинг по регионам РФ
    - Rate limiting для предотвращения блокировок
    """
    
    BASE_URL = 'https://yandex.ru/search/'
    JS_URL = 'https://yandex.ru/search/'
    
    # Пути к элементам капчи
    CAPTCHA_SELECTORS = [
        '#captcha', '.captcha', '[class*="captcha"]',
        '[id*="captcha"]', '.SmartCaptcha', '[data-testid="captcha"]'
    ]
    
    def __init__(self, region='213', delay=3, max_retries=2):
        """
        Инициализация парсера.
        
        Args:
            region: ID региона РФ (по умолчанию 213 - Москва)
            delay: Базовая задержка между запросами в секундах
            max_retries: Максимальное количество попыток при ошибке
        """
        self.region = YANDEX_REGION_MAP.get(str(region), '213')
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self._setup_session_headers()
        self.driver = None
        self.cookies = {}
        self.last_request_time = 0
        
    def _setup_session_headers(self):
        """Настройка реалистичных заголовков сессии."""
        headers = get_default_headers()
        # Дополнительные заголовки для Яндекса
        headers.update({
            'Referer': 'https://yandex.ru/',
            'Origin': 'https://yandex.ru',
            'Sec-Ch-Ua': '"Chromium";v="125", "Not.A/Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        self.session.headers.update(headers)
        
    def _random_delay(self, min_factor=0.7, max_factor=1.5):
        """Случайная задержка с рандомизацией."""
        delay_range = self.delay * (max_factor - min_factor)
        actual_delay = self.delay * min_factor + random.uniform(0, delay_range)
        time.sleep(actual_delay)
        
    def _check_rate_limit(self):
        """Проверка rate limiting."""
        current_time = time.time()
        if current_time - self.last_request_time < 2:  # Минимум 2 секунды между запросами
            time.sleep(2 - (current_time - self.last_request_time))
        self.last_request_time = time.time()
        
    def _is_captcha(self, html):
        """Проверка наличия капчи в HTML."""
        for selector in self.CAPTCHA_SELECTORS:
            try:
                soup = BeautifulSoup(html, 'lxml')
                if soup.select_one(selector):
                    return True
            except:
                pass
        # Проверка по тексту
        captcha_keywords = ['captcha', 'капча', 'подтвердите', 'robot']
        html_lower = html.lower()
        return any(kw in html_lower for kw in captcha_keywords)
        
    def _handle_captcha(self):
        """Обработка капчи (логирование и ожидание)."""
        print("YandexParser: Обнаружена капча. Ожидание...")
        time.sleep(random.uniform(10, 20))  # Длительная пауза при капче
        
    def search(self, query, positions=5, use_selenium=True):
        """
        Поиск по Яндексу.
        
        Args:
            query: Поисковый запрос
            positions: Количество результатов
            use_selenium: Использовать Selenium для JS-рендеринга
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        all_results = {'organic': [], 'ads': []}
        
        # Попытка HTTP-парсинга
        for attempt in range(self.max_retries):
            try:
                self._check_rate_limit()
                self._random_delay()
                
                response = self.session.get(
                    self.BASE_URL,
                    params={
                        'text': query,
                        'lr': self.region,  # Параметр локализации
                        'redircnt': '1'     # Избегаем редиректов
                    },
                    timeout=20,
                    allow_redirects=True
                )
                
                if response.status_code == 429:  # Too Many Requests
                    print(f"YandexParser: Rate limit (429). Ожидание...")
                    time.sleep(random.uniform(30, 60))
                    continue
                    
                if response.status_code != 200:
                    print(f"YandexParser: Статус {response.status_code}")
                    break
                    
                # Проверка на капчу
                if self._is_captcha(response.text):
                    self._handle_captcha()
                    continue
                
                # Парсинг результатов
                results = self._parse_page(response.text)
                if results:
                    all_results['organic'] = results[:positions]
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"YandexParser HTTP error (attempt {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                continue
            except Exception as e:
                print(f"YandexParser unexpected error: {e}")
                break
        
        # Fallback на Selenium если HTTP не сработал или нужен JS-рендеринг
        if SELENIUM_AVAILABLE and use_selenium and (not all_results['organic'] or True):
            try:
                selenium_results = self._search_selenium(query, positions)
                if selenium_results.get('ads'):
                    all_results['ads'] = selenium_results['ads']
                if selenium_results.get('organic'):
                    # Объединяем результаты, предпочитая Selenium
                    all_results['organic'] = selenium_results['organic'][:positions]
            except Exception as e:
                print(f"YandexParser selenium error: {e}")
        
        return all_results
    
    def _search_selenium(self, query, positions):
        """
        Поиск через Selenium для обхода JS-защиты.
        
        Args:
            query: Поисковый запрос
            positions: Количество результатов
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        results = {'organic': [], 'ads': []}
        
        if not self.driver:
            options = ChromeOptions()
            setup_selenium_options(options)
            # Дополнительные настройки для Яндекса
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('prefs', {
                'profile.default_content_setting_values.cookies': 1,
                'profile.default_content_setting_values.notifications': 2,
                'profile.default_content_setting_values.popups': 2,
                'profile.managed_default_content_settings.geolocation': 1,
            })
            
            self.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
            
            # Внедрение CDP для обхода детекции
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en']
                    });
                '''
            })
        
        # Формирование URL с параметрами
        search_url = f'{self.JS_URL}?text={quote(query)}&lr={self.region}'
        
        try:
            self.driver.get(search_url)
            
            # Ожидание загрузки результатов
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.serp-item, div.org'))
            )
            
            # Дополнительная задержка для полного рендеринга
            time.sleep(random.uniform(2, 4))
            
            # Проверка на капчу в Selenium
            for selector in self.CAPTCHA_SELECTORS:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, selector):
                        print("YandexParser Selenium: Обнаружена капча")
                        self._handle_captcha()
                        return results
                except:
                    pass
            
            # Парсинг органических результатов
            organic_selectors = [
                'li.serp-item',
                'div.org',
                'article.serp-item',
                '[data-testid="organic-result"]'
            ]
            
            organic_items = []
            for selector in organic_selectors:
                try:
                    organic_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if organic_items:
                        break
                except:
                    continue
            
            for idx, item in enumerate(organic_items[:positions], 1):
                try:
                    # Попытка найти ссылку разными способами
                    link_selectors = [
                        'a.link__domin__icon',
                        'a.Link',
                        'h2 a',
                        '.OrganicTitle-LinkText',
                        'a[href*="://"]'
                    ]
                    
                    link_elem = None
                    for sel in link_selectors:
                        try:
                            link_elem = item.find_element(By.CSS_SELECTOR, sel)
                            if link_elem:
                                break
                        except:
                            continue
                    
                    if not link_elem:
                        continue
                        
                    href = link_elem.get_attribute('href')
                    if not href:
                        continue
                    
                    # Извлечение чистого URL из редиректа Яндекса
                    url = self._extract_yandex_url(href)
                    
                    # Извлечение заголовка
                    title_selectors = [
                        '.OrganicTitle-LinkText',
                        'h2 a',
                        'a.Link',
                        '.title'
                    ]
                    
                    title = ''
                    for sel in title_selectors:
                        try:
                            title_elem = item.find_element(By.CSS_SELECTOR, sel)
                            if title_elem:
                                title = title_elem.text.strip()
                                break
                        except:
                            continue
                    
                    domain = extract_domain(url)
                    if domain and not is_excluded_domain(domain):
                        results['organic'].append({
                            'position': idx,
                            'domain': domain,
                            'title': title,
                            'url': url,
                            'type': 'organic'
                        })
                        
                except Exception as e:
                    print(f"YandexParser Selenium organic error: {e}")
                    continue
            
            # Парсинг рекламных результатов
            ad_selectors = [
                'li.serp-item[data-ad]',
                'div.org[data-ad]',
                '[class*="advertising"]',
                '[data-testid="ad-result"]'
            ]
            
            ad_items = []
            for selector in ad_selectors:
                try:
                    ad_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if ad_items:
                        break
                except:
                    continue
            
            for idx, item in enumerate(ad_items[:positions], 1):
                try:
                    link_elem = item.find_element(By.CSS_SELECTOR, 'a[href*="://"]')
                    href = link_elem.get_attribute('href')
                    url = self._extract_yandex_url(href)
                    
                    title = ''
                    try:
                        title_elem = item.find_element(By.CSS_SELECTOR, '.OrganicTitle-LinkText, h2 a, a.Link')
                        if title_elem:
                            title = title_elem.text.strip()
                    except:
                        pass
                    
                    domain = extract_domain(url)
                    if domain and not is_excluded_domain(domain):
                        results['ads'].append({
                            'position': idx,
                            'domain': domain,
                            'title': title,
                            'url': url,
                            'type': 'ad'
                        })
                        
                except Exception as e:
                    print(f"YandexParser Selenium ad error: {e}")
                    continue
                    
        except TimeoutException:
            print("YandexParser Selenium: Timeout при загрузке страницы")
        except Exception as e:
            print(f"YandexParser Selenium error: {e}")
        
        return results
    
    def _extract_yandex_url(self, href):
        """
        Извлечение чистого URL из редиректа Яндекса.
        
        Яндекс использует свои редиректы вида:
        https://yandex.ru/clck/jsredir?text=...&url=...
        """
        if not href:
            return ''
        
        # Обработка редиректов Яндекса
        if 'yandex.ru/clck/' in href or 'yandex.com/clck/' in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            
            # Параметр url содержит целевой URL
            if 'url' in qs:
                return unquote(qs['url'][0])
            
            # Альтернативные параметры
            for param in ['data', 'redirect_url']:
                if param in qs:
                    return unquote(qs[param][0])
        
        # Прямые ссылки
        if href.startswith('http://') or href.startswith('https://'):
            if 'yandex.ru' not in href and 'yandex.com' not in href:
                return href
        
        return href
    
    def _parse_page(self, html):
        """
        Парсинг HTML-страницы выдачи Яндекса.
        
        Args:
            html: HTML-код страницы
            
        Returns:
            list словарей с результатами
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []
        
        # Селекторы для органических результатов
        organic_selectors = [
            'li.serp-item',
            'div.org',
            'article.serp-item'
        ]
        
        items = []
        for selector in organic_selectors:
            items = soup.select(selector)
            if items:
                break
        
        for idx, item in enumerate(items, 1):
            try:
                # Пропускаем рекламу
                if item.get('data-ad') or item.select_one('[class*="advertising"]'):
                    continue
                
                # Извлечение ссылки
                link_selectors = [
                    'a.link__domin__icon',
                    'a.Link',
                    'h2 a',
                    '.OrganicTitle-LinkText'
                ]
                
                link_elem = None
                for sel in link_selectors:
                    link_elem = item.select_one(sel)
                    if link_elem:
                        break
                
                if not link_elem:
                    continue
                
                href = link_elem.get('href', '')
                url = self._extract_yandex_url(href)
                
                if not url or is_excluded_domain(extract_domain(url)):
                    continue
                
                # Извлечение заголовка
                title = link_elem.get_text(strip=True)
                
                results.append({
                    'position': idx,
                    'domain': extract_domain(url),
                    'title': title,
                    'url': url,
                    'type': 'organic'
                })
                
            except Exception as e:
                print(f"YandexParser parse error: {e}")
                continue
        
        return results
    
    def find_competitors(self, queries, positions=5):
        """
        Поиск конкурентов по списку запросов.
        
        Args:
            queries: Список поисковых запросов
            positions: Количество результатов на запрос
            
        Returns:
            list уникальных конкурентов с метаданными
        """
        competitors = {}
        
        for query in queries:
            print(f"YandexParser: Поиск по запросу '{query}'...")
            results = self.search(query, positions)
            
            # Обработка органических результатов
            for item in results.get('organic', []):
                domain = item['domain']
                if is_excluded_domain(domain):
                    continue
                    
                if domain not in competitors:
                    competitors[domain] = {
                        'domain': domain,
                        'found_in_queries': [],
                        'positions': {},
                        'types': ['organic'],
                        'title': item.get('title', ''),
                        'url': item.get('url', '')
                    }
                
                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = item['position']
                
                # Обновляем тип если есть реклама
                if item.get('type') == 'ad' and 'ad' not in competitors[domain]['types']:
                    competitors[domain]['types'].append('ad')
            
            # Обработка рекламных результатов
            for item in results.get('ads', []):
                domain = item['domain']
                if is_excluded_domain(domain):
                    continue
                    
                if domain not in competitors:
                    competitors[domain] = {
                        'domain': domain,
                        'found_in_queries': [],
                        'positions': {},
                        'types': [],
                        'title': item.get('title', ''),
                        'url': item.get('url', '')
                    }
                
                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = item['position']
                
                if 'ad' not in competitors[domain]['types']:
                    competitors[domain]['types'].append('ad')
        
        print(f"YandexParser: Найдено {len(competitors)} уникальных конкурентов")
        return list(competitors.values())
    
    def __del__(self):
        """Закрытие WebDriver при уничтожении объекта."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
