"""
OryxShield — Custom Permissions
========================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Permission classes
------------------
IsOwnerOrAdmin              — object owner or staff
IsAdminOrReadOnly           — read any, write staff only
CanManageUsers              — user CRUD gated to staff; self-edit allowed
CanViewAuditLogs            — superuser only
CanManageSystemConfiguration — read any, write staff only
CanEscalateResponse         — staff or 'can_escalate' in profile permissions
CanManageAlerts             — staff or 'can_manage_alerts' in profile permissions
CanAccessSensitiveData      — superuser or 'can_access_sensitive_data'
IsDataEntryPersonnel        — GET/POST/PUT/PATCH all users; DELETE staff only
IsHealthOfficer             — staff or job_title keyword match
LocationBasedPermission     — object accessible only if in user's location subtree
IsAPIKeyAuthenticated       — request.auth is an APIKey instance
IsSelfOrAdmin               — user-related self-only or staff
HasPermission               — generic profile-permission gate (uses view.permission_required)
IsVerifiedUser              — email or phone verified
NotLocked                   — account not currently locked
IsActiveUser                — user.is_active must be True
HasAcceptedTerms            — terms_accepted_at must be set
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import permissions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(request) -> object | None:
    user = getattr(request, "user", None)
    return getattr(user, "profile", None) if user else None


def _profile_permissions(request) -> list:
    p = _profile(request)
    return p.get_permissions() if p else []


# ---------------------------------------------------------------------------
# Core access-control permissions
# ---------------------------------------------------------------------------


class IsOwnerOrAdmin(permissions.BasePermission):
    """Allow the object owner (via user/created_by/owner attribute) or any staff."""

    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        for attr in ("user", "created_by", "owner"):
            if hasattr(obj, attr) and getattr(obj, attr) == request.user:
                return True
        return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """Safe methods are open to all authenticated users; writes require staff."""

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff


class CanManageUsers(permissions.BasePermission):
    """
    Read: any authenticated user.
    Write: staff only (cannot modify superusers unless caller is superuser).
    Object: read self or staff; write self or staff with superuser guard.
    """

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff

    def has_object_permission(self, request, view, obj) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return obj == request.user or request.user.is_staff
        if request.user.is_staff:
            if getattr(obj, "is_superuser", False) and not request.user.is_superuser:
                return False
            return True
        return obj == request.user


class CanViewAuditLogs(permissions.BasePermission):
    """Audit log access is restricted to superusers only."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_superuser)


class CanManageSystemConfiguration(permissions.BasePermission):
    """Read: any authenticated. Write: staff only."""

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff


# ---------------------------------------------------------------------------
# Domain-specific permissions
# ---------------------------------------------------------------------------


class CanEscalateResponse(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        return "can_escalate" in _profile_permissions(request)


class CanManageAlerts(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        return "can_manage_alerts" in _profile_permissions(request)


class CanAccessSensitiveData(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        return "can_access_sensitive_data" in _profile_permissions(request)


class IsDataEntryPersonnel(permissions.BasePermission):
    """Create/read/update for everyone; delete requires staff."""

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH"):
            return True
        if request.method == "DELETE":
            return request.user.is_staff
        return False


class IsHealthOfficer(permissions.BasePermission):
    """Staff, or user whose job_title contains a health-related keyword."""

    _KEYWORDS = frozenset({
        "health officer", "doctor", "nurse", "physician",
        "medical officer", "epidemiologist", "public health",
        "clinical officer", "lab technician",
    })

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        p = _profile(request)
        if p and p.job_title:
            title = p.job_title.lower()
            return any(kw in title for kw in self._KEYWORDS)
        return False


class LocationBasedPermission(permissions.BasePermission):
    """
    Object permission: allow access only if the object's location is the user's
    assigned location or a descendant of it. Staff bypass.
    Objects without a location attribute always pass.

    Ancestor walk is cached on the request object so multiple checks within the
    same request hit the DB only once per unique location.
    """

    @staticmethod
    def _ancestor_ids(location) -> frozenset:
        """Return frozenset of all ancestor PKs (inclusive) for a location."""
        ids = set()
        node = location
        while node:
            ids.add(node.pk)
            # Django caches the related instance after the first FK access.
            # Guard against cycles in malformed data.
            node = node.parent
            if node is not None and node.pk in ids:
                break
        return frozenset(ids)

    def has_object_permission(self, request, view, obj) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True

        if not hasattr(obj, "location"):
            return True  # no location constraint

        p = _profile(request)
        if not p or not p.location:
            return False  # user must have an assigned location

        obj_location = getattr(obj, "location", None)
        if obj_location is None:
            return True  # object has no location — allow

        # Use per-request cache to avoid re-walking the same ancestor chain
        cache_attr = "_lbp_ancestor_cache"
        if not hasattr(request, cache_attr):
            setattr(request, cache_attr, {})
        cache = getattr(request, cache_attr)

        loc_pk = obj_location.pk
        if loc_pk not in cache:
            cache[loc_pk] = self._ancestor_ids(obj_location)

        return p.location.pk in cache[loc_pk]


# ---------------------------------------------------------------------------
# Authentication-method permissions
# ---------------------------------------------------------------------------


class IsAPIKeyAuthenticated(permissions.BasePermission):
    """True only if request was authenticated via an APIKey instance."""

    def has_permission(self, request, view) -> bool:
        from .models import APIKey
        return isinstance(getattr(request, "auth", None), APIKey)


# ---------------------------------------------------------------------------
# User-centric permissions
# ---------------------------------------------------------------------------


class IsSelfOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if getattr(request.user, "is_staff", False):
            return True
        if hasattr(obj, "user"):
            return obj.user == request.user
        if obj.__class__.__name__ == "User":
            return obj == request.user
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        for attr in ("user", "created_by"):
            if hasattr(obj, attr) and getattr(obj, attr) == request.user:
                return True
        return False


class IsActiveUser(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class IsVerifiedUser(permissions.BasePermission):
    """Staff bypass; others need email_verified or phone_verified."""

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        p = _profile(request)
        return bool(p and (p.email_verified or p.phone_verified))


class NotLocked(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        p = _profile(request)
        return (not p) or (not p.is_account_locked())


class HasAcceptedTerms(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        p = _profile(request)
        return bool(p and p.terms_accepted_at)


# ---------------------------------------------------------------------------
# Generic profile-permission gate
# ---------------------------------------------------------------------------


class HasPermission(permissions.BasePermission):
    """
    Require a named permission from the user's profile.

    Set ``permission_required = 'can_export_data'`` on the view.
    Staff always pass. If permission_required is unset the check passes.
    """

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True
        required = getattr(view, "permission_required", None)
        if not required:
            return True
        p = _profile(request)
        return bool(p and p.has_permission(required))


# ---------------------------------------------------------------------------
# Rate-limit permission (view-level, distinct from middleware)
# ---------------------------------------------------------------------------


class RateLimitPermission(permissions.BasePermission):
    """
    View-scoped rate limit via cache.
    Set ``rate_limit`` and ``rate_window`` on the view to customise.
    Staff bypass.
    """

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True

        limit = getattr(view, "rate_limit", 100)
        window = getattr(view, "rate_window", 3600)

        from django.core.cache import cache
        key = f"vrl:{request.user.pk}:{view.__class__.__name__}"
        count = cache.get(key, 0)

        if count >= limit:
            logger.warning(
                "View rate limit exceeded: user=%s view=%s",
                request.user.username, view.__class__.__name__,
            )
            return False

        cache.set(key, count + 1, window)
        return True