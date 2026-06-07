# Price Monitor - Система мониторинга цен конкурентов

Веб-приложение для автоматического мониторинга цен конкурентов с возможностью анализа, сравнения товаров и отслеживания динамики цен.

## Описание проекта

Система позволяет пользователям:
- Регистрироваться и авторизовываться в системе (JWT)
- Создавать анализы цен (**автоматические** и **ручные**)
- Автоматически искать конкурентов через DuckDuckGo
- Настраивать CSS-селекторы для парсинга сайтов конкурентов
- Отслеживать конкурентов в поисковой выдаче
- Сравнивать цены связанных товаров
- Анализировать динамику изменения цен во времени
- Экспортировать результаты анализа в Excel

## Технологический стек

### Backend
- **Python 3.14+**
- **Flask** - веб-фреймворк
- **Flask-JWT-Extended** - аутентификация через JWT токены (access + refresh)
- **Flask-SQLAlchemy** - ORM для работы с базой данных
- **Flask-CORS** - поддержка CORS
- **PostgreSQL** (продакшен) / **SQLite** (разработка) - база данных
- **BeautifulSoup4** + **lxml** - парсинг HTML
- **Requests** - HTTP-клиент
- **Selenium** (опционально) - для поиска в DuckDuckGo
- **OpenPyXL** - экспорт в Excel

### Frontend
- **React 18** с использованием **Vite**
- **React Router DOM 6** - маршрутизация
- **Tailwind CSS 3** + **Headless UI** - стилизация
- **Axios** - HTTP-клиент с интерцепторами
- **Recharts** - визуализация данных (графики)
- **Lucide React** - иконки

## Структура проекта

```
.
├── backend/                      # Серверная часть (Flask)
│   ├── app/
│   │   ├── __init__.py          # Инициализация приложения
│   │   ├── models/
│   │   │   └── models.py        # SQLAlchemy модели (User, Analysis, Competitor, Product, PriceHistory, ProductLink)
│   │   ├── routes/
│   │   │   ├── auth.py          # Эндпоинты аутентификации
│   │   │   └── analysis.py      # Эндпоинты анализов (22 endpoint'а)
│   │   ├── services/
│   │   │   ├── analysis_service.py      # Бизнес-логика анализов
│   │   │   └── price_update_service.py  # Обновление цен с rate limiting
│   │   └── utils/
│   │       ├── duckduckgo_parser.py     # Поиск конкурентов
│   │       ├── site_parser.py           # Парсинг товаров с сайтов
│   │       ├── parser.py                # YandexParser (не используется)
│   │       └── helpers.py               # Вспомогательные функции
│   ├── config/
│   │   └── config.py            # Конфигурация приложения
│   ├── migrations/              # Миграции БД
│   ├── main.py                  # Точка входа
│   └── requirements.txt         # Зависимости Python
│
├── frontend/                     # Клиентская часть (React)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Charts.jsx               # Графики сравнения цен
│   │   │   ├── PriceDynamicsChart.jsx   # График динамики цен
│   │   │   └── Layout.jsx               # Основной layout
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx            # Список анализов, создание
│   │   │   ├── AnalysisDetail.jsx       # Детали анализа, товары, графики
│   │   │   ├── SelectorsSetup.jsx       # Мастер настройки селекторов
│   │   │   ├── Login.jsx                # Авторизация
│   │   │   ├── Register.jsx             # Регистрация
│   │   │   └── Profile.jsx              # Профиль пользователя
│   │   ├── context/
│   │   │   ├── AuthContext.jsx          # Контекст аутентификации
│   │   │   ├── ThemeContext.jsx         # Темная/светлая тема
│   │   │   └── ToastContext.jsx         # Уведомления
│   │   ├── utils/
│   │   │   ├── api.js                   # API клиент (axios)
│   │   │   └── export.js                # Экспорт в Excel
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── docker-compose.yml           # Docker конфигурация
├── amvera.yaml                  # Конфигурация деплоя
└── README.md
```

## Установка и запуск

### Вариант 1: Локальная разработка

#### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Создание .env файла
cp .env.example .env  # или создайте вручную

# Запуск сервера
python3 main.py 5001
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Приложение будет доступно по адресу: `http://localhost:5173`

### Вариант 2: Docker

```bash
docker-compose up --build
```

## Переменные окружения

Создайте файл `.env` в папке `backend/`:

```env
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# JWT
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pricemonitor
# или для SQLite:
# DATABASE_URL=sqlite:///pricemonitor.db

# CORS
FRONTEND_URL=http://localhost:5173

# Опционально: Selenium
SELENIUM_HEADLESS=true
```

## API Endpoints

