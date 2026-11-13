"""
Seeded-data tests: every GET route must work against realistic data (no 5xx),
stay inside a query budget (guards against N+1 regressions) and respond quickly.
"""
import time

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.test_api_smoke import ROUTES

MAX_QUERIES = 40
MAX_SECONDS = 1.5
WARM_UP = "/api/v1/"  # first request pays one-off import/URL-resolver cost


@pytest.fixture
def seeded(db, monkeypatch):
    monkeypatch.setenv("SEED_USER_PASSWORD", "unused-in-tests")
    call_command("seed_data", verbosity=0)


@pytest.mark.django_db
def test_all_get_routes_with_seed_data(api_client, admin_user, seeded):
    api_client.force_authenticate(admin_user)
    api_client.get(WARM_UP)
    failures = []
    for url in ROUTES:
        if url == WARM_UP:
            continue
        with CaptureQueriesContext(connection) as ctx:
            t0 = time.perf_counter()
            r = api_client.get(url)
            dt = time.perf_counter() - t0
        if r.status_code >= 500:
            failures.append(f"{url}: HTTP {r.status_code}")
        if len(ctx) > MAX_QUERIES:
            failures.append(f"{url}: {len(ctx)} queries (budget {MAX_QUERIES})")
        if dt > MAX_SECONDS:
            failures.append(f"{url}: {dt:.2f}s (budget {MAX_SECONDS}s)")
    assert not failures, "\n".join(failures)


@pytest.mark.django_db
def test_location_tree_is_single_query_and_correct(api_client, admin_user):
    from core.models import Location
    root = Location.objects.create(name="Namibia", code="NA", location_type="COUNTRY")
    for i in range(5):
        region = Location.objects.create(name=f"R{i}", code=f"R{i}", location_type="REGION", parent=root)
        for j in range(5):
            Location.objects.create(name=f"C{i}{j}", code=f"C{i}{j}", location_type="CONSTITUENCY", parent=region)
    dead = Location.objects.create(name="Gone", code="GONE", location_type="REGION", parent=root)
    dead.is_deleted = True
    dead.save()

    api_client.force_authenticate(admin_user)
    with CaptureQueriesContext(connection) as ctx:
        r = api_client.get("/api/v1/locations/tree/")
    data = r.json()
    assert r.status_code == 200 and len(data) == 1
    assert len(data[0]["children"]) == 5                      # soft-deleted excluded
    assert all(len(c["children"]) == 5 for c in data[0]["children"])
    assert len(ctx) <= 6, f"tree used {len(ctx)} queries"    # auth/session overhead only


@pytest.mark.django_db
def test_large_responses_are_gzipped(api_client, admin_user):
    from core.models import Location
    for i in range(80):
        Location.objects.create(name=f"Location number {i}", code=f"L{i}", location_type="WARD")
    api_client.force_authenticate(admin_user)
    r = api_client.get("/api/v1/locations/", {"page_size": 100}, HTTP_ACCEPT_ENCODING="gzip")
    assert r.status_code == 200
    assert r.headers.get("Content-Encoding") == "gzip"
