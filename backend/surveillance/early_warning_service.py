"""
Scan recent surveillance data with the early-warning engine and raise
AnomalyDetection records for locations/diseases showing aberrations.
"""
import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .early_warning import analyze, fill_daily_series
from .models import AnomalyDetection, HealthData

logger = logging.getLogger(__name__)

METHOD_PREFIX = "EARLY_WARNING"
MIN_TOTAL_CASES = 5       # ignore near-empty series (noise)
DEDUPE_HOURS = 24


def _severity(result) -> str:
    n = len(result.reasons)
    if result.status == "ALERT":
        return "CRITICAL" if n >= 5 else "HIGH"
    return "MEDIUM"


def _grouped_series(days: int, now):
    """Yield (location_id, location_name, code, disease_name, series) for every pair with data."""
    end = now.date()
    start = end - timedelta(days=days - 1)
    rows = (
        HealthData.objects.filter(is_deleted=False, date_recorded__date__gte=start)
        .values("location_id", "location__name", "disease_code", "disease_name", "date_recorded__date")
        .annotate(n=Count("id"))
    )
    grouped: dict = {}
    first_seen: dict = {}  # location -> first day with any data (avoids leading-zero false alarms)
    for r in rows:
        d = r["date_recorded__date"]
        if r["location_id"] not in first_seen or d < first_seen[r["location_id"]]:
            first_seen[r["location_id"]] = d
        key = (r["location_id"], r["disease_code"])
        g = grouped.setdefault(key, {"name": r["disease_name"], "loc": r["location__name"], "counts": {}})
        g["counts"][d] = r["n"]
    for (location_id, code), g in grouped.items():
        series = fill_daily_series(g["counts"], max(start, first_seen[location_id]), end)
        yield location_id, g["loc"], code, g["name"], series


_STATUS_RANK = {"ALERT": 3, "WARNING": 2, "WATCH": 1, "NORMAL": 0, "INSUFFICIENT_DATA": -1}


def overview(days: int = 60, limit: int = 12, now=None) -> list[dict]:
    """
    Current early-warning status for every location/disease pair, worst first.
    Read-only: unlike scan() it never creates records. Each entry carries the last
    30 days of counts for sparklines.
    """
    now = now or timezone.now()
    out = []
    for location_id, loc_name, code, name, series in _grouped_series(days, now):
        if sum(series) < MIN_TOTAL_CASES:
            continue
        res = analyze(series)
        out.append({
            "location": str(location_id), "location_name": loc_name,
            "disease_code": code, "disease_name": name,
            "status": res.status, "signals": res.reasons,
            "rt": res.rt["rt"] if res.rt else None,
            "last_7_days": sum(series[-7:]),
            "series": series[-30:],
        })
    out.sort(key=lambda e: (-_STATUS_RANK.get(e["status"], 0), -e["last_7_days"]))
    return out[:limit]


def scan(days: int = 60, now=None) -> dict:
    """
    Analyse every (location, disease) pair with data in the last ``days`` days.
    Creates one AnomalyDetection per pair at WARNING/ALERT status, skipping pairs
    that already have an early-warning anomaly in the last 24 h.
    """
    now = now or timezone.now()
    stats = {"series_analysed": 0, "anomalies_created": 0, "skipped_duplicates": 0}
    cutoff = now - timedelta(hours=DEDUPE_HOURS)
    for location_id, _loc, code, disease_name, series in _grouped_series(days, now):
        if sum(series) < MIN_TOTAL_CASES:
            continue
        stats["series_analysed"] += 1
        result = analyze(series)
        if result.status not in {"WARNING", "ALERT"}:
            continue
        if AnomalyDetection.objects.filter(
            location_id=location_id, disease_code=code, is_deleted=False,
            detection_method__startswith=METHOD_PREFIX, detected_at__gte=cutoff,
        ).exists():
            stats["skipped_duplicates"] += 1
            continue
        recent = sum(series[-7:])
        prior = series[-35:-7] or [0]
        baseline = round(sum(prior) / len(prior) * 7)
        pct = round((recent - baseline) / baseline * 100, 2) if baseline else 100.0
        AnomalyDetection.objects.create(
            location_id=location_id, disease_code=code, disease_name=disease_name,
            anomaly_type="OUTBREAK" if result.status == "ALERT" else "SPIKE",
            severity=_severity(result),
            detection_method=f"{METHOD_PREFIX}:{'+'.join(result.reasons)}"[:100],
            confidence_score=min(99, 40 + 12 * len(result.reasons)),
            expected_cases=baseline, actual_cases=recent, baseline_cases=baseline,
            percentage_increase=max(min(pct, 999999), -999999),
            start_date=now - timedelta(days=7), end_date=now,
            notes=f"Early-warning status {result.status}; Rt={result.rt['rt'] if result.rt else 'n/a'}",
        )
        stats["anomalies_created"] += 1
        logger.info("early warning %s for %s in %s", result.status, code, location_id)
    return stats
