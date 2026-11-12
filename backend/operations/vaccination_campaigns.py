"""
Domain-layer helpers for vaccination campaign workflows.
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def record_dose(
    campaign,
    record_id: str,
    patient_name: str,
    patient_age: int,
    patient_gender: str,
    location,
    vaccine_name: str,
    vaccine_batch: str,
    dose_number: int,
    vaccination_date,
    administered_by=None,
    patient_id_number: str = '',
    patient_contact: str = '',
    vaccination_site: str = '',
    next_dose_due=None,
) -> 'VaccinationRecord':
    """
    Atomically create a vaccination record and update campaign progress counters.
    """
    from .models import VaccinationRecord

    with transaction.atomic():
        record = VaccinationRecord.objects.create(
            record_id=record_id,
            campaign=campaign,
            patient_name=patient_name,
            patient_age=patient_age,
            patient_gender=patient_gender,
            patient_id_number=patient_id_number,
            patient_contact=patient_contact,
            location=location,
            vaccination_site=vaccination_site,
            vaccine_name=vaccine_name,
            vaccine_batch=vaccine_batch,
            dose_number=dose_number,
            vaccination_date=vaccination_date,
            next_dose_due=next_dose_due,
            administered_by=administered_by,
        )

        campaign.doses_administered += 1
        if dose_number == 1:
            campaign.people_vaccinated += 1
        campaign.save(update_fields=['doses_administered', 'people_vaccinated', 'updated_at'])

    logger.info(
        "VaccinationRecord %s created for campaign %s (dose %d)",
        record_id, campaign.campaign_code, dose_number,
    )
    return record


def get_campaign_progress_report(campaign) -> dict:
    """
    Return a detailed progress report for a vaccination campaign.
    """
    from .models import VaccinationRecord
    from django.db.models import Count

    records = VaccinationRecord.objects.filter(
        campaign=campaign, is_deleted=False
    )
    by_dose = dict(
        records.values('dose_number').annotate(count=Count('id')).values_list('dose_number', 'count')
    )
    adverse_count = records.filter(adverse_event_reported=True).count()
    today = timezone.now().date()
    today_count = records.filter(vaccination_date=today).count()

    return {
        'campaign_code': campaign.campaign_code,
        'vaccine_name': campaign.vaccine_name,
        'status': campaign.status,
        'target_population': campaign.target_population,
        'people_vaccinated': campaign.people_vaccinated,
        'doses_administered': campaign.doses_administered,
        'coverage_rate': campaign.coverage_rate,
        'doses_by_number': by_dose,
        'adverse_events': adverse_count,
        'vaccinations_today': today_count,
        'days_remaining': max(0, (campaign.end_date - today).days) if campaign.end_date else None,
    }


def find_individuals_due_for_next_dose(days_ahead: int = 7) -> list:
    """
    Return vaccination records where next_dose_due falls within the next N days.
    """
    from .models import VaccinationRecord
    from datetime import timedelta

    today = timezone.now().date()
    cutoff = today + timedelta(days=days_ahead)
    return list(
        VaccinationRecord.objects.filter(
            next_dose_due__range=(today, cutoff),
            is_deleted=False,
        ).select_related('campaign', 'location')
    )