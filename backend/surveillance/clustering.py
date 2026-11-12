"""
Geographic clustering algorithms: SaTScan-like spatial scan + Getis-Ord Gi* hotspot detection.
"""
import logging
from datetime import timedelta

import numpy as np
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def identify_clusters(health_data_queryset) -> list[dict]:
    """
    SaTScan-like spatial scan: group cases by location/disease, compute
    significance via Poisson test, return cluster dicts.
    """
    from .models import Location

    groups = (
        health_data_queryset.values("location_id", "disease_code", "disease_name")
        .annotate(case_count=Count("id"))
    )

    clusters = []
    for group in groups:
        if group["case_count"] < 5:
            continue

        try:
            location = Location.objects.get(id=group["location_id"])
        except Location.DoesNotExist:
            continue

        center_lat, center_lon, radius_km = _geo_stats(
            health_data_queryset, group["location_id"], group["disease_code"]
        )

        population = getattr(location, "population", None) or 1_000
        p_value = _cluster_significance(group["case_count"], population)

        clusters.append({
            "name": f"Cluster — {location.name} / {group['disease_name']}",
            "disease_code": group["disease_code"],
            "disease_name": group["disease_name"],
            "location": location,
            "case_count": group["case_count"],
            "start_date": timezone.now() - timedelta(days=7),
            "center_latitude": center_lat,
            "center_longitude": center_lon,
            "radius_km": radius_km,
            "detection_method": "SaTScan-like Spatial Scan",
            "detection_algorithm": "SaTScan",
            "p_value": p_value,
            "is_active": True,
        })

    logger.info("identify_clusters: %d clusters identified", len(clusters))
    return clusters


def detect_geographic_hotspots(health_data_queryset) -> list[dict]:
    """
    Getis-Ord Gi* hotspot detection.  Returns hotspot dicts for locations
    with HIGH or CRITICAL z-scores.
    """
    from .models import Location

    location_counts = (
        health_data_queryset.values("location_id", "disease_code", "disease_name")
        .annotate(case_count=Count("id"))
    )

    hotspots = []
    for item in location_counts:
        try:
            location = Location.objects.get(id=item["location_id"])
        except Location.DoesNotExist:
            continue

        gi_star, z_score = _getis_ord_gi(item["case_count"], location)

        if z_score >= 2.58:
            risk_level = "CRITICAL"
        elif z_score >= 1.96:
            risk_level = "HIGH"
        elif z_score >= 1.65:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        if risk_level not in ("HIGH", "CRITICAL"):
            continue

        lat = float(getattr(location, "latitude", 0) or 0)
        lon = float(getattr(location, "longitude", 0) or 0)

        hotspots.append({
            "location": location,
            "disease_code": item["disease_code"],
            "disease_name": item["disease_name"],
            "risk_level": risk_level,
            "latitude": lat,
            "longitude": lon,
            "radius_km": 10.0,
            "case_count": item["case_count"],
            "gi_statistic": gi_star,
            "z_score": z_score,
            "p_value": _p_from_z(z_score),
            "start_date": timezone.now() - timedelta(days=7),
            "is_active": True,
        })

    logger.info("detect_geographic_hotspots: %d hotspots found", len(hotspots))
    return hotspots


def analyze_cluster_evolution(cluster_id) -> dict | None:
    """Return time-series evolution for a single CaseCluster."""
    from .models import CaseCluster, HealthData

    try:
        cluster = CaseCluster.objects.get(id=cluster_id, is_deleted=False)
    except CaseCluster.DoesNotExist:
        return None

    cases = (
        HealthData.objects.filter(
            is_deleted=False,
            location=cluster.location,
            disease_code=cluster.disease_code,
            date_recorded__gte=cluster.start_date,
        )
        .values("date_recorded__date")
        .annotate(count=Count("id"))
        .order_by("date_recorded__date")
    )

    if not cases:
        return None

    time_series = [(c["date_recorded__date"], c["count"]) for c in cases]
    peak = max(time_series, key=lambda x: x[1])

    return {
        "cluster_id": str(cluster.id),
        "time_series": time_series,
        "trend": _analyze_trend(time_series),
        "peak_date": peak[0],
        "peak_count": peak[1],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _geo_stats(qs, location_id, disease_code) -> tuple[float | None, float | None, float]:
    """Compute geographic center and radius for a cluster."""
    cases = qs.filter(
        location_id=location_id,
        disease_code=disease_code,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    if not cases.exists():
        return None, None, 0.0

    lats = np.array([float(c.latitude) for c in cases])
    lons = np.array([float(c.longitude) for c in cases])
    center_lat, center_lon = float(np.mean(lats)), float(np.mean(lons))

    distances = np.array([haversine(center_lat, center_lon, la, lo) for la, lo in zip(lats, lons)])
    radius_km = float(np.max(distances)) if distances.size else 0.0

    return center_lat, center_lon, radius_km


def _cluster_significance(observed: int, population: int) -> float:
    """Poisson-based one-sided p-value for cluster significance."""
    try:
        from scipy import stats as sp_stats
    except ImportError:
        logger.warning("scipy not installed — returning default p-value 0.05")
        return 0.05

    expected = population * 0.001  # assume 0.1% baseline incidence
    if expected <= 0:
        return 1.0
    return float(1 - sp_stats.poisson.cdf(observed - 1, expected))


def _getis_ord_gi(case_count: int, location) -> tuple[float, float]:
    """
    Simplified Getis-Ord Gi* statistic.
    Compares location case count against sibling locations (same parent).
    """
    from .models import Location, HealthData

    siblings = Location.objects.filter(parent=location.parent).exclude(id=location.id)
    week_ago = timezone.now() - timedelta(days=7)

    neighbor_counts = [
        HealthData.objects.filter(
            is_deleted=False, location=sib, date_recorded__gte=week_ago
        ).count()
        for sib in siblings[:10]
    ]

    if not neighbor_counts:
        neighbor_counts = [0]

    arr = np.array(neighbor_counts, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr)) if len(arr) > 1 else 1.0

    z = (case_count - mean) / std if std > 0 else 0.0
    return float(z), float(z)  # gi_star ≈ z in simplified form


def _p_from_z(z_score: float) -> float:
    """Convert a z-score to a one-sided p-value."""
    try:
        from scipy import stats as sp_stats
        return float(1 - sp_stats.norm.cdf(abs(z_score)))
    except ImportError:
        # Rough approximation
        return max(0.0, 1.0 - min(abs(z_score) / 4.0, 1.0))


def _analyze_trend(time_series: list[tuple]) -> str:
    if len(time_series) < 3:
        return "insufficient_data"
    values = np.array([v for _, v in time_series], dtype=float)
    slope = float(np.polyfit(np.arange(len(values)), values, 1)[0])
    if slope > 0.5:
        return "increasing"
    if slope < -0.5:
        return "decreasing"
    return "stable"


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres."""
    R = 6_371.0
    φ1, φ2 = np.radians(lat1), np.radians(lat2)
    Δφ = np.radians(lat2 - lat1)
    Δλ = np.radians(lon2 - lon1)
    a = np.sin(Δφ / 2) ** 2 + np.cos(φ1) * np.cos(φ2) * np.sin(Δλ / 2) ** 2
    return float(R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))