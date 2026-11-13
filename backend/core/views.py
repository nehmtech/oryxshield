"""
OryxShield — Core Views
=================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

ViewSets
--------
UserViewSet              — user CRUD + activate/deactivate/statistics
UserProfileViewSet       — profile read/update + 2FA enable/disable
LocationViewSet          — location CRUD + tree/children/ancestors/descendants/nearby
AuditLogViewSet          — read-only + activity_summary + export_csv
SystemConfigurationViewSet — CRUD + by_category + toggle_active
NotificationViewSet      — CRUD + unread/unread_count/mark_read/mark_all_read
APIKeyViewSet            — CRUD + regenerate + revoke + usage_stats

Auth views (APIView)
--------------------
RegisterView, LoginView, LogoutView, ChangePasswordView, SocialAuthCallbackView

System views (function-based)
------------------------------
health_check, health_check_detailed, system_status
"""

from __future__ import annotations

import csv
import logging

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import MethodNotAllowed
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import APIKeyAuthentication
from .exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError as OryxShieldValidationError,
)
from .mixins import (
    AuditMixin,
    BulkOperationsMixin,
    ExportMixin,
    SoftDeleteViewMixin,
    StatisticsMixin,
)
from .models import (
    APIKey,
    AuditLog,
    Location,
    Notification,
    SystemConfiguration,
    UserProfile,
)
from .pagination import CustomPagination, LargePagination, SmallPagination
from .permissions import (
    CanManageSystemConfiguration,
    CanManageUsers,
    CanViewAuditLogs,
    IsActiveUser,
    IsAdminOrReadOnly,
    IsOwnerOrAdmin,
)
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    AuditLogSerializer,
    ChangePasswordSerializer,
    LocationDetailSerializer,
    LocationSerializer,
    LocationTreeSerializer,
    LoginResponseSerializer,
    MessageSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
    SystemConfigurationSerializer,
    SystemConfigurationWriteSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    UserSerializer,
)
from .utils import get_client_ip

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# ---------------------------------------------------------------------------
# UserViewSet
# ---------------------------------------------------------------------------


