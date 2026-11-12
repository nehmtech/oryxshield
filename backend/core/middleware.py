"""
OryxShield — Custom Middleware
=======================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Middleware stack (add to settings in this order after SecurityMiddleware/CorsMiddleware):
  CorrelationIdMiddleware      — unique X-Request-ID per request
  RequestTimingMiddleware      — X-Request-Duration header + slow-request logging
  AuditLoggingMiddleware       — write AuditLog for mutating API calls
  ExceptionLoggingMiddleware   — log unhandled exceptions with full context
  RateLimitMiddleware          — per-user request-rate enforcement (cache-backed)
  SecurityHeadersMiddleware    — CSP, HSTS, XFO, XCTO, Referrer-Policy
  UserActivityMiddleware       — lightweight last-active cache update
  HealthCheckBypassMiddleware  — fast path for /health/ probes
  MaintenanceModeMiddleware    — 503 gate (staff bypass)
"""

from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AUDIT_EXCLUDE_PREFIXES = (
    "/admin/",
    "/api/v1/auth/login/",
    "/api/v1/auth/logout/",
    "/api/v1/auth/token/",
    "/api/v1/health/",
    "/health/",
    "/api/schema/",
    "/api/docs/",
    "/api/redoc/",
    "/static/",
    "/media/",
)

_HEALTH_PATHS = frozenset({"/health/", "/api/v1/health/", "/ready/", "/live/"})


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


# ---------------------------------------------------------------------------
# CorrelationIdMiddleware
# ---------------------------------------------------------------------------


class CorrelationIdMiddleware(MiddlewareMixin):
    """
    Attach a unique correlation ID to every request.

    Honours an existing X-Request-ID header from upstream proxies/load balancers.
    The ID is attached to request.request_id and echoed in the response header.
    """

    def process_request(self, request) -> None:
        request.request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# RequestTimingMiddleware
# ---------------------------------------------------------------------------


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Record request processing time; log slow requests; add X-Request-Duration.
    """

    SLOW_THRESHOLD_SECONDS: float = getattr(settings, "SLOW_REQUEST_THRESHOLD", 2.0)

    def process_request(self, request) -> None:
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        start = getattr(request, "_start_time", None)
        if start is None:
            return response

        duration = time.monotonic() - start
        response["X-Request-Duration"] = f"{duration:.3f}s"

        if duration > self.SLOW_THRESHOLD_SECONDS:
            user_str = (
                request.user.username
                if getattr(request, "user", None) and request.user.is_authenticated
                else "anonymous"
            )
            logger.warning(
                "Slow request: %s %s %.3fs — user=%s rid=%s",
                request.method,
                request.path,
                duration,
                user_str,
                getattr(request, "request_id", "-"),
                extra={"duration": duration},
            )
        elif settings.DEBUG:
            logger.debug(
                "%s %s %.3fs %s",
                request.method,
                request.path,
                duration,
                response.status_code,
            )

        return response


# ---------------------------------------------------------------------------
# AuditLoggingMiddleware
# ---------------------------------------------------------------------------


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Write an AuditLog entry for every authenticated mutating API request.

    Skips: unauthenticated requests, safe methods (GET/HEAD/OPTIONS),
    non-API paths, and explicitly excluded paths.
    Failures in audit logging NEVER break the original request.
    """

    _MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    _METHOD_TO_ACTION = {
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }

    def process_response(self, request, response):
        if not (getattr(request, "user", None) and request.user.is_authenticated):
            return response
        if request.method not in self._MUTATING_METHODS:
            return response
        path = request.path
        if not path.startswith("/api/v1/"):
            return response
        if any(path.startswith(p) for p in _AUDIT_EXCLUDE_PREFIXES):
            return response

        try:
            from .models import AuditLog  # local import to avoid circular

            parts = path.strip("/").split("/")
            model_name = parts[2].replace("-", " ").title() if len(parts) >= 3 else "Unknown"
            object_id = (
                parts[3]
                if len(parts) >= 4 and (len(parts[3]) > 8 or parts[3].isdigit())
                else ""
            )

            AuditLog.log(
                user=request.user,
                action=self._METHOD_TO_ACTION.get(request.method, "UPDATE"),
                model_name=model_name,
                object_id=object_id,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                request_method=request.method,
                request_path=path,
                success=(200 <= response.status_code < 400),
                metadata={
                    "status_code": response.status_code,
                    "request_id": getattr(request, "request_id", ""),
                },
            )
        except Exception as exc:
            logger.error("AuditLoggingMiddleware error: %s", exc, exc_info=True)

        return response


# ---------------------------------------------------------------------------
# ExceptionLoggingMiddleware
# ---------------------------------------------------------------------------


