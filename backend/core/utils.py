"""
OryxShield — Utility Functions
=======================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Sections
--------
IP / request helpers
String helpers (generation, hashing, formatting)
Cache helpers
Date / time helpers
Pagination helpers
File / upload helpers
Data formatting helpers
Email helpers
Geospatial helpers (Google Maps API)
"""

from __future__ import annotations

import hashlib
import re
import secrets
import string
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, send_mass_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify as django_slugify

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IP / request helpers
# ---------------------------------------------------------------------------

def get_client_ip(request) -> str:
    """Extract the real client IP address, honouring X-Forwarded-For."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


def get_user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:500]


def is_ajax(request) -> bool:
    return request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def generate_random_string(
    length: int = 32,
    *,
    include_digits: bool = True,
    include_special: bool = False,
) -> str:
    """Generate a cryptographically secure random string."""
    chars = string.ascii_letters
    if include_digits:
        chars += string.digits
    if include_special:
        chars += "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))


def generate_api_key() -> str:
    """Return a 64-char URL-safe API key."""
    return secrets.token_urlsafe(48)


def generate_token(length: int = 32) -> str:
    """Return a hex token for password-reset / email-verify links."""
    return secrets.token_hex(length)


def generate_otp(digits: int = 6) -> str:
    """Return a numeric OTP suitable for SMS / email 2FA."""
    return "".join(secrets.choice(string.digits) for _ in range(digits))


def hash_string(value: str, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    h.update(value.encode("utf-8"))
    return h.hexdigest()


def truncate_string(text: str, length: int = 100, suffix: str = "…") -> str:
    if not text or len(text) <= length:
        return text
    return text[: length - len(suffix)] + suffix


def slugify(text: str) -> str:
    return django_slugify(text)


def sanitize_filename(filename: str) -> str:
    """Remove path components and dangerous characters from a filename."""
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^\w\s\-.]", "", filename)
    return filename.replace(" ", "_")[:255] or "file"


def mask_sensitive(value: str, show_chars: int = 4) -> str:
    """Return a masked version of a sensitive string, e.g. API key display."""
    if not value or len(value) <= show_chars:
        return "***"
    return value[:show_chars] + "***"


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    return bool(value)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def cache_key(*parts: Any) -> str:
    """Build a normalised, collision-resistant cache key."""
    raw = ":".join(str(p) for p in parts)
    return hash_string(raw, "sha1")[:40]


def cached(key: str, ttl: int, factory):
    """Return cached value or call factory(), cache result, and return it."""
    value = cache.get(key)
    if value is None:
        value = factory()
        cache.set(key, value, ttl)
    return value


def invalidate_cache_prefix(prefix: str) -> int:
    """Delete all cache keys starting with prefix. Returns count deleted (best-effort)."""
    try:
        if hasattr(cache, "delete_pattern"):
            return cache.delete_pattern(f"{prefix}*")
    except Exception:
        logger.warning("invalidate_cache_prefix failed for prefix=%r", prefix, exc_info=True)
    return 0


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def now() -> datetime:
    return timezone.now()


def today() -> date:
    return timezone.localdate()


def days_ago(n: int) -> datetime:
    return timezone.now() - timedelta(days=n)


def days_from_now(n: int) -> datetime:
    return timezone.now() + timedelta(days=n)


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime(fmt)


def format_date(d: date | None, fmt: str = "%Y-%m-%d") -> str:
    return d.strftime(fmt) if d else ""


def is_past(dt: datetime) -> bool:
    return timezone.now() > dt


def is_future(dt: datetime) -> bool:
    return timezone.now() < dt


def datetime_range(start: datetime, end: datetime, step_minutes: int = 60) -> list[datetime]:
    """Yield datetimes from start to end at step_minutes intervals."""
    result, current = [], start
    while current <= end:
        result.append(current)
        current += timedelta(minutes=step_minutes)
    return result


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

def paginate_queryset(queryset, page: int = 1, page_size: int = 50) -> tuple:
    """
    Simple paginator returning (items, total_count, total_pages, has_next, has_prev).
    Prefer DRF pagination classes in views; use this for non-view contexts.
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    paginator = Paginator(queryset, max(1, page_size))
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return (
        page_obj.object_list,
        paginator.count,
        paginator.num_pages,
        page_obj.has_next(),
        page_obj.has_previous(),
    )


# ---------------------------------------------------------------------------
# File / upload helpers
# ---------------------------------------------------------------------------

