"""
OryxShield - Production Settings
=========================================

Overrides for Railway (or any cloud) production deployment.

Differences from base.py:
- PostgreSQL (via DATABASE_URL or explicit DB_* vars)
- Redis for cache, sessions, channel layer & Celery
- HTTPS / HSTS / CSP enforced
- WhiteNoise for static files
- Sentry error tracking & performance monitoring
- Strict CORS / CSRF
- JSON-only DRF renderer (no browsable API)
- Argon2 password hashing
- Compressed, cached templates
- Production-grade logging

Required environment variables (see .env.example):
    SECRET_KEY, DATABASE_URL (or DB_*), REDIS_URL,
    ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS,
    EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

Optional but recommended:
    SENTRY_DSN, APP_VERSION
"""

from pathlib import Path
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import dj_database_url
import logging as _logging

from .base import *    # noqa: F401, F403


# =============================================================================
# DEBUG
# =============================================================================

DEBUG = False
TEMPLATE_DEBUG = False


# =============================================================================
# DATABASE  — PostgreSQL
# =============================================================================

_DATABASE_URL = config("DATABASE_URL", default="")

if _DATABASE_URL:
    # Railway / Heroku supply a DATABASE_URL
    DATABASES = {
        "default": dj_database_url.config(
            default=_DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
    DATABASES["default"]["ENGINE"] = "django.db.backends.postgresql"
    DATABASES["default"].update({
        "ATOMIC_REQUESTS": True,
        "DISABLE_SERVER_SIDE_CURSORS": True,   # Required for PgBouncer
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",   # 30 s
            "sslmode": "require",
        },
    })
else:
    # Manual configuration fallback
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT", default=5432, cast=int),
            "ATOMIC_REQUESTS": True,
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "OPTIONS": {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",
                "sslmode": "require",
            },
        }
    }


# =============================================================================
# REDIS
# =============================================================================

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")


# =============================================================================
# CACHE  — Redis
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,   # Degrade gracefully if Redis is down
        },
        "KEY_PREFIX": "oryxshield_prod",
        "TIMEOUT": 300,
    }
}


# =============================================================================
# SESSIONS  — Redis-backed
# =============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"


# =============================================================================
# CELERY  — Redis broker
# =============================================================================

CELERY_BROKER_URL = f"{REDIS_URL}/0"
CELERY_RESULT_BACKEND = "django-db"    # Persist results in PostgreSQL
CELERY_CACHE_BACKEND = "default"

CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fairer task distribution under load
CELERY_WORKER_MAX_TASKS_PER_CHILD = 500
CELERY_TASK_COMPRESSION = "gzip"
CELERY_RESULT_COMPRESSION = "gzip"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,   # 1 hour; prevents premature task requeue
    "max_retries": 3,
}


# =============================================================================
# CHANNELS  — Redis channel layer
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
            "group_expiry": 86400,
        },
    },
}


# =============================================================================
# STORAGE & MEDIA
# =============================================================================

# Railway persistent volume mounted at /app/media
MEDIA_ROOT = config("MEDIA_ROOT", default="/app/media")
MEDIA_URL = "/media/"
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

STATIC_ROOT = config("STATIC_ROOT", default="/app/staticfiles")
STATIC_URL = "/static/"


# =============================================================================
# WHITENOISE  — Efficient static file serving
# =============================================================================

MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MAX_AGE = 31536000   # 1 year (immutable hashed files)
WHITENOISE_ALLOW_ALL_ORIGINS = False
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = [
    "jpg", "jpeg", "png", "gif", "webp",
    "woff", "woff2", "ttf", "eot",
    "zip", "gz", "tgz", "bz2",
    "mp4", "webm",
]


# =============================================================================
# SECURITY HEADERS
# =============================================================================

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv())
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Content Security Policy (tighten after audit)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",) + tuple(
    f"wss://{h}" for h in config("ALLOWED_HOSTS", cast=Csv()) if h not in ("localhost", "127.0.0.1")
) + ("https:",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_BASE_URI = ("'self'",)


# =============================================================================
# CORS  — Strict
# =============================================================================

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv())
CORS_ALLOW_CREDENTIALS = True


# =============================================================================
# EMAIL  — SMTP
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@oryxshield.gov.na")
SERVER_EMAIL = config("SERVER_EMAIL", default="admin@oryxshield.gov.na")

ADMINS = [
    (config("ADMIN_NAME", default="Admin"), config("ADMIN_EMAIL")),
]
MANAGERS = ADMINS


# =============================================================================
# REST FRAMEWORK  — JSON only, strict throttling
# =============================================================================

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
)

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "100/hour",
    "user": "2000/hour",
    "burst": "60/minute",
    "sustained": "1000/hour",
    "high_priority": "10000/hour",
}


# =============================================================================
# JWT  — Short, secure lifetimes
# =============================================================================

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=60)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=1)
SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] = True
SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] = True


# =============================================================================
# PASSWORD HASHERS  — Argon2 first
# =============================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]


# =============================================================================
# TEMPLATE CACHING
# =============================================================================

