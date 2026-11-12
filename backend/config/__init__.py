"""
OryxShield - Config Package
=====================================

Initialises the Django project package and ensures Celery is loaded
whenever Django starts, so that @shared_task decorators work correctly.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
__version__ = "1.0.0"