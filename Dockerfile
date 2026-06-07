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
    && rm -rf /var/lib/apt/lists/*

COPY Price-monitor/price-monitor/backend/requirements.txt ./
RUN pip install --no-cache-dir -i https://pypi.org/simple -r requirements.txt

COPY Price-monitor/price-monitor/backend/ ./

# Собранный фронт кладём рядом, Flask его раздаёт
COPY --from=frontend /fe/dist /app/frontend_dist

ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1
ENV FRONTEND_DIST=/app/frontend_dist

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]