### Аутентификация
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/auth/register` | Регистрация нового пользователя |
| POST | `/api/auth/login` | Авторизация пользователя |
| POST | `/api/auth/refresh` | Обновление JWT токена |
| GET | `/api/auth/me` | Получение информации о текущем пользователе |

### Анализы (основные)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/analysis` | Получение списка анализов пользователя |
| POST | `/api/analysis` | Создание нового анализа |
| GET | `/api/analysis/:id` | Получение деталей конкретного анализа |
| PUT | `/api/analysis/:id/name` | Обновление имени анализа |
| DELETE | `/api/analysis/:id` | Удаление анализа |

### Конкуренты
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis/:id/competitor` | Добавить конкурента вручную |
| PUT | `/api/analysis/competitor/:id` | Обновить CSS-селекторы конкурента |
| POST | `/api/analysis/competitor/:id/parse` | Парсинг товаров конкурента |
| POST | `/api/analysis/competitor/:id/verify-selectors` | Проверка селекторов |
| POST | `/api/analysis/competitor/:id/reparse` | Повторный парсинг с новыми селекторами |
| POST | `/api/analysis/competitor/:id/update-prices` | Обновление цен конкурента |
| POST | `/api/analysis/:id/update-prices` | Массовое обновление всех конкурентов |
| POST | `/api/analysis/:id/select-competitors` | Автоматический выбор конкурентов из поиска |

### Товары и сравнение
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis/link` | Связка товаров (мой ↔ конкурент) |
| DELETE | `/api/analysis/unlink/:id` | Развязка товаров |
| GET | `/api/analysis/:id/price-dynamics` | Динамика цен (для графика) |
| GET | `/api/analysis/:id/report` | Отчёт по анализу |

### Утилиты
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/analysis/check-site` | Проверка доступности сайта |

## Модель данных

### User
- `id`, `email`, `password_hash`, `created_at`

### Analysis
- `id`, `user_id`, `name`, `analysis_type` (auto/manual), `region`, `queries` (JSON), `user_site`, `created_at`

### Competitor
- `id`, `analysis_id`, `domain`, `competitor_type`, `position`, `is_user_site`
- `title_selector`, `price_selector`, `sku_selector` - CSS-селекторы для парсинга
- `last_price_update`, `update_status`, `update_error_message` - мониторинг обновлений

### Product
- `id`, `competitor_id`, `name`, `price`, `currency`, `external_id` (артикул/SKU), `url`, `created_at`

### PriceHistory
- `id`, `product_id`, `price`, `currency`, `recorded_at`

### ProductLink
- `id`, `analysis_id`, `user_product_id`, `competitor_product_id`

## Особенности

### 🔐 Безопасность
- JWT аутентификация с access token (15 мин) и refresh token (30 дней)
- HttpOnly cookies для хранения токенов
- Защита CORS
- Хеширование паролей (bcrypt)

### 🔍 Поиск конкурентов
- Автоматический поиск через **DuckDuckGo** с поддержкой регионов
- Фильтрация исключённых доменов (поисковики, агрегаторы, соцсети)
- Ручное добавление конкурентов

### 🕷️ Парсинг
- Гибкая настройка CSS-селекторов для каждого конкурента
- Поддержка множественных селекторов (через запятую)
- Валидация и очистка цен (удаление %, скидок, мусора)
- Извлечение SKU/артикулов
- Rate limiting (минимум 3 минуты между обновлениями)

### 📊 Визуализация
- **График динамики цен** - изменение цен во времени (7 дней)
- **Сравнение цен** - наглядное сравнение связанных товаров
- **Разница цен** - процентное отклонение цен
- **История анализов** - активность пользователя
- **Распределение конкурентов** - статистика по типам

### 📥 Экспорт
- Выгрузка отчетов в Excel (.xlsx)
- Данные о товарах, ценах, динамике

### 🎨 Интерфейс
- Темная/светлая тема
- Адаптивный дизайн
- Уведомления (toast)
- Пошаговый мастер настройки селекторов

## Известные ограничения

1. **URL товаров**: поле `url` в модели Product предназначено для кликабельных ссылок в графиках, но в текущей версии не заполняется автоматически при парсинге. Требуется доработка `site_parser.py`.

2. **Асинхронность**: Обновление цен происходит синхронно, что может приводить к таймаутам при большом количестве товаров. Рекомендуется внедрение Celery/RQ.

3. **YandexParser**: Код парсера Яндекс присутствует в проекте, но не используется (основной источник - DuckDuckGo).

## Разработка

### Запуск миграций БД
```bash
cd backend
python3 migrate_db.py
```

### Тестирование API
```bash
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

## Деплой

Проект готов к деплою на платформу **Amvera** (конфигурация в `amvera.yaml`).

## Лицензия

MIT License

## Контакты

Проект разработан для мониторинга цен конкурентов и анализа рыночной ситуации.
