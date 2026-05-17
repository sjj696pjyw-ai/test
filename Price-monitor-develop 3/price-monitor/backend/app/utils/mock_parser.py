from .helpers import is_excluded_domain
import time
import random


class MockSearchParser:
    """Мок-парсер для тестирования без реальных поисковых запросов."""

    def __init__(self, region='213', delay=1):
        self.region = region
        self.delay = delay

    def find_competitors(self, queries, positions=5, result_types=None):
        if result_types is None:
            result_types = ['organic']

        time.sleep(self.delay)

        mock_competitors = {
            'amazon.com': {'domain': 'amazon.com', 'types': ['organic', 'ads']},
            'ebay.com': {'domain': 'ebay.com', 'types': ['organic', 'ads']},
            'aliexpress.com': {'domain': 'aliexpress.com', 'types': ['organic']},
            'ozon.ru': {'domain': 'ozon.ru', 'types': ['organic']},
            'wildberries.ru': {'domain': 'wildberries.ru', 'types': ['organic']},
            'citilink.ru': {'domain': 'citilink.ru', 'types': ['organic']},
            'dns-shop.ru': {'domain': 'dns-shop.ru', 'types': ['organic']},
            'mvideo.ru': {'domain': 'mvideo.ru', 'types': ['organic']},
            'technopark.ru': {'domain': 'technopark.ru', 'types': ['organic']},
            'leroymerlin.ru': {'domain': 'leroymerlin.ru', 'types': ['organic']},
            'sbermegamarket.ru': {'domain': 'sbermegamarket.ru', 'types': ['organic']},
            'yamarket.ru': {'domain': 'yamarket.ru', 'types': ['organic']},
        }

        competitors = {}
        for query in queries:
            available = [d for d in mock_competitors.keys() if not is_excluded_domain(d)]
            if not available:
                available = ['example-shop.ru', 'my-store.com', 'best-prices.net']

            selected = random.sample(available, min(3, len(available)))

            for idx, domain in enumerate(selected, 1):
                if domain not in competitors:
                    competitors[domain] = mock_competitors[domain].copy()
                    competitors[domain]['found_in_queries'] = []
                    competitors[domain]['positions'] = {}

                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = idx
                original_types = competitors[domain]['types']
                filtered_types = [t for t in original_types if t in result_types]
                if not filtered_types:
                    filtered_types = [result_types[0]] if result_types else ['organic']
                competitors[domain]['types'] = filtered_types

        return list(competitors.values())

    def search(self, query, positions=5, result_types=None):
        if result_types is None:
            result_types = ['organic']

        results = {rt: [] for rt in result_types}
        mock_domains = [
            'example-shop.ru', 'my-store.com', 'best-prices.net',
            'top-market.org', 'buy-here.biz'
        ]
        available_domains = [d for d in mock_domains if not is_excluded_domain(d)]
        if not available_domains:
            available_domains = ['shop.example.com', 'store.test.org']

        for i, domain in enumerate(available_domains[:positions]):
            for rt in result_types:
                results[rt].append({
                    'position': i + 1,
                    'domain': domain,
                    'title': f'Product {i+1} for {query}',
                    'url': f'https://{domain}/product/{i+1}',
                    'type': rt
                })

        return results
