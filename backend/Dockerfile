# ─── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps for psycopg2, cryptography, Pillow, lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libssl-dev libffi-dev libxml2-dev libxslt1-dev \
    libjpeg-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages into /home/app/.local (no-cache, user-scope)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ─── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim

# Minimal runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libssl3 && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r django && useradd -r -g django -d /app -s /sbin/nologin django

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/django/.local

# Copy application source (exclude .env, __pycache__, media, etc.)
COPY --chown=django:django . .

# Ensure user-installed packages are on PATH
# DJANGO_SETTINGS_MODULE defaults to production but can be overridden at
# runtime via: docker run -e DJANGO_SETTINGS_MODULE=config.settings.development ...
ARG SETTINGS_MODULE=config.settings.production
ENV PATH=/home/django/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=${SETTINGS_MODULE}

# Collect static files at build time (requires SECRET_KEY to be set via --build-arg)
ARG SECRET_KEY=build-time-placeholder
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

USER django

EXPOSE 8000

# Health check — polls the /health/ endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/')" || exit 1

# Default: Gunicorn ASGI (Daphne for WebSocket support is preferred in production)
CMD ["python", "-m", "gunicorn", \
     "config.asgi:application", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--log-level", "info"]
