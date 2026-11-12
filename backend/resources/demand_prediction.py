"""
Demand prediction utilities for resources app.

Provides statistical helpers for computing demand forecasts used by the
generate_demand_forecasts Celery task and the DemandForecast model.
"""
import logging
import math
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum

logger = logging.getLogger(__name__)


def compute_historical_daily_average(resource_item, location, days: int = 30) -> float:
    """
    Return the average daily consumption of `resource_item` at `location`
    over the last `days` days, based on ISSUE stock movements.

    Returns 0.0 if there are no movements.
    """
    from .models import StockMovement

    since = timezone.now() - timedelta(days=days)
    total = (
        StockMovement.objects
        .filter(
            is_deleted=False,
            resource_item=resource_item,
            movement_type='ISSUE',
            movement_date__gte=since,
            from_facility__location=location,
        )
        .aggregate(total=Sum('quantity'))['total'] or 0
    )
    return total / days if days > 0 else 0.0


def compute_trend_factor(resource_item, location, short_days: int = 7, long_days: int = 30) -> float:
    """
    Compute a trend multiplier by comparing short-term vs long-term daily averages.

    Returns:
        > 1.0  if demand is accelerating
        = 1.0  if demand is flat
        < 1.0  if demand is declining
    """
    short_avg = compute_historical_daily_average(resource_item, location, days=short_days)
    long_avg = compute_historical_daily_average(resource_item, location, days=long_days)

    if long_avg == 0:
        return 1.0
    return round(short_avg / long_avg, 4)


def forecast_demand(
    resource_item,
    location,
    period_days: int = 30,
    buffer_pct: float = 0.20,
) -> dict:
    """
    Produce a demand forecast dict for `resource_item` at `location`.

    Algorithm:
        1. Compute 30-day daily average.
        2. Apply trend multiplier (7-day vs 30-day).
        3. Project over `period_days`.
        4. Add `buffer_pct` safety buffer.
        5. Estimate confidence based on data availability.

    Returns a dict suitable for constructing a DemandForecast instance:
        {
            'predicted_demand': int,
            'confidence_level': float,   # 0–100
            'forecast_model': str,
            'daily_average': float,
            'trend_factor': float,
        }
    """
    from .models import StockMovement

    daily_avg = compute_historical_daily_average(resource_item, location, days=30)
    trend_factor = compute_trend_factor(resource_item, location)

    # Count how many data points we have for confidence estimation
    since_30 = timezone.now() - timedelta(days=30)
    data_points = StockMovement.objects.filter(
        is_deleted=False,
        resource_item=resource_item,
        movement_type='ISSUE',
        movement_date__gte=since_30,
        from_facility__location=location,
    ).count()

    # Confidence: scales from 50% (1 data point) toward 95% (30+ data points)
    confidence = min(50 + (data_points / 30) * 45, 95.0) if data_points > 0 else 40.0

    projected = daily_avg * trend_factor * period_days
    buffered = int(math.ceil(projected * (1 + buffer_pct)))

    return {
        'predicted_demand': buffered,
        'confidence_level': round(confidence, 2),
        'forecast_model': f'Historical Average + {int(buffer_pct * 100)}% Buffer (trend={trend_factor})',
        'daily_average': round(daily_avg, 4),
        'trend_factor': trend_factor,
    }


def batch_forecast_critical_items(period_days: int = 30) -> list[dict]:
    """
    Run forecast_demand for all critical resource items across all locations.

    Returns a list of result dicts, each containing:
        'resource_item_id', 'location_id', and all keys from forecast_demand().

    Skips item/location pairs with zero historical demand.
    """
    from .models import ResourceItem
    from core.models import Location

    results = []
    items = ResourceItem.objects.filter(is_deleted=False, is_critical=True)
    locations = Location.objects.filter(is_deleted=False)

    for item in items:
        for location in locations:
            forecast = forecast_demand(item, location, period_days=period_days)
            if forecast['predicted_demand'] == 0:
                continue
            results.append({
                'resource_item_id': str(item.id),
                'location_id': str(location.id),
                **forecast,
            })

    logger.info("batch_forecast_critical_items: %d forecasts computed", len(results))
    return results