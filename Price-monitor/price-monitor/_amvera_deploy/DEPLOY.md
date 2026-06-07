# Деплой на Amvera — одно приложение (фронт + бэкенд вместе)

Один Docker-образ: на этапе сборки собирается фронтенд (Vite), затем тот же
бэкенд (gunicorn/Flask) раздаёт собранную статику и обслуживает `/api`.
Фронт и API — на одном домене, поэтому `VITE_API_URL` и CORS не нужны
(в `api.js` baseURL = `/api`).

Файлы подготовлены под структуру, где **корень git-репозитория — родитель папки
`Price-monitor-develop 3`**, а код в `Price-monitor-develop 3/price-monitor/...`.

## Что сделать

1. Переместить в **корень репозитория** (рядом с `.git`):
   - `amvera.yml`
   - `Dockerfile`
2. Удалить из корня лишнее, чтобы не путалось:
   - старый `amvera.yaml` (иначе конфликт двух конфигов Amvera),
   - `Dockerfile.frontend`, `docker-compose.yml`, `cloud.yml` — для этого
     варианта не нужны (можно оставить, но они не используются).
3. `git add . && git commit && git push amvera <branch>`.

## Переменные окружения (в панели Amvera)

```
FLASK_ENV=production
SECRET_KEY=<случайная строка>        # python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=<случайная строка>    # сгенерировать отдельно
DATABASE_URL=sqlite:////data/pricemonitor.db
```
(4 слэша = абсолютный путь к тому `/data`; база переживает пересборки.)

`FRONTEND_DIST` задавать НЕ нужно — он уже прописан в Dockerfile
(`/app/frontend_dist`).

## Как это работает

- `GET /` и любые клиентские маршруты (например `/dashboard`) → отдаётся
  `index.html` (SPA).
- статика (`/assets/...`) → раздаётся Flask из `frontend_dist`.
- `GET/POST /api/...` → обрабатывает бэкенд.
- порт 5000, постоянный том `/data` (для SQLite).

## Рекомендация

Пробел и « 3» в `Price-monitor-develop 3` делают пути `COPY` хрупкими (нужна
JSON-форма). Чище — переименовать корневую папку без пробела ИЛИ сделать корнем
репозитория саму `price-monitor/`; тогда в Dockerfile пути упростятся до
`COPY backend/...` и `COPY frontend/...`.
