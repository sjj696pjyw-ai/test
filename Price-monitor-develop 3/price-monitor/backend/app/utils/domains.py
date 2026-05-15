import json
import os

EXCLUDED_DOMAINS = [
    'market.yandex.ru', 'avito.ru', 'cian.ru', '2gis.ru', 
    'drom.ru', 'auto.ru', 'irr.ru', 'ozon.ru', 'wildberries.ru',
    'dns-shop.ru', 'citilink.ru', 'eldorado.ru', 'technopark.ru',
    'sbermegamarket.ru', 'mvideo.ru', 'leroymerlin.ru', 'vk.com',
    'youtube.com', 'google.com', 'yandex.ru', 'mail.ru', 'rambler.ru'
]


def load_excluded_domains():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'excluded_domains.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            custom = json.load(f)
            return list(set(EXCLUDED_DOMAINS + custom.get('aggregators', []) + custom.get('marketplaces', [])))
    return EXCLUDED_DOMAINS


def is_excluded_domain(domain):
    excluded = load_excluded_domains()
    domain_lower = domain.lower()
    for exc in excluded:
        if exc in domain_lower or domain_lower.endswith('.' + exc):
            return True
    return False


def extract_domain(url):
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return url
