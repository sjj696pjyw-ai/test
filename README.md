# PriceMonitor — мониторинг цен конкурентов

Приложение для отслеживания цен конкурентов: парсинг каталогов по селекторам, связывание своих товаров с товарами конкурентов, сравнение цен и анализ их динамики во времени с автоматическим ночным обновлением.

## Возможности

- Регистрация и вход по JWT (access 24 ч, refresh 30 дней).
- Создание анализов: регион, поисковые запросы, свой сайт.
- Добавление конкурентов вручную с настройкой селекторов (название, цена).
- Парсинг товаров в каталоге сайта.
- Связывание «мой товар ↔ товар конкурента» и сравнение цен.
- График динамики цен и отчёт по анализу, экспорт в Excel.
- Ручное обновление цен с rate-limit (не чаще раза в 3 минуты) и автоматическое ночное обновление по всем анализам (19:30 UTC).
- Тёмная/светлая тема, всплывающие уведомления.

## Технологический стек

### Backend

- **Python 3.11**, **Flask 3.1**
- **Flask-JWT-Extended** — аутентификация (access + refresh)
- **Flask-SQLAlchemy** — ORM
- **Flask-Bcrypt** — хеширование паролей
- **Flask-CORS** — CORS
- **SQLite** — база данных (в т.ч. в проде, на постоянном томе `/data`)
- **requests** + **BeautifulSoup4** + **lxml** — парсинг HTML (быстрый путь)
- **Selenium 4** + headless **Chromium** — для сайтов с подгрузкой через JS
- **APScheduler** — планировщик ночного обновления цен
- **Gunicorn** — WSGI-сервер в проде

### Frontend

- **React 18** + **Vite 5**
- **React Router 6** — маршрутизация
- **Tailwind CSS 3** — стили
- **Axios** — HTTP-клиент с интерцепторами (JWT, нормализация кодировки)
- **Recharts** / **Chart.js** — графики
- **lucide-react** — иконки
- **xlsx (SheetJS)** — экспорт в Excel на стороне клиента

## Структура проекта

Код находится в `Price-monitor/price-monitor/`. В корне репозитория — `Dockerfile` и `amvera.yml` для деплоя.

```
.
├── Dockerfile                       # Многоэтапная сборка (фронт → бэкенд раздаёт статику)
├── amvera.yml                       # Конфигурация деплоя на Amvera
└── Price-monitor/price-monitor/
    ├── backend/                     # Серверная часть (Flask)
    │   ├── app/
    │   │   ├── __init__.py          # create_app: CORS, JWT, БД, планировщик
    │   │   ├── logging_config.py    # Настройка логирования (LOG_LEVEL / DEBUG)
    │   │   ├── scheduler.py         # APScheduler: ночное обновление цен (19:30 UTC)
    │   │   ├── models/
    │   │   │   └── models.py        # User, Analysis, Competitor, Product, PriceHistory, ProductLink
    │   │   ├── routes/
    │   │   │   ├── auth.py          # Аутентификация и сброс пароля
    │   │   │   └── analysis.py      # Анализы, конкуренты, цены, отчёты
    │   │   ├── services/
    │   │   │   ├── analysis_service.py      # Логика анализов и сбора товаров
    │   │   │   ├── price_update_service.py  # Обновление цен (rate-limit, параллельный сбор)
    │   │   │   └── product_upsert.py        # Общий upsert товаров + история цен
    │   │   └── utils/
    │   │       ├── site_parser.py           # Парсер каталогов (пагинация, SPA, Selenium)
    │   │       └── helpers.py               # Домены, заголовки, опции Selenium
    │   ├── config/config.py         # Конфигурация (Dev/Prod/Testing)
    │   ├── main.py                  # Точка входа (локальный запуск)
    │   └── requirements.txt
    └── frontend/                    # Клиентская часть (React + Vite)
        ├── src/
        │   ├── components/          # Charts, PriceDynamicsChart, Layout
        │   ├── pages/               # Home, Dashboard, AnalysisDetail, SelectorsSetup,
        │   │                        # Login, Register, ForgotPassword, Profile
        │   ├── context/            # AuthContext, ThemeContext, ToastContext
        │   ├── utils/              # api.js, export.js, encoding.js, regions.js
        │   └── styles/
        ├── package.json
        └── vite.config.js
```

## Запуск локально

Нужны два терминала: бэкенд на порту 5001, фронтенд на 3000 (Vite проксирует `/api` → `http://localhost:5001`).

### Backend

