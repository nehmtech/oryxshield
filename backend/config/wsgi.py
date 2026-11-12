"""
OryxShield - WSGI Configuration
=========================================

WSGI entrypoint for HTTP-only (non-WebSocket) deployments.

NOTE: For WebSocket support use ASGI (asgi.py) with Daphne.
      This file is kept for compatibility and for Gunicorn-based deploys.

Production Gunicorn command (Procfile):
    web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT \
             --workers 4 --timeout 60 \
             --access-logfile - --error-logfile -

For more information on WSGI, see:
    https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

from decouple import config

# Ensure the project root is on the Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    config("DJANGO_SETTINGS_MODULE", default="config.settings.production"),
)

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()