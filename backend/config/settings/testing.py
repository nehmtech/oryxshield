"""
OryxShield - Testing Settings
=======================================

Inherits from base.py. Optimised for fast, hermetic, deterministic tests.

Key differences:
- In-memory SQLite (no migrations, no disk I/O)
- MD5 password hasher (fast hashing)
- Memory email backend (inspect django.test.utils.mail.outbox)
- Dummy cache (consistent, no Redis)
- Eager Celery (synchronous, no workers)
- In-memory channel layer (no Redis)
- Minimal logging (only ERRORs)
- All external services disabled & mocked
- Temporary media directory (cleaned up after test run)
- Migrations disabled (schema created from models directly)

Usage:
    # pytest (recommended)
    DJANGO_SETTINGS_MODULE=config.settings.testing pytest

    # Django test runner
    python manage.py test --settings=config.settings.testing
"""

import atexit
import shutil
import tempfile
import warnings
from pathlib import Path

from .base import *   # noqa: F401, F403


# =============================================================================
# DEBUG
# =============================================================================

DEBUG = True            # So exceptions propagate cleanly
TEMPLATE_DEBUG = True


# =============================================================================
# DATABASE  — In-memory SQLite (fastest possible)
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "ATOMIC_REQUESTS": True,
    }
}


# =============================================================================
# PASSWORD HASHERS  — MD5 is fast; never use in production
# =============================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# =============================================================================
# EMAIL  — Memory backend (inspect via django.test.utils.mail.outbox)
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


# =============================================================================
# CACHE  — Dummy (deterministic, no Redis)
# =============================================================================

CACHES = {
    "default": {
        # LocMemCache instead of DummyCache so 2FA session tokens, OTPs,
        # and rate-limit keys are stored in memory during test runs.
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


# =============================================================================
# CELERY  — Eager (synchronous, tasks run inline)
# =============================================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"


# =============================================================================
# CHANNELS  — In-memory channel layer
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


# =============================================================================
# SECURITY  — Relaxed (not relevant in tests)
# =============================================================================

ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0


# =============================================================================
# STATIC FILES
# =============================================================================

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


# =============================================================================
# MEDIA FILES  — Temporary directory (auto-cleaned)
# =============================================================================

MEDIA_ROOT = tempfile.mkdtemp()


def _cleanup_test_media():
    """Remove temporary test media directory on exit."""
    try:
        if Path(MEDIA_ROOT).exists():
            shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
    except Exception:
        pass


atexit.register(_cleanup_test_media)


# =============================================================================
# MIGRATIONS  — Disabled (create schema from models; much faster)
# =============================================================================

class DisableMigrations:
    """Treat every app as having no migrations."""

    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str):
        return None


MIGRATION_MODULES = DisableMigrations()


# =============================================================================
# LOGGING  — Silence everything except errors
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "ERROR",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "celery": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}


# =============================================================================
# REST FRAMEWORK  — No throttling in tests
# =============================================================================

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}
REST_FRAMEWORK["TEST_REQUEST_DEFAULT_FORMAT"] = "json"
REST_FRAMEWORK["TEST_REQUEST_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
]


# =============================================================================
# JWT  — Long-lived tokens for test convenience
# =============================================================================

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=1)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=7)


# =============================================================================
# FEATURE FLAGS  — Disable anything that would call external services
# =============================================================================

ENABLE_SMS_NOTIFICATIONS = False
ENABLE_EMAIL_NOTIFICATIONS = False     # Use locmem backend; don't call SMTP
ENABLE_PUSH_NOTIFICATIONS = False
ENABLE_ML_PREDICTIONS = False          # Avoid slow model loading
ENABLE_DHIS2_INTEGRATION = False
ENABLE_SORMAS_INTEGRATION = False
ENABLE_WHO_REPORTING = False
ENABLE_TWO_FACTOR_AUTH = False         # Simpler auth in tests
ENABLE_RATE_LIMITING = False


# =============================================================================
# FILE UPLOADS
# =============================================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024   # 100 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024   # 100 MB


# =============================================================================
# DATA RETENTION
# =============================================================================

DATA_RETENTION_DAYS = 7
LOG_RETENTION_DAYS = 1


# =============================================================================
# MOCK EXTERNAL SERVICES  — Safe test credentials / URLs
# =============================================================================

# Africa's Talking
AFRICASTALKING_USERNAME = "sandbox"
AFRICASTALKING_API_KEY = "test-africastalking-api-key"

# Twilio
TWILIO_ACCOUNT_SID = "ACtest-twilio-account-sid"
TWILIO_AUTH_TOKEN = "test-twilio-auth-token"
TWILIO_PHONE_NUMBER = "+15005550006"  # Twilio magic test number

# DHIS2
DHIS2_BASE_URL = "http://test-dhis2.example.local"
DHIS2_USERNAME = "admin"
DHIS2_PASSWORD = "district"

# SORMAS
SORMAS_BASE_URL = "http://test-sormas.example.local"
SORMAS_API_KEY = "test-sormas-api-key"

# WHO
WHO_API_KEY = "test-who-api-key"
WHO_API_BASE_URL = "http://test-who.example.local/"

# Africa CDC
AFRICA_CDC_API_KEY = "test-africa-cdc-api-key"
AFRICA_CDC_API_BASE_URL = "http://test-africacdc.example.local/"

# Geospatial
MAPBOX_ACCESS_TOKEN = "pk.test_mapbox_token"
GOOGLE_MAPS_API_KEY = "test-google-maps-key"

# Sentry (disabled in tests)
SENTRY_DSN = ""


# =============================================================================
# TEST RUNNER & FIXTURES
# =============================================================================

TEST_RUNNER = "django.test.runner.DiscoverRunner"

FIXTURE_DIRS = [
    BASE_DIR / "tests" / "fixtures",
]

# Factory Boy
FAKER_LOCALE = "en_US"

# Coverage (supplement .coveragerc)
COVERAGE_MODULE_EXCLUDES = [
    "tests$", "settings$", "urls$", "locale$",
    "migrations", "fixtures", "admin$",
]


# =============================================================================
# HELPERS  — Flags that test code can check
# =============================================================================

TESTING = True
IS_TESTING = True


# =============================================================================
# SUPPRESS DEPRECATION WARNINGS
# =============================================================================

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="django.utils.deprecation",
)
warnings.filterwarnings(
    "ignore",
    message="No directory at",
    category=UserWarning,
)


# =============================================================================
# START-UP BANNER
# =============================================================================

_banner_width = 78
print("=" * _banner_width)
print("🧪  ORYXSHIELD — TESTING MODE")
print("=" * _banner_width)
print(f"  Database        : In-memory SQLite")
print(f"  Migrations      : Disabled (schema from models)")
print(f"  Email           : Memory backend")
print(f"  Cache           : Dummy")
print(f"  Celery          : Eager / synchronous")
print(f"  Channels        : In-Memory")
print(f"  External APIs   : Mocked")
print(f"  Media root      : {MEDIA_ROOT} (temp, auto-cleaned)")
print("=" * _banner_width)
print("  Run tests:")
print("    pytest")
print("    pytest tests/test_surveillance.py -v")
print("    pytest --cov=. --cov-report=html")
print("    pytest -n auto   (parallel)")
print("=" * _banner_width)
print()