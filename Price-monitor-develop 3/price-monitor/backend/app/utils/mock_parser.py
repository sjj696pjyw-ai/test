from app.utils.domains import is_excluded_domain
import time
import random

class MockSearchParser:

    def __init__(self, region='213', delay=1):
        self.region = region
        self.delay = delay

    def find_competitors(self, queries, positions=5, result_types=None):
        # Default to organic if no result_types specified
        if result_types is None:
            result_types = ['organic']
            
        time.sleep(self.delay)  # Simulate search delay

        # Enhanced mock competitors with more variety and city-specific domains
        mock_competitors = {
            # Global sites
            'amazon.com': {
                'domain': 'amazon.com',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic', 'ads']
            },
            'ebay.com': {
                'domain': 'ebay.com',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic', 'ads']
            },
            'aliexpress.com': {
                'domain': 'aliexpress.com',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            
            # Russian e-commerce
            'ozon.ru': {
                'domain': 'ozon.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'wildberries.ru': {
                'domain': 'wildberries.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'citilink.ru': {
                'domain': 'citilink.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'dns-shop.ru': {
                'domain': 'dns-shop.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'mvideo.ru': {
                'domain': 'mvideo.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'technopark.ru': {
                'domain': 'technopark.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'leroymerlin.ru': {
                'domain': 'leroymerlin.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'sbermegamarket.ru': {
                'domain': 'sbermegamarket.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'yamarket.ru': {
                'domain': 'yamarket.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            
            # Classifieds (should be filtered out by is_excluded_domain)
            'avito.ru': {
                'domain': 'avito.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'youla.ru': {
                'domain': 'youla.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
            'irr.ru': {
                'domain': 'irr.ru',
                'found_in_queries': [],
                'positions': {},
                'types': ['organic']
            },
        }

        competitors = {}
        for query in queries:
            # Filter out excluded domains first
            available = [d for d in mock_competitors.keys() if not is_excluded_domain(d)]
            
            # If all mock domains are excluded, create some generic ones
            if not available:
                available = ['example-shop.ru', 'my-store.com', 'best-prices.net']
            
            # Select 2-3 random competitors for each query
            selected = random.sample(available, min(3, len(available)))

            for idx, domain in enumerate(selected, 1):
                if domain not in competitors:
                    competitors[domain] = mock_competitors[domain].copy()
                    competitors[domain]['found_in_queries'] = []
                    competitors[domain]['positions'] = {}

                competitors[domain]['found_in_queries'].append(query)
                competitors[domain]['positions'][query] = idx
                
                # Filter types based on what was requested
                original_types = competitors[domain]['types']
                filtered_types = [t for t in original_types if t in result_types]
                if not filtered_types:  # If none match, use first requested type
                    filtered_types = [result_types[0]] if result_types else ['organic']
                competitors[domain]['types'] = filtered_types

        return list(competitors.values())

    def search(self, query, positions=5, result_types=None):
        # Return mock data based on result_types
        if result_types is None:
            result_types = ['organic']
            
        results = {rt: [] for rt in result_types}
        
        # Generate some mock results
        mock_domains = [
            'example-shop.ru',
            'my-store.com', 
            'best-prices.net',
            'top-market.org',
            'buy-here.biz'
        ]
        
        # Filter out excluded domains
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
