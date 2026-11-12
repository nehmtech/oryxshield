"""
Predictive modelling for outbreak forecasting.

The run_prediction() function is the single entry point invoked by the
predict_outbreak Celery task.  In production, replace simple_forecast()
with a call to the serialised model binary stored in PredictiveModel.model_file.
"""
import logging
from datetime import timedelta

import numpy as np
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_prediction(model, location_id: str, disease_code: str, prediction_horizon: int = 7) -> dict:
    """
    Run an outbreak forecast for a given location / disease pair.

    Args:
        model: PredictiveModel instance (registry entry only; binary not yet loaded).
        location_id: UUID string of the target Location.
        disease_code: ICD / internal disease code.
        prediction_horizon: Number of days to forecast (1–90).

    Returns:
        A dict with 'status' and, on success, 'predictions' and 'confidence'.
    """
    from core.models import Location

    try:
        location = Location.objects.get(id=location_id, is_deleted=False)
    except Location.DoesNotExist:
        return {"status": "error", "message": f"Location {location_id} not found."}

    historical = _historical_daily_counts(location_id, disease_code, days=30)

    if len(historical) < 3:
        return {
            "status": "insufficient_data",
            "message": "At least 3 days of historical data are required.",
        }

    predictions = simple_forecast(historical, prediction_horizon)
    confidence = _prediction_confidence(len(historical))

    return {
        "status": "success",
        "location": location.name,
        "disease_code": disease_code,
        "prediction_horizon": prediction_horizon,
        "predictions": predictions,
        "confidence": confidence,
        "model_name": model.name,
        "model_version": model.version,
    }


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

def simple_forecast(daily_counts: list[int], horizon: int) -> list[dict]:
    """
    Moving-average + trend extrapolation.

    Uses the most recent 7-day window to estimate a daily growth rate, then
    projects that rate forward for *horizon* days.
    """
    if not daily_counts:
        return [{"day": d, "predicted_cases": 0, "date": (timezone.now() + timedelta(days=d)).date().isoformat()}
                for d in range(1, horizon + 1)]

    if len(daily_counts) < 7:
        avg = float(np.mean(daily_counts))
        return [
            {
                "day": d,
                "predicted_cases": round(avg, 1),
                "date": (timezone.now() + timedelta(days=d)).date().isoformat(),
            }
            for d in range(1, horizon + 1)
        ]

    recent_avg = float(np.mean(daily_counts[-7:]))
    previous_avg = float(np.mean(daily_counts[-14:-7])) if len(daily_counts) >= 14 else recent_avg
    growth_rate = (recent_avg / previous_avg - 1) if previous_avg > 0 else 0.0

    last = float(daily_counts[-1])
    predictions = []
    for day in range(1, horizon + 1):
        predicted = max(0.0, last * (1 + growth_rate) ** day)
        predictions.append(
            {
                "day": day,
                "predicted_cases": round(predicted, 1),
                "date": (timezone.now() + timedelta(days=day)).date().isoformat(),
            }
        )
    return predictions


# ---------------------------------------------------------------------------
# Feature preparation (used by future ML pipeline)
# ---------------------------------------------------------------------------

def prepare_features(daily_counts: list[int], location) -> dict:
    """Extract scalar features from a time series and location metadata."""
    arr = np.array(daily_counts, dtype=float)
    return {
        "mean": float(np.mean(arr)) if len(arr) else 0.0,
        "std": float(np.std(arr)) if len(arr) else 0.0,
        "trend": _linear_trend(arr),
        "population": location.population or 1_000,
        "population_density": _population_density(location),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _historical_daily_counts(location_id: str, disease_code: str, days: int = 30) -> list[int]:
    """Return a sorted list of daily case counts for the past *days* days."""
    from surveillance.models import HealthData

    start = timezone.now() - timedelta(days=days)
    rows = (
        HealthData.objects.filter(
            location_id=location_id,
            disease_code=disease_code,
            date_recorded__gte=start,
            is_deleted=False,
        )
        .values("date_recorded__date")
        .annotate(count=Count("id"))
        .order_by("date_recorded__date")
    )
    return [r["count"] for r in rows]


def _prediction_confidence(data_points: int) -> float:
    """Confidence percentage based on available data volume."""
    if data_points >= 30:
        return 85.0
    if data_points >= 14:
        return 70.0
    if data_points >= 7:
        return 55.0
    return 40.0


def _linear_trend(series: np.ndarray) -> float:
    """Slope of least-squares linear fit. Returns 0 for series shorter than 2."""
    if len(series) < 2:
        return 0.0
    x = np.arange(len(series))
    coeffs = np.polyfit(x, series, 1)
    return float(coeffs[0])


def _population_density(location) -> float:
    """People per km²; 0 when area or population data is unavailable."""
    area = getattr(location, "area_sq_km", None)
    if location.population and area:
        return location.population / float(area)
    return 0.0