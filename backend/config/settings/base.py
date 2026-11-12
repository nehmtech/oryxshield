"""
OryxShield - Base Settings
====================================

Common settings shared by ALL environments (development, production, testing).
Environment-specific files MUST import from this module:

    from .base import *

Do NOT put secrets or environment-specific overrides here.
All sensitive values are read from environment variables via python-decouple.
"""

from pathlib import Path
from datetime import timedelta
import os
from decouple import config, Csv

# =============================================================================
# PATHS
# =============================================================================

# Root of the Django project (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Persistent runtime directories - created if they don't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ML_MODELS_DIR = BASE_DIR / "ml_models"
ML_MODELS_DIR.mkdir(exist_ok=True)


# =============================================================================
# CORE SECURITY
# =============================================================================

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-local-dev-only-NEVER-use-in-production",
)
# Warn loudly if using the insecure default key
if SECRET_KEY == "django-insecure-local-dev-only-NEVER-use-in-production":
    import warnings
    warnings.warn(
        "Django SECRET_KEY is set to the insecure default. "
        "Set a strong random SECRET_KEY environment variable before any real deployment.",
        stacklevel=2,
    )

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())


# =============================================================================
# INSTALLED APPS
# =============================================================================

INSTALLED_APPS = [
    # Daphne MUST be first to enable ASGI / WebSocket support
    "daphne",

    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # "django.contrib.gis",       # Uncomment when PostGIS is available
    # "django.contrib.postgres",  # Uncomment in production with PostgreSQL

    # --- REST API ---
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",

    # --- Real-time & Async ---
    "channels",
    "django_celery_beat",
    "django_celery_results",

    # --- Auth & Permissions ---
    "guardian",          # Object-level permissions
    "django_otp",        # Two-factor authentication (base)
    "django_otp.plugins.otp_totp",   # TOTP (Google Authenticator)
    "django_otp.plugins.otp_email",  # Email OTP fallback

    # --- Social Auth ---
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.twitter_oauth2",
    "allauth.socialaccount.providers.github",

    # --- Utilities ---
    "import_export",      # CSV / XLS data import-export via admin
    "django_cleanup",     # Auto-delete orphaned media files
    "phonenumber_field",  # Phone number model field

    # --- Health checks ---
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
    "health_check.contrib.migrations",
    "health_check.contrib.celery",
    "health_check.contrib.redis",

    # --- OryxShield apps ---
    "core",
    "surveillance",
    "risk_assessment",
    "response",
    "coordination",
    "resources",
    "communications",
    "analytics",
    "operations",
    "mobile",
    "integrations",
    "websockets",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    # 1. Security (must be first)
    "django.middleware.security.SecurityMiddleware",

    # 2. CORS (before any middleware that generates a response)
    "corsheaders.middleware.CorsMiddleware",

    # 3. Session
    "django.contrib.sessions.middleware.SessionMiddleware",

    # 4. Common
    "django.middleware.common.CommonMiddleware",

    # 5. CSRF
    "django.middleware.csrf.CsrfViewMiddleware",

    # 6. Auth
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # 7. OTP / 2FA (must be after AuthenticationMiddleware)
    "django_otp.middleware.OTPMiddleware",

    # 8. Messages
    "django.contrib.messages.middleware.MessageMiddleware",

    # 9. Clickjacking
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # 10. Allauth
    "allauth.account.middleware.AccountMiddleware",

    # 11. Custom middleware
    "core.middleware.RequestSizeLimitMiddleware", # Reject oversized payloads early
    "core.middleware.CorrelationIdMiddleware",    # Adds X-Correlation-ID header
    "core.middleware.RequestTimingMiddleware",    # Logs request duration
    "core.middleware.AuditLoggingMiddleware",     # Audit trail for write operations
    "core.middleware.ExceptionLoggingMiddleware",
    "core.middleware.RateLimitMiddleware",
]


# =============================================================================
# URL / WSGI / ASGI
# =============================================================================

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
            ],
        },
    },
]


# =============================================================================
# DATABASE  (overridden in each environment)
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "ATOMIC_REQUESTS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASE_ROUTERS: list = []


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "core.validators.StrongPasswordValidator",
        "OPTIONS": {
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": True,
        },
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]