class UserViewSet(viewsets.ModelViewSet, StatisticsMixin):
    """
    CRUD for User model.

    Endpoints (relative to /api/v1/users/)
    GET    /               — list (staff only for all; self for non-staff)
    POST   /               — create (staff only)
    GET    /{id}/          — retrieve
    PATCH  /{id}/          — update
    DELETE /{id}/          — delete (staff only)
    GET    /me/            — current user
    POST   /{id}/activate/ — activate (staff only)
    POST   /{id}/deactivate/ — deactivate (staff only)
    GET    /statistics/    — user statistics
    """

    permission_classes = [IsAuthenticated, CanManageUsers]
    pagination_class = CustomPagination
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "date_joined", "last_login"]
    ordering = ["-date_joined"]

    # Roles that map to groups (not is_staff flags)
    ROLE_GROUPS = ["analyst", "coordinator", "field_officer"]

    def get_queryset(self):
        qs = (
            User.objects
            .select_related("profile")
            .prefetch_related("groups")
            .order_by("-date_joined")
        )
        if not self.request.user.is_staff:
            qs = qs.filter(pk=self.request.user.pk)

        # Optional is_active filter from query params
        params = self.request.query_params
        if is_active := params.get("is_active"):
            qs = qs.filter(is_active=(is_active.lower() == "true"))

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("retrieve", "me"):
            return UserDetailSerializer
        return UserSerializer

    @action(detail=False, methods=["get"])
    def me(self, request) -> Response:
        """Return the currently authenticated user's full record."""
        serializer = UserDetailSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageUsers])
    def activate(self, request, pk=None) -> Response:
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"status": "success", "message": f"User {user.username} activated."})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageUsers])
    def deactivate(self, request, pk=None) -> Response:
        user = self.get_object()
        if user == request.user:
            return Response(
                {"error": "Cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"status": "success", "message": f"User {user.username} deactivated."})

    @action(detail=False, methods=["get"])
    def statistics(self, request) -> Response:
        return Response({
            "total": User.objects.count(),
            "active": User.objects.filter(is_active=True).count(),
            "staff": User.objects.filter(is_staff=True).count(),
            "new_this_week": User.objects.filter(
                date_joined__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
        })

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageUsers])
    def assign_role(self, request, pk=None) -> Response:
        """
        POST /users/{id}/assign_role/
        Body: { "role": "admin" | "analyst" | "coordinator" | "field_officer" | "public" }

        - admin       → is_staff=True  + remove group membership
        - analyst     → is_staff=False + group 'analyst'
        - coordinator → is_staff=False + group 'coordinator'
        - field_officer → is_staff=False + group 'field_officer'
        - public      → is_staff=False + remove all role groups
        """
        user = self.get_object()
        if user == request.user:
            return Response(
                {"error": "Cannot change your own role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if getattr(user, "is_superuser", False) and not request.user.is_superuser:
            return Response(
                {"error": "Only superusers can modify superuser accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = request.data.get("role", "").lower()
        valid_roles = ["admin", "analyst", "coordinator", "field_officer", "public"]
        if role not in valid_roles:
            return Response(
                {"error": f"Invalid role. Must be one of: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Remove user from all role-based groups
        role_group_names = self.ROLE_GROUPS
        role_groups = Group.objects.filter(name__in=role_group_names)
        user.groups.remove(*role_groups)

        if role == "admin":
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        elif role in role_group_names:
            user.is_staff = False
            user.save(update_fields=["is_staff"])
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
        else:
            # public — remove staff and all groups
            user.is_staff = False
            user.save(update_fields=["is_staff"])

        AuditLog.log(
            user=request.user,
            action=AuditLog.ActionType.UPDATE,
            model_name="User",
            object_id=str(user.pk),
            object_repr=user.username,
            changes={"role": role},
            ip_address=get_client_ip(request),
            request_method="POST",
            request_path=request.path,
            success=True,
        )

        from .serializers import UserDetailSerializer as _UDS
        return Response({
            "status": "success",
            "message": f"{user.username} assigned role '{role}'.",
            "user": _UDS(user, context={"request": request}).data,
        })


# ---------------------------------------------------------------------------
# UserProfileViewSet
# ---------------------------------------------------------------------------


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    Profile read/update.

    GET    /profiles/my_profile/ — current user profile
    PATCH  /profiles/my_profile/ — update current user profile
    POST   /profiles/enable_2fa/ — enable 2FA
    POST   /profiles/disable_2fa/ — disable 2FA
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = SmallPagination

    def create(self, request, *args, **kwargs):
        # Profiles are created automatically with their user (signal); never via the API.
        raise MethodNotAllowed(request.method)

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserProfile.objects.select_related("user", "location").all()
        return UserProfile.objects.filter(user=self.request.user).select_related("user", "location")

    def get_serializer_class(self):
        if self.action in ("update", "partial_update", "my_profile"):
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    @action(detail=False, methods=["get", "patch"])
    def my_profile(self, request) -> Response:
        profile = request.user.profile
        if request.method == "PATCH":
            serializer = UserProfileUpdateSerializer(
                profile, data=request.data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(UserProfileSerializer(profile, context={"request": request}).data)
        return Response(UserProfileSerializer(profile, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def enable_2fa(self, request) -> Response:
        profile = request.user.profile
        method = request.data.get("method", "TOTP")
        if method not in [c[0] for c in UserProfile.TwoFactorMethod.choices]:
            return Response({"error": "Invalid 2FA method."}, status=status.HTTP_400_BAD_REQUEST)
        profile.two_factor_enabled = True
        profile.two_factor_method = method
        profile.save(update_fields=["two_factor_enabled", "two_factor_method"])
        return Response({"status": "success", "message": f"2FA enabled via {method}."})

    @action(detail=False, methods=["post"])
    def disable_2fa(self, request) -> Response:
        profile = request.user.profile
        profile.two_factor_enabled = False
        profile.save(update_fields=["two_factor_enabled"])
        return Response({"status": "success", "message": "2FA disabled."})


# ---------------------------------------------------------------------------
# LocationViewSet
# ---------------------------------------------------------------------------


class LocationViewSet(viewsets.ModelViewSet, SoftDeleteViewMixin):
    """
    Hierarchical location management.

    GET  /locations/tree/                — full tree
    GET  /locations/{id}/children/       — direct children
    GET  /locations/{id}/ancestors/      — ancestors to root
    GET  /locations/{id}/descendants/    — all descendants
    GET  /locations/nearby/?lat=&lng=&km= — within radius
    """

    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = CustomPagination
    search_fields = ["name", "code"]
    ordering_fields = ["name", "location_type", "created_at"]

    def get_queryset(self):
        return Location.objects.filter(is_deleted=False).select_related("parent")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LocationDetailSerializer
        if self.action == "tree":
            return LocationTreeSerializer
        return LocationSerializer

    def perform_destroy(self, instance: Location) -> None:
        instance.soft_delete()

    @action(detail=False, methods=["get"])
    def tree(self, request) -> Response:
        roots = self.get_queryset().filter(parent=None)
        serializer = LocationTreeSerializer(roots, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None) -> Response:
        loc = self.get_object()
        qs = loc.children.filter(is_deleted=False)
        serializer = LocationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def ancestors(self, request, pk=None) -> Response:
        loc = self.get_object()
        serializer = LocationSerializer(loc.get_ancestors(), many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def descendants(self, request, pk=None) -> Response:
        loc = self.get_object()
        qs = loc.get_descendants()
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = LocationSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = LocationSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def nearby(self, request) -> Response:
        from .utils import calculate_distance_km
        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
            radius_km = float(request.query_params.get("km", 50))
        except (KeyError, ValueError):
            return Response(
                {"error": "lat, lng query params are required (km optional, default 50)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidates = self.get_queryset().exclude(latitude=None).exclude(longitude=None)
        nearby = [
            loc for loc in candidates
            if calculate_distance_km(lat, lng, float(loc.latitude), float(loc.longitude)) <= radius_km
        ]
        serializer = LocationSerializer(nearby, many=True, context={"request": request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# AuditLogViewSet
# ---------------------------------------------------------------------------


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet, ExportMixin):
    """
    Read-only audit log. Superuser only.

    GET /audit-logs/activity_summary/ — aggregated activity
    GET /audit-logs/export_csv/       — CSV download
    """

    permission_classes = [IsAuthenticated, CanViewAuditLogs]
    pagination_class = LargePagination
    serializer_class = AuditLogSerializer
    search_fields = ["user__username", "action", "model_name", "ip_address"]
    ordering_fields = ["timestamp", "action", "model_name"]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user").order_by("-timestamp")
        params = self.request.query_params
        if user_id := params.get("user_id"):
            qs = qs.filter(user_id=user_id)
        if action := params.get("action"):
            qs = qs.filter(action=action)
        if model := params.get("model_name"):
            qs = qs.filter(model_name__icontains=model)
        if start := params.get("start_date"):
            qs = qs.filter(timestamp__date__gte=start)
        if end := params.get("end_date"):
            qs = qs.filter(timestamp__date__lte=end)
        return qs

    @action(detail=False, methods=["get"])
    def activity_summary(self, request) -> Response:
        from django.db.models import Count
        summary = (
            AuditLog.objects.values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response({"summary": list(summary)})

    @action(detail=False, methods=["get"])
    def export_csv(self, request) -> HttpResponse:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(["Timestamp", "User", "Action", "Model", "Object ID", "IP", "Success"])
        for log in self.get_queryset()[:50000]:
            writer.writerow([
                log.timestamp.isoformat(),
                log.user.username if log.user else "Anonymous",
                log.action, log.model_name, log.object_id,
                log.ip_address or "", log.success,
            ])
        return response


# ---------------------------------------------------------------------------
# SystemConfigurationViewSet
# ---------------------------------------------------------------------------


class SystemConfigurationViewSet(viewsets.ModelViewSet):
    """
    System configuration management.

    GET /configurations/by_category/       — grouped by category
    POST /configurations/{id}/toggle_active/ — flip is_active
    """

    permission_classes = [IsAuthenticated, CanManageSystemConfiguration]
    pagination_class = CustomPagination
    search_fields = ["key", "description"]
    ordering_fields = ["key", "category", "created_at"]

    def get_queryset(self):
        qs = SystemConfiguration.objects.filter(is_deleted=False)
        if cat := self.request.query_params.get("category"):
            qs = qs.filter(category=cat)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SystemConfigurationWriteSerializer
        return SystemConfigurationSerializer

    @action(detail=False, methods=["get"])
    def by_category(self, request) -> Response:
        grouped: dict = {}
        for cfg in self.get_queryset().order_by("category", "key"):
            cat = cfg.get_category_display()
            grouped.setdefault(cat, []).append(
                SystemConfigurationSerializer(cfg, context={"request": request}).data
            )
        return Response(grouped)

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None) -> Response:
        cfg = self.get_object()
        cfg.is_active = not cfg.is_active
        cfg.save(update_fields=["is_active"])
        return Response({
            "status": "success",
            "key": cfg.key,
            "is_active": cfg.is_active,
        })


# ---------------------------------------------------------------------------
# NotificationViewSet
# ---------------------------------------------------------------------------


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Notification management (each user sees their own).

    GET  /notifications/unread/         — unread notifications
    GET  /notifications/unread_count/   — count of unread
    POST /notifications/{id}/mark_read/ — mark one read
    POST /notifications/mark_all_read/  — mark all read
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = SmallPagination

    def get_queryset(self):
        qs = Notification.objects.filter(is_deleted=False)
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs.select_related("user").order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return NotificationCreateSerializer
        return NotificationSerializer

    def perform_create(self, serializer) -> None:
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=["get"])
    def unread(self, request) -> Response:
        qs = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(NotificationSerializer(page, many=True).data)
        return Response(NotificationSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request) -> Response:
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None) -> Response:
        notif = self.get_object()
        notif.mark_as_read()
        return Response({"status": "success", "message": "Notification marked as read."})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request) -> Response:
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"status": "success", "notifications_marked": updated})


# ---------------------------------------------------------------------------
# APIKeyViewSet
# ---------------------------------------------------------------------------


class APIKeyViewSet(viewsets.ModelViewSet, SoftDeleteViewMixin):
    """
    API key management.

    POST /api-keys/{id}/regenerate/  — regenerate key
    POST /api-keys/{id}/revoke/      — revoke key
    GET  /api-keys/{id}/usage_stats/ — usage statistics
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = SmallPagination

    def get_queryset(self):
        qs = APIKey.objects.filter(is_deleted=False)
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs.select_related("user")

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None) -> Response:
        api_key = self.get_object()
        new_key = api_key.regenerate()
        return Response({
            "status": "success",
            "key": new_key,
            "warning": "Store this key securely. It will not be shown again.",
        })

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None) -> Response:
        api_key = self.get_object()
        api_key.revoke()
        return Response({"status": "success", "message": "API key revoked."})

    @action(detail=True, methods=["get"])
    def usage_stats(self, request, pk=None) -> Response:
        api_key = self.get_object()
        return Response({
            "usage_count": api_key.usage_count,
            "last_used_at": api_key.last_used_at,
            "last_used_ip": api_key.last_used_ip,
            "is_valid": api_key.is_valid(),
            "expires_at": api_key.expires_at,
        })


# ---------------------------------------------------------------------------
# Authentication views
# ---------------------------------------------------------------------------


class RegisterView(APIView):
    """POST /auth/register/ — create a new user account."""

    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        serializer = UserCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = _tokens_for_user(user)
        return Response(
            {
                "status": "success",
                "message": "Account created successfully.",
                "user": UserSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /auth/login/ — authenticate and return JWT tokens or 2FA challenge.

    Response when 2FA disabled:
        { status, user, access, refresh }

    Response when 2FA enabled (step 1 of 2):
        { status, requires_2fa: true, session_token, method }
        → Client then POSTs to /auth/2fa/verify/ with { session_token, code }
    """

    permission_classes = [AllowAny]

    _SESSION_TTL = 300  # 5 minutes for 2FA challenge window

    def post(self, request) -> Response:
        username = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "username/email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 1: verify password only (before 2FA check)
        user = self._verify_password(request, username, password)
        if user is None:
            return Response(
                {"error": "Invalid credentials or account locked."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Step 2: if 2FA enabled, issue challenge instead of tokens
        profile = getattr(user, "profile", None)
        if profile and profile.two_factor_enabled:
            return self._issue_2fa_challenge(request, user, profile)

        # No 2FA — issue tokens immediately
        AuditLog.log(
            user=user,
            action=AuditLog.ActionType.LOGIN,
            model_name="User",
            object_id=str(user.pk),
            ip_address=get_client_ip(request),
            request_method="POST",
            request_path=request.path,
            success=True,
        )
        tokens = _tokens_for_user(user)
        return Response({
            "status": "success",
            "requires_2fa": False,
            "user": UserDetailSerializer(user, context={"request": request}).data,
            **tokens,
        })

    @staticmethod
    def _verify_password(request, username: str, password: str):
        """Verify username+password using EmailOrUsernameModelBackend only."""
        from django.contrib.auth.backends import ModelBackend
        from .authentication import EmailOrUsernameModelBackend
        backend = EmailOrUsernameModelBackend()
        return backend.authenticate(request, username=username, password=password)

    def _issue_2fa_challenge(self, request, user, profile) -> Response:
        """Generate a session token, optionally send OTP, return challenge."""
        import secrets as _secrets
        from django.core.cache import cache

        session_token = _secrets.token_urlsafe(32)
        cache_key = f"2fa_session:{session_token}"
        cache.set(cache_key, str(user.pk), self._SESSION_TTL)

        method = profile.two_factor_method  # TOTP | SMS | EMAIL

        # For SMS/Email: generate and deliver a 6-digit OTP
        if method in ("SMS", "EMAIL"):
            otp = f"{_secrets.randbelow(900000) + 100000:06d}"
            otp_prefix = "sms_otp" if method == "SMS" else "email_otp"
            cache.set(f"{otp_prefix}:{user.pk}", otp, self._SESSION_TTL)
            self._deliver_otp(user, profile, method, otp)

        logger.info("2FA challenge issued: user=%s method=%s ip=%s",
                    user.username, method, get_client_ip(request))

        return Response({
            "status": "success",
            "requires_2fa": True,
            "session_token": session_token,
            "method": method.lower(),
        })

    @staticmethod
    def _deliver_otp(user, profile, method: str, otp: str) -> None:
        """Best-effort OTP delivery — never raises."""
        try:
            if method == "SMS" and profile.phone_number:
                from communications.sms_gateway import sms_gateway
                sms_gateway.send_sms(
                    profile.phone_number,
                    f"Your OryxShield verification code is {otp}. Valid for 5 minutes.",
                )
            elif method == "EMAIL":
                from communications.email_service import email_service
                email_service.send_simple_email(
                    to_email=user.email,
                    subject="OryxShield — Your verification code",
                    body=f"Your verification code is: {otp}\n\nThis code expires in 5 minutes.",
                )
        except Exception as exc:
            logger.warning("OTP delivery failed for user=%s method=%s: %s",
                           user.username, method, exc)


class TwoFactorVerifyView(APIView):
    """
    POST /auth/2fa/verify/ — verify 2FA code and issue JWT tokens.

    Body: { session_token, code }
    """

    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        from django.core.cache import cache
        from .authentication import TwoFactorAuthenticationBackend

        session_token = request.data.get("session_token", "").strip()
        code = request.data.get("code", "").strip()

        if not session_token or not code:
            return Response(
                {"error": "session_token and code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"2fa_session:{session_token}"
        user_id = cache.get(cache_key)
        if not user_id:
            return Response(
                {"error": "Session expired or invalid. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = User.objects.select_related("profile").get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found or account deactivated."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not TwoFactorAuthenticationBackend._validate_otp(user, code):
            AuditLog.log(
                user=user,
                action=AuditLog.ActionType.LOGIN_FAILED,
                model_name="User",
                object_id=str(user.pk),
                ip_address=get_client_ip(request),
                request_method="POST",
                request_path=request.path,
                success=False,
                error_message="Invalid 2FA OTP",
            )
            return Response(
                {"error": "Invalid verification code."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # OTP valid — consume session, issue JWT
        cache.delete(cache_key)

        if hasattr(user, "profile"):
            user.profile.record_successful_login(ip_address=get_client_ip(request))

        AuditLog.log(
            user=user,
            action=AuditLog.ActionType.LOGIN,
            model_name="User",
            object_id=str(user.pk),
            ip_address=get_client_ip(request),
            request_method="POST",
            request_path=request.path,
            success=True,
            metadata={"two_factor": True},
        )

        tokens = _tokens_for_user(user)
        return Response({
            "status": "success",
            "user": UserDetailSerializer(user, context={"request": request}).data,
            **tokens,
        })


class TwoFactorResendView(APIView):
    """
    POST /auth/2fa/resend/ — resend OTP for an active 2FA session.

    Body: { session_token }
    """

    permission_classes = [AllowAny]

    # Minimum seconds between resend requests (anti-spam)
    _RESEND_COOLDOWN = 60

    def post(self, request) -> Response:
        from django.core.cache import cache

        session_token = request.data.get("session_token", "").strip()
        if not session_token:
            return Response(
                {"error": "session_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"2fa_session:{session_token}"
        user_id = cache.get(cache_key)
        if not user_id:
            return Response(
                {"error": "Session expired or invalid. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Cooldown check
        cooldown_key = f"2fa_resend_cooldown:{session_token}"
        if cache.get(cooldown_key):
            return Response(
                {"error": f"Please wait {self._RESEND_COOLDOWN} seconds before requesting a new code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            user = User.objects.select_related("profile").get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = getattr(user, "profile", None)
        if not profile or profile.two_factor_method not in ("SMS", "EMAIL"):
            return Response(
                {"error": "Resend is only available for SMS and Email 2FA methods."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate and resend OTP
        import secrets as _secrets
        otp = f"{_secrets.randbelow(900000) + 100000:06d}"
        otp_prefix = "sms_otp" if profile.two_factor_method == "SMS" else "email_otp"
        cache.set(f"{otp_prefix}:{user.pk}", otp, 300)
        cache.set(cooldown_key, "1", self._RESEND_COOLDOWN)

        LoginView._deliver_otp(user, profile, profile.two_factor_method, otp)

        logger.info("2FA OTP resent: user=%s method=%s", user.username, profile.two_factor_method)
        return Response({"status": "success", "message": "Verification code resent."})


class LogoutView(APIView):
    """POST /auth/logout/ — blacklist the refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Blacklisting failure should not prevent UX logout

        return Response({"status": "success", "message": "Logged out successfully."})


class ChangePasswordView(APIView):
    """POST /auth/change-password/ — change the authenticated user's password."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.ActionType.PASSWORD_CHANGE,
            model_name="User",
            object_id=str(request.user.pk),
            ip_address=get_client_ip(request),
            request_method="POST",
            request_path=request.path,
            success=True,
        )
        return Response({"status": "success", "message": "Password changed successfully."})


class SocialAuthCallbackView(APIView):
    """POST /auth/social/callback/ — handle social OAuth callback and issue JWT."""

    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        # allauth handles the OAuth flow; this endpoint issues JWT for SPA clients
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": "Social authentication failed."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        tokens = _tokens_for_user(request.user)
        return Response({
            "status": "success",
            "user": UserDetailSerializer(request.user, context={"request": request}).data,
            **tokens,
        })


# ---------------------------------------------------------------------------
# System / health views
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request) -> Response:
    """GET /health/ — basic liveness probe."""
    return Response({"status": "ok", "timestamp": timezone.now().isoformat()})


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check_detailed(request) -> Response:
    """GET /health/detailed/ — service-level health check (uses cached results)."""
    cached = cache.get("service_health")
    if cached:
        return Response(cached)

    result: dict = {"timestamp": timezone.now().isoformat()}

    # Database
    try:
        User.objects.count()
        result["database"] = "ok"
    except Exception as exc:
        result["database"] = f"error: {exc}"

    # Cache
    try:
        cache.set("_probe", "1", 5)
        result["cache"] = "ok" if cache.get("_probe") == "1" else "error"
    except Exception as exc:
        result["cache"] = f"error: {exc}"

    result["overall"] = "ok" if all(v == "ok" for k, v in result.items() if k != "timestamp") else "degraded"
    cache.set("service_health", result, 60)
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def system_status(request) -> Response:
    """GET /system/status/ — comprehensive system status (staff only)."""
    if not request.user.is_staff:
        return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

    metrics = cache.get("system_metrics") or {}
    health = cache.get("service_health") or {}
    report = cache.get("daily_system_report") or {}

    return Response({
        "metrics": metrics,
        "health": health,
        "last_report": report,
        "timestamp": timezone.now().isoformat(),
    })