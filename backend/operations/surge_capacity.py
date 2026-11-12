"""
Surge capacity planning helpers for operations app.

Provides functions to assess testing, quarantine, and vaccination
capacity against current and projected demand.
"""
import logging
from django.utils import timezone
from django.db.models import Count, Sum

logger = logging.getLogger(__name__)


def get_surge_status() -> dict:
    """
    Return a system-wide surge capacity snapshot:
    - Testing center load vs capacity
    - Quarantine facility occupancy vs capacity
    - Active case count vs 7-day trend
    """
    from .models import (
        Case, Contact, TestingCenter, TestingAppointment,
        QuarantineFacility, QuarantineRecord,
    )
    from datetime import timedelta

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Testing
    testing_centers = TestingCenter.objects.filter(is_operational=True, is_deleted=False)
    total_testing_capacity = sum(c.daily_capacity for c in testing_centers) or 1
    total_testing_load = sum(c.current_load for c in testing_centers)
    testing_utilisation = round((total_testing_load / total_testing_capacity) * 100, 2)

    # Quarantine
    facilities = QuarantineFacility.objects.filter(is_operational=True, is_deleted=False)
    total_quarantine_capacity = sum(f.total_capacity for f in facilities) or 1
    total_quarantine_occupancy = sum(f.current_occupancy for f in facilities)
    quarantine_utilisation = round(
        (total_quarantine_occupancy / total_quarantine_capacity) * 100, 2
    )

    # Cases trend
    active_cases = Case.objects.filter(status='ACTIVE', is_deleted=False).count()
    new_cases_7d = Case.objects.filter(
        created_at__date__gte=week_ago, is_deleted=False
    ).count()

    # Contacts
    contacts_monitoring = Contact.objects.filter(
        status=Contact.STATUS_MONITORING, is_deleted=False
    ).count()

    # Surge thresholds (configurable)
    TESTING_SURGE_THRESHOLD = 85  # %
    QUARANTINE_SURGE_THRESHOLD = 80  # %

    return {
        'timestamp': timezone.now().isoformat(),
        'testing': {
            'centers_operational': testing_centers.count(),
            'total_capacity': total_testing_capacity,
            'current_load': total_testing_load,
            'utilisation_pct': testing_utilisation,
            'is_surge': testing_utilisation >= TESTING_SURGE_THRESHOLD,
        },
        'quarantine': {
            'facilities_operational': facilities.count(),
            'total_capacity': total_quarantine_capacity,
            'current_occupancy': total_quarantine_occupancy,
            'available_beds': total_quarantine_capacity - total_quarantine_occupancy,
            'utilisation_pct': quarantine_utilisation,
            'is_surge': quarantine_utilisation >= QUARANTINE_SURGE_THRESHOLD,
        },
        'cases': {
            'active': active_cases,
            'new_last_7_days': new_cases_7d,
        },
        'contacts': {
            'under_monitoring': contacts_monitoring,
        },
        'overall_surge': (
            testing_utilisation >= TESTING_SURGE_THRESHOLD
            or quarantine_utilisation >= QUARANTINE_SURGE_THRESHOLD
        ),
    }


def project_quarantine_demand(days_ahead: int = 14) -> list:
    """
    Project daily quarantine demand for the next N days based on
    new contacts being placed under monitoring.
    """
    from .models import Contact
    from datetime import timedelta, date

    today = timezone.now().date()
    projections = []

    for i in range(days_ahead):
        target_date = today + timedelta(days=i)
        # Contacts whose quarantine end date falls on target_date
        releasing = Contact.objects.filter(
            quarantine_end_date=target_date,
            is_quarantined=True,
            is_deleted=False,
        ).count()
        # New contacts whose monitoring start date falls today (proxy for new admissions)
        new_admissions = Contact.objects.filter(
            quarantine_start_date=today,
            is_quarantined=True,
            is_deleted=False,
        ).count() if i == 0 else 0

        projections.append({
            'date': str(target_date),
            'projected_releases': releasing,
            'new_admissions_estimate': new_admissions,
        })

    return projections