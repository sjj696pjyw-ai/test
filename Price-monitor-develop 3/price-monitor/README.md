# PriceMonitor - Сервис анализа цен конкурентов

Веб-сервис для мониторинга цен конкурентов в поисковой выдаче Яндекс с автоматическим сбором и сравнением ценовых данных.

## Возможности

- **Автоматический поиск конкурентов** - ввод поисковых запросов и получение списка конкурентов из выдачи Яндекс
- **Ручной ввод конкурентов** - указание конкретных сайтов для анализа
- **Парсинг цен** - сбор цен с сайтов конкурентов по CSS-селекторам с проверкой
- **Сравнительный отчёт** - анализ разницы цен с вашими товарами
- **Визуализация** - графики Chart.js для наглядного анализа
- **Экспорт данных** - выгрузка в Excel и CSV форматы
- **История анализов** - сохранение и просмотр всех проведённых анализов
- **Dark Mode** - тёмная тема интерфейса

## Технологии

### Backend
- Python 3.11+
- Flask
- SQLAlchemy (SQLite)
- Flask-JWT-Extended
- BeautifulSoup4
- Requests

### Frontend
- React 18
- Vite
- Tailwind CSS
- React Router
- Axios
- Chart.js
- Lucide Icons

## Установка и запуск

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip3 install -r requirements.txt
python3 main.py
```

Сервер запустится на http://localhost:5000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Приложение будет доступно на http://localhost:3000

## Структура проекта

```
price-monitor/
├── backend/
│   ├── app/
│   │   ├── models/      # Модели базы данных
│   │   ├── routes/      # API маршруты
│   │   ├── services/   # Бизнес-логика
│   │   └── utils/      # Парсеры (Yandex, Site)
│   ├── config/         # Конфигурация
│   ├── main.py         # Точка входа
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/  # React компоненты
│   │   ├── pages/       # Страницы приложения
│   │   ├── context/     # React Context
│   │   ├── utils/       # Утилиты
│   │   └── styles/      # CSS стили
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Авторизация
- `POST /api/auth/register` - Регистрация
- `POST /api/auth/login` - Вход
- `POST /api/auth/refresh` - Обновление токена
- `GET /api/auth/me` - Текущий пользователь
- `POST /api/auth/forgot-password` - Восстановление пароля

### Анализы
- `GET /api/analysis` - Список анализов
- `POST /api/analysis` - Создание анализа
- `GET /api/analysis/{id}` - Детали анализа
- `DELETE /api/analysis/{id}` - Удаление анализа
- `POST /api/analysis/link` - Связывание товаров
- `POST /api/analysis/competitor/{id}/verify-selectors` - Проверка селекторов
- `POST /api/analysis/competitor/{id}/parse` - Парсинг товаров

## Конфигурация

Переменные окружения для backend (.env):

```
FLASK_ENV=development
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=sqlite:///pricemonitor.db
```

## Функционал

### Режим 1: Автоматический поиск конкурентов
- Ввод до 10 поисковых запросов
- Выбор региона из списка
- Настройка количества позиций (1-10)
- Фильтрация по типу выдачи (органическая/реклама)

### Режим 2: Ручной ввод конкурентов
- Указание своего сайта
- Ввод до 3 конкурентов
- Настройка CSS-селекторов для парсинга
- Проверка селекторов перед парсингом

### Сопоставление товаров
- Ручное связывание товаров пользователя с товарами конкурентов
- Расчёт разницы цен

### Отчёты
- Таблица сравнения цен
- Графики Chart.js
- Экспорт в Excel и CSV

## Дипломный проект 2026
