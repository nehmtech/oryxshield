"""Tests: early-warning statistics and API endpoint."""
from datetime import timedelta

import pytest
from django.utils import timezone

from surveillance import early_warning as ew

FLAT = [4, 5, 3, 4, 6, 5, 4, 5, 4, 3, 5, 4, 5, 4, 6, 5, 4, 5, 4, 5]
SURGE = FLAT + [12, 18, 27, 40]


class TestHelpers:
    def test_fill_daily_series(self):
        from datetime import date
        s = ew.fill_daily_series({date(2026, 1, 2): 3}, date(2026, 1, 1), date(2026, 1, 4))
        assert s == [0, 3, 0, 0]

    def test_fill_rejects_reversed_range(self):
        from datetime import date
        with pytest.raises(ValueError):
            ew.fill_daily_series({}, date(2026, 1, 5), date(2026, 1, 1))

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            ew.ears([1, 2, -1, 4, 5, 6, 7, 8, 9, 10, 11])


class TestDetectors:
    @pytest.mark.parametrize("variant", ["C1", "C2", "C3"])
    def test_flat_series_no_alarm(self, variant):
        assert not ew.ears(FLAT, variant)[-1]["alarm"]

    @pytest.mark.parametrize("variant", ["C1", "C2", "C3"])
    def test_surge_alarms(self, variant):
        assert ew.ears(SURGE, variant)[-1]["alarm"]

    def test_invalid_variant(self):
        with pytest.raises(ValueError):
            ew.ears(FLAT, "C9")

    def test_zero_baseline_does_not_divide_by_zero(self):
        res = ew.ears([0] * 12 + [9], "C1")
        assert res[-1]["alarm"]

    def test_cusum_detects_sustained_shift(self):
        assert any(r["alarm"] for r in ew.cusum(FLAT[:14] + [9] * 10))

    def test_cusum_quiet_on_flat(self):
        assert not any(r["alarm"] for r in ew.cusum(FLAT))

    def test_cusum_short_series(self):
        assert ew.cusum([1, 2, 3]) == []


class TestPoisson:
    def test_sf_edges(self):
        assert ew.poisson_sf(0, 5) == 1.0
        assert ew.poisson_sf(3, 0) == 0.0
        assert 0.0 <= ew.poisson_sf(10, 5) <= 1.0

    def test_sf_known_value(self):
        # P(X>=1) for lambda=1 is 1-e^-1
        assert ew.poisson_sf(1, 1.0) == pytest.approx(0.6321, abs=1e-3)

    def test_exceedance_alarm_and_none(self):
        assert ew.poisson_exceedance((FLAT + FLAT)[:30] + [15] * 7)["alarm"]
        assert not ew.poisson_exceedance((FLAT + FLAT)[:36])["alarm"]
        assert ew.poisson_exceedance([1, 2, 3]) is None


class TestRt:
    def test_growth_gives_rt_above_one(self):
        series = [round(5 * 1.2 ** i) for i in range(25)]
        rt = ew.estimate_rt(series)
        assert rt["rt"] > 1.0 and rt["growing"]

    def test_decline_gives_rt_below_one(self):
        series = [round(100 * 0.85 ** i) + 1 for i in range(25)]
        rt = ew.estimate_rt(series)
        assert rt["rt"] < 1.0 and not rt["growing"]

    def test_no_cases_returns_none(self):
        assert ew.estimate_rt([0] * 20) is None

    def test_serial_interval_normalised(self):
        assert ew.serial_interval_pmf().sum() == pytest.approx(1.0)
        with pytest.raises(ValueError):
            ew.serial_interval_pmf(mean=0)


class TestAnalyze:
    def test_insufficient(self):
        assert ew.analyze([1, 2, 3]).status == "INSUFFICIENT_DATA"

    def test_normal(self):
        assert ew.analyze(FLAT).status == "NORMAL"

    def test_surge_is_alert(self):
        r = ew.analyze(SURGE)
        assert r.status in {"WARNING", "ALERT"} and r.reasons


@pytest.mark.django_db
class TestEarlyWarningAPI:
    URL = "/api/v1/surveillance/dashboard/early-warning/"

    @pytest.fixture
    def seeded(self, db):
        from core.models import Location
        from surveillance.models import DataSource, HealthData
        loc = Location.objects.create(name="Khomas", code="NA-KH", location_type="REGION")
        src = DataSource.objects.create(name="Hosp", source_type="HOSPITAL", location=loc)
        today = timezone.now()
        series = FLAT[-16:] + [10, 16, 24, 36]
        rows = []
        for i, n in enumerate(series):
            day = today - timedelta(days=len(series) - 1 - i)
            rows += [HealthData(data_source=src, location=loc, data_type="CASE", date_recorded=day,
                                disease_code="A00", disease_name="Cholera") for _ in range(n)]
        HealthData.objects.bulk_create(rows)
        return loc

    def test_requires_auth(self, api_client):
        assert api_client.get(self.URL, {"disease_code": "A00"}).status_code in (401, 403)

    def test_missing_disease_code(self, api_client, analyst_user):
        api_client.force_authenticate(analyst_user)
        assert api_client.get(self.URL).status_code == 400

    @pytest.mark.parametrize("days", ["abc", "5", "9999"])
    def test_bad_days(self, api_client, analyst_user, days):
        api_client.force_authenticate(analyst_user)
        assert api_client.get(self.URL, {"disease_code": "A00", "days": days}).status_code == 400

    def test_bad_location(self, api_client, analyst_user):
        api_client.force_authenticate(analyst_user)
        assert api_client.get(self.URL, {"disease_code": "A00", "location": "not-a-uuid"}).status_code == 400

    def test_surge_detected(self, api_client, analyst_user, seeded):
        api_client.force_authenticate(analyst_user)
        r = api_client.get(self.URL, {"disease_code": "A00", "days": 20, "location": str(seeded.id)})
        assert r.status_code == 200
        assert r.json()["status"] in {"WARNING", "ALERT"}
        assert len(r.json()["series"]) == 20

    def test_unknown_disease_insufficient_or_normal(self, api_client, analyst_user):
        api_client.force_authenticate(analyst_user)
        r = api_client.get(self.URL, {"disease_code": "ZZZ", "days": 30})
        assert r.status_code == 200 and r.json()["status"] == "NORMAL"