TEMPLATES[0]["APP_DIRS"] = False
TEMPLATES[0]["OPTIONS"]["loaders"] = [
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    ),
]
TEMPLATES[0]["OPTIONS"]["debug"] = False


# =============================================================================
# FILE UPLOADS
# =============================================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB


# =============================================================================
# LOGGING  — Production (JSON + files + Sentry)
# =============================================================================

LOGGING["handlers"]["console"]["formatter"] = "json"
LOGGING["handlers"]["file"]["formatter"] = "json"
LOGGING["handlers"]["error_file"]["formatter"] = "json"
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["root"]["level"] = "WARNING"


# =============================================================================
# SENTRY  — Error tracking & performance monitoring
# =============================================================================

SENTRY_DSN = config("SENTRY_DSN", default="")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
                signals_spans=True,
                cache_spans=True,
            ),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
            LoggingIntegration(
                level=_logging.INFO,
                event_level=_logging.ERROR,
            ),
        ],
        # Performance
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float),
        profiles_sample_rate=0.05,

        # Error sampling
        sample_rate=1.0,

        # Privacy
        send_default_pii=False,

        # Metadata
        environment="production",
        release=config("APP_VERSION", default="1.0.0"),

        # Filter out noisy errors
        before_send=lambda event, hint: (
            None if event.get("level") == "debug" else event
        ),

        # Ignore specific errors
        ignore_errors=[
            KeyboardInterrupt,
            SystemExit,
        ],
    )


# =============================================================================
# FEATURE FLAGS  — All on (governed by external API credentials)
# =============================================================================

ENABLE_SMS_NOTIFICATIONS = config("ENABLE_SMS_NOTIFICATIONS", default=True, cast=bool)
ENABLE_EMAIL_NOTIFICATIONS = config("ENABLE_EMAIL_NOTIFICATIONS", default=True, cast=bool)
ENABLE_PUSH_NOTIFICATIONS = config("ENABLE_PUSH_NOTIFICATIONS", default=True, cast=bool)
ENABLE_AUTO_ESCALATION = config("ENABLE_AUTO_ESCALATION", default=True, cast=bool)
ENABLE_ML_PREDICTIONS = config("ENABLE_ML_PREDICTIONS", default=True, cast=bool)
ENABLE_GEOSPATIAL_ANALYSIS = config("ENABLE_GEOSPATIAL_ANALYSIS", default=True, cast=bool)
ENABLE_REAL_TIME_ALERTS = config("ENABLE_REAL_TIME_ALERTS", default=True, cast=bool)
ENABLE_TWO_FACTOR_AUTH = config("ENABLE_TWO_FACTOR_AUTH", default=True, cast=bool)
ENABLE_RATE_LIMITING = config("ENABLE_RATE_LIMITING", default=True, cast=bool)
ENABLE_AUDIT_LOGGING = config("ENABLE_AUDIT_LOGGING", default=True, cast=bool)
ENABLE_DHIS2_INTEGRATION = config("ENABLE_DHIS2_INTEGRATION", default=True, cast=bool)
ENABLE_SORMAS_INTEGRATION = config("ENABLE_SORMAS_INTEGRATION", default=True, cast=bool)
ENABLE_WHO_REPORTING = config("ENABLE_WHO_REPORTING", default=True, cast=bool)


# =============================================================================
# DATA RETENTION
# =============================================================================

DATA_RETENTION_DAYS = config("DATA_RETENTION_DAYS", default=365, cast=int)
LOG_RETENTION_DAYS = config("LOG_RETENTION_DAYS", default=90, cast=int)


# =============================================================================
# HEALTH CHECKS
# =============================================================================

HEALTH_CHECK["DISK_USAGE_MAX"] = 85
HEALTH_CHECK["MEMORY_MIN"] = 256


# =============================================================================
# START-UP BANNER
# =============================================================================

import logging as _settings_log
_settings_logger = _settings_log.getLogger("oryxshield.settings")
_banner_width = 78
_settings_logger.info("=" * _banner_width)
_settings_logger.info("ORYXSHIELD — PRODUCTION MODE")
_settings_logger.info("=" * _banner_width)
_settings_logger.info("  Debug           : %s", DEBUG)
_settings_logger.info("  Database        : PostgreSQL (via %s)", 'DATABASE_URL' if config('DATABASE_URL', default='') else 'DB_* vars')
_settings_logger.info("  Cache           : Redis (%s)", REDIS_URL)
_settings_logger.info("  Sessions        : Redis-backed")
_settings_logger.info("  Celery broker   : %s", CELERY_BROKER_URL)
_settings_logger.info("  Channel layer   : Redis")
_settings_logger.info("  Media root      : %s", MEDIA_ROOT)
_settings_logger.info("  Static root     : %s", STATIC_ROOT)
_settings_logger.info("  Sentry          : %s", 'Enabled' if SENTRY_DSN else 'Disabled (set SENTRY_DSN)')
_settings_logger.info("  Allowed hosts   : %s", ALLOWED_HOSTS)
_settings_logger.info("=" * _banner_width)