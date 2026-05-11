FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/domain-admin-master/requirements/production.txt /tmp/requirements-production.txt
COPY all4win/requirements-server.txt /tmp/requirements-all4win.txt

RUN pip install --upgrade pip setuptools wheel gunicorn \
    && pip install -r /tmp/requirements-production.txt \
    && pip install -r /tmp/requirements-all4win.txt

COPY server/domain-admin-master /app/server/domain-admin-master
COPY all4win /app/all4win
COPY --from=frontend-builder /frontend/dist /app/server/domain-admin-master/public

WORKDIR /app/server/domain-admin-master

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "domain_admin.main:app"]
