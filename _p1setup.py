import os
import sys

# ============================================================================
# Phase 1 Master Setup Script
# Writes all required files for Phase 1 blocker clearance
# ============================================================================

def w(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# FILE 1: Dockerfile.local (BOOT-005 fix)
w('Dockerfile.local', '''FROM python:3.9-slim-bullseye
LABEL version=1.9.0-local
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc curl procps && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash sovereign
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY database/ ./database/
COPY scripts/ ./scripts/
COPY services/ ./services/
COPY data_ingestion/ ./data_ingestion/
COPY jobs/ ./jobs/
COPY tools/ ./tools/
COPY main.py ./main.py
RUN mkdir -p /app/logs /app/data && chown -R sovereign:sovereign /app
USER sovereign
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=5 CMD curl -f http://localhost:8080/health || exit 1
CMD [\\ uvicorn\\, \app.main:app\\, \\--host\\, \0.0.0.0\\, \\--port\\, \\8080\\, \\--workers\\, \1\\, \\--log-level\\, \\info\\]
''')

