"""
Domain-layer helpers for contact tracing workflows.

These functions encapsulate multi-step contact tracing logic that
would be too heavy to live in a viewset or a model method.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


def trace_contacts_for_case(case, contacts_data: list, assigned_to=None, monitoring_period: int = 14) -> list:
    """
    Bulk-create contact records for a confirmed case and start monitoring.

    contacts_data: list of dicts with keys matching Contact field names.
    Returns list of created Contact instances.
    """
    from .models import Contact

    created = []
    with transaction.atomic():
        for data in contacts_data:
            contact = Contact.objects.create(
                source_case=case,
                assigned_to=assigned_to,
                **data,
            )
            contact.start_monitoring(period_days=monitoring_period)
            created.append(contact)
            logger.info(
                "Contact %s created for case %s and placed under monitoring.",
                contact.contact_id, case.case_id,
            )
    return created


def generate_monitoring_summary(contact) -> dict:
    """
    Return a monitoring summary dict for a contact.
    """
    records = contact.monitoring_records.filter(is_deleted=False).order_by('monitoring_date')
    total_days = records.count()
    symptomatic_days = records.filter(has_symptoms=True).count()
    non_compliant_days = records.filter(is_compliant=False).count()
    unreachable_days = records.filter(is_reachable=False).count()

    today = timezone.now().date()
    remaining = 0
    if contact.monitoring_end_date:
        delta = contact.monitoring_end_date - today
        remaining = max(0, delta.days)

    return {
        'contact_id': contact.contact_id,
        'contact_name': contact.contact_name,
        'status': contact.status,
        'monitoring_start_date': str(contact.monitoring_start_date or ''),
        'monitoring_end_date': str(contact.monitoring_end_date or ''),
        'days_remaining': remaining,
        'total_records': total_days,
        'symptomatic_days': symptomatic_days,
        'non_compliant_days': non_compliant_days,
        'unreachable_days': unreachable_days,
        'compliance_rate': round((1 - non_compliant_days / total_days) * 100, 1) if total_days else 100.0,
    }


def get_contacts_requiring_followup(location=None) -> list:
    """
    Return contacts that need immediate follow-up:
    - Symptomatic and not yet converted to case
    - Non-compliant for 2+ consecutive days
    """
    from .models import Contact, ContactMonitoring

    qs = Contact.objects.filter(
        status__in=[Contact.STATUS_SYMPTOMATIC, Contact.STATUS_MONITORING],
        is_deleted=False,
    )
    if location:
        qs = qs.filter(location=location)

    results = []
    for contact in qs.select_related('assigned_to', 'source_case'):
        if contact.status == Contact.STATUS_SYMPTOMATIC:
            results.append({'contact': contact, 'reason': 'symptomatic'})
            continue

        # Check for consecutive non-compliance
        recent = list(
            contact.monitoring_records.filter(is_deleted=False)
            .order_by('-monitoring_date')[:2]
            .values_list('is_compliant', flat=True)
        )
        if len(recent) == 2 and not any(recent):
            results.append({'contact': contact, 'reason': 'consecutive_non_compliance'})

    return results