"""
OryxShield — pytest fixtures
"""
import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username="testadmin",
        email="admin@test.com",
        password="Testpass@2026!",
        is_staff=True,
        is_superuser=True,
    )
    return user


@pytest.fixture
def analyst_user(db):
    group, _ = Group.objects.get_or_create(name="analyst")
    user = User.objects.create_user(
        username="testanalyst",
        email="analyst@test.com",
        password="Testpass@2026!",
        is_staff=False,
    )
    user.groups.add(group)
    return user


@pytest.fixture
def coordinator_user(db):
    group, _ = Group.objects.get_or_create(name="coordinator")
    user = User.objects.create_user(
        username="testcoordinator",
        email="coordinator@test.com",
        password="Testpass@2026!",
        is_staff=False,
    )
    user.groups.add(group)
    return user


@pytest.fixture
def field_officer_user(db):
    group, _ = Group.objects.get_or_create(name="field_officer")
    user = User.objects.create_user(
        username="testfield",
        email="field@test.com",
        password="Testpass@2026!",
        is_staff=False,
    )
    user.groups.add(group)
    return user


@pytest.fixture
def public_user(db):
    return User.objects.create_user(
        username="testpublic",
        email="public@test.com",
        password="Testpass@2026!",
        is_staff=False,
    )


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client
