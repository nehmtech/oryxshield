"""
OryxShield — Authentication Backends
=============================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Backends
--------
EmailOrUsernameModelBackend   — username or email login with lockout tracking
APIKeyAuthentication          — DRF authentication class (Authorization: ApiKey <key>)
TwoFactorAuthenticationBackend — password + TOTP/SMS/Email OTP
SocialAuthenticationBackend   — allauth post-login profile enrichment
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def _create_audit_log(user, action: str, request=None, **extra) -> None:
    """Write an AuditLog entry, silently ignoring errors so auth is never broken."""
    try:
        from .models import AuditLog
        AuditLog.log(
            user=user,
            action=action,
            model_name="User",
            object_id=str(user.pk) if user else "",
            ip_address=_get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
            request_method="POST",
            request_path=(request.path if request else ""),
            success=(action in {"LOGIN"}),
            **extra,
        )
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc)


# ---------------------------------------------------------------------------
# EmailOrUsernameModelBackend
# ---------------------------------------------------------------------------


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate with either username or email (case-insensitive).

    Features
    --------
    - Account lockout after configurable failed attempts
    - Successful-login tracking (IP, location, counter reset)
    - Timing-safe by running the hasher even for missing users
    - Audit log on every login attempt (success or fail)
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            User().set_password(password)  # prevent timing oracle
            logger.warning("Login: user not found — identifier=%s", username)
            return None
        except User.MultipleObjectsReturned:
            logger.error("Login: multiple users for identifier=%s", username)
            return None

        if not user.is_active:
            _create_audit_log(user, "LOGIN_FAILED", request, error_message="Account inactive")
            return None

        profile = getattr(user, "profile", None)
        if profile and profile.is_account_locked():
            _create_audit_log(user, "LOGIN_FAILED", request, error_message="Account locked")
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            if profile:
                profile.record_successful_login(
                    ip_address=_get_client_ip(request),
                    location="",  # extend with GeoIP integration if needed
                )
            _create_audit_log(user, "LOGIN", request)
            logger.info("Login success: user=%s", user.username)
            return user

        # Failed password
        if profile:
            locked = profile.record_failed_login(
                max_attempts=getattr(settings, "MAX_LOGIN_ATTEMPTS", 5),
                lockout_minutes=getattr(settings, "LOCKOUT_DURATION_MINUTES", 60),
            )
            if locked:
                logger.warning("Login: account locked — user=%s", user.username)
            else:
                logger.warning("Login: invalid password — user=%s", user.username)
        _create_audit_log(user, "LOGIN_FAILED", request, error_message="Invalid password")
        return None


# ---------------------------------------------------------------------------
# APIKeyAuthentication  (DRF authentication class)
# ---------------------------------------------------------------------------


class APIKeyAuthentication(BaseAuthentication):
    """
    DRF authentication backend for API key access.

    Header format::

        Authorization: ApiKey <key>

    Validates active status, expiry, IP allowlist, then records usage.
    """

    KEYWORD = "ApiKey"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.KEYWORD:
            return None

        raw_key = parts[1]

        try:
            from .models import APIKey
            api_key = APIKey.objects.select_related("user").get(
                key=raw_key, is_deleted=False
            )
        except Exception:
            raise AuthenticationFailed("Invalid API key.")

        if not api_key.is_valid():
            raise AuthenticationFailed("API key is inactive or expired.")

        client_ip = _get_client_ip(request) or ""
        if not api_key.is_ip_allowed(client_ip):
            raise AuthenticationFailed("IP address not authorised for this key.")

        api_key.record_usage(ip_address=client_ip)
        logger.debug("API key auth: user=%s key=%s…", api_key.user.username, raw_key[:8])
        return (api_key.user, api_key)

    def authenticate_header(self, request) -> str:
        return self.KEYWORD


# ---------------------------------------------------------------------------
# TwoFactorAuthenticationBackend
# ---------------------------------------------------------------------------


class TwoFactorAuthenticationBackend(ModelBackend):
    """
    Extends standard password auth with TOTP, SMS, or Email OTP verification.

    When a user's profile has two_factor_enabled=True, the ``otp`` kwarg must be
    supplied.  OTP validation delegates to django-otp (TOTP) or cache-backed
    tokens (SMS/Email).
    """

    def authenticate(self, request, username=None, password=None, otp=None, **kwargs):
        if not username or not password:
            return None

        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)
            return None

        if not user.check_password(password) or not self.user_can_authenticate(user):
            return None

        profile = getattr(user, "profile", None)
        if profile and profile.two_factor_enabled:
            if not otp:
                raise AuthenticationFailed("OTP required for this account.")
            if not self._validate_otp(user, otp):
                if profile:
                    profile.record_failed_login()
                _create_audit_log(user, "LOGIN_FAILED", request, error_message="Invalid OTP")
                raise AuthenticationFailed("Invalid OTP.")

        if profile:
            profile.record_successful_login(ip_address=_get_client_ip(request))
        _create_audit_log(
            user, "LOGIN", request,
            metadata={"two_factor": True},
        )
        return user

    # ------------------------------------------------------------------
    # OTP validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_otp(user, otp: str) -> bool:
        profile = getattr(user, "profile", None)
        if not profile:
            return False
        method = profile.two_factor_method
        if method == "TOTP":
            return TwoFactorAuthenticationBackend._validate_totp(user, otp)
        if method == "SMS":
            return TwoFactorAuthenticationBackend._validate_cache_otp(user, "sms_otp", otp)
        if method == "EMAIL":
            return TwoFactorAuthenticationBackend._validate_cache_otp(user, "email_otp", otp)
        return False

    @staticmethod
    def _validate_totp(user, otp: str) -> bool:
        try:
            from django_otp import match_token
            return match_token(user, otp) is not None
        except Exception as exc:
            logger.error("TOTP validation error: %s", exc)
            return False

    @staticmethod
    def _validate_cache_otp(user, prefix: str, otp: str) -> bool:
        from django.core.cache import cache
        key = f"{prefix}:{user.pk}"
        stored = cache.get(key)
        if stored and stored == otp:
            cache.delete(key)
            return True
        return False


# ---------------------------------------------------------------------------
# SocialAuthenticationBackend
# ---------------------------------------------------------------------------


class SocialAuthenticationBackend:
    """
    Post-login hook invoked by the allauth social_account_added signal.

    Enriches UserProfile with social-auth provider tracking, email verification
    status, and avatar URL from provider extra_data.
    """

    @staticmethod
    def process_social_login(request, social_login) -> None:
        user = social_login.user
        account = social_login.account

        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)

        profile.has_social_auth = True
        if account.provider not in profile.social_providers:
            profile.social_providers.append(account.provider)

        extra = account.extra_data or {}

        # Auto-verify email from trusted providers
        if not profile.email_verified and account.provider in {"google", "facebook"}:
            profile.email_verified = True

        # Cache social avatar URL without downloading
        if not profile.avatar and extra.get("picture"):
            profile.metadata["social_avatar_url"] = extra["picture"]

        # Phone from provider if not already set
        if not profile.phone_number and extra.get("phone"):
            profile.phone_number = extra["phone"]

        profile.save()

        _create_audit_log(
            user, "LOGIN", request,
            metadata={"social_auth": True, "provider": account.provider, "profile_created": created},
        )

        logger.info(
            "Social login: user=%s provider=%s profile_created=%s",
            user.username, account.provider, created,
        )