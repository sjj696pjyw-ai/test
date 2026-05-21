import requests
from urllib.parse import urlparse, parse_qs, unquote
import time
import random
from .helpers import extract_domain, is_excluded_domain


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
    Парсер поисковой выдачи Яндекса через Yandex XML API.
    
    Особенности:
    - Официальный API Яндекса (xml.yandex.ru)
    - Не требует Selenium/браузера
    - Стабильная работа без капч и блокировок
    - Гео-таргетинг по регионам РФ
    - Rate limiting для предотвращения блокировок
    
    Для работы требуется получить бесплатный API ключ:
    https://yandex.ru/dev/xml/
    """
    
    XML_API_URL = 'https://yandex-search-api.yandex.ru/search/'
    
    def __init__(self, region='213', delay=1, max_retries=2, api_key=None):
        """
        Инициализация парсера.
        
        Args:
            region: ID региона РФ (по умолчанию 213 - Москва)
            delay: Базовая задержка между запросами в секундах
            max_retries: Максимальное количество попыток при ошибке
            api_key: Yandex XML API ключ (если None, используется демо-режим)
        """
        self.region = YANDEX_REGION_MAP.get(str(region), '213')
        self.delay = delay
        self.max_retries = max_retries
        self.api_key = api_key
        self.session = requests.Session()
        self.last_request_time = 0
        
        # Настройка заголовков
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)',
            'Accept': 'application/xml, text/xml, */*',
        })
        
    def _random_delay(self, min_factor=0.5, max_factor=1.5):
        """Случайная задержка с рандомизацией."""
        delay_range = self.delay * (max_factor - min_factor)
        actual_delay = self.delay * min_factor + random.uniform(0, delay_range)
        time.sleep(actual_delay)
        
    def _check_rate_limit(self):
        """Проверка rate limiting."""
        current_time = time.time()
        if current_time - self.last_request_time < 1:
            time.sleep(1 - (current_time - self.last_request_time))
        self.last_request_time = time.time()
        
    def search(self, query, positions=5):
        """
        Поиск по Яндексу через XML API.
        
        Args:
            query: Поисковый запрос
            positions: Количество результатов
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        all_results = {'organic': [], 'ads': []}
        
        for attempt in range(self.max_retries):
            try:
                self._check_rate_limit()
                self._random_delay()
                
                # Параметры запроса к Yandex XML API
                params = {
                    'text': query,
                    'lr': self.region,
                    'page': 0,
                }
                
                # Если есть API ключ, добавляем его
                if self.api_key:
                    params['apikey'] = self.api_key
                
                response = self.session.get(
                    self.XML_API_URL,
                    params=params,
                    timeout=20
                )
                
                if response.status_code == 429:
                    print(f"YandexParser: Rate limit (429). Ожидание...")
                    time.sleep(random.uniform(10, 30))
                    continue
                    
                if response.status_code != 200:
                    print(f"YandexParser: Статус {response.status_code}")
                    break
                
                # Парсинг XML ответа
                results = self._parse_xml(response.text, positions)
                if results:
                    all_results = results
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"YandexParser HTTP error (attempt {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                continue
            except Exception as e:
                print(f"YandexParser unexpected error: {e}")
                break
        
        return all_results
    
    def _parse_xml(self, xml_content, positions):
        """
        Парсинг XML ответа от Yandex API.
        
        Args:
            xml_content: XML строка
            positions: Количество результатов
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        results = {'organic': [], 'ads': []}
        
        try:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(xml_content)
            
            # Namespace для Yandex XML
            ns = {'yandex': 'https://yandex.ru/yandex-search'}
            
            # Поиск органических результатов
            organic_items = root.findall('.//yandex:doc', ns)
            
            for idx, item in enumerate(organic_items[:positions], 1):
                try:
                    url_elem = item.find('yandex:url', ns)
                    title_elem = item.find('yandex:title', ns)
                    
                    if url_elem is not None and url_elem.text:
                        url = url_elem.text
                        domain = extract_domain(url)
                        
                        if domain and not is_excluded_domain(domain):
                            results['organic'].append({
                                'position': idx,
                                'domain': domain,
                                'title': title_elem.text.strip() if title_elem is not None and title_elem.text else '',
                                'url': url,
                                'type': 'organic'
                            })
                except Exception as e:
                    print(f"YandexParser XML organic error: {e}")
                    continue
            
            # Поиск рекламных результатов (если есть в ответе)
            ad_items = root.findall('.//yandex:ad', ns)
            
            for idx, item in enumerate(ad_items[:positions], 1):
                try:
                    url_elem = item.find('yandex:url', ns)
                    title_elem = item.find('yandex:title', ns)
                    
                    if url_elem is not None and url_elem.text:
                        url = url_elem.text
                        domain = extract_domain(url)
                        
                        if domain and not is_excluded_domain(domain):
                            results['ads'].append({
                                'position': idx,
                                'domain': domain,
                                'title': title_elem.text.strip() if title_elem is not None and title_elem.text else '',
                                'url': url,
                                'type': 'ad'
                            })
                except Exception as e:
                    print(f"YandexParser XML ad error: {e}")
                    continue
                    
        except ET.ParseError as e:
            print(f"YandexParser XML parse error: {e}")
            # Fallback: пробуем парсить как HTML если XML не распарсился
            results = self._parse_html_fallback(xml_content, positions)
        
        return results
    
    def _parse_html_fallback(self, html, positions):
        """
        Резервный парсер HTML (если XML не доступен).
        Использует BeautifulSoup для парсинга.
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            results = {'organic': [], 'ads': []}
            
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
            
            for idx, item in enumerate(items[:positions], 1):
                try:
                    # Пропускаем рекламу
                    if item.get('data-ad') or item.select_one('[class*="advertising"]'):
                        continue
                    
                    link_elem = item.select_one('a.link__domin__icon, a.Link, h2 a, .OrganicTitle-LinkText')
                    
                    if not link_elem:
                        continue
                    
                    href = link_elem.get('href', '')
                    url = self._extract_yandex_url(href)
                    
                    if not url or is_excluded_domain(extract_domain(url)):
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    
                    results['organic'].append({
                        'position': idx,
                        'domain': extract_domain(url),
                        'title': title,
                        'url': url,
                        'type': 'organic'
                    })
                    
                except Exception as e:
                    print(f"YandexParser HTML fallback error: {e}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"YandexParser fallback failed: {e}")
            return {'organic': [], 'ads': []}
    
    def _extract_yandex_url(self, href):
        """
        Извлечение чистого URL из редиректа Яндекса.
        """
        if not href:
            return ''
        
        # Обработка редиректов Яндекса
        if 'yandex.ru/clck/' in href or 'yandex.com/clck/' in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            
            if 'url' in qs:
                return unquote(qs['url'][0])
            
            for param in ['data', 'redirect_url']:
                if param in qs:
                    return unquote(qs[param][0])
        
        # Прямые ссылки
        if href.startswith('http://') or href.startswith('https://'):
            if 'yandex.ru' not in href and 'yandex.com' not in href:
                return href
        
        return href

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
