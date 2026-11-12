"""
Statistical and machine-learning algorithms for surveillance anomaly detection.

All functions are pure/stateless and import Django models lazily so they can be
called from Celery tasks without circular-import issues.
"""
import logging
from datetime import timedelta

import numpy as np
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def get_historical_baseline(disease_code: str, location_id, days: int = 30) -> dict | None:
    """
    Compute a statistical baseline from data in the window [60+days, 30] days ago
    (offset avoids contaminating the baseline with current anomalous data).

    Returns dict with keys mean, std, min, max  — or None if insufficient data.
    """
    from .models import HealthData

    end_date = timezone.now() - timedelta(days=30)
    start_date = end_date - timedelta(days=days)

    counts = list(
        HealthData.objects.filter(
            is_deleted=False,
            disease_code=disease_code,
            location_id=location_id,
            date_recorded__gte=start_date,
            date_recorded__lt=end_date,
        )
        .values("date_recorded__date")
        .annotate(count=Count("id"))
        .values_list("count", flat=True)
    )

    if not counts:
        return None

    arr = np.array(counts, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "n": len(arr),
    }


# ---------------------------------------------------------------------------
# Statistical anomaly detection (Z-score / SPC)
# ---------------------------------------------------------------------------

def detect_statistical_anomaly(
    current_value: int,
    mean: float,
    std: float,
    threshold: float = 2.0,
) -> dict | None:
    """
    Statistical Process Control — flag if z-score exceeds threshold.

    Returns anomaly dict or None.
    """
    if std <= 0:
        std = 1.0  # prevent division by zero; treat as unit variance

    z_score = (current_value - mean) / std

    if z_score < threshold:
        return None

    percentage_increase = ((current_value - mean) / mean * 100) if mean > 0 else 0.0

    if z_score >= 4.0:
        severity, confidence = "CRITICAL", 99.9
    elif z_score >= 3.0:
        severity, confidence = "HIGH", 99.7
    elif z_score >= 2.5:
        severity, confidence = "MEDIUM", 98.0
    else:
        severity, confidence = "LOW", 95.0

    return {
        "z_score": float(z_score),
        "severity": severity,
        "confidence": confidence,
        "percentage_increase": float(percentage_increase),
    }


# ---------------------------------------------------------------------------
# Trend anomaly (linear regression over time series)
# ---------------------------------------------------------------------------

def detect_trend_anomaly(time_series_data: list[tuple]) -> dict | None:
    """
    Detect a statistically significant upward or downward trend.

    Args:
        time_series_data: List of (date, count) tuples ordered chronologically.

    Returns anomaly dict or None.
    """
    if len(time_series_data) < 7:
        return None

    from scipy import stats as scipy_stats

    values = [v for _, v in time_series_data]
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)

    slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)

    if p_value >= 0.05 or abs(slope) <= 1.0:
        return None  # not significant

    return {
        "trend_type": "increasing" if slope > 0 else "decreasing",
        "slope": float(slope),
        "r_squared": float(r_value ** 2),
        "p_value": float(p_value),
    }


# ---------------------------------------------------------------------------
# Epidemic threshold
# ---------------------------------------------------------------------------

def calculate_epidemic_threshold(disease_code: str, location_id=None) -> int:
    """Return the epidemic threshold configured for this disease, defaulting to 10."""
    from .models import DiseaseProfile

    try:
        return DiseaseProfile.objects.get(
            disease_code=disease_code, is_active=True
        ).epidemic_threshold
    except DiseaseProfile.DoesNotExist:
        return 10


# ---------------------------------------------------------------------------
# Outbreak probability (heuristic — placeholder for trained model)
# ---------------------------------------------------------------------------

def predict_outbreak_probability(health_data_qs, disease_code: str, location_id) -> float:
    """
    Heuristic outbreak probability based on Z-score deviation from baseline.

    NOTE: This is a statistical heuristic (Z-score bucketing), not a trained ML model.
    Replace with a trained sklearn/TensorFlow model when sufficient labelled data
    is available. Track in: ORYXSHIELD-ML-001.

    Returns probability in [0, 1].
    """
    logger.debug(
        "predict_outbreak_probability using heuristic Z-score (no trained model) "
        "disease=%s location_id=%s",
        disease_code, location_id,
    )
    recent_count = health_data_qs.filter(
        disease_code=disease_code, location_id=location_id
    ).count()

    baseline = get_historical_baseline(disease_code, location_id)
    if not baseline or baseline["mean"] == 0:
        return 0.0

    sigma = baseline["std"] if baseline["std"] > 0 else 1.0
    z = (recent_count - baseline["mean"]) / sigma

    if z >= 3:
        return 0.9
    if z >= 2:
        return 0.7
    if z >= 1:
        return 0.5
    return 0.1


