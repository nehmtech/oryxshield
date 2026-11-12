"""
Domain-layer helpers for testing coordination workflows.
"""
import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


def schedule_appointment(
    testing_center,
    appointment_id: str,
    patient_name: str,
    patient_contact: str,
    appointment_date,
    appointment_time,
    test_type: str,
    contact=None,
    case=None,
    patient_id_number: str = '',
) -> 'TestingAppointment':
    """
    Atomically schedule a testing appointment, checking center capacity.
    Raises ValueError if center is at capacity.
    """
    from .models import TestingAppointment

    with transaction.atomic():
        if testing_center.is_at_capacity:
            raise ValueError(
                f"Testing center '{testing_center.name}' has no available slots for {appointment_date}."
            )

        appointment = TestingAppointment.objects.create(
            appointment_id=appointment_id,
            testing_center=testing_center,
            patient_name=patient_name,
            patient_contact=patient_contact,
            patient_id_number=patient_id_number,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            test_type=test_type,
            contact=contact,
            case=case,
        )
        # Increment load
        testing_center.current_load += 1
        testing_center.save(update_fields=['current_load', 'updated_at'])

    logger.info(
        "TestingAppointment %s scheduled at %s on %s",
        appointment_id, testing_center.code, appointment_date,
    )
    return appointment


def get_center_daily_report(testing_center, date=None) -> dict:
    """
    Return a daily appointment breakdown for a testing center.
    """
    from .models import TestingAppointment
    from django.db.models import Count

    date = date or timezone.now().date()
    apts = TestingAppointment.objects.filter(
        testing_center=testing_center,
        appointment_date=date,
        is_deleted=False,
    )

    by_status = dict(
        apts.values('status').annotate(count=Count('id')).values_list('status', 'count')
    )
    by_result = dict(
        apts.filter(status=TestingAppointment.STATUS_COMPLETED)
        .values('result').annotate(count=Count('id'))
        .values_list('result', 'count')
    )

    return {
        'center': testing_center.code,
        'date': str(date),
        'daily_capacity': testing_center.daily_capacity,
        'total_appointments': apts.count(),
        'by_status': by_status,
        'by_result': by_result,
        'positivity_rate': (
            round(
                by_result.get(TestingAppointment.RESULT_POSITIVE, 0)
                / apts.filter(status=TestingAppointment.STATUS_COMPLETED).count() * 100, 2
            )
            if apts.filter(status=TestingAppointment.STATUS_COMPLETED).exists()
            else 0.0
        ),
    }


def find_available_centers(location=None, test_type: str = '') -> list:
    """
    Return testing centers with available slots, optionally filtered by
    location and test type offered.
    """
    from .models import TestingCenter

    qs = TestingCenter.objects.filter(is_operational=True, is_deleted=False)
    if location:
        qs = qs.filter(location=location)

    results = []
    for center in qs.select_related('location'):
        if center.is_at_capacity:
            continue
        if test_type and test_type not in (center.test_types or []):
            continue
        results.append(center)

    return results