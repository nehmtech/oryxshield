"""
Anomaly detection orchestration layer.
Thin wrapper that delegates to ml_models and adds outbreak / spatial pattern checks.
"""
import logging
from datetime import timedelta

import numpy as np
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


def detect_anomalies(health_data_queryset) -> list[dict]:
    """
    Entry-point for the Celery anomaly detection task.
    Delegates to ml_models.detect_anomalies and supplements with outbreak patterns.
    """
    from .ml_models import detect_anomalies as _stat_detect

    return _stat_detect(health_data_queryset)


def detect_outbreak_pattern(disease_code: str, location_id, days: int = 14) -> dict | None:
    """
    Detect potential outbreak patterns using a rolling doubling-time heuristic.

    Returns a dict with pattern, doubling_time, and severity or None.
    """
    from .models import HealthData

    start_date = timezone.now() - timedelta(days=days)
    recent_cases = (
        HealthData.objects.filter(
            is_deleted=False,
            disease_code=disease_code,
            location_id=location_id,
            date_recorded__gte=start_date,
        )
        .values("date_recorded__date")
        .annotate(count=Count("id"))
        .order_by("date_recorded__date")
    )

    counts = [c["count"] for c in recent_cases]
    if len(counts) < 3:
        return None

    half = len(counts) // 2
    first_half = sum(counts[:half])
    second_half = sum(counts[half:])

    if second_half <= first_half * 1.5:
        return None  # no exponential growth

    return {
        "pattern": "exponential_growth",
        "doubling_time": _calculate_doubling_time(counts),
        "severity": "HIGH",
    }


def _calculate_doubling_time(case_counts: list[int]) -> float | None:
    """Return the average observed doubling time in days."""
    if len(case_counts) < 2:
        return None

    doublings = []
    for i in range(len(case_counts) - 1):
        for j in range(i + 1, len(case_counts)):
            if case_counts[j] >= case_counts[i] * 2:
                doublings.append(j - i)
                break

    return float(np.mean(doublings)) if doublings else None


def detect_spatial_clustering(health_data_queryset) -> list[dict]:
    """
    Detect spatial clusters using DBSCAN on lat/lon coordinates.

    Returns a list of cluster dicts with center_latitude, center_longitude,
    radius_km, and case_count.
    """
    geo_qs = health_data_queryset.filter(
        latitude__isnull=False, longitude__isnull=False
    )
    if geo_qs.count() < 10:
        return []

    try:
        from sklearn.cluster import DBSCAN
    except ImportError:
        logger.warning("scikit-learn not installed — spatial clustering skipped")
        return []

    coordinates = np.array(
        [[float(c.latitude), float(c.longitude)] for c in geo_qs]
    )

    # eps = 0.1° ≈ 11 km at the equator; min_samples = 5 cases to form a cluster
    labels = DBSCAN(eps=0.1, min_samples=5).fit(coordinates).labels_

    clusters = []
    for label in set(labels) - {-1}:
        mask = labels == label
        pts = coordinates[mask]
        center_lat = float(np.mean(pts[:, 0]))
        center_lon = float(np.mean(pts[:, 1]))
        distances = np.sqrt(
            (pts[:, 0] - center_lat) ** 2 + (pts[:, 1] - center_lon) ** 2
        )
        radius_km = float(np.max(distances)) * 111  # 1° ≈ 111 km
        clusters.append({
            "center_latitude": center_lat,
            "center_longitude": center_lon,
            "radius_km": radius_km,
            "case_count": int(np.sum(mask)),
        })

    return clusters


def detect_temporal_pattern(case_timeseries: list[tuple]) -> dict | None:
    """
    Fit a linear trend to the time series and classify direction + severity.

    Args:
        case_timeseries: List of (date, count) tuples.

    Returns dict with pattern, slope, severity or None if < 7 points.
    """
    if len(case_timeseries) < 7:
        return None

    _, counts = zip(*case_timeseries)
    arr = np.array(counts, dtype=float)
    x = np.arange(len(arr), dtype=float)
    coeffs = np.polyfit(x, arr, 1)
    slope = float(coeffs[0])

    if slope > 1.0:
        pattern, severity = "increasing", "HIGH"
    elif slope > 0.5:
        pattern, severity = "increasing", "MEDIUM"
    elif slope < -0.5:
        pattern, severity = "decreasing", "LOW"
    else:
        pattern, severity = "stable", "LOW"

    return {"pattern": pattern, "slope": slope, "severity": severity}


def calculate_attack_rate(case_count: int, population_at_risk: int) -> float:
    """Return attack rate as a percentage."""
    if not population_at_risk:
        return 0.0
    return round((case_count / population_at_risk) * 100, 4)