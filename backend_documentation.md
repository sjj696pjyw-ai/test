# Backend компонентов

## Backend (серверная часть) — Python / Flask

### Корневые файлы

- **main.py** – точка входа в приложение. Создаёт экземпляр Flask, импортирует и регистрирует Blueprints (auth, analysis), загружает конфигурацию и запускает сервер.
- **requirements.txt** – список зависимостей: Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS, Flask-Bcrypt, BeautifulSoup4, Selenium, duckduckgo-search, pandas, openpyxl.

### config/

- **config.py** – классы конфигурации (DevelopmentConfig, ProductionConfig). Содержит параметры подключения к БД, секретные ключи JWT, настройки CORS.
- **excluded_domains.json** – JSON-массив доменов (маркетплейсы, соцсети, поисковики), которые игнорируются при подборе и проверке конкурентов. Загружается динамически через утилиты.

### app/

- **__init__.py** – создание экземпляра приложения Flask, инициализация расширений (db, jwt, cors, bcrypt), регистрация Blueprint'ов.
- **models/models.py** – централизованные модели данных SQLAlchemy:
  - **User** (таблица `user`): поля `id`, `email`, `password_hash`, `created_at`.
  - **Analysis** (таблица `analyses`): поля `id`, `user_id`, `name`, `queries`, `region`, `analysis_type`, `user_site`, `created_at`.
  - **Competitor** (таблица `competitors`): поля `id`, `analysis_id` (FK → Analysis), `domain`, `url`, `title_selector`, `price_selector`, `sku_selector`, `name_selector`, `image_selector`.
  - **Product** (таблица `products`): поля `id`, `competitor_id` (FK → Competitor), `name`, `price`, `currency`, `external_id`, `url`, `last_parsed_at`.
  - **PriceHistory** (таблица `price_history`): поля `id`, `product_id` (FK → Product), `price`, `recorded_at`.

### app/routes/ — эндпоинты API

#### auth.py – маршруты аутентификации:
- `POST /api/auth/register` – регистрация нового пользователя.
- `POST /api/auth/login` – вход (возврат access/refresh токенов).
- `POST /api/auth/refresh` – обновление access токена.
- `GET /api/auth/me` – получение данных текущего пользователя.

#### analysis.py – управление анализами:
- `GET /api/analysis` – список всех анализов пользователя.
- `POST /api/analysis` – создание нового анализа.
- `GET /api/analysis/<id>` – детали конкретного анализа.
- `DELETE /api/analysis/<id>` – удаление анализа.
- `PUT /api/analysis/<id>/name` – обновление имени анализа.
- `POST /api/analysis/<id>/select-competitors` – утверждение найденных конкурентов для анализа.
- `PUT /api/analysis/competitor/<id>` – обновление селекторов парсинга для конкурента.
- `POST /api/analysis/competitor/<id>/verify-selectors` – проверка валидности CSS-селекторов на тестовой странице.
- `POST /api/analysis/competitor/<id>/parse` – запуск парсинга товаров у конкурента.
- `POST /api/analysis/competitor/<id>/reparse` – повторный парсинг товаров конкурента.
- `POST /api/analysis/link` – добавление связи между продуктом и историей цен.
- `DELETE /api/analysis/unlink/<id>` – удаление связи продукта с историей цен.
- `POST /api/analysis/update-prices` – массовое обновление цен продуктов.
- `GET /api/analysis/<id>/price-dynamics` – получение динамики цен по анализу.
- `GET /api/analysis/<id>/report` – генерация отчёта (Excel/JSON).

### app/services/ — бизнес-логика (реализована внутри analysis_service.py)

- **analysis_service.py** – оркестрация всех процессов анализа:
  - Класс **AnalysisService**: создание анализа, управление конкурентами, формирование отчётов, обновление цен, расчёт динамики цен.
  - Класс **SearchService**: управление поиском конкурентов. Выбирает стратегию поиска (DuckDuckGo), вызывает парсеры, фильтрует результаты через модуль domains.
  - Класс **SiteParsingService**: парсинг страниц конкурентов. Использует Selenium для рендеринга JS, применяет селекторы из модели Competitor, извлекает товары, проверяет селекторы, сохраняет продукты и историю цен.

### app/utils/ — вспомогательные утилиты

- **duckduckgo_parser.py** – основной модуль поиска. Реализует поиск через библиотеку duckduckgo-search.
- **parser.py** – общие функции парсинга HTML с использованием BeautifulSoup.
- **site_parser.py** – низкоуровневый инструмент работы с браузером (Selenium): прокрутка страницы, закрытие попапов, ожидание элементов. Используется классом SiteParsingService.
- **helpers.py** – вспомогательные функции, включая `load_excluded_domains()`, которая читает `config/excluded_domains.json`.
- **domains.py** – логика фильтрации доменов. Использует список исключений из helpers.py для очистки результатов поиска.
- **mock_parser.py** – заглушки для тестирования (возвращают фиктивные данные при парсинге).

---

## Примечания по архитектуре

1. **Расширения Flask** (SQLAlchemy, JWT, CORS, Bcrypt) инициализируются в `app/__init__.py` и импортируются в `app/models/models.py`, отдельного файла `extensions.py` нет.
2. **Все модели данных** находятся в одном файле `app/models/models.py`, а не в отдельных файлах для каждой модели.
3. **Сервисы поиска и парсинга** (SearchService, SiteParsingService) реализованы как классы внутри `analysis_service.py`, а не как отдельные модули.
4. **Валидация селекторов** реализована в методе `SiteParsingService.verify_selectors()`, отдельного файла `selector_validator.py` нет.
5. **Эндпоинты управления связями** (`/api/analysis/link` и `/api/analysis/unlink/<id>`) присутствуют в коде и используются для управления историей изменений цен.