class ExceptionLoggingMiddleware(MiddlewareMixin):
    """
    Log unhandled exceptions with full request context before Django processes them.
    Returns None to let Django's default 500 handling continue.
    """

    def process_exception(self, request, exception) -> None:
        logger.error(
            "Unhandled exception: %s — %s",
            exception.__class__.__name__,
            exception,
            exc_info=True,
            extra={
                "request_id": getattr(request, "request_id", ""),
                "user": (
                    request.user.username
                    if getattr(request, "user", None) and request.user.is_authenticated
                    else "anonymous"
                ),
                "path": request.path,
                "method": request.method,
                "ip": _get_client_ip(request),
            },
        )
        return None  # allow Django's exception handling to continue


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(MiddlewareMixin):
    """
    Per-user cache-backed rate limiting.

    Settings
    --------
    RATE_LIMIT_REQUESTS  : max requests in window (default 100)
    RATE_LIMIT_WINDOW    : window in seconds (default 60)
    ENABLE_RATE_LIMITING : set False to disable entirely (default True)

    Staff users are always bypassed. Returns JSON 429 on breach.
    """

    _LIMIT: int = getattr(settings, "RATE_LIMIT_REQUESTS", 100)
    _WINDOW: int = getattr(settings, "RATE_LIMIT_WINDOW", 60)

    def process_request(self, request):
        if not getattr(settings, "ENABLE_RATE_LIMITING", True):
            return None
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated) or user.is_staff:
            return None
        if request.path.startswith(("/admin/", "/static/", "/media/")):
            return None

        cache_key = f"rl:user:{user.pk}"
        count = cache.get(cache_key, 0)

        if count >= self._LIMIT:
            logger.warning(
                "Rate limit exceeded — user=%s count=%d", user.username, count
            )
            return JsonResponse(
                {
                    "error": {
                        "status_code": 429,
                        "message": "Rate limit exceeded. Please try again later.",
                        "type": "RateLimitExceeded",
                        "retry_after": self._WINDOW,
                    }
                },
                status=429,
            )

        if count == 0:
            cache.set(cache_key, 1, self._WINDOW)
        else:
            try:
                cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, self._WINDOW)

        request._rl_remaining = max(0, self._LIMIT - count - 1)
        return None

    def process_response(self, request, response):
        if hasattr(request, "_rl_remaining"):
            response["X-RateLimit-Limit"] = str(self._LIMIT)
            response["X-RateLimit-Remaining"] = str(request._rl_remaining)
            response["X-RateLimit-Window"] = str(self._WINDOW)
        return response


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Inject security-related HTTP headers on every response.

    In production these supplement Django's built-in SECURE_* settings.
    In development most headers are still applied to catch issues early.
    """

    def process_response(self, request, response):
        h = response

        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-XSS-Protection", "1; mode=block")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )

        if not settings.DEBUG:
            h.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' data:; "
                    "connect-src 'self';"
                ),
            )
            if request.is_secure():
                h.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains; preload",
                )

        return response


# ---------------------------------------------------------------------------
# UserActivityMiddleware
# ---------------------------------------------------------------------------


class UserActivityMiddleware(MiddlewareMixin):
    """
    Cache user activity timestamp every 5 minutes to support active-user tracking.
    Does not write to the database on every request.
    """

    _TTL = 300  # 5 minutes

    def process_request(self, request) -> None:
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            cache.set(f"user_active:{user.pk}", timezone.now().isoformat(), self._TTL)


# ---------------------------------------------------------------------------
# HealthCheckBypassMiddleware
# ---------------------------------------------------------------------------


class HealthCheckBypassMiddleware(MiddlewareMixin):
    """
    Mark health-check requests so downstream middleware can skip heavy processing.
    """

    def process_request(self, request) -> None:
        if request.path in _HEALTH_PATHS:
            request.is_health_check = True


# ---------------------------------------------------------------------------
# MaintenanceModeMiddleware
# ---------------------------------------------------------------------------


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    Return 503 for all non-staff, non-health requests when MAINTENANCE_MODE=True.
    Enable via settings: MAINTENANCE_MODE = True
    """

    def process_request(self, request):
        if not getattr(settings, "MAINTENANCE_MODE", False):
            return None

        # Health probes always pass through
        if request.path in _HEALTH_PATHS:
            return None

        # Staff users bypass maintenance gate
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_staff:
            return None

        return JsonResponse(
            {
                "error": {
                    "status_code": 503,
                    "message": "System is under maintenance. Please try again later.",
                    "type": "MaintenanceMode",
                }
            },
            status=503,
        )


# ---------------------------------------------------------------------------
# RequestSizeLimitMiddleware
# ---------------------------------------------------------------------------

class RequestSizeLimitMiddleware(MiddlewareMixin):
    """
    Reject requests whose Content-Length exceeds DATA_UPLOAD_MAX_MEMORY_SIZE
    before Django parses the body. Prevents memory exhaustion from large payloads.
    """

    def process_request(self, request):
        max_bytes = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return JsonResponse(
                        {
                            "error": {
                                "status_code": 413,
                                "message": f"Request payload exceeds the {max_bytes // 1024 // 1024} MB limit.",
                                "type": "PayloadTooLarge",
                            }
                        },
                        status=413,
                    )
            except (ValueError, TypeError):
                pass
        return None
