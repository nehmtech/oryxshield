"""
WebSocket URL routing for OryxShield.

Mount this in your ASGI application via:

    from channels.routing import ProtocolTypeRouter, URLRouter
    from websockets.routing import websocket_urlpatterns
    from websockets.middleware import (
        JWTAuthMiddleware,
        IPWhitelistMiddleware,
        RateLimitMiddleware,
        LoggingMiddleware,
    )

    application = ProtocolTypeRouter({
        'websocket': LoggingMiddleware(
            IPWhitelistMiddleware(
                RateLimitMiddleware(
                    JWTAuthMiddleware(
                        URLRouter(websocket_urlpatterns)
                    )
                )
            )
        ),
    })
"""
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Alerts & notifications
    re_path(r'^ws/alerts/$',        consumers.AlertConsumer.as_asgi()),
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),

    # Surveillance
    re_path(r'^ws/surveillance/$',  consumers.SurveillanceConsumer.as_asgi()),

    # Dashboard (per-user)
    re_path(r'^ws/dashboard/$',     consumers.DashboardConsumer.as_asgi()),

    # Response coordination
    re_path(r'^ws/response/$',      consumers.ResponseConsumer.as_asgi()),

    # Resource management
    re_path(r'^ws/resources/$',     consumers.ResourceConsumer.as_asgi()),

    # Operations (contact tracing / quarantine)
    re_path(r'^ws/operations/$',    consumers.OperationsConsumer.as_asgi()),

    # System status (staff only)
    re_path(r'^ws/system-status/$', consumers.SystemStatusConsumer.as_asgi()),
]