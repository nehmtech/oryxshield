"""
OryxShield - Development Settings
==========================================

Overrides for local development. Inherits everything from base.py.

Key differences from production:
- SQLite database (no PostgreSQL required)
- Debug Toolbar + Browser Reload
- Console email backend
- Dummy cache (no Redis required by default)
- Eager Celery (no workers / Redis required)
- In-memory channel layer (no Redis required)
- CORS / HTTPS relaxed
- Browsable DRF API enabled
- Longer JWT lifetimes
- Verbose logging
- All external integrations disabled by default

Usage:
    export DJANGO_SETTINGS_MODULE=config.settings.development
    python manage.py runserver
"""

import socket
import sys
from .base import *

# =============================================================================
# DEBUG
# =============================================================================

DEBUG = True
TEMPLATE_DEBUG = True


# =============================================================================
# DATABASE  — SQLite (zero-config)
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "ATOMIC_REQUESTS": True,
    }
}

# If you want to test with PostgreSQL locally, uncomment and fill in:
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": config("DB_NAME", default="oryxshield_dev"),
#         "USER": config("DB_USER", default="postgres"),
#         "PASSWORD": config("DB_PASSWORD", default="password"),
#         "HOST": config("DB_HOST", default="localhost"),
#         "PORT": config("DB_PORT", default=5432, cast=int),
#         "ATOMIC_REQUESTS": True,
#     }
# }


# =============================================================================
# INSTALLED APPS — Development extras
# =============================================================================

INSTALLED_APPS += [
    "django_extensions",        # shell_plus, runserver_plus, graph_models, etc.
    "debug_toolbar",            # SQL / cache / template profiling
    "django_browser_reload",    # Live browser reload
]


# =============================================================================
# MIDDLEWARE — Development extras
# =============================================================================

# Debug Toolbar must come just after CommonMiddleware
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,
    "debug_toolbar.middleware.DebugToolbarMiddleware",
)
# Browser reload at the very end
MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")


# =============================================================================
# EMAIL  — Print to console, no SMTP needed
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# =============================================================================
# CACHE  — Dummy (no Redis required)
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# If Redis is running locally, swap to this instead:
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://localhost:6379/1",
#         "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#     }
# }


# =============================================================================
# CELERY  — Eager (synchronous, no Redis / workers needed)
# =============================================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

CELERY_BEAT_SCHEDULE = {
    "run_anomaly_detection": {
        "task": "surveillance.tasks.run_anomaly_detection",
        "schedule": 60,  # every 1 min in dev (5 min in prod)
    },
    "identify_case_clusters": {
        "task": "surveillance.tasks.identify_case_clusters",
        "schedule": 120,
    },
    "detect_hotspots": {
        "task": "surveillance.tasks.detect_hotspots",
        "schedule": 180,
    },
    "calculate_all_risk_scores": {
        "task": "risk_assessment.tasks.calculate_all_risk_scores",
        "schedule": 60,
    },
    "check_thresholds": {
        "task": "risk_assessment.tasks.check_thresholds",
        "schedule": 60,
    },
    "generate_alerts_from_anomalies": {
        "task": "risk_assessment.tasks.generate_alerts_from_anomalies",
        "schedule": 60,
    },
    "auto_acknowledge_expired_alerts": {
        "task": "risk_assessment.tasks.auto_acknowledge_expired_alerts",
        "schedule": 300,
    },
    "check_escalation_triggers": {
        "task": "response.tasks.check_escalation_triggers",
        "schedule": 60,
    },
    "check_overdue_actions": {
        "task": "response.tasks.check_overdue_actions",
        "schedule": 300,
    },
    "update_response_progress": {
        "task": "response.tasks.update_response_progress",
        "schedule": 120,
    },
}


# =============================================================================
# CHANNELS  — In-Memory (no Redis needed)
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Real WebSocket testing — use Redis:
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {"hosts": [("localhost", 6379)]},
#     }
# }


# =============================================================================
# SECURITY  — Relaxed for localhost
# =============================================================================

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = None

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8000",
]


# =============================================================================
# STATIC FILES
# =============================================================================

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


# =============================================================================
# REST FRAMEWORK  — Browsable API + no throttling
# =============================================================================

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}


# =============================================================================
# JWT  — Longer token lifetimes for convenience
# =============================================================================

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=1)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=14)


# =============================================================================
# SESSION
# =============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"


# =============================================================================
# PASSWORD HASHERS  — MD5 for speed; NEVER in production
# =============================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# =============================================================================
# DEBUG TOOLBAR
# =============================================================================

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "SHOW_COLLAPSED": True,
    "ENABLE_STACKTRACES": True,
}

# Include Docker-internal gateway IPs so toolbar shows inside containers
INTERNAL_IPS = ["127.0.0.1", "localhost", "::1"]
try:
    _hostname, _, _ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [ip[:-1] + "1" for ip in _ips if ip.endswith(".")]
except Exception:
    pass


