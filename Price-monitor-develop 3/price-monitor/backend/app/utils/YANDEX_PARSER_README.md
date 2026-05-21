# YandexParser - Основной парсер поисковой выдачи

## Обзор

`YandexParser` теперь является **основным методом** поиска конкурентов в системе мониторинга цен. 
Парсер использует Яндекс для поиска, так как он предоставляет наиболее релевантную выдачу для РФ.

## Ключевые особенности

### 1. Усиленная антибот-защита

- **Реалистичные заголовки**: Полный набор HTTP-заголовков включая Sec-Ch-Ua, Sec-Fetch-* и другие
- **Рандомизированные задержки**: Случайные паузы между запросами (2-5 секунд)
- **Rate limiting**: Минимум 2 секунды между запросами, автоматическая пауза при 429 ошибке
- **Обработка капчи**: Детекция капчи по HTML и тексту, длительная пауза (10-20 сек) при обнаружении
- **Cookies поддержка**: Сохранение и использование cookies сессии

### 2. Двухрежимный парсинг

#### HTTP-режим (быстрый)
- Использует `requests` + `BeautifulSoup`
- Парсит HTML-версию выдачи Яндекса
- Быстрое получение результатов без overhead Selenium

#### Selenium-режим (для JS-сайтов)
- Активируется автоматически если HTTP не сработал
- Полная эмуляция браузера Chrome
- Обход JavaScript-рендеринга
- CDP (Chrome DevTools Protocol) для скрытия автоматизации:
  - Удаление `navigator.webdriver`
  - Подделка `navigator.plugins`
  - Подделка `navigator.languages`

### 3. Гео-таргетинг

Поддержка 30 регионов РФ через параметр `lr`:
```python
YANDEX_REGION_MAP = {
    '213': '213',  # Москва
    '2': '2',      # Санкт-Петербург
    '54': '54',    # Новосибирск
    # ... и другие
}
```

### 4. Извлечение URL из редиректов

Яндекс использует свои редиректы вида:
```
https://yandex.ru/clck/jsredir?text=...&url=ENCODED_URL
```
Парсер автоматически извлекает чистый целевой URL.

## Использование

### Базовое использование

```python
from app.utils import YandexParser

# Создание парсера
parser = YandexParser(region='213', delay=3, max_retries=2)

# Поиск по одному запросу
results = parser.search('купить iphone 15', positions=5)
print(results['organic'])  # Органические результаты
print(results['ads'])      # Рекламные результаты

# Поиск конкурентов по нескольким запросам
competitors = parser.find_competitors(
    ['купить iphone 15', 'iphone 15 цена'],
    positions=5
)
for comp in competitors:
    print(f"{comp['domain']}: {comp['positions']}")
```

### В контексте анализа

```python
from app.services.analysis_service import SearchService

# SearchService автоматически использует YandexParser
competitors = SearchService.perform_search(
    analysis_id=1,
    queries=['купить iphone 15'],
    positions=5,
    result_types=['organic'],
    region='213'
)
```

## Антибот-меры (детально)

### Заголовки запросов

```python
{
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...',
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-Ch-Ua': '"Chromium";v="125", "Not.A/Brand";v="24"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    ...
}
```

### Детекция капчи

Проверяются селекторы:
- `#captcha`, `.captcha`, `[class*="captcha"]`
- `[id*="captcha"]`, `.SmartCaptcha`, `[data-testid="captcha"]`

И ключевые слова в тексте:
- `captcha`, `капча`, `подтвердите`, `robot`

### Rate Limiting

- Минимальная задержка: 2 секунды между запросами
- При 429 ошибке: пауза 30-60 секунд
- Рандомизация: ±30% от базовой задержки

## Fallback логика

Если YandexParser не сработал (ошибка импорта, исключение, пустые результаты):
```python
# 1. Попытка Yandex
try:
    yandex = YandexParser(region=region, delay=3)
    competitors = yandex.find_competitors(queries, positions)
except Exception:
    pass

# 2. Fallback на DuckDuckGo
if not competitors:
    ddg = DuckDuckGoParser(region=region)
    competitors = ddg.find_competitors(queries, positions)
```

## Структура файлов

```
app/utils/
├── __init__.py           # Экспорт YandexParser из yandex_parser
├── yandex_parser.py      # НОВЫЙ: Основной парсер Яндекса
├── parser.py             # СТАРЫЙ: Базовая версия (можно удалить)
├── duckduckgo_parser.py  # Fallback парсер
├── helpers.py            # Общие утилиты
└── site_parser.py        # Парсинг сайтов конкурентов
```

## Отличия от старой версии (parser.py)

| Функция | Старая версия | Новая версия |
|---------|--------------|--------------|
| Заголовки | Базовые | Расширенные (Sec-*, Fetch-*) |
| Задержки | Фиксированные | Рандомизированные |
| Капча | Нет обработки | Детекция + пауза |
| Rate limit | Нет | Есть (2 сек минимум) |
| CDP обход | Нет | Есть (webdriver, plugins, languages) |
| retries | 1 попытка | до 3 попыток |
| 429 обработка | Нет | Пауза 30-60 сек |

## Рекомендации по использованию

1. **Задержка**: Используйте `delay=3` для баланса скорость/надёжность
2. **Max retries**: `max_retries=2` достаточно для большинства случаев
3. **Selenium**: Включён по умолчанию для максимальной надёжности
4. **Регион**: Всегда указывайте актуальный регион для гео-таргетинга

## Пример полного цикла

```python
from app.utils import YandexParser
from config.region_config import adapt_query_to_city

# Адаптация запросов под регион
region = '213'  # Москва
queries = ['купить iphone 15', 'iphone 15 москва']
adapted = [adapt_query_to_city(q, region) for q in queries]

# Поиск
parser = YandexParser(region=region, delay=3)
competitors = parser.find_competitors(adapted, positions=5)

# Обработка результатов
for comp in competitors:
    print(f"Домен: {comp['domain']}")
    print(f"  Найден в запросах: {comp['found_in_queries']}")
    print(f"  Позиции: {comp['positions']}")
    print(f"  Типы: {comp['types']}")
```

## Troubleshooting

### Проблема: Много капч
**Решение**: Увеличьте `delay` до 5 секунд, добавьте больше рандомизации

### Problem: Пустые результаты
**Решение**: Проверьте что Selenium установлен и работает

### Проблема: 429 Too Many Requests
**Решение**: Автоматическая пауза 30-60 сек уже встроена, просто подождите

### Проблема: Неправильные URL
**Решение**: Метод `_extract_yandex_url` должен обрабатывать редиректы, проверьте логи
