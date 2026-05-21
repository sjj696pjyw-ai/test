"""Парсер поисковой выдачи Яндекса через Yandex Search API (Cloud API)."""
import json
import os
import base64
import time
import random
import xml.etree.ElementTree as ET
import requests
from urllib.parse import urlparse

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


def _get_api_config():
    """
    Загружает конфигурацию Yandex Search API из JSON файла.
    
    Returns:
        tuple: (api_key, folder_id) или (None, None) если не настроено
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config', 'yandex_xml.json'
    )
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            if cfg.get('enabled') and cfg.get('key'):
                return cfg['key'], cfg.get('folder_id', '')
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None, None


class YandexParser:
    """
    Парсер поисковой выдачи Яндекса через Yandex Search API (Cloud API).
    
    Особенности:
    - Официальный Yandex Search API (searchapi.api.cloud.yandex.net)
    - Не требует Selenium/браузера
    - Стабильная работа без капч и блокировок
    - Гео-таргетинг по регионам РФ
    - Rate limiting для предотвращения блокировок
    
    Для работы требуется получить API ключ:
    https://yandex.cloud/ru/docs/search/api/quickstart
    """
    
    API_URL = 'https://searchapi.api.cloud.yandex.net/v2/web/search'
    
    def __init__(self, region='213', delay=1, max_retries=2, api_key=None, folder_id=None):
        """
        Инициализация парсера.
        
        Args:
            region: ID региона РФ (по умолчанию 213 - Москва)
            delay: Базовая задержка между запросами в секундах
            max_retries: Максимальное количество попыток при ошибке
            api_key: Yandex Search API ключ (если None, загружается из конфига)
            folder_id: Yandex Cloud Folder ID (опционально)
        """
        self.region = YANDEX_REGION_MAP.get(str(region), '213')
        self.delay = delay
        self.max_retries = max_retries
        self.api_key = api_key
        self.folder_id = folder_id
        self.session = requests.Session()
        self.last_request_time = 0
        
        # Если ключ не передан, пробуем загрузить из конфига
        if not self.api_key:
            self.api_key, self.folder_id = _get_api_config()
        
        # Настройка заголовков
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
    
    @staticmethod
    def is_configured():
        """Проверяет, настроен ли API ключ."""
        key, _ = _get_api_config()
        return bool(key)
    
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
        Поиск по Яндексу через Search API.
        
        Args:
            query: Поисковый запрос
            positions: Количество результатов
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        if not self.api_key:
            return {'organic': [], 'ads': []}
        
        all_results = {'organic': [], 'ads': []}
        
        for attempt in range(self.max_retries):
            try:
                self._check_rate_limit()
                self._random_delay()
                
                # Формируем тело запроса согласно Yandex Search API
                body = {
                    'query': {
                        'searchType': 'SEARCH_TYPE_RU',
                        'queryText': query,
                    },
                    'responseFormat': 'FORMAT_XML',
                }
                
                # Добавляем folder_id если указан
                if self.folder_id:
                    body['folderId'] = self.folder_id
                
                response = self.session.post(
                    self.API_URL,
                    headers={
                        'Authorization': f'Api-Key {self.api_key}',
                        'Content-Type': 'application/json',
                    },
                    json=body,
                    timeout=15,
                )
                
                if response.status_code == 429:
                    print(f"YandexParser: Rate limit (429). Ожидание...")
                    time.sleep(random.uniform(10, 30))
                    continue
                
                if response.status_code != 200:
                    print(f"YandexParser: Статус {response.status_code} - {response.text[:200]}")
                    break
                
                # Парсим JSON ответ
                data = response.json()
                raw_data = data.get('rawData', '')
                
                if not raw_data:
                    print("YandexParser: Пустой rawData в ответе")
                    break
                
                # Декодируем base64 XML
                xml_bytes = base64.b64decode(raw_data)
                xml_text = xml_bytes.decode('utf-8')
                
                # Парсим XML
                results = self._parse_xml(xml_text, positions)
                if results and (results['organic'] or results['ads']):
                    all_results = results
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"YandexParser HTTP error (attempt {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                continue
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"YandexParser JSON decode error: {e}")
                break
            except Exception as e:
                print(f"YandexParser unexpected error: {e}")
                break
        
        return all_results
    
    def _parse_xml(self, xml_text, positions):
        """
        Парсинг XML ответа от Yandex Search API.
        
        Формат XML от searchapi.api.cloud.yandex.net:
        - Корневой элемент: <response>
        - Группы результатов: <group name="organic|ads">
        - Документы: <doc> внутри группы
        - Поля: <field name="url"><value>...</value></field>
        
        Args:
            xml_text: XML строка (уже декодированная из base64)
            positions: Количество результатов
            
        Returns:
            dict с ключами 'organic' и 'ads'
        """
        result = {'organic': [], 'ads': []}
        
        try:
            root = ET.fromstring(xml_text)
            
            # Определяем namespace динамически
            ns = self._get_namespace(root)
            
            # Ищем органические результаты в группе organic
            organic_group = root.find(f'.//{ns}group[@name="organic"]')
            if organic_group is not None:
                for idx, doc in enumerate(organic_group.findall(f'{ns}doc'), 1):
                    if idx > positions:
                        break
                    try:
                        url = self._get_field_value(doc, 'url')
                        title = self._get_field_value(doc, 'title')
                        
                        if url:
                            domain = extract_domain(url)
                            if domain and not is_excluded_domain(domain):
                                result['organic'].append({
                                    'position': idx,
                                    'domain': domain,
                                    'title': title or '',
                                    'url': url,
                                    'type': 'organic',
                                })
                    except Exception as e:
                        print(f"YandexParser organic doc error: {e}")
                        continue
            
            # Ищем рекламные результаты в группе ads
            ads_group = root.find(f'.//{ns}group[@name="ads"]')
            if ads_group is not None:
                for idx, doc in enumerate(ads_group.findall(f'{ns}doc'), 1):
                    if idx > positions:
                        break
                    try:
                        url = self._get_field_value(doc, 'url')
                        title = self._get_field_value(doc, 'title')
                        
                        if url:
                            domain = extract_domain(url)
                            if domain and not is_excluded_domain(domain):
                                result['ads'].append({
                                    'position': idx,
                                    'domain': domain,
                                    'title': title or '',
                                    'url': url,
                                    'type': 'ad',
                                })
                    except Exception as e:
                        print(f"YandexParser ads doc error: {e}")
                        continue
            
            # Альтернативный формат: ищем <doc> напрямую без групп
            if not result['organic'] and not result['ads']:
                for doc in root.findall(f'.//{ns}doc'):
                    try:
                        group_elem = doc.find(f'{ns}group')
                        group_name = group_elem.get('name', 'organic') if group_elem is not None else 'organic'
                        
                        url = self._get_field_value(doc, 'url')
                        title = self._get_field_value(doc, 'title')
                        
                        if url:
                            domain = extract_domain(url)
                            if domain and not is_excluded_domain(domain):
                                item_type = 'ad' if group_name == 'ads' else 'organic'
                                target_list = result[item_type]
                                
                                if len(target_list) < positions:
                                    target_list.append({
                                        'position': len(target_list) + 1,
                                        'domain': domain,
                                        'title': title or '',
                                        'url': url,
                                        'type': item_type,
                                    })
                    except Exception as e:
                        continue
        
        except ET.ParseError as e:
            print(f"YandexParser XML parse error: {e}")
            print(f"XML content preview: {xml_text[:500]}")
        
        return result
    
    @staticmethod
    def _get_namespace(root):
        """
        Извлекает namespace из корневого элемента.
        
        Args:
            root: Корневой ElementTree элемент
            
        Returns:
            Строка namespace в формате '{http://...}' или пустая строка
        """
        tag = root.tag
        ns_end = tag.find('}')
        if ns_end != -1:
            return tag[:ns_end + 1]
        return ''
    
    @staticmethod
    def _get_field_value(elem, field_name):
        """
        Извлекает значение поля из XML элемента.
        
        Формат: <field name="url"><value>https://example.com</value></field>
        
        Args:
            elem: Родительский элемент
            field_name: Имя поля для поиска
            
        Returns:
            Значение поля или None
        """
        ns = YandexParser._get_namespace(elem)
        
        # Ищем поле по имени атрибута name
        for field in elem.findall(f'{ns}field'):
            if field.get('name') == field_name:
                value_elem = field.find(f'{ns}value')
                if value_elem is not None and value_elem.text:
                    return value_elem.text.strip()
        
        # Альтернативно: ищем элемент с именем поля напрямую
        direct_elem = elem.find(f'{ns}{field_name}')
        if direct_elem is not None and direct_elem.text:
            return direct_elem.text.strip()
        
        return None
    
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