# =============================================================================
# INTERNATIONALISATION
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="Africa/Windhoek")
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("en",  "English"),
    ("af",  "Afrikaans"),
    ("ng",  "Oshiwambo"),
    ("naq", "Damara/Nama"),
    ("hz",  "Herero"),
    ("kav", "Kavango"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]


# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = config("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

ALLOWED_UPLOAD_EXTENSIONS = [
    # Documents
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
    # Images
    "jpg", "jpeg", "png", "gif", "svg", "webp",
    # Data
    "json", "xml", "geojson",
    # Archives (for bulk data import)
    "zip",
]


# =============================================================================
# AUTHENTICATION & SESSIONS
# =============================================================================

# Swap in core.User once the model is ready:
# AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400          # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False       # Enabled in production.py

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False          # Enabled in production.py
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"


# =============================================================================
# DJANGO ALLAUTH  (Social Auth)
# =============================================================================

SITE_ID = 1

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_RATE_LIMITS = {'login_failed': '5/5m'}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True


SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_QUERY_EMAIL = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": config("GOOGLE_CLIENT_ID", default=""),
            "secret": config("GOOGLE_CLIENT_SECRET", default=""),
            "key": "",
        },
    },
    "facebook": {
        "METHOD": "oauth2",
        "SCOPE": ["email", "public_profile"],
        "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        "FIELDS": ["id", "email", "name", "first_name", "last_name", "verified"],
        "EXCHANGE_TOKEN": True,
        "VERIFIED_EMAIL": False,
        "VERSION": "v18.0",
        "APP": {
            "client_id": config("FACEBOOK_CLIENT_ID", default=""),
            "secret": config("FACEBOOK_CLIENT_SECRET", default=""),
            "key": "",
        },
    },
    "twitter_oauth2": {
        "APP": {
            "client_id": config("TWITTER_CLIENT_ID", default=""),
            "secret": config("TWITTER_CLIENT_SECRET", default=""),
        },
    },
    "github": {
        "SCOPE": ["user", "user:email"],
        "APP": {
            "client_id": config("GITHUB_CLIENT_ID", default=""),
            "secret": config("GITHUB_CLIENT_SECRET", default=""),
        },
    },
}


# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    # Authentication
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # Admin
    ),

    # Permissions
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    # Filtering
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),

    # Pagination
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CustomCursorPagination",
    "PAGE_SIZE": 20,
    "MAX_PAGE_SIZE": 200,

    # Rendering
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),

    # Parsing
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),

    # Throttling
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("API_THROTTLE_RATE_ANON", default="100/hour"),
        "user": config("API_THROTTLE_RATE_USER", default="1000/hour"),
        "burst": config("API_THROTTLE_RATE_BURST", default="60/minute"),
        "sustained": config("API_THROTTLE_RATE_SUSTAINED", default="1000/hour"),
        "high_priority": config("API_THROTTLE_RATE_HIGH", default="10000/hour"),
    },

    # Versioning
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],

    # Schema
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    # Exception handling
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",

    # Content negotiation
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "rest_framework.negotiation.DefaultContentNegotiation",

    # Date/time format (ISO-8601 UTC)
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%fZ",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",

    # Testing
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "TEST_REQUEST_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}


# =============================================================================
# SIMPLE JWT
# =============================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_REFRESH_TOKEN_LIFETIME", default=1440, cast=int)  # 24 h
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,

    "ALGORITHM": config("JWT_ALGORITHM", default="HS256"),
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": "oryxshield",

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}


# =============================================================================
# CORS
# =============================================================================

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    cast=Csv(),
)
CORS_ALLOW_ALL_ORIGINS = False  # True only in development.py
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-correlation-id",
]

CORS_EXPOSE_HEADERS = [
    "content-disposition",
    "x-correlation-id",
]


# =============================================================================
# DJANGO GUARDIAN
# =============================================================================

GUARDIAN_RAISE_403 = True
GUARDIAN_RENDER_403 = False
GUARDIAN_TEMPLATE_403 = "403.html"
ANONYMOUS_USER_NAME = None


# =============================================================================
# CELERY
# =============================================================================

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60       # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 min soft limit
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 3600 * 24 * 7  # 7 days

CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_SEND_TASK_ERROR_EMAILS = True

# Store Celery results in Django database
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"


