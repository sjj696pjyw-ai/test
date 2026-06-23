# ---------- Этап 1: сборка фронтенда ----------
FROM node:18-alpine AS frontend
WORKDIR /fe
COPY Price-monitor/price-monitor/frontend/package.json Price-monitor/price-monitor/frontend/package-lock.json ./
RUN npm ci
COPY Price-monitor/price-monitor/frontend/ ./
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

COPY --from=frontend /fe/dist /app/frontend_dist

ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1
ENV FRONTEND_DIST=/app/frontend_dist
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PARSER_USE_SELENIUM=1
ENV ENABLE_SCHEDULER=1
ENV SCHEDULER_LOCK_DIR=/data
ENV COLLECT_MAX_WORKERS=2

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "180", "--graceful-timeout", "30", "--max-requests", "200", "--max-requests-jitter", "40", "main:app"]