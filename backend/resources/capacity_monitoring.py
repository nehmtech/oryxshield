"""
Capacity monitoring utilities for resources app.

Provides helper functions for analysing facility capacity trends,
projecting saturation dates, and computing system-wide occupancy summaries.
These are consumed by the dashboard view and the update_capacity_metrics task.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Max, Min

logger = logging.getLogger(__name__)


def get_occupancy_trend(facility, days: int = 7) -> list[dict]:
    """
    Return daily average occupancy rate for a facility over the last `days` days.

    Returns a list of dicts: [{'date': date, 'avg_occupancy': float}, ...]
    sorted oldest-first.
    """
    from .models import FacilityCapacity

    since = timezone.now() - timedelta(days=days)
    records = (
        FacilityCapacity.objects
        .filter(is_deleted=False, facility=facility, recorded_at__gte=since)
        .order_by('recorded_at')
    )

    # Group by date manually (avoids DB-level date truncation compatibility issues)
    daily: dict = {}
    for record in records:
        day = record.recorded_at.date()
        if day not in daily:
            daily[day] = []
        if record.occupancy_rate is not None:
            daily[day].append(float(record.occupancy_rate))

    trend = []
    for day in sorted(daily.keys()):
        values = daily[day]
        trend.append({
            'date': day.isoformat(),
            'avg_occupancy': round(sum(values) / len(values), 2) if values else None,
        })
    return trend


def project_saturation_date(facility) -> dict:
    """
    Project the date at which a facility will reach 100% occupancy,
    based on the linear trend of the last 14 days.

    Returns a dict with 'projected_date' (str ISO or None) and 'slope_per_day' (float).
    """
    trend = get_occupancy_trend(facility, days=14)
    if len(trend) < 2:
        return {'projected_date': None, 'slope_per_day': None, 'reason': 'Insufficient data.'}

    values = [t['avg_occupancy'] for t in trend if t['avg_occupancy'] is not None]
    if len(values) < 2:
        return {'projected_date': None, 'slope_per_day': None, 'reason': 'Insufficient occupancy data.'}

    # Simple linear slope: (last - first) / n_days
    slope = (values[-1] - values[0]) / (len(values) - 1)

    if slope <= 0:
        return {'projected_date': None, 'slope_per_day': round(slope, 4), 'reason': 'Occupancy not increasing.'}

    current = values[-1]
    days_to_full = (100.0 - current) / slope
    projected = timezone.now().date() + timedelta(days=int(days_to_full))

    return {
        'projected_date': projected.isoformat(),
        'slope_per_day': round(slope, 4),
        'reason': None,
    }


def system_capacity_summary() -> dict:
    """
    Return a system-wide summary of current capacity across all operational facilities.

    Queries the latest capacity snapshot per facility.
    Returns aggregated totals and averages.
    """
    from .models import FacilityCapacity, Facility

    facility_ids = Facility.objects.filter(
        is_deleted=False, is_operational=True
    ).values_list('id', flat=True)

    latest_records = []
    for fid in facility_ids:
        record = (
            FacilityCapacity.objects
            .filter(is_deleted=False, facility_id=fid)
            .order_by('-recorded_at')
            .first()
        )
        if record:
            latest_records.append(record)

    if not latest_records:
        return {
            'total_facilities_with_data': 0,
            'total_beds': 0,
            'total_occupied': 0,
            'total_available': 0,
            'system_occupancy_rate': None,
            'critical_facilities': 0,
            'warning_facilities': 0,
        }

    total_occupied = sum(r.beds_occupied for r in latest_records)
    total_available = sum(r.beds_available for r in latest_records)
    total_beds = total_occupied + total_available
    system_rate = round((total_occupied / total_beds) * 100, 2) if total_beds > 0 else 0

    critical_count = sum(
        1 for r in latest_records
        if r.occupancy_rate is not None and r.occupancy_rate >= 95
    )
    warning_count = sum(
        1 for r in latest_records
        if r.occupancy_rate is not None and 80 <= r.occupancy_rate < 95
    )

    return {
        'total_facilities_with_data': len(latest_records),
        'total_beds': total_beds,
        'total_occupied': total_occupied,
        'total_available': total_available,
        'system_occupancy_rate': system_rate,
        'critical_facilities': critical_count,
        'warning_facilities': warning_count,
    }