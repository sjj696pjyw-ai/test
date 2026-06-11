# ---------- Этап 1: сборка фронтенда ----------
FROM node:18-alpine AS frontend
WORKDIR /fe
COPY Price-monitor/price-monitor/frontend/package.json Price-monitor/price-monitor/frontend/package-lock.json ./
RUN npm ci
COPY Price-monitor/price-monitor/frontend/ ./
# VITE_API_URL не задаём — фронт и API на одном домене, baseURL = '/api'
RUN npm run build

# ---------- Этап 2: бэкенд + раздача фронта ----------
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    chromium \
    chromium-driver \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY Price-monitor/price-monitor/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY Price-monitor/price-monitor/backend/ ./

# Собранный фронт кладём рядом, Flask его раздаёт
COPY --from=frontend /fe/dist /app/frontend_dist

ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1
ENV FRONTEND_DIST=/app/frontend_dist
# Браузер для Selenium (парсинг JS-сайтов с прокруткой)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
# Отключить Selenium и работать только через requests можно так: PARSER_USE_SELENIUM=0
ENV PARSER_USE_SELENIUM=1

EXPOSE 5000

# --timeout 180: Selenium-сбор (прокрутка/пагинация) может идти дольше дефолтных
#   30 с — иначе gunicorn убивает воркера SIGKILL'ом посреди сессии и Chrome
#   остаётся висеть (утечка памяти).
# --graceful-timeout 30 + --max-requests: периодически перезапускаем воркеров,
#   чтобы подчистить возможные осиротевшие процессы/память браузера.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "180", "--graceful-timeout", "30", "--max-requests", "200", "--max-requests-jitter", "40", "main:app"]