@pytest.mark.django_db
class TestEarlyWarningScan:
    def _seed(self, series, code="A00"):
        from core.models import Location
        from surveillance.models import DataSource, HealthData
        loc, _ = Location.objects.get_or_create(name="Erongo", code="NA-ER", defaults={"location_type": "REGION"})
        src, _ = DataSource.objects.get_or_create(name="H", source_type="HOSPITAL", location=loc)
        now = timezone.now()
        rows = []
        for i, n in enumerate(series):
            day = now - timedelta(days=len(series) - 1 - i)
            rows += [HealthData(data_source=src, location=loc, data_type="CASE", date_recorded=day,
                                disease_code=code, disease_name="Cholera") for _ in range(n)]
        HealthData.objects.bulk_create(rows)

    def test_creates_anomaly_once(self):
        from surveillance.early_warning_service import scan
        from surveillance.models import AnomalyDetection
        self._seed(FLAT[-16:] + [10, 16, 24, 36])
        first = scan()
        assert first["anomalies_created"] == 1
        a = AnomalyDetection.objects.get()
        assert a.detection_method.startswith("EARLY_WARNING") and a.severity in {"MEDIUM", "HIGH", "CRITICAL"}
        second = scan()
        assert second["anomalies_created"] == 0 and second["skipped_duplicates"] == 1

    def test_quiet_and_tiny_series_ignored(self):
        from surveillance.early_warning_service import scan
        self._seed(FLAT)
        assert scan()["anomalies_created"] == 0

    def test_task_runs(self):
        from surveillance.tasks import run_early_warning_scan
        self._seed(FLAT[-16:] + [10, 16, 24, 36])
        assert run_early_warning_scan.apply().get()["anomalies_created"] == 1


@pytest.mark.django_db
def test_anomaly_list_exposes_detection_method_and_search(api_client, analyst_user):
    from core.models import Location
    from surveillance.models import AnomalyDetection
    loc = Location.objects.create(name="Omusati", code="NA-OM", location_type="REGION")
    now = timezone.now()
    for method in ("EARLY_WARNING:ears_c2", "ZSCORE"):
        AnomalyDetection.objects.create(
            location=loc, disease_code="A00", disease_name="Cholera", anomaly_type="SPIKE",
            severity="HIGH", detection_method=method, confidence_score=80,
            start_date=now, end_date=now)
    api_client.force_authenticate(analyst_user)
    r = api_client.get("/api/v1/surveillance/anomalies/", {"search": "EARLY_WARNING"})
    rows = r.json()["results"]
    assert len(rows) == 1 and rows[0]["detection_method"].startswith("EARLY_WARNING")


@pytest.mark.django_db
def test_hotspot_search_does_not_error(api_client, analyst_user):
    api_client.force_authenticate(analyst_user)
    assert api_client.get("/api/v1/surveillance/hotspots/", {"search": "x"}).status_code == 200


@pytest.mark.django_db
class TestEarlyWarningOverview:
    URL = "/api/v1/surveillance/dashboard/early-warning-overview/"

    def test_ranks_surging_first_and_has_series(self, api_client, analyst_user):
        helper = TestEarlyWarningScan()
        helper._seed(FLAT[-16:] + [10, 16, 24, 36], code="A00")
        helper._seed(FLAT, code="B00")
        api_client.force_authenticate(analyst_user)
        r = api_client.get(self.URL)
        rows = r.json()["results"]
        assert r.status_code == 200 and len(rows) == 2
        assert rows[0]["disease_code"] == "A00" and rows[0]["status"] in {"WARNING", "ALERT"}
        assert len(rows[0]["series"]) <= 30 and rows[1]["status"] == "NORMAL"

    def test_does_not_create_records(self, api_client, analyst_user):
        from surveillance.models import AnomalyDetection
        TestEarlyWarningScan()._seed(FLAT[-16:] + [10, 16, 24, 36])
        api_client.force_authenticate(analyst_user)
        api_client.get(self.URL)
        assert AnomalyDetection.objects.count() == 0

    def test_validation_and_auth(self, api_client, analyst_user):
        assert api_client.get(self.URL).status_code in (401, 403)
        api_client.force_authenticate(analyst_user)
        assert api_client.get(self.URL, {"limit": "abc"}).status_code == 400
