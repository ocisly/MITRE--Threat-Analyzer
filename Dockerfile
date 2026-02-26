# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
# VITE_BACKEND_URL is empty — frontend is served from the same origin as the API,
# so all fetch calls use relative paths (same as local Vite proxy mode).
RUN npm run build


# ── Stage 2: Production Python image ──────────────────────────────────────
FROM python:3.11-slim

# ── System packages: ODBC Driver 18 for SQL Server (Azure SQL) ─────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
       https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ──────────────────────────────────────────────────────────
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# ── Python dependencies (cached layer) ────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────
COPY app/ ./app/

# ── Frontend build output (served by FastAPI StaticFiles) ──────────────────
COPY --from=frontend-builder /frontend/dist ./dist

# ── Runtime directories (STIX cache; DB only used for SQLite dev) ──────────
RUN mkdir -p data/stix && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# 1 Uvicorn worker -- avoids lifespan race condition during initial MITRE sync.
# The app is async/I-O-bound so a single worker handles concurrent requests fine.
# Timeout 120s covers LLM streaming responses.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