# =============================================================================
# DJANGO CHANNELS (WebSockets)
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(
                config("REDIS_HOST", default="localhost"),
                config("REDIS_PORT", default=6379, cast=int),
            )],
            "capacity": 1500,
            "expiry": 10,
            "group_expiry": 86400,   # 24 h
        },
    },
}


# =============================================================================
# CACHE
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": (
            f"redis://{config('REDIS_HOST', default='localhost')}"
            f":{config('REDIS_PORT', default=6379, cast=int)}/1"
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": False,  # Raise in non-production
        },
        "KEY_PREFIX": "oryxshield",
        "TIMEOUT": 300,  # 5 minutes default TTL
    }
}

CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = "mw"


# =============================================================================
# EMAIL
# =============================================================================

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@oryxshield.gov.na")
SERVER_EMAIL = config("SERVER_EMAIL", default="admin@oryxshield.gov.na")

ADMINS = [
    (config("ADMIN_NAME", default="Admin"), config("ADMIN_EMAIL", default="admin@oryxshield.gov.na")),
]
MANAGERS = ADMINS


# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} [{module}] pid={process:d} tid={thread:d} | {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} | {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s %(correlation_id)s",
        },
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "oryxshield.log"),
            "maxBytes": 1024 * 1024 * 15,  # 15 MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "errors.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "security.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "celery_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "celery.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "include_html": True,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["error_file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["security_file", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        # OryxShield app loggers
        "core":           {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "surveillance":   {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "risk_assessment":{"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "response":       {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "coordination":   {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "resources":      {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "communications": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "analytics":      {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "operations":     {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "mobile":         {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "integrations":   {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}


# =============================================================================
# DRF SPECTACULAR (OpenAPI docs)
# =============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "OryxShield API",
    "DESCRIPTION": (
        "Automated Pandemic Response & Health Surveillance System\n\n"
        "**Base URL:** `/api/v1/`\n\n"
        "**Authentication:** JWT Bearer tokens via `/api/v1/auth/token/`\n\n"
        "All endpoints require `Authorization: Bearer <access_token>` unless noted."
    ),
    "VERSION": config("APP_VERSION", default="1.0.0"),
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "SERVE_AUTHENTICATION": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "displayRequestDuration": True,
        "filter": True,
    },
    "SWAGGER_UI_OAUTH2_CONFIG": {},
    "SORT_OPERATIONS": True,
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "TAGS": [
        {"name": "auth",            "description": "Authentication & token management"},
        {"name": "surveillance",    "description": "Real-time health surveillance & anomaly detection"},
        {"name": "risk",            "description": "Risk scoring & alert management"},
        {"name": "response",        "description": "Tiered response activation & escalation"},
        {"name": "coordination",    "description": "Multi-agency coordination & RBAC"},
        {"name": "resources",       "description": "Inventory, facilities & supply chain"},
        {"name": "communications",  "description": "Public alerts & multi-channel messaging"},
        {"name": "analytics",       "description": "Epidemiological models & reporting"},
        {"name": "operations",      "description": "Contact tracing, quarantine & vaccination"},
        {"name": "mobile",          "description": "Mobile-optimised & field operation endpoints"},
        {"name": "integrations",    "description": "External system connectors (DHIS2, WHO, etc.)"},
        {"name": "health",          "description": "System health & readiness probes"},
    ],
}


# =============================================================================
# SMS GATEWAYS
# =============================================================================

# Africa's Talking
AFRICASTALKING_USERNAME = config("AFRICASTALKING_USERNAME", default="sandbox")
AFRICASTALKING_API_KEY = config("AFRICASTALKING_API_KEY", default="")
AFRICASTALKING_SENDER_ID = config("AFRICASTALKING_SENDER_ID", default="ORYXSHIELD")

# Twilio
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="")

# Infobip
INFOBIP_API_KEY = config("INFOBIP_API_KEY", default="")
INFOBIP_BASE_URL = config("INFOBIP_BASE_URL", default="")


# =============================================================================
# PUSH NOTIFICATIONS
# =============================================================================

# Firebase Cloud Messaging (FCM v1 via Admin SDK recommended)
FCM_SERVER_KEY = config("FCM_SERVER_KEY", default="")
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_PROJECT_ID = config("FIREBASE_PROJECT_ID", default="")

