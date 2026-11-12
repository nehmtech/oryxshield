"""
OryxShield - Settings Package
=======================================

Settings are split by environment:

    base.py         — Shared settings for all environments
    development.py  — SQLite, debug, eager Celery, in-memory cache
    production.py   — PostgreSQL, Redis, HTTPS, Sentry, WhiteNoise
    testing.py      — In-memory SQLite, no migrations, mocked services

Select the active settings module via the environment variable:

    export DJANGO_SETTINGS_MODULE=config.settings.development
    python manage.py runserver

    export DJANGO_SETTINGS_MODULE=config.settings.production
    gunicorn config.wsgi:application

    export DJANGO_SETTINGS_MODULE=config.settings.testing
    pytest

The default in asgi.py / wsgi.py / celery.py is production for safety.
"""

__all__ = ["base", "development", "production", "testing"]