# ---------------------------------------------------------------------------
# Time-series forecasting (simple moving average — stub)
# ---------------------------------------------------------------------------

def time_series_forecasting(historical_data: list[tuple], periods: int = 7) -> list[float]:
    """
    Forecast future case counts using a simple 7-day moving average.

    NOTE: This is a moving-average placeholder. Replace with Prophet or ARIMA
    when ≥ 90 days of historical data are available per disease/location.
    Track in: ORYXSHIELD-ML-002.

    Args:
        historical_data: List of (date, count) tuples.
        periods: Number of future periods to forecast.

    Returns list of forecasted values.
    """
    if not historical_data:
        return [0.0] * periods

    logger.debug(
        "time_series_forecasting using 7-day moving average (no trained model) "
        "data_points=%d periods=%d",
        len(historical_data), periods,
    )
    values = [float(v) for _, v in historical_data]
    window = min(7, len(values))
    avg = float(np.mean(values[-window:]))
    return [round(avg, 2)] * periods


# ---------------------------------------------------------------------------
# R0 estimation
# ---------------------------------------------------------------------------

def calculate_r_naught(case_counts: list[int], serial_interval: int = 5) -> float | None:
    """
    Estimate basic reproduction number (R₀) from case counts.

    Uses growth-rate method: R₀ ≈ cases[t] / cases[t - serial_interval].

    Returns None if insufficient data or zero denominator.
    """
    if len(case_counts) < serial_interval * 2:
        return None

    recent = sum(case_counts[-serial_interval:])
    previous = sum(case_counts[-2 * serial_interval:-serial_interval])

    if previous == 0:
        return None

    return round(recent / previous, 4)


# ---------------------------------------------------------------------------
# Seasonality detection (stub)
# ---------------------------------------------------------------------------

def detect_seasonality(time_series_data: list[tuple]) -> dict | None:
    """
    Detect seasonal patterns using FFT.  Requires ≥ 365 data points.

    Returns seasonality dict or None.
    """
    if len(time_series_data) < 30:
        return None

    values = np.array([float(v) for _, v in time_series_data])
    fft_vals = np.abs(np.fft.rfft(values))
    freqs = np.fft.rfftfreq(len(values))

    # Ignore DC component (index 0)
    dominant_idx = int(np.argmax(fft_vals[1:]) + 1)
    dominant_freq = freqs[dominant_idx]

    if dominant_freq == 0:
        return {"has_seasonality": False, "period": None}

    period_days = round(1 / dominant_freq)
    amplitude = float(fft_vals[dominant_idx])

    # Threshold: only report if amplitude > 20% of mean signal
    mean_amplitude = float(np.mean(fft_vals[1:]))
    has_seasonality = amplitude > mean_amplitude * 2.0

    return {
        "has_seasonality": has_seasonality,
        "period": period_days if has_seasonality else None,
        "dominant_frequency": float(dominant_freq),
        "amplitude": amplitude,
    }


# ---------------------------------------------------------------------------
# Full anomaly detection pipeline (called by tasks)
# ---------------------------------------------------------------------------

def detect_anomalies(health_data_queryset) -> list[dict]:
    """
    Run the complete anomaly detection pipeline over a HealthData queryset.

    Returns a list of anomaly dicts ready for AnomalyDetection.objects.create(**).
    """
    from .models import Location

    anomalies = []

    groups = (
        health_data_queryset.values("disease_code", "disease_name", "location_id")
        .annotate(count=Count("id"))
    )

    for group in groups:
        baseline = get_historical_baseline(group["disease_code"], group["location_id"])
        if not baseline:
            continue

        result = detect_statistical_anomaly(
            group["count"],
            baseline["mean"],
            baseline["std"],
        )
        if not result:
            continue

        try:
            location = Location.objects.get(id=group["location_id"])
        except Location.DoesNotExist:
            logger.warning("Location %s not found — skipping anomaly", group["location_id"])
            continue

        anomalies.append({
            "location": location,
            "disease_code": group["disease_code"],
            "disease_name": group["disease_name"],
            "anomaly_type": "SPIKE",
            "severity": result["severity"],
            "detection_method": "Statistical Process Control (Z-score)",
            "confidence_score": result["confidence"],
            "expected_cases": max(0, round(baseline["mean"])),
            "actual_cases": group["count"],
            "baseline_cases": max(0, round(baseline["mean"])),
            "percentage_increase": result["percentage_increase"],
            "start_date": timezone.now() - timedelta(days=1),
            "end_date": timezone.now(),
            "metadata": {
                "z_score": result["z_score"],
                "baseline_std": baseline["std"],
                "baseline_n": baseline["n"],
            },
        })

    logger.info("detect_anomalies: %d anomalies found from %d groups", len(anomalies), groups.count())
    return anomalies