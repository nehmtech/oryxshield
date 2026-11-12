"""
OryxShield - Root URL Configuration
=============================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

URL hierarchy:

  /admin/                       Django admin
  /health/                      Quick liveness probe
  /health/detailed/             Full health check (DB, cache, Redis, Celery)
  /health/ready/                Readiness probe
  /health/live/                 Liveness probe

  /api/schema/                  OpenAPI schema (JSON)
  /api/docs/                    Swagger UI
  /api/redoc/                   ReDoc UI

  /api/v1/auth/register/        Registration
  /api/v1/auth/login/           JWT login
  /api/v1/auth/logout/          Logout
  /api/v1/auth/token/refresh/   Token refresh
  /api/v1/auth/change-password/ Password change
  /api/v1/users/                User management (ViewSet)
  /api/v1/profiles/             User profiles (ViewSet)
  /api/v1/locations/            Location reference data (ViewSet)
  /api/v1/notifications/        Notifications (ViewSet)
  /api/v1/audit-logs/           Audit log (ViewSet, superuser-only)
  /api/v1/configurations/       System configuration (ViewSet)
  /api/v1/api-keys/             API keys (ViewSet)
  /api/v1/surveillance/         Surveillance data & anomaly detection
  /api/v1/risk/                 Risk scores & alerts
  /api/v1/response/             Response protocol & escalation
  /api/v1/coordination/         Multi-agency coordination
  /api/v1/resources/            Inventory & facility management
  /api/v1/communications/       Public alerts & messaging
  /api/v1/analytics/            Epidemiological reports & dashboards
  /api/v1/operations/           Contact tracing, quarantine, vaccination
  /api/v1/mobile/               Mobile-optimised endpoints
  /api/v1/integrations/         External system connectors

  /media/<path>                 Served user-uploaded files

NOTE: core.urls is mounted at the ROOT of api/v1/ (empty string ""),
      NOT under "auth/" — because core/urls.py already defines its own
      internal "auth/" prefix for auth endpoints, and its router registers
      users/, profiles/, locations/, notifications/, audit-logs/,
      configurations/, api-keys/ directly at the root level.
      Mounting under "auth/" would create doubled paths like
      /api/v1/auth/auth/login/ and /api/v1/auth/users/ — both wrong.
"""

import os

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


# =============================================================================
# HEALTH CHECK VIEWS
# =============================================================================

@require_GET
def health_check(request):
    """
    Minimal liveness probe for Railway / load-balancer.
    Returns 200 as long as the Django process is running.
    """
    return JsonResponse({
        "status": "healthy",
        "service": "oryxshield",
        "version": settings.SPECTACULAR_SETTINGS.get("VERSION", "1.0.0"),
    })


@require_GET
def health_check_detailed(request):
    """
    Comprehensive health check — verifies DB, cache, Redis, and Celery.
    Returns 200 if all services are healthy, 503 if any are degraded.
    """
    from django.db import connection
    from django.core.cache import cache

    status = "healthy"
    checks: dict = {}

    # Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"
        status = "degraded"

    # Cache
    try:
        cache.set("_health_check_", "ok", 10)
        assert cache.get("_health_check_") == "ok"
        checks["cache"] = "healthy"
    except Exception as exc:
        checks["cache"] = f"unhealthy: {exc}"
        status = "degraded"

    # Redis
    try:
        import redis as _redis
        _client = _redis.from_url(getattr(settings, "REDIS_URL", "redis://localhost:6379"))
        _client.ping()
        checks["redis"] = "healthy"
    except Exception as exc:
        checks["redis"] = f"unhealthy: {exc}"
        status = "degraded"

    # Celery
    try:
        from config.celery import app as _celery
        _stats = _celery.control.inspect(timeout=2).stats()
        checks["celery"] = "healthy" if _stats else "no workers"
        if not _stats:
            status = "degraded"
    except Exception as exc:
        checks["celery"] = f"unhealthy: {exc}"
        status = "degraded"

    http_status = 200 if status == "healthy" else 503
    return JsonResponse(
        {
            "status": status,
            "service": "oryxshield",
            "version": settings.SPECTACULAR_SETTINGS.get("VERSION", "1.0.0"),
            "checks": checks,
        },
        status=http_status,
    )


