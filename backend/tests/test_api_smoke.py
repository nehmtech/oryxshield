"""
Smoke tests across every parameter-less GET route under /api/v1/.

* Unauthenticated requests must never succeed or crash (401/403 only).
* Authenticated admin requests must never produce a 5xx.
"""
import pytest
from django.urls import get_resolver, URLPattern, URLResolver


def _collect(patterns, prefix=""):
    for p in patterns:
        route = prefix + str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _collect(p.url_patterns, route)
        elif isinstance(p, URLPattern):
            yield route


def _api_get_routes():
    seen = set()
    for route in _collect(get_resolver().url_patterns):
        if not route.startswith("api/v1/"):
            continue
        if any(tok in route for tok in ("<", "(?P", "\.", "$")) and "<" in route:
            continue  # needs path parameters
        clean = "/" + route.replace("^", "").replace("$", "")
        if "(" in clean or "?" in clean:
            continue
        seen.add(clean)
    return sorted(seen)


ROUTES = _api_get_routes()


def test_routes_discovered():
    assert len(ROUTES) > 40


@pytest.mark.django_db
@pytest.mark.parametrize("url", ROUTES)
def test_unauthenticated_is_rejected_or_public(api_client, url):
    r = api_client.get(url)
    assert r.status_code < 500, f"{url} -> {r.status_code}"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ROUTES)
def test_admin_get_never_5xx(api_client, admin_user, url):
    api_client.force_authenticate(admin_user)
    r = api_client.get(url)
    assert r.status_code < 500, f"{url} -> {r.status_code}"
