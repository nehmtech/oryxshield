"""
Domain-layer helpers for quarantine management workflows.
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def admit_to_quarantine(
    facility,
    individual_name: str,
    admission_date,
    expected_release_date,
    record_id: str,
    contact=None,
    case=None,
    room_number: str = '',
    individual_contact: str = '',
    individual_id_number: str = '',
) -> 'QuarantineRecord':
    """
    Atomically admit an individual to a quarantine facility.
    Raises ValueError if the facility is at capacity.
    """
    from .models import QuarantineRecord

    with transaction.atomic():
        if facility.is_full:
            raise ValueError(f"Facility '{facility.name}' is at full capacity.")

        record = QuarantineRecord.objects.create(
            record_id=record_id,
            facility=facility,
            individual_name=individual_name,
            individual_contact=individual_contact,
            individual_id_number=individual_id_number,
            case=case,
            contact=contact,
            admission_date=admission_date,
            expected_release_date=expected_release_date,
            status=QuarantineRecord.STATUS_ADMITTED,
            room_number=room_number,
        )
        facility.increment_occupancy()

        # Update linked contact if provided
        if contact and not contact.is_quarantined:
            contact.is_quarantined = True
            contact.quarantine_start_date = admission_date
            contact.quarantine_end_date = expected_release_date
            contact.quarantine_location = facility.name
            contact.status = contact.STATUS_QUARANTINED
            contact.save(update_fields=[
                'is_quarantined', 'quarantine_start_date',
                'quarantine_end_date', 'quarantine_location',
                'status', 'updated_at',
            ])

    logger.info(
        "QuarantineRecord %s created at %s (occupancy: %s/%s)",
        record_id, facility.code,
        facility.current_occupancy, facility.total_capacity,
    )
    return record


def get_facility_capacity_report(operational_only: bool = True) -> list:
    """
    Return a capacity summary for all quarantine facilities.
    """
    from .models import QuarantineFacility

    qs = QuarantineFacility.objects.filter(is_deleted=False)
    if operational_only:
        qs = qs.filter(is_operational=True)

    return [
        {
            'name': f.name,
            'code': f.code,
            'facility_type': f.get_facility_type_display(),
            'total_capacity': f.total_capacity,
            'current_occupancy': f.current_occupancy,
            'available_beds': f.available_beds,
            'occupancy_rate': f.occupancy_rate,
            'is_full': f.is_full,
        }
        for f in qs
    ]


def get_records_releasing_soon(days_ahead: int = 3) -> list:
    """
    Return quarantine records whose expected release date falls within the next N days.
    """
    from .models import QuarantineRecord
    from datetime import timedelta

    today = timezone.now().date()
    cutoff = today + timedelta(days=days_ahead)

    return list(
        QuarantineRecord.objects.filter(
            status=QuarantineRecord.STATUS_IN_QUARANTINE,
            expected_release_date__range=(today, cutoff),
            is_deleted=False,
        ).select_related('facility', 'contact', 'case')
    )