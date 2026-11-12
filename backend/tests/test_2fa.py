"""
Tests: 2FA login flow — challenge, verify, resend.
"""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestLoginNo2FA:
    """Users without 2FA get tokens immediately."""

    def test_login_returns_tokens(self, api_client, admin_user):
        res = api_client.post("/api/v1/auth/login/", {
            "username": "testadmin", "password": "Testpass@2026!",
        })
        assert res.status_code == 200
        assert res.data["requires_2fa"] is False
        assert "access" in res.data
        assert "refresh" in res.data

    def test_login_wrong_password_rejected(self, api_client, admin_user):
        res = api_client.post("/api/v1/auth/login/", {
            "username": "testadmin", "password": "wrongpass",
        })
        assert res.status_code == 401

    def test_login_missing_fields_rejected(self, api_client):
        res = api_client.post("/api/v1/auth/login/", {"username": "x"})
        assert res.status_code == 400


@pytest.mark.django_db
class TestLogin2FAChallenge:
    """Users with 2FA enabled receive a session_token challenge, not tokens."""

    @pytest.fixture
    def user_with_2fa(self, db):
        from django.contrib.auth.models import User
        user = User.objects.create_user(
            username="twofa_user", email="twofa@test.com",
            password="Testpass@2026!", is_active=True,
        )
        profile = user.profile
        profile.two_factor_enabled = True
        profile.two_factor_method = "EMAIL"
        profile.save()
        return user

    def test_2fa_login_returns_challenge(self, api_client, user_with_2fa):
        res = api_client.post("/api/v1/auth/login/", {
            "username": "twofa_user", "password": "Testpass@2026!",
        })
        assert res.status_code == 200
        assert res.data["requires_2fa"] is True
        assert "session_token" in res.data
        assert res.data["method"] == "email"
        assert "access" not in res.data

    def test_2fa_challenge_cached(self, api_client, user_with_2fa):
        res = api_client.post("/api/v1/auth/login/", {
            "username": "twofa_user", "password": "Testpass@2026!",
        })
        session_token = res.data["session_token"]
        cached = cache.get(f"2fa_session:{session_token}")
        assert cached == str(user_with_2fa.pk)


@pytest.mark.django_db
class TestTwoFactorVerify:
    """POST /auth/2fa/verify/ validates OTP and issues JWT."""

    @pytest.fixture
    def session_and_user(self, db):
        from django.contrib.auth.models import User
        import secrets

        user = User.objects.create_user(
            username="verify_user", email="verify@test.com",
            password="Testpass@2026!", is_active=True,
        )
        profile = user.profile
        profile.two_factor_enabled = True
        profile.two_factor_method = "EMAIL"
        profile.save()

        # Simulate the challenge cache entries
        session_token = secrets.token_urlsafe(32)
        otp = "123456"
        cache.set(f"2fa_session:{session_token}", str(user.pk), 300)
        cache.set(f"email_otp:{user.pk}", otp, 300)
        return session_token, otp, user

    def test_verify_correct_otp_returns_tokens(self, api_client, session_and_user):
        session_token, otp, user = session_and_user
        res = api_client.post("/api/v1/auth/2fa/verify/", {
            "session_token": session_token, "code": otp,
        })
        assert res.status_code == 200
        assert "access" in res.data
        assert "refresh" in res.data
        assert res.data["user"]["username"] == "verify_user"

    def test_verify_wrong_otp_rejected(self, api_client, session_and_user):
        session_token, otp, user = session_and_user
        res = api_client.post("/api/v1/auth/2fa/verify/", {
            "session_token": session_token, "code": "000000",
        })
        assert res.status_code == 401

    def test_verify_expired_session_rejected(self, api_client):
        res = api_client.post("/api/v1/auth/2fa/verify/", {
            "session_token": "nonexistent_token", "code": "123456",
        })
        assert res.status_code == 401

    def test_verify_missing_fields_rejected(self, api_client):
        res = api_client.post("/api/v1/auth/2fa/verify/", {"session_token": "x"})
        assert res.status_code == 400

    def test_session_consumed_after_verify(self, api_client, session_and_user):
        """Session token should be invalidated after successful verify."""
        session_token, otp, user = session_and_user
        api_client.post("/api/v1/auth/2fa/verify/", {
            "session_token": session_token, "code": otp,
        })
        assert cache.get(f"2fa_session:{session_token}") is None


@pytest.mark.django_db
class TestTwoFactorResend:
    """POST /auth/2fa/resend/ generates and resends OTP."""

    @pytest.fixture
    def session_with_sms_user(self, db):
        from django.contrib.auth.models import User
        import secrets

        user = User.objects.create_user(
            username="resend_user", email="resend@test.com",
            password="Testpass@2026!", is_active=True,
        )
        profile = user.profile
        profile.two_factor_enabled = True
        profile.two_factor_method = "SMS"
        profile.phone_number = "+264810000001"
        profile.save()

        session_token = secrets.token_urlsafe(32)
        cache.set(f"2fa_session:{session_token}", str(user.pk), 300)
        return session_token, user

    def test_resend_valid_session(self, api_client, session_with_sms_user):
        session_token, user = session_with_sms_user
        res = api_client.post("/api/v1/auth/2fa/resend/", {
            "session_token": session_token,
        })
        assert res.status_code == 200
        assert res.data["status"] == "success"
        # New OTP should be in cache
        assert cache.get(f"sms_otp:{user.pk}") is not None

    def test_resend_expired_session_rejected(self, api_client):
        res = api_client.post("/api/v1/auth/2fa/resend/", {
            "session_token": "expired_token",
        })
        assert res.status_code == 401

    def test_resend_cooldown_enforced(self, api_client, session_with_sms_user):
        session_token, user = session_with_sms_user
        # First resend — succeeds
        api_client.post("/api/v1/auth/2fa/resend/", {"session_token": session_token})
        # Second resend — within cooldown window, should be throttled
        res = api_client.post("/api/v1/auth/2fa/resend/", {"session_token": session_token})
        assert res.status_code == 429
