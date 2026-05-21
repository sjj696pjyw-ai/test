# Рефакторинг Yandex XML Parser

## Основные проблемы старого кода и их решения

### 1. Неправильный API URL
**Проблема:** Старый код использовал несуществующий URL `https://yandex-search-api.yandex.ru/search/` с GET-запросом.

**Решение:** Используется правильный endpoint Yandex Search API (Cloud API):
```python
API_URL = 'https://searchapi.api.cloud.yandex.net/v2/web/search'
```

### 2. Неправильный формат запроса
**Проблема:** Старый код отправлял параметры через query string (`params={'text': query, 'lr': region}`).

**Решение:** Yandex Search API требует POST-запрос с JSON body:
```python
body = {
    'query': {
        'searchType': 'SEARCH_TYPE_RU',
        'queryText': query,
    },
    'responseFormat': 'FORMAT_XML',
}
if folder_id:
    body['folderId'] = folder_id
```

### 3. Неправильная аутентификация
**Проблема:** Старый код использовал параметр `apikey` в query string.

**Решение:** API ключ передаётся в заголовке Authorization:
```python
headers={
    'Authorization': f'Api-Key {api_key}',
    'Content-Type': 'application/json',
}
```

### 4. Неправильный парсинг XML ответа
**Проблема:** 
- Старый код ожидал namespace `{'yandex': 'https://yandex.ru/yandex-search'}`
- Искал элементы `<yandex:url>` и `<yandex:title>` напрямую
- Не учитывал структуру с группами результатов

**Решение:** 
- Динамическое определение namespace из ответа
- Правильная структура XML от Cloud API:
  ```xml
  <response xmlns="https://searchapi.cloud.yandex.net/search">
      <group name="organic">
          <doc>
              <field name="url"><value>https://...</value></field>
              <field name="title"><value>...</value></field>
          </doc>
      </group>
      <group name="ads">...</group>
  </response>
  ```

### 5. Отсутствие обработки base64
**Проблема:** API возвращает XML в base64 кодировке в поле `rawData`, старый код этого не учитывал.

**Решение:** Добавлено декодирование:
```python
data = response.json()
raw_data = data.get('rawData', '')
xml_bytes = base64.b64decode(raw_data)
xml_text = xml_bytes.decode('utf-8')
```

### 6. Конфигурация
**Проблема:** Отсутствовал единый механизм загрузки конфигурации.

**Решение:** Добавлена функция `_get_api_config()` которая загружает настройки из `config/yandex_xml.json`:
```json
{
    "enabled": true,
    "key": "YOUR_API_KEY",
    "folder_id": "YOUR_FOLDER_ID"
}
```

## Структура файла yandex_parser.py

### Новые методы:
1. `_get_api_config()` - загрузка конфигурации из JSON
2. `is_configured()` - проверка наличия API ключа
3. `_get_namespace(root)` - динамическое определение XML namespace
4. `_get_field_value(elem, field_name)` - извлечение значений полей из XML

### Улучшения:
- Добавлен type hinting и подробные docstrings
- Улучшена обработка ошибок с детальным логированием
- Добавлен preview XML при ошибке парсинга
- Сохранена поддержка fallback на HTML парсинг
- Оптимизирован поиск конкурентов

## Требуемые зависимости:
```bash
pip install requests flask-cors flask-jwt-extended flask-bcrypt flask-sqlalchemy psycopg2-binary
```

## Пример использования:
```python
from app.utils.yandex_parser import YandexParser

# Проверка конфигурации
if not YandexParser.is_configured():
    print("API не настроен")

# Создание парсера
parser = YandexParser(region='213')

# Поиск
results = parser.search('купить телефон', positions=5)
print(f"Найдено органических: {len(results['organic'])}")
print(f"Найдено рекламы: {len(results['ads'])}")

# Поиск конкурентов
competitors = parser.find_competitors(['купить телефон', 'смартфоны'], positions=5)
for comp in competitors:
    print(f"{comp['domain']}: {comp['types']}")
```

## Причины неработоспособности старого кода (кратко):

1. **Неверный endpoint** - старый URL не существует
2. **Неверный HTTP метод** - нужен POST вместо GET
3. **Неверный формат запроса** - нужен JSON body вместо query params
4. **Неверная аутентификация** - нужен заголовок Authorization
5. **Неверный парсинг XML** - другая структура и namespace
6. **Отсутствие base64 декодирования** - rawData приходит в base64
7. **Отсутствие folder_id** - требуется для Cloud API
