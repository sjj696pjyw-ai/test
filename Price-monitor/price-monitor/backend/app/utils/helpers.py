"""Общие утилиты для проекта Price Monitor."""
import json
import os
from urllib.parse import urlparse

REAL_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

EXCLUDED_DOMAINS = [
    'google.com', 'yandex.ru', 'yandex.com', 'duckduckgo.com',
    'facebook.com', 'instagram.com', 'youtube.com',
    'vk.com', 'ok.ru', 't.me', 'mail.ru'
]

def extract_domain(url):
    """Извлекает домен из URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return url

def host_of(url):
    """Возвращает хост URL без www и без схемы/пути. Терпим к URL без схемы."""
    u = (url or '').strip().lower()
    if not u.startswith(('http://', 'https://')):
        u = 'https://' + u
    host = urlparse(u).netloc
    if host.startswith('www.'):
        host = host[4:]
    return host


# Двухуровневые публичные суффиксы: для них регистрируемый домен — 3 последних
# метки (напр. site.msk.ru, shop.co.uk). Список краткий, но покрывает частые
# случаи РФ/СНГ и популярные международные.
_MULTI_SUFFIXES = {
    'msk.ru', 'spb.ru', 'com.ru', 'net.ru', 'org.ru', 'edu.ru', 'gov.ru',
    'co.uk', 'org.uk', 'com.ua', 'co.il', 'com.br', 'com.tr', 'com.kz',
    'com.by', 'co.kz',
}


def base_domain(host):
    """Регистрируемый («общий») домен хоста: novosibirsk.rus-buket.ru → rus-buket.ru.
    Учитывает частые двухуровневые суффиксы (site.msk.ru → site.msk.ru)."""
    host = (host or '').strip().lower().strip('.')
    if not host:
        return ''
    parts = host.split('.')
    if len(parts) <= 2:
        return host
    last2 = '.'.join(parts[-2:])
    if last2 in _MULTI_SUFFIXES:
        return '.'.join(parts[-3:])
    return last2


def same_site(url_a, url_b):
    """True, если оба URL относятся к одному общему домену (поддомены считаются
    одним сайтом: shop.example.ru и example.ru — один сайт)."""
    da, db = base_domain(host_of(url_a)), base_domain(host_of(url_b))
    return bool(da) and da == db


def is_excluded_domain(domain, custom_excluded=None):
    """Проверяет, является ли домен исключённым."""
    domain_lower = domain.lower()

    if custom_excluded is None:
        custom_excluded = load_excluded_domains()

    def _matches(exc):
        exc = exc.lower().lstrip('.')
        return domain_lower == exc or domain_lower.endswith('.' + exc)

    for exc in EXCLUDED_DOMAINS:
        if _matches(exc):
            return True

    if custom_excluded:
        for exc in custom_excluded:
            if _matches(exc):
                return True

    return False

def load_excluded_domains():
    """Загружает список исключённых доменов из JSON-конфигурации."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config', 'excluded_domains.json'
    )
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            custom = json.load(f)
            aggregators = custom.get('aggregators', [])
            marketplaces = custom.get('marketplaces', [])
            social_networks = custom.get('social_networks', [])
            search_engines = custom.get('search_engines', [])
            return list(set(aggregators + marketplaces + social_networks + search_engines))
    return []

def get_default_headers():
    """Возвращает стандартные заголовки для HTTP-запросов."""
    return {
        'User-Agent': REAL_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
    }

def setup_selenium_options(options):
    """Настраивает общие опции для Selenium WebDriver."""
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,1024')
    options.add_argument(f'user-agent={REAL_UA}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-notifications')
    options.add_argument('--mute-audio')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    return options
