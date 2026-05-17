import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import time
import random
from .helpers import extract_domain, REAL_UA, get_default_headers, setup_selenium_options, is_excluded_domain

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class YandexParser:
    BASE_URL = 'https://yandex.ru/search/'

    def __init__(self, region='213', delay=2, use_selenium=True):
        self.region = region
        self.delay = delay
        self.use_selenium = SELENIUM_AVAILABLE and use_selenium
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update(get_default_headers())

    def search(self, query, positions=5, result_types=None):
        if result_types is None:
            result_types = ['organic', 'ads']
        all_results = {'organic': [], 'ads': []}

        try:
            time.sleep(random.uniform(self.delay * 0.5, self.delay * 1.5))
            params = {
                'text': query,
                'lr': self.region,
                'nocfg': '1',
                'numdoc': str(positions * 2)
            }
            response = self.session.get(self.BASE_URL, params=params, timeout=15)
            if response.status_code == 200:
                results = self._parse_page(response.text)
                for rt in result_types:
                    if rt in results and results[rt]:
                        all_results[rt] = results[rt][:positions]
                if all_results['organic'] or all_results['ads']:
                    return all_results
        except Exception:
            pass

        if self.use_selenium:
            try:
                all_results = self._search_selenium(query, positions, result_types)
            except Exception as e:
                print(f"Yandex selenium error: {e}")

        return all_results

    def _search_selenium(self, query, positions, result_types):
        all_results = {'organic': [], 'ads': []}

        if not self.driver:
            options = ChromeOptions()
            setup_selenium_options(options)
            self.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )

        search_url = f"{self.BASE_URL}?text={quote(query)}&lr={self.region}&numdoc={positions * 2}"
        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        html = self.driver.page_source
        results = self._parse_page(html)

        for rt in result_types:
            if rt in results:
                all_results[rt] = results[rt][:positions]

        return all_results

    def _parse_page(self, html):
        soup = BeautifulSoup(html, 'lxml')
        results = {'organic': [], 'ads': []}

        ads = soup.select('.OrganicPureEntity, .serp-item[data-type="adv"]')
        for idx, item in enumerate(ads, 1):
            try:
                link_elem = item.select_one('a.OrganicTitle-link, .OrganicTitle a, a[href]')
                title_elem = item.select_one('h2.OrganicTitle, .OrganicTitle')
                if link_elem:
                    url = link_elem.get('href', '')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    if url and not url.startswith('#'):
                        results['ads'].append({
                            'position': idx,
                            'domain': extract_domain(url),
                            'title': title,
                            'url': url,
                            'type': 'ad'
                        })
            except Exception:
                continue

        organic_items = soup.select('.serp-item:not([data-type="adv"])')
        for idx, item in enumerate(organic_items, 1):
            try:
                link_elem = item.select_one('a.OrganicTitle-link, a[href]')
                title_elem = item.select_one('h2.OrganicTitle, .OrganicTitle')
                if link_elem:
                    url = link_elem.get('href', '')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    if url and not url.startswith('#'):
                        results['organic'].append({
                            'position': idx,
                            'domain': extract_domain(url),
                            'title': title,
                            'url': url,
                            'type': 'organic'
                        })
            except Exception:
                continue

        return results

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def find_competitors(self, queries, positions=5, result_types=None):
        competitors = {}
        for query in queries:
            results = self.search(query, positions, result_types)
            for result_type in result_types or ['organic', 'ads']:
                for item in results.get(result_type, []):
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
                    if result_type not in competitors[domain]['types']:
                        competitors[domain]['types'].append(result_type)
        return list(competitors.values())
