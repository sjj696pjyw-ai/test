# Парсеры поисковых систем

## Обзор

В проекте используются два парсера для поиска конкурентов через поисковые системы:

1. **YandexParser** (основной) - через Yandex XML API
2. **DuckDuckGoParser** (запасной) - через HTML/Lite версию DuckDuckGo

## YandexParser

### Особенности
- Использует официальный Yandex XML API
- Не требует Selenium/браузера
- Стабильная работа без капч и блокировок
- Гео-таргетинг по регионам РФ
- Автоматический fallback на HTML-парсинг если XML недоступен

### Установка API ключа
Для полноценной работы рекомендуется получить бесплатный API ключ:
https://yandex.ru/dev/xml/

API ключ можно передать при инициализации:
```python
yandex = YandexParser(region='213', api_key='ваш_ключ')
```

Без ключа парсер работает в демо-режиме с ограничениями.

### Пример использования
```python
from app.utils import YandexParser

parser = YandexParser(region='213', delay=1)
results = parser.search('купить смартфон', positions=5)
competitors = parser.find_competitors(['купить смартфон', 'смартфон цены'], positions=5)
```

## DuckDuckGoParser

### Особенности
- Использует HTML версию DuckDuckGo (html.duckduckgo.com)
- Автоматический fallback на Lite версию (lite.duckduckgo.com)
- Не требует Selenium/браузера
- Гео-таргетинг по регионам РФ

### Пример использования
```python
from app.utils import DuckDuckGoParser

parser = DuckDuckGoParser(region='213', delay=2)
results = parser.search('купить смартфон', positions=5)
competitors = parser.find_competitors(['купить смартфон'], positions=5)
```

## Логика переключения

В `analysis_service.py` реализована следующая логика:

1. Сначала всегда пробуем **YandexParser** (более релевантная выдача для РФ)
2. Если Яндекс не вернул результаты или произошла ошибка → используем **DuckDuckGoParser** как fallback

```python
# Основной парсер - Yandex
yandex_success = False
try:
    yandex = YandexParser(region=region, delay=3)
    competitors = yandex.find_competitors(adapted_queries, positions)
    yandex_success = True
except Exception as e:
    print(f"YandexParser ошибка: {e}")

# Fallback на DuckDuckGo
if not yandex_success and not competitors:
    ddg = DuckDuckGoParser(region=region)
    competitors = ddg.find_competitors(adapted_queries, positions)
```

## Регионы РФ

Поддерживаемые регионы (коды Яндекса):
- 213 - Москва (по умолчанию)
- 2 - Санкт-Петербург
- 54 - Новосибирск
- 47 - Екатеринбург
- 43 - Нижний Новгород
- 120 - Казань
- 51 - Челябинск
- 24 - Красноярск
- и другие (полный список в `YANDEX_REGION_MAP`)

## Отличия от предыдущей версии

### Удалено
- Selenium-зависимости из обоих парсеров
- Прямой парсинг yandex.ru через браузер
- Сложная антибот-защита (теперь не нужна благодаря API)

### Добавлено
- Yandex XML API как основной метод
- DuckDuckGo Lite version как дополнительный fallback
- Упрощённая архитектура без браузерных зависимостей

### Преимущества
- Быстрее (нет overhead на запуск браузера)
- Стабильнее (нет капч и блокировок)
- Проще в поддержке (меньше зависимостей)
- Дешевле в deploy (не нужен Chrome/WebDriver)
