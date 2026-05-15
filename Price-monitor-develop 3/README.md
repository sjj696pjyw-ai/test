# Price Monitor - Система мониторинга цен конкурентов

Веб-приложение для автоматического мониторинга цен конкурентов с возможностью анализа и сравнения товаров.

## Описание проекта

Система позволяет пользователям:
- Регистрироваться и авторизовываться в системе
- Создавать анализы цен (автоматические и ручные)
- Отслеживать конкурентов в поисковой выдаче
- Сравнивать цены товаров
- Экспортировать результаты анализа

## Технологический стек

### Backend
- **Python 3.14+**
- **Flask** - веб-фреймворк
- **Flask-JWT-Extended** - аутентификация через JWT токены
- **SQLAlchemy** - ORM для работы с базой данных
- **SQLite** - база данных

### Frontend
- **React 18** с использованием Vite
- **React Router DOM 6** - маршрутизация
- **Tailwind CSS 3** - стилизация
- **Axios** - HTTP-клиент
- **Chart.js / React-ChartJS-2** - графики
- **Lucide React** - иконки

## Структура проекта

```
.
├── backend/                 # Серверная часть (Flask)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models/         # Модели данных
│   │   ├── routes/         # API маршруты
│   │   ├── services/       # Бизнес-логика
│   │   └── utils/          # Вспомогательные функции
│   ├── config/
│   │   └── config.py      # Конфигурация
│   └── main.py            # Точка входа
│
├── frontend/               # Клиентская часть (React)
│   ├── src/
│   │   ├── components/    # React-компоненты
│   │   ├── pages/         # Страницы приложения
│   │   ├── context/       # React контексты
│   │   └── utils/         # Вспомогательные функции
│   └── public/
│
└── price-monitor/         # Старая структура (перенесено в корень)
```

## Установка и запуск

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows
pip install -r requirements.txt
python3 main.py 5001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Приложение будет доступно по адресу: `http://localhost:5173`

## Переменные окружения

Создайте файл `.env` в папке `backend/`:

```
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
DATABASE_URL=sqlite:///pricemonitor.db
```

## API Endpoints

### Аутентификация
- `POST /api/auth/register` - Регистрация
- `POST /api/auth/login` - Вход
- `POST /api/auth/refresh` - Обновление токена
- `GET /api/auth/me` - Информация о пользователе

### Анализы
- `GET /api/analysis` - Список анализов
- `POST /api/analysis` - Создание анализа
- `GET /api/analysis/:id` - Детали анализа
- `DELETE /api/analysis/:id` - Удаление анализа

## Особенности

- 🌙 Поддержка темной темы
- 🔐 Безопасная аутентификация (JWT)
- 📊 Визуализация данных (графики)
- 🔍 Автоматический поиск конкурентов
- 📥 Экспорт результатов в Excel
- 🎯 Настройка CSS-селекторов для парсинга

## Лицензия

MIT License
