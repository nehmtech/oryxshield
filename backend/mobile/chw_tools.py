"""
Community Health Worker (CHW) tools — OryxShield.

Provides high-level helpers consumed by:
- CHW-specific API views (see views.py CHWDashboardViewSet)
- Celery tasks
- Management commands

All DB access uses .filter(is_deleted=False) and select_related for efficiency.
"""
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caseload summary
# ---------------------------------------------------------------------------

def get_worker_caseload(worker_id: int, days: int = 30) -> Dict:
    """
    Return a caseload summary for the given FieldWorker PK
    over the past `days` days.
    """
    from .models import FieldWorker, FieldActivity, SurveyResponse, FormSubmission

    try:
        worker = FieldWorker.objects.select_related(
            'user', 'assigned_location'
        ).get(pk=worker_id, is_deleted=False)
    except FieldWorker.DoesNotExist:
        logger.warning("get_worker_caseload: worker %s not found.", worker_id)
        return {}

    since = timezone.now().date() - timedelta(days=days)

    activities = FieldActivity.objects.filter(
        field_worker=worker,
        activity_date__gte=since,
        is_deleted=False,
    )

    activity_by_type = (
        activities.values('activity_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    total_people = activities.aggregate(total=Sum('people_reached'))['total'] or 0

    survey_count = SurveyResponse.objects.filter(
        field_worker=worker,
        response_date__gte=since,
        is_deleted=False,
    ).count()

    submission_count = FormSubmission.objects.filter(
        field_worker=worker,
        submission_date__gte=since,
        is_deleted=False,
    ).count()

    return {
        'worker_id': worker.worker_id,
        'worker_name': worker.user.get_full_name(),
        'worker_type': worker.get_worker_type_display(),
        'assigned_location': (
            worker.assigned_location.name if worker.assigned_location else None
        ),
        'period_days': days,
        'since': since.isoformat(),
        'total_activities': activities.count(),
        'activities_by_type': list(activity_by_type),
        'total_people_reached': total_people,
        'surveys_submitted': survey_count,
        'forms_submitted': submission_count,
        'lifetime_counters': {
            'cases_managed': worker.cases_managed,
            'contacts_traced': worker.contacts_traced,
            'surveys_completed': worker.surveys_completed,
            'activities_logged': worker.activities_logged,
        },
    }


# ---------------------------------------------------------------------------
# Task list
# ---------------------------------------------------------------------------

def get_worker_tasks(worker_id: int) -> List[Dict]:
    """
    Return outstanding tasks for a CHW derived from:
    - Unread HIGH/URGENT notifications (TASK type).
    - Pending form submissions (is_validated=False).
    - Pending offline data items (sync_status=PENDING|FAILED).
    """
    from .models import (
        FieldWorker, MobileNotification, FormSubmission, OfflineData, MobileDevice,
    )

    try:
        worker = FieldWorker.objects.get(pk=worker_id, is_deleted=False)
    except FieldWorker.DoesNotExist:
        return []

    tasks: List[Dict] = []

    # Unread task notifications
    for notif in MobileNotification.objects.filter(
        user=worker.user,
        notification_type='TASK',
        priority__in=['HIGH', 'URGENT'],
        is_read=False,
        is_deleted=False,
    ).order_by('-created_at')[:20]:
        tasks.append({
            'source': 'notification',
            'id': notif.notification_id,
            'priority': notif.priority,
            'title': notif.title,
            'body': notif.body,
            'action_url': notif.action_url,
            'created_at': notif.created_at.isoformat(),
        })

    # Unvalidated form submissions
    for sub in FormSubmission.objects.filter(
        field_worker=worker,
        is_validated=False,
        is_deleted=False,
    ).select_related('form').order_by('-submission_date')[:10]:
        tasks.append({
            'source': 'form_submission',
            'id': sub.submission_id,
            'priority': 'NORMAL',
            'title': f'Submission needs validation: {sub.form.title}',
            'body': f'Submitted on {sub.submission_date}. Errors: {sub.validation_errors}',
            'action_url': f'/forms/{sub.pk}/validate/',
            'created_at': sub.created_at.isoformat(),
        })

    # Pending / failed offline data
    device_ids = MobileDevice.objects.filter(
        user=worker.user, is_deleted=False
    ).values_list('id', flat=True)

    pending_count = OfflineData.objects.filter(
        device_id__in=device_ids,
        sync_status__in=['PENDING', 'FAILED'],
        is_deleted=False,
    ).count()

    if pending_count:
        tasks.append({
            'source': 'offline_sync',
            'id': 'offline_sync',
            'priority': 'HIGH',
            'title': f'{pending_count} offline record(s) pending sync',
            'body': 'Connect to sync your offline data to the server.',
            'action_url': '/mobile/sync/',
            'created_at': timezone.now().isoformat(),
        })

    # Sort by priority weight
    priority_order = {'URGENT': 0, 'HIGH': 1, 'NORMAL': 2, 'LOW': 3}
    tasks.sort(key=lambda t: priority_order.get(t['priority'], 99))
    return tasks


# ---------------------------------------------------------------------------
# Visit checklist
# ---------------------------------------------------------------------------

ACTIVITY_CHECKLISTS: Dict[str, List[Dict]] = {
    'CASE_VISIT': [
        {'id': 'identify_household', 'label': 'Identify household and confirm case identity'},
        {'id': 'symptom_check', 'label': 'Conduct symptom assessment'},
        {'id': 'medication_adherence', 'label': 'Check medication adherence'},
        {'id': 'isolation_status', 'label': 'Confirm isolation / quarantine status'},
        {'id': 'contact_list', 'label': 'Update contact list'},
        {'id': 'referral', 'label': 'Make referral if needed'},
        {'id': 'record_visit', 'label': 'Record visit in app'},
    ],
    'CONTACT_TRACING': [
        {'id': 'identify_contact', 'label': 'Identify and locate contact'},
        {'id': 'risk_assessment', 'label': 'Conduct risk assessment'},
        {'id': 'test_offer', 'label': 'Offer testing if eligible'},
        {'id': 'quarantine_guidance', 'label': 'Provide quarantine guidance'},
        {'id': 'support_resources', 'label': 'Connect to support resources'},
        {'id': 'record_tracing', 'label': 'Record in contact tracing form'},
    ],
    'VACCINATION': [
        {'id': 'eligibility_check', 'label': 'Confirm eligibility'},
        {'id': 'consent', 'label': 'Obtain informed consent'},
        {'id': 'administer_vaccine', 'label': 'Administer vaccine'},
        {'id': 'adverse_events', 'label': 'Monitor for immediate adverse events (15 min)'},
        {'id': 'record_dose', 'label': 'Record dose in system'},
        {'id': 'next_dose_info', 'label': 'Provide next-dose information'},
    ],
    'HEALTH_EDUCATION': [
        {'id': 'gather_community', 'label': 'Gather community members'},
        {'id': 'present_content', 'label': 'Present health education content'},
        {'id': 'q_and_a', 'label': 'Conduct Q&A session'},
        {'id': 'distribute_materials', 'label': 'Distribute IEC materials'},
        {'id': 'record_attendance', 'label': 'Record attendance count'},
    ],
    'SURVEILLANCE': [
        {'id': 'household_visit', 'label': 'Conduct household surveillance visit'},
        {'id': 'symptom_screening', 'label': 'Screen for symptoms'},
        {'id': 'sample_collection', 'label': 'Collect samples if indicated'},
        {'id': 'data_entry', 'label': 'Enter surveillance data'},
        {'id': 'report_anomalies', 'label': 'Report any anomalies immediately'},
    ],
    'SAMPLE_COLLECTION': [
        {'id': 'ppe', 'label': 'Don appropriate PPE'},
        {'id': 'consent_sample', 'label': 'Obtain consent for sample'},
        {'id': 'label_sample', 'label': 'Label sample with ID and date'},
        {'id': 'cold_chain', 'label': 'Maintain cold chain'},
        {'id': 'transport_form', 'label': 'Complete sample transport form'},
        {'id': 'record_collection', 'label': 'Record in app'},
    ],
}


def get_activity_checklist(activity_type: str) -> List[Dict]:
    """Return the standard checklist for a given activity type."""
    return ACTIVITY_CHECKLISTS.get(activity_type, [])


# ---------------------------------------------------------------------------
# CHW dashboard
# ---------------------------------------------------------------------------

def build_chw_dashboard(worker_id: int) -> Dict:
    """
    Aggregate all CHW-relevant data into a single dashboard payload.
    Intended for the mobile home screen.
    """
    from .models import FieldWorker, MobileNotification

    try:
        worker = FieldWorker.objects.select_related(
            'user', 'assigned_location'
        ).get(pk=worker_id, is_deleted=False)
    except FieldWorker.DoesNotExist:
        return {'error': 'Worker not found.'}

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())

    from .models import FieldActivity

    today_activities = FieldActivity.objects.filter(
        field_worker=worker,
        activity_date=today,
        is_deleted=False,
    ).count()

    week_activities = FieldActivity.objects.filter(
        field_worker=worker,
        activity_date__gte=week_start,
        is_deleted=False,
    ).count()

    unread_notifications = MobileNotification.objects.filter(
        user=worker.user,
        is_read=False,
        is_deleted=False,
    ).count()

    pending_tasks = get_worker_tasks(worker_id)

    return {
        'worker': {
            'worker_id': worker.worker_id,
            'full_name': worker.user.get_full_name(),
            'worker_type': worker.get_worker_type_display(),
            'assigned_location': (
                worker.assigned_location.name if worker.assigned_location else None
            ),
            'is_active': worker.is_active,
        },
        'today': {
            'date': today.isoformat(),
            'activities': today_activities,
        },
        'this_week': {
            'week_start': week_start.isoformat(),
            'activities': week_activities,
        },
        'lifetime': {
            'cases_managed': worker.cases_managed,
            'contacts_traced': worker.contacts_traced,
            'surveys_completed': worker.surveys_completed,
            'activities_logged': worker.activities_logged,
        },
        'notifications': {
            'unread': unread_notifications,
        },
        'pending_tasks': pending_tasks[:5],  # top 5 for home screen
    }


# ---------------------------------------------------------------------------
# Location helpers
# ---------------------------------------------------------------------------

def workers_near_location(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
) -> List[Dict]:
    """
    Return active field workers within approximately `radius_km` of the
    given coordinates using the Haversine approximation (no PostGIS).

    Returns a list of {worker_id, full_name, worker_type, distance_km, lat, lng}.
    """
    import math

    from .models import FieldWorker

    workers = FieldWorker.objects.filter(
        is_active=True,
        is_deleted=False,
        current_latitude__isnull=False,
        current_longitude__isnull=False,
    ).select_related('user')

    results = []
    for w in workers:
        dist = _haversine(
            float(latitude), float(longitude),
            float(w.current_latitude), float(w.current_longitude),
        )
        if dist <= radius_km:
            results.append({
                'worker_id': w.worker_id,
                'full_name': w.user.get_full_name(),
                'worker_type': w.get_worker_type_display(),
                'distance_km': round(dist, 3),
                'latitude': float(w.current_latitude),
                'longitude': float(w.current_longitude),
            })

    results.sort(key=lambda x: x['distance_km'])
    return results


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km."""
    import math

    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))