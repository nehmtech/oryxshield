"""
OryxShield - ASGI Configuration
=========================================

ASGI entrypoint supporting both HTTP and WebSocket protocols.

Protocol routing:
  http       → Django ASGI application
  websocket  → JWT-authenticated Channels consumers (with origin validation)

WebSocket URL examples:
  ws://localhost:8000/ws/surveillance/alerts/?token=<jwt>
  wss://api.oryxshield.gov.na/ws/response/status/?token=<jwt>
  wss://api.oryxshield.gov.na/ws/notifications/user/?token=<jwt>

Deployment (Railway Procfile):
  web: daphne -b 0.0.0.0 -p $PORT config.asgi:application

For more information on ASGI, see:
  https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import django
import logging

from decouple import config

# ── Settings module selection ─────────────────────────────────────────────────

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    config("DJANGO_SETTINGS_MODULE", default="config.settings.production"),
)

# Initialise Django (must happen before any ORM / app imports)
django.setup()

# ── Standard Django imports (after setup) ─────────────────────────────────────

from django.core.asgi import get_asgi_application    # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack          # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

logger = logging.getLogger("django")

# ── Django HTTP application ───────────────────────────────────────────────────

_django_asgi_app = get_asgi_application()

# ── WebSocket routing ─────────────────────────────────────────────────────────

try:
    from websockets.routing import websocket_urlpatterns    # noqa: E402
    from websockets.middleware import JWTAuthMiddleware      # noqa: E402
    _websockets_configured = True
    logger.info("WebSocket routing loaded successfully.")
except ImportError as _e:
    _websockets_configured = False
    websocket_urlpatterns = []
    logger.warning(
        "WebSocket module not found (%s) — falling back to HTTP-only ASGI.", _e
    )

    def JWTAuthMiddleware(inner):  # noqa: N802
        """No-op placeholder when websockets app is not installed."""
        return inner


# ── ASGI Application ──────────────────────────────────────────────────────────

if _websockets_configured:
    application = ProtocolTypeRouter({
        # HTTP requests → Django
        "http": _django_asgi_app,

        # WebSocket requests:
        #   1. AllowedHostsOriginValidator  — prevents CSWSH
        #   2. JWTAuthMiddleware            — sets scope["user"] from JWT
        #   3. AuthMiddlewareStack          — Django session/cookie auth (admin)
        #   4. URLRouter                   — routes to consumers
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(
                AuthMiddlewareStack(
                    URLRouter(websocket_urlpatterns)
                )
            )
        ),
    })
else:
    # HTTP-only fallback (WebSocket features will be unavailable)
    application = ProtocolTypeRouter({
        "http": _django_asgi_app,
    })