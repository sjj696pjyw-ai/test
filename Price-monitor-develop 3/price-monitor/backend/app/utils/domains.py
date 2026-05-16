import json
import os


def load_excluded_domains():
    """Загружает список исключённых доменов из JSON-конфигурации."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'excluded_domains.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            custom = json.load(f)
            aggregators = custom.get('aggregators', [])
            marketplaces = custom.get('marketplaces', [])
            social_networks = custom.get('social_networks', [])
            search_engines = custom.get('search_engines', [])
            return list(set(aggregators + marketplaces + social_networks + search_engines))
    return []


def is_excluded_domain(domain):
    """Проверяет, является ли домен исключённым (агрегатор или маркетплейс)."""
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
