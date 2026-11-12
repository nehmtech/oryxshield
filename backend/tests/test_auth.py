"""
Tests: authentication endpoints and role derivation.
"""
from tests.constants import TEST_PASSWORD
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, admin_user):
        url = "/api/v1/auth/login/"
        res = api_client.post(url, {"username": "testadmin", "password": TEST_PASSWORD})
        assert res.status_code == 200
        assert "access" in res.data
        assert "refresh" in res.data

    def test_login_wrong_password(self, api_client, admin_user):
        res = api_client.post("/api/v1/auth/login/", {"username": "testadmin", "password": "wrong"})
        assert res.status_code == 401

    def test_me_returns_groups(self, api_client, analyst_user):
        api_client.force_authenticate(user=analyst_user)
        res = api_client.get("/api/v1/users/me/")
        assert res.status_code == 200
        assert "analyst" in res.data["groups"]
        assert res.data["is_staff"] is False

    def test_admin_me_returns_is_staff(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/users/me/")
        assert res.status_code == 200
        assert res.data["is_staff"] is True
        assert res.data["is_superuser"] is True


@pytest.mark.django_db
class TestAssignRole:
    def test_admin_can_assign_role(self, auth_client, public_user):
        url = f"/api/v1/users/{public_user.pk}/assign_role/"
        res = auth_client.post(url, {"role": "analyst"})
        assert res.status_code == 200
        assert res.data["status"] == "success"
        public_user.refresh_from_db()
        assert public_user.groups.filter(name="analyst").exists()
        assert public_user.is_staff is False

    def test_assign_admin_role_sets_is_staff(self, auth_client, public_user):
        url = f"/api/v1/users/{public_user.pk}/assign_role/"
        res = auth_client.post(url, {"role": "admin"})
        assert res.status_code == 200
        public_user.refresh_from_db()
        assert public_user.is_staff is True

    def test_cannot_assign_self(self, auth_client, admin_user):
        url = f"/api/v1/users/{admin_user.pk}/assign_role/"
        res = auth_client.post(url, {"role": "public"})
        assert res.status_code == 400

    def test_invalid_role_rejected(self, auth_client, public_user):
        url = f"/api/v1/users/{public_user.pk}/assign_role/"
        res = auth_client.post(url, {"role": "supervillain"})
        assert res.status_code == 400

    def test_non_staff_cannot_assign_roles(self, api_client, analyst_user, public_user):
        api_client.force_authenticate(user=analyst_user)
        url = f"/api/v1/users/{public_user.pk}/assign_role/"
        res = api_client.post(url, {"role": "analyst"})
        assert res.status_code == 403