# Apple Push Notification Service
APNS_CERTIFICATE_PATH = config("APNS_CERTIFICATE_PATH", default="")
APNS_KEY_ID = config("APNS_KEY_ID", default="")
APNS_TEAM_ID = config("APNS_TEAM_ID", default="")
APNS_BUNDLE_ID = config("APNS_BUNDLE_ID", default="com.oryxshield.app")


# =============================================================================
# EXTERNAL API INTEGRATIONS
# =============================================================================

# DHIS2
DHIS2_BASE_URL = config("DHIS2_BASE_URL", default="https://play.dhis2.org/dev")
DHIS2_USERNAME = config("DHIS2_USERNAME", default="")
DHIS2_PASSWORD = config("DHIS2_PASSWORD", default="")
DHIS2_TIMEOUT = 30  # seconds

# SORMAS
SORMAS_BASE_URL = config("SORMAS_BASE_URL", default="")
SORMAS_API_KEY = config("SORMAS_API_KEY", default="")

# WHO
WHO_API_KEY = config("WHO_API_KEY", default="")
WHO_API_BASE_URL = config("WHO_API_BASE_URL", default="https://extranet.who.int/eios/")

# Africa CDC
AFRICA_CDC_API_KEY = config("AFRICA_CDC_API_KEY", default="")
AFRICA_CDC_API_BASE_URL = config("AFRICA_CDC_API_BASE_URL", default="")

# Laboratory Information System
LIS_BASE_URL = config("LIS_BASE_URL", default="")
LIS_API_KEY = config("LIS_API_KEY", default="")

# Electronic Medical Records
EMR_BASE_URL = config("EMR_BASE_URL", default="")
EMR_API_KEY = config("EMR_API_KEY", default="")

# OpenWeatherMap (environmental correlation)
OPENWEATHER_API_KEY = config("OPENWEATHER_API_KEY", default="")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/"

# OpenFDA (adverse events)
OPENFDA_API_KEY = config("OPENFDA_API_KEY", default="")
OPENFDA_BASE_URL = "https://api.fda.gov/"


# =============================================================================
# GEOSPATIAL
# =============================================================================

MAPBOX_ACCESS_TOKEN = config("MAPBOX_ACCESS_TOKEN", default="")
GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="")

# PostGIS library paths (set these if using GeoDjango locally)
GDAL_LIBRARY_PATH = config("GDAL_LIBRARY_PATH", default="")
GEOS_LIBRARY_PATH = config("GEOS_LIBRARY_PATH", default="")


# =============================================================================
# MACHINE LEARNING
# =============================================================================

ML_MODEL_PATH = config("ML_MODEL_PATH", default=str(ML_MODELS_DIR))
ML_ENABLE_GPU = config("ML_ENABLE_GPU", default=False, cast=bool)
ML_BATCH_SIZE = config("ML_BATCH_SIZE", default=32, cast=int)
ML_PREDICTION_THRESHOLD = config("ML_PREDICTION_THRESHOLD", default=0.7, cast=float)

# TensorFlow: 0=all, 1=info, 2=warning, 3=error
os.environ["TF_CPP_MIN_LOG_LEVEL"] = config("TF_LOG_LEVEL", default="2")


# =============================================================================
# MONITORING
# =============================================================================

SENTRY_DSN = config("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = config("SENTRY_ENVIRONMENT", default="development")
SENTRY_TRACES_SAMPLE_RATE = config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float)


# =============================================================================
# FEATURE FLAGS
# =============================================================================

ENABLE_SMS_NOTIFICATIONS = config("ENABLE_SMS_NOTIFICATIONS", default=True, cast=bool)
ENABLE_EMAIL_NOTIFICATIONS = config("ENABLE_EMAIL_NOTIFICATIONS", default=True, cast=bool)
ENABLE_PUSH_NOTIFICATIONS = config("ENABLE_PUSH_NOTIFICATIONS", default=True, cast=bool)

ENABLE_AUTO_ESCALATION = config("ENABLE_AUTO_ESCALATION", default=True, cast=bool)
ENABLE_ML_PREDICTIONS = config("ENABLE_ML_PREDICTIONS", default=True, cast=bool)
ENABLE_GEOSPATIAL_ANALYSIS = config("ENABLE_GEOSPATIAL_ANALYSIS", default=True, cast=bool)
ENABLE_REAL_TIME_ALERTS = config("ENABLE_REAL_TIME_ALERTS", default=True, cast=bool)