def get_file_extension(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    return parts[1].lower() if len(parts) == 2 else ""


def is_allowed_file_type(filename: str, allowed: list[str] | None = None) -> bool:
    allowed = allowed or ["jpg", "jpeg", "png", "gif", "pdf", "csv", "xlsx"]
    return get_file_extension(filename) in allowed


def get_upload_path(instance, filename: str, base: str = "uploads") -> str:
    """Return a date-partitioned upload path to prevent directory bloat."""
    ext = get_file_extension(filename)
    name = sanitize_filename(filename.rsplit(".", 1)[0])
    date_path = timezone.now().strftime("%Y/%m/%d")
    return f"{base}/{date_path}/{name}_{generate_token(8)}.{ext}"


def human_readable_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes} PB"


# ---------------------------------------------------------------------------
# Data formatting helpers
# ---------------------------------------------------------------------------

def format_phone_number(phone: str, country_code: str = "+264") -> str:
    """Normalise a Namibian phone number to E.164 format."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) == 10:
        return country_code + digits[1:]
    if digits.startswith("254") and len(digits) == 12:
        return "+" + digits
    return phone  # return as-is if unrecognised


def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def format_currency(amount: Decimal | float, currency: str = "KES") -> str:
    return f"{currency} {float(amount):,.2f}"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base dict."""
    result = base.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items: list = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: list, size: int) -> list[list]:
    """Split list into chunks of at most size elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def send_html_email(
    subject: str,
    template: str,
    context: dict,
    recipients: list[str],
    *,
    from_email: str | None = None,
    attachments: list | None = None,
) -> bool:
    """
    Send a single HTML email rendered from a Django template.
    Returns True on success.
    """
    try:
        html_content = render_to_string(template, context)
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        msg.content_subtype = "html"
        for attachment in (attachments or []):
            msg.attach(*attachment)
        msg.send()
        return True
    except Exception as exc:
        logger.error("Failed to send email '%s': %s", subject, exc)
        return False


def send_bulk_email(messages: list[tuple]) -> int:
    """
    Send multiple plain-text emails using send_mass_mail.
    messages: list of (subject, body, from_email, [recipients])
    Returns count sent.
    """
    try:
        return send_mass_mail(messages, fail_silently=False)
    except Exception as exc:
        logger.error("Bulk email error: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Geospatial helpers (Google Maps API)
# ---------------------------------------------------------------------------

def calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Haversine formula — straight-line distance between two coordinates in km.
    Does not require PostGIS.
    """
    import math

    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def coordinates_within_radius(
    center_lat: float,
    center_lng: float,
    point_lat: float,
    point_lng: float,
    radius_km: float,
) -> bool:
    return calculate_distance_km(center_lat, center_lng, point_lat, point_lng) <= radius_km


def google_maps_static_url(
    lat: float,
    lng: float,
    zoom: int = 14,
    size: str = "600x400",
    maptype: str = "roadmap",
) -> str:
    """Build a Google Maps Static API URL (requires GOOGLE_MAPS_API_KEY in settings)."""
    key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
    return (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lng}&zoom={zoom}&size={size}&maptype={maptype}&key={key}"
    )


def google_maps_directions_url(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> str:
    return (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_lat},{origin_lng}"
        f"&destination={dest_lat},{dest_lng}"
    )


# ---------------------------------------------------------------------------
# Misc system helpers
# ---------------------------------------------------------------------------

def get_system_metrics() -> dict:
    """Return cached system metrics or an empty dict if not yet calculated."""
    return cache.get("system_metrics") or {}


def log_performance(func_name: str, duration: float, threshold: float = 1.0) -> None:
    if duration > threshold:
        logger.warning("Performance: %s took %.3fs (threshold %.1fs)", func_name, duration, threshold)
    else:
        logger.debug("Performance: %s took %.3fs", func_name, duration)


def get_setting(key: str, default: Any = None) -> Any:
    """
    Look up a value first in SystemConfiguration (DB), then in Django settings.
    Falls back to ``default`` if not found in either.
    """
    try:
        from .models import SystemConfiguration
        cfg = SystemConfiguration.objects.filter(key=key, is_active=True).first()
        if cfg is not None:
            return cfg.value
    except Exception:
        logger.warning("get_config_value failed for key=%r, falling back to settings/default", key, exc_info=True)
    return getattr(settings, key, default)