```bash
cd Price-monitor/price-monitor/backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

База данных (SQLite) создаётся автоматически при старте. `.env` для локальной разработки необязателен — в `config.py` есть значения по умолчанию для `SECRET_KEY` / `JWT_SECRET_KEY` (на проде их обязательно задать через переменные окружения). Чтобы увидеть отладочные логи парсера: `DEBUG=1 python main.py`.

### Frontend

```bash
cd Price-monitor/price-monitor/frontend
npm install
npm run dev                       # http://localhost:3000
```

## Переменные окружения

Все переменные опциональны для локального запуска (есть значения по умолчанию). Для прода как минимум задайте секреты.

| Переменная | Назначение | По умолчанию |
|------------|------------|--------------|
| `SECRET_KEY` | Секрет Flask | dev-значение |
| `JWT_SECRET_KEY` | Секрет для JWT | dev-значение |
| `DATABASE_URL` | Строка подключения к БД | `sqlite:///pricemonitor.db` |
| `FLASK_ENV` | Профиль конфигурации | `development` |
| `FRONTEND_DIST` | Путь к собранному фронту для раздачи статики | — |
| `LOG_LEVEL` / `DEBUG` | Уровень логирования (`DEBUG=1` включает debug) | `INFO` |
| `PARSER_USE_SELENIUM` | Разрешить Selenium для JS-сайтов | — (в Docker `1`) |
| `CHROME_BIN` / `CHROMEDRIVER_PATH` | Пути к Chromium и драйверу | — (заданы в Docker) |
| `ENABLE_SCHEDULER` | Включить ночной планировщик (`1`) | `0` |
| `SCHEDULER_LOCK_DIR` | Каталог файла-замка планировщика | `/data` или `instance/` |
| `COLLECT_MAX_WORKERS` | Параллелизм сбора цен | `2` |

## API

Базовый префикс — `/api`. Все защищённые эндпоинты требуют заголовок `Authorization: Bearer <access_token>`.

### Аутентификация

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/auth/register` | Регистрация |
| POST | `/api/auth/login` | Вход |
| POST | `/api/auth/refresh` | Обновление access-токена |
| GET | `/api/auth/me` | Текущий пользователь |
| POST | `/api/auth/forgot-password` | Запрос сброса пароля (токен возвращается в ответе) |
| POST | `/api/auth/reset-password` | Сброс пароля по токену |

### Анализы

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis` | Создать анализ |
| GET | `/api/analysis` | Список анализов |
| GET | `/api/analysis/:id` | Детали анализа |
| PUT | `/api/analysis/:id/name` | Переименовать анализ |
| DELETE | `/api/analysis/:id` | Удалить анализ |
| GET | `/api/analysis/:id/report` | Отчёт по анализу |
| GET | `/api/analysis/:id/price-dynamics` | Данные для графика динамики цен |
| GET | `/api/analysis/events` | Уведомления о изменений цен |

### Конкуренты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis/:id/competitor` | Добавить конкурента |
| GET | `/api/analysis/competitor/:id` | Данные конкурента |
| PUT | `/api/analysis/competitor/:id` | Обновить селекторы/домен |
| DELETE | `/api/analysis/competitor/:id` | Удалить конкурента |
| POST | `/api/analysis/competitor/:id/parse` | Собрать товары |
| POST | `/api/analysis/competitor/:id/verify-selectors` | Проверить селекторы |

### Цены и связывание

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis/link` | Связать товары (мой ↔ конкурент) |
| DELETE | `/api/analysis/unlink/:id` | Удалить связь |
| POST | `/api/analysis/competitor/:id/update-prices` | Обновить цены конкурента |
| POST | `/api/analysis/:id/update-prices` | Обновить цены по всему анализу |
| POST | `/api/analysis/update-all-prices` | Обновить цены по всем анализам (ручной запуск ночной задачи) |
| POST | `/api/analysis/check-site` | Проверить доступность сайта |

## Модель данных

- **User** — `id`, `email`, `password_hash`, `created_at`.
- **Analysis** — `id`, `user_id`, `name`, `analysis_type`, `region`, `queries`, `user_site`, `created_at`.
- **Competitor** — `id`, `analysis_id`, `domain`, `competitor_type`, `position`, `is_user_site`, `title_selector`, `price_selector`, `last_price_update`, `update_status`, `update_error_message`.
- **Product** — `id`, `competitor_id`, `name`, `price`, `currency`, `external_id`, `url`, `created_at`.
- **PriceHistory** — `id`, `product_id`, `price`, `currency`, `recorded_at`.
- **ProductLink** — `id`, `analysis_id`, `user_product_id`, `competitor_product_id`, `created_at`.

## Парсинг и обновление цен

- `site_parser.py` собирает товары многоуровнево: сначала быстрый путь через `requests` + BeautifulSoup, при необходимости — Selenium с прокруткой и пагинацией для динамических сайтов; цены очищаются от скидочных токенов, товары дедуплицируются по названию.
- Обновление цен ограничено rate-limit'ом (не чаще раза в 3 минуты на конкурента при ручном запуске); сбор по нескольким конкурентам идёт параллельно (`COLLECT_MAX_WORKERS`).
- Ночью в 19:30 UTC `scheduler.py` обновляет цены по всем анализам. Планировщик включается переменной `ENABLE_SCHEDULER=1` и использует файловую блокировку, чтобы при нескольких gunicorn-воркерах задача выполнилась один раз.

## Сборка для хостинга

Проект собирается одним многоэтапным `Dockerfile`: на первом этапе Node собирает фронтенд, на втором Python-образ ставит зависимости, копирует бэкенд и собранную статику и запускается через Gunicorn (3 воркера, `--timeout 180`, `--max-requests 200`). В образ устанавливается Chromium с драйвером для Selenium.

Деплой настроен на платформу **Amvera** (`amvera.yml`): контейнер слушает порт 5000, под БД примонтирован постоянный том `/data`.