# =============================================================================
# SHELL PLUS (django-extensions)
# =============================================================================

SHELL_PLUS_PRINT_SQL = True
SHELL_PLUS_PRINT_SQL_TRUNCATE = 1000

SHELL_PLUS_PRE_IMPORTS = [
    ("datetime", ("datetime", "timedelta", "date")),
    ("json", ("dumps", "loads")),
    ("pprint", "pprint"),
    ("uuid", "uuid4"),
]

NOTEBOOK_ARGUMENTS = [
    "--ip", "0.0.0.0",
    "--port", "8888",
    "--allow-root",
    "--no-browser",
]


# =============================================================================
# RUNSERVER PLUS (django-extensions)
# =============================================================================

RUNSERVERPLUS_SERVER_ADDRESS_PORT = "0.0.0.0:8000"


# =============================================================================
# LOGGING  — Verbose in development
# =============================================================================

LOGGING["root"]["level"] = "DEBUG"
LOGGING["handlers"]["console"]["level"] = "DEBUG"
LOGGING["loggers"]["django"]["level"] = "DEBUG"

# Show SQL queries in the console (very verbose — toggle as needed)
# LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"

# Replace RotatingFileHandler with NullHandler for file-based handlers.
# On Windows, RotatingFileHandler raises PermissionError (WinError 32) when
# it tries to rename an open log file during rotation. Console output
# (already at DEBUG above) captures everything needed in development.
for _h in ("file", "error_file", "security_file", "celery_file"):
    LOGGING["handlers"][_h] = {"class": "logging.NullHandler"}


# =============================================================================
# FILE UPLOADS  — Relaxed limits for testing
# =============================================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024   # 100 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024   # 100 MB


# =============================================================================
# FEATURE FLAGS  — All on except those that need real credentials
# =============================================================================

ENABLE_AUTO_ESCALATION = True
ENABLE_ML_PREDICTIONS = True
ENABLE_REAL_TIME_ALERTS = True
ENABLE_GEOSPATIAL_ANALYSIS = True
ENABLE_TWO_FACTOR_AUTH = False        # Easier local login
ENABLE_RATE_LIMITING = False          # No throttle while developing
ENABLE_AUDIT_LOGGING = True

ENABLE_DHIS2_INTEGRATION = False
ENABLE_SORMAS_INTEGRATION = False
ENABLE_WHO_REPORTING = False

ENABLE_SMS_NOTIFICATIONS = False      # Requires real API keys
ENABLE_PUSH_NOTIFICATIONS = False


# =============================================================================
# EXTERNAL SERVICES  — Disabled; use sandbox/test credentials
# =============================================================================

AFRICASTALKING_USERNAME = "sandbox"
AFRICASTALKING_API_KEY = "dev-africastalking-api-key"

TWILIO_ACCOUNT_SID = "dev-twilio-account-sid"
TWILIO_AUTH_TOKEN = "dev-twilio-auth-token"

DHIS2_BASE_URL = "https://play.dhis2.org/dev"
DHIS2_USERNAME = "admin"
DHIS2_PASSWORD = "district"


# =============================================================================
# DATA RETENTION  — Short for development
# =============================================================================

DATA_RETENTION_DAYS = 30
LOG_RETENTION_DAYS = 7


# =============================================================================
# SYSTEM CHECKS  — Silence irrelevant warnings
# =============================================================================

SILENCED_SYSTEM_CHECKS = [
    "security.W004",   # SECURE_HSTS_SECONDS
    "security.W008",   # SECURE_SSL_REDIRECT
    "security.W012",   # SESSION_COOKIE_SECURE
    "security.W016",   # CSRF_COOKIE_SECURE
]


# =============================================================================
# START-UP BANNER
# =============================================================================

_banner_width = 78
print("=" * _banner_width)
print("ORYXSHIELD - DEVELOPMENT MODE")
print("=" * _banner_width)
print(f"  Debug           : {DEBUG}")
print(f"  Database        : SQLite ({DATABASES['default']['NAME']})")
print(f"  Email           : Console (no SMTP)")
print(f"  Cache           : Dummy (no Redis)")
print(f"  Celery          : Eager / synchronous (no workers)")
print(f"  Channels        : In-Memory (no Redis)")
print(f"  CORS            : Allow ALL origins")
print(f"  Throttling      : Disabled")
print(f"  2FA             : Disabled")
print()
print(f"  Admin           : http://localhost:8000/admin/")
print(f"  API Docs        : http://localhost:8000/api/docs/")
print(f"  ReDoc           : http://localhost:8000/api/redoc/")
print(f"  Debug Toolbar   : Enabled (GET param ?debug=1 not needed)")
print("=" * _banner_width)
print("  Quick commands:")
print("    python manage.py runserver")
print("    python manage.py shell_plus")
print("    python manage.py createsuperuser")
print("    python manage.py makemigrations && python manage.py migrate")
print("    pytest  OR  python manage.py test")
print("=" * _banner_width)
print()