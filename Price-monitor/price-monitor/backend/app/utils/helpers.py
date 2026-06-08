"""Общие утилиты для проекта Price Monitor."""
from urllib.parse import urlparse
import json
import os


# Единый User-Agent для всех запросов
REAL_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

# Домены для исключения из результатов поиска
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


def is_excluded_domain(domain, custom_excluded=None):
    """Проверяет, является ли домен исключённым."""
    domain_lower = domain.lower()
    
    # Загружаем пользовательские исключения из конфига
    if custom_excluded is None:
        custom_excluded = load_excluded_domains()
    
    # Сравниваем по границе домена, а не по подстроке: домен либо точно
    # совпадает с записью, либо является её поддоменом. Иначе короткие записи
    # давали ложные срабатывания (например 'ya.ru' матчил бы 'moya.ru').
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
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,1024')
    options.add_argument(f'user-agent={REAL_UA}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    return options
