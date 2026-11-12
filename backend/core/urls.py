"""
OryxShield — Core URL Configuration
=============================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Mount this module under /api/v1/ in config/urls.py:

    path("api/v1/", include("core.urls", namespace="core")),

Endpoints
---------
Authentication
  POST   /auth/register/              Register new user
  POST   /auth/login/                 Login → JWT tokens
  POST   /auth/logout/                Logout (blacklist refresh token)
  POST   /auth/token/refresh/         Refresh access token
  POST   /auth/token/verify/          Verify token
  POST   /auth/token/blacklist/       Blacklist token
  POST   /auth/change-password/       Change password
  POST   /auth/social/callback/       Social OAuth callback

Users
  GET/POST       /users/              List/create
  GET/PATCH/DEL  /users/{id}/         Detail/update/delete
  GET            /users/me/           Current user
  POST           /users/{id}/activate/
  POST           /users/{id}/deactivate/
  GET            /users/statistics/

Profiles
  GET/PATCH  /profiles/my_profile/   Own profile
  POST       /profiles/enable_2fa/
  POST       /profiles/disable_2fa/

Locations
  GET/POST    /locations/             List/create
  GET/PATCH   /locations/{id}/        Detail/update
  DELETE      /locations/{id}/        Soft-delete
  GET         /locations/tree/        Full hierarchy tree
  GET         /locations/{id}/children/
  GET         /locations/{id}/ancestors/
  GET         /locations/{id}/descendants/
  GET         /locations/nearby/?lat=&lng=&km=

Audit Logs
  GET  /audit-logs/                   List (superuser only)
  GET  /audit-logs/{id}/
  GET  /audit-logs/activity_summary/
  GET  /audit-logs/export_csv/

System Configuration
  GET/POST       /configurations/
  GET/PATCH/DEL  /configurations/{id}/
  GET            /configurations/by_category/
  POST           /configurations/{id}/toggle_active/

Notifications
  GET/POST      /notifications/
  GET/PATCH/DEL /notifications/{id}/
  GET           /notifications/unread/
  GET           /notifications/unread_count/
  POST          /notifications/{id}/mark_read/
  POST          /notifications/mark_all_read/

API Keys
  GET/POST      /api-keys/
  GET/PATCH/DEL /api-keys/{id}/
  POST          /api-keys/{id}/regenerate/
  POST          /api-keys/{id}/revoke/
  GET           /api-keys/{id}/usage_stats/

System
  GET  /health/              Basic liveness probe
  GET  /health/detailed/     Service-level health
  GET  /system/status/       Full status (staff only)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    # ViewSets
    APIKeyViewSet,
    AuditLogViewSet,
    LocationViewSet,
    NotificationViewSet,
    SystemConfigurationViewSet,
    UserProfileViewSet,
    UserViewSet,
    # Auth views
    ChangePasswordView,
    LoginView,
    LogoutView,
    RegisterView,
    SocialAuthCallbackView,
    TwoFactorVerifyView,
    TwoFactorResendView,
    # System views
    health_check,
    health_check_detailed,
    system_status,
)

app_name = "core"

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"profiles", UserProfileViewSet, basename="userprofile")
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"configurations", SystemConfigurationViewSet, basename="configuration")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"api-keys", APIKeyViewSet, basename="apikey")

urlpatterns = [
    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("auth/social/callback/", SocialAuthCallbackView.as_view(), name="social_callback"),
    path("auth/2fa/verify/",  TwoFactorVerifyView.as_view(),  name="2fa_verify"),
    path("auth/2fa/resend/",  TwoFactorResendView.as_view(),  name="2fa_resend"),

    # ------------------------------------------------------------------
    # System / health
    # ------------------------------------------------------------------
    path("health/", health_check, name="health_check"),
    path("health/detailed/", health_check_detailed, name="health_check_detailed"),
    path("system/status/", system_status, name="system_status"),

    # ------------------------------------------------------------------
    # REST API (ViewSets via router)
    # ------------------------------------------------------------------
    path("", include(router.urls)),
]