"""
Negative-path tests for every /api/v1/ route (including detail routes):
bad bodies and unknown IDs must produce 4xx, never a server error, and
anonymous users must not be able to modify data.
"""
import re
import uuid

import pytest
from django.urls import get_resolver, URLPattern, URLResolver

FAKE_ID = str(uuid.uuid4())
# Public or special endpoints where anonymous POST is legitimate or has side effects
ANON_POST_OK = ("auth/", "contact", "feedback", "webhooks", "public", "password", "register", "token")
SKIP = ("ws-mgmt", "schema", "docs", "logout")


def _collect(patterns, prefix=""):
    for p in patterns:
        route = prefix + str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _collect(p.url_patterns, route)
        elif isinstance(p, URLPattern):
            yield route


def _routes():
    out = set()
    for route in _collect(get_resolver().url_patterns):
        if not route.startswith("api/v1/") or "(?P<format>" in route or "\." in route:
            continue
        r = re.sub(r"<(?:uuid|int|str|slug):?\w*>|<\w+>", FAKE_ID, route)
        r = re.sub(r"\(\?P<\w+>[^)]*\)", FAKE_ID, r).replace("^", "").replace("$", "")
        if "(" in r or "?" in r:
            continue
        if any(s in r for s in SKIP):
            continue
        out.add("/" + r)
    return sorted(out)


ROUTES = _routes()
GARBAGE = {"x": "y", "id": "not-a-uuid", "location": "zzz", "start_date": "nope", "amount": -1}


def test_routes_found():
    assert len(ROUTES) > 100


@pytest.mark.django_db
@pytest.mark.parametrize("url", ROUTES)
def test_admin_bad_writes_never_5xx(api_client, admin_user, url):
    api_client.force_authenticate(admin_user)
    for method in ("post", "put", "patch", "delete"):
        for body in ({}, GARBAGE):
            r = getattr(api_client, method)(url, body, format="json")
            assert r.status_code < 500, f"{method.upper()} {url} {body} -> {r.status_code}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ROUTES)
def test_anonymous_cannot_modify(api_client, url):
    if any(tok in url for tok in ANON_POST_OK):
        pytest.skip("public endpoint")
    for method in ("post", "put", "patch", "delete"):
        r = getattr(api_client, method)(url, {}, format="json")
        assert r.status_code in (401, 403, 404, 405), f"{method.upper()} {url} -> {r.status_code}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ROUTES)
def test_low_privilege_bad_writes_never_5xx(api_client, field_officer_user, url):
    api_client.force_authenticate(field_officer_user)
    for method in ("post", "put", "patch", "delete"):
        r = getattr(api_client, method)(url, GARBAGE, format="json")
        assert r.status_code < 500, f"{method.upper()} {url} -> {r.status_code}"


@pytest.mark.django_db
def test_profile_create_not_allowed(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    assert api_client.post("/api/v1/profiles/", {}, format="json").status_code == 405


@pytest.mark.django_db
def test_mobile_ping_is_get_only(api_client):
    assert api_client.get("/api/v1/mobile/ping/").status_code == 200
    assert api_client.post("/api/v1/mobile/ping/", {}, format="json").status_code == 405