@require_GET
def readiness_check(request):
    """
    Readiness probe — signals that the app is ready to receive traffic.
    Checks database connectivity.
    """
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ready"})
    except Exception as exc:
        return JsonResponse({"status": "not ready", "reason": str(exc)}, status=503)


@require_GET
def liveness_check(request):
    """
    Liveness probe — if this returns anything other than 200, restart the pod.
    """
    return JsonResponse({"status": "alive"})


# =============================================================================
# URL PATTERNS
# =============================================================================

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Health probes ───────────────────────────────────────────────────────
    path("health/",          health_check,          name="health-check"),
    path("health/detailed/", health_check_detailed, name="health-check-detailed"),
    path("health/ready/",    readiness_check,        name="readiness-check"),
    path("health/live/",     liveness_check,         name="liveness-check"),

    # ── API Documentation ───────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        cache_page(60 * 15)(SpectacularSwaggerView.as_view(url_name="schema")),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        cache_page(60 * 15)(SpectacularRedocView.as_view(url_name="schema")),
        name="redoc",
    ),

    # ── API v1 ──────────────────────────────────────────────────────────────
    path("api/v1/", include([

        # Core — auth endpoints + all ViewSets (users, profiles, locations,
        # notifications, audit-logs, configurations, api-keys).
        #
        # IMPORTANT: mount at "" (root), NOT "auth/".
        # core/urls.py already has path("auth/login/", ...) internally.
        # Mounting here under "auth/" would produce /api/v1/auth/auth/login/.
        # The router-registered ViewSets (users/, profiles/, etc.) also live
        # at the root of core.urls, so they resolve correctly as
        # /api/v1/users/, /api/v1/profiles/, etc.
        path("", include("core.urls", namespace="core")),

        # Surveillance — data ingestion, anomaly detection, clustering, hotspots
        path("surveillance/",   include("surveillance.urls")),

        # Risk Assessment — scores, thresholds, alerts, forecasts
        path("risk/",           include("risk_assessment.urls")),

        # Response — protocols, escalation rules, action tracking
        path("response/",       include("response.urls")),

        # Coordination — multi-agency, RBAC, task board
        path("coordination/",   include("coordination.urls")),

        # Resources — inventory, facilities, supply chain, procurement
        path("resources/",      include("resources.urls")),

        # Communications — SMS, email, push, geo-targeted broadcasts
        path("communications/", include("communications.urls")),

        # Analytics — epi curves, reports, dashboards, WHO/IHR exports
        path("analytics/",      include("analytics.urls")),

        # Operations — contact tracing, quarantine, vaccination, lab
        path("operations/",     include("operations.urls")),

        # Mobile — offline sync, CHW tools, public-facing endpoints
        path("mobile/",         include("mobile.urls")),

        # Integrations — DHIS2, SORMAS, WHO EIOS, Africa CDC, LIS/EMR
        path("integrations/",   include("integrations.urls")),

        # WebSocket REST management (connection audit, channel groups, broadcasts)
        path("ws-mgmt/",        include("websockets.urls")),
    ])),
]


# =============================================================================
# MEDIA FILES
# =============================================================================

# Serve /media/ in all environments (Nginx handles this in bare-metal prod)
if settings.MEDIA_ROOT and os.path.exists(settings.MEDIA_ROOT):
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT, "show_indexes": False},
            name="media",
        ),
    ]


# =============================================================================
# DEVELOPMENT EXTRAS
# =============================================================================

if settings.DEBUG:
    # Serve static files
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Serve media (if not already added above)
    _has_media = any(getattr(p, "name", None) == "media" for p in urlpatterns)
    if not _has_media:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Browser auto-reload
    if "django_browser_reload" in settings.INSTALLED_APPS:
        urlpatterns = [
            path("__reload__/", include("django_browser_reload.urls")),
        ] + urlpatterns

    # Django Debug Toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns


# =============================================================================
# ADMIN SITE BRANDING
# =============================================================================

admin.site.site_header = "OryxShield Administration"
admin.site.site_title  = "OryxShield Admin Portal"
admin.site.index_title = "Automated Pandemic Response System"