ENABLE_DHIS2_INTEGRATION = config("ENABLE_DHIS2_INTEGRATION", default=False, cast=bool)
ENABLE_SORMAS_INTEGRATION = config("ENABLE_SORMAS_INTEGRATION", default=False, cast=bool)
ENABLE_WHO_REPORTING = config("ENABLE_WHO_REPORTING", default=False, cast=bool)

ENABLE_OFFLINE_MODE = config("ENABLE_OFFLINE_MODE", default=True, cast=bool)
OFFLINE_SYNC_INTERVAL = config("OFFLINE_SYNC_INTERVAL", default=300, cast=int)

ENABLE_TWO_FACTOR_AUTH = config("ENABLE_TWO_FACTOR_AUTH", default=True, cast=bool)
ENABLE_AUDIT_LOGGING = config("ENABLE_AUDIT_LOGGING", default=True, cast=bool)
ENABLE_RATE_LIMITING = config("ENABLE_RATE_LIMITING", default=True, cast=bool)


# =============================================================================
# SECURITY HEADERS (base values; production.py tightens these)
# =============================================================================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SECURE_SSL_REDIRECT = False        # Enabled in production
SECURE_HSTS_SECONDS = 0            # Enabled in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# CSP base (tightened in production)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Inline styles required by React; use nonces to tighten further
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)


# =============================================================================
# APPLICATION THRESHOLDS
# =============================================================================

ALERT_THRESHOLD_LOW = config("ALERT_THRESHOLD_LOW", default=0.3, cast=float)
ALERT_THRESHOLD_MEDIUM = config("ALERT_THRESHOLD_MEDIUM", default=0.6, cast=float)
ALERT_THRESHOLD_HIGH = config("ALERT_THRESHOLD_HIGH", default=0.8, cast=float)
ALERT_THRESHOLD_CRITICAL = config("ALERT_THRESHOLD_CRITICAL", default=0.9, cast=float)

RESPONSE_ESCALATION_LEVEL_1 = config("RESPONSE_ESCALATION_LEVEL_1", default=15, cast=int)  # min
RESPONSE_ESCALATION_LEVEL_2 = config("RESPONSE_ESCALATION_LEVEL_2", default=30, cast=int)
RESPONSE_ESCALATION_LEVEL_3 = config("RESPONSE_ESCALATION_LEVEL_3", default=60, cast=int)

RESOURCE_CAPACITY_WARNING = config("RESOURCE_CAPACITY_WARNING", default=0.7, cast=float)
RESOURCE_CAPACITY_CRITICAL = config("RESOURCE_CAPACITY_CRITICAL", default=0.9, cast=float)

DATA_RETENTION_DAYS = config("DATA_RETENTION_DAYS", default=365, cast=int)
LOG_RETENTION_DAYS = config("LOG_RETENTION_DAYS", default=90, cast=int)

MAX_SYNC_RETRIES = config("MAX_SYNC_RETRIES", default=3, cast=int)
SYNC_RETRY_DELAY = config("SYNC_RETRY_DELAY", default=60, cast=int)

MAX_NOTIFICATION_RETRIES = config("MAX_NOTIFICATION_RETRIES", default=3, cast=int)
NOTIFICATION_BATCH_SIZE = config("NOTIFICATION_BATCH_SIZE", default=100, cast=int)


# =============================================================================
# MISC THIRD-PARTY
# =============================================================================

# django-import-export
IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_SKIP_ADMIN_LOG = False

# django-health-check
HEALTH_CHECK = {
    "DISK_USAGE_MAX": 90,   # %
    "MEMORY_MIN": 100,       # MB
}

# django-otp
OTP_TOTP_ISSUER = "OryxShield"

# phonenumber-field
PHONENUMBER_DEFAULT_REGION = "KE"
PHONENUMBER_DB_FORMAT = "E164"

# Internal IPs for debug toolbar
INTERNAL_IPS = ["127.0.0.1", "localhost", "::1"]
DEBUG_PROPAGATE_EXCEPTIONS = DEBUG