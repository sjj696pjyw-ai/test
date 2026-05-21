import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, parse_qs, unquote
import time
import random
from .helpers import extract_domain, get_default_headers, is_excluded_domain


DDG_REGION_MAP = {
    '213': 'ru-ru', '2': 'ru-ru', '54': 'ru-ru', '47': 'ru-ru',
    '43': 'ru-ru', '120': 'ru-ru', '51': 'ru-ru', '24': 'ru-ru',
    '35': 'ru-ru', '39': 'ru-ru', '38': 'ru-ru', '59': 'ru-ru',
    '28': 'ru-ru', '48': 'ru-ru', '50': 'ru-ru', '64': 'ru-ru',
    '189': 'ru-ru', '30': 'ru-ru', '66': 'ru-ru', '75': 'ru-ru',
    '44': 'ru-ru', '58': 'ru-ru', '57': 'ru-ru', '192': 'ru-ru',
    '69': 'ru-ru', '68': 'ru-ru', '22': 'ru-ru', '26': 'ru-ru',
    '70': 'ru-ru', '49': 'ru-ru',
}


class DuckDuckGoParser:
    """
    Парсер поисковой выдачи DuckDuckGo.
    
    Особенности:
    - Использует HTML версию DuckDuckGo (html.duckduckgo.com)
    - Не требует Selenium/браузера
    - Автоматический fallback на Lite версию
    - Гео-таргетинг по регионам РФ
    """
    BASE_URL = 'https://html.duckduckgo.com/html/'
    LITE_URL = 'https://lite.duckduckgo.com/lite/'

    def __init__(self, region='213', delay=2):
        self.region = DDG_REGION_MAP.get(str(region), 'ru-ru')
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(get_default_headers())

    def search(self, query, positions=5):
        all_results = {'organic': [], 'ads': []}

        try:
            time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
            
            # Попытка через HTML версию
            response = self.session.get(
                self.BASE_URL,
                params={'q': query, 'kl': self.region},
                headers={'Referer': 'https://duckduckgo.com/'},
                timeout=15
            )
            
            if response.status_code == 200:
                results = self._parse_page(response.text)
                if results:
                    all_results['organic'] = results[:positions]
                    
        except Exception as e:
            print(f"DuckDuckGo HTML error: {e}")
            # Fallback на Lite версию
            try:
                time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
                response = self.session.get(
                    self.LITE_URL,
                    params={'q': query, 'kl': self.region},
                    timeout=15
                )
                
                if response.status_code == 200:
                    results = self._parse_lite_page(response.text)
                    if results:
                        all_results['organic'] = results[:positions]
            except Exception as e2:
                print(f"DuckDuckGo Lite error: {e2}")

        return all_results

    def _parse_lite_page(self, html):
        """Парсинг Lite версии DuckDuckGo."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Селекторы для Lite версии
        items = soup.select('table.result-table td.result-body')
        
        for idx, item in enumerate(items, 1):
            try:
                link_elem = item.select_one('a.result-link')
                if link_elem:
                    href = link_elem.get('href', '')
                    url = self._extract_ddg_url(href)
                    title = link_elem.get_text(strip=True)
                    
                    if url and not is_excluded_domain(extract_domain(url)):
                        results.append({
                            'position': idx,
                            'domain': extract_domain(url),
                            'title': title,
                            'url': url,
                            'type': 'organic'
                        })
            except Exception:
                continue

        return results

    def _extract_ddg_url(self, href):
        if not href:
            return ''
        if 'uddg=' in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if 'uddg' in qs:
                return unquote(qs['uddg'][0])
        if '//duckduckgo.com/l/' in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if 'uddg' in qs:
                return unquote(qs['uddg'][0])
        return href

    def _parse_page(self, html):
        soup = BeautifulSoup(html, 'lxml')
        results = []

        items = soup.select('.result')
        for idx, item in enumerate(items, 1):
            try:
                link_elem = item.select_one('a.result__a')
                if link_elem:
                    href = link_elem.get('href', '')
                    url = self._extract_ddg_url(href)
                    title = link_elem.get_text(strip=True)
                    results.append({
                        'position': idx,
                        'domain': extract_domain(url),
                        'title': title,
                        'url': url,
                        'type': 'organic'
                    })
            except Exception:
                continue

        return results

    def find_competitors(self, queries, positions=5):
        competitors = {}

        for query in queries:
            results = self.search(query, positions)

            for item in results.get('organic', []):
                domain = item['domain']
                if is_excluded_domain(domain):
                    continue
                if domain not in competitors:
                    competitors[domain] = {
                        'domain': domain,
                        'found_in_queries': [],
                        'positions': {},
                        'types': ['organic']
                    }
                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = item['position']

            for item in results.get('ads', []):
                domain = item['domain']
                if is_excluded_domain(domain):
                    continue
                if domain not in competitors:
                    competitors[domain] = {
                        'domain': domain,
                        'found_in_queries': [],
                        'positions': {},
                        'types': []
                    }
                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = item['position']
                if 'ad' not in competitors[domain]['types']:
                    competitors[domain]['types'].append('ad')

        return list(competitors.values())
