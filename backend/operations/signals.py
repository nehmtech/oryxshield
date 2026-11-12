"""
Signal handlers for operations app.
"""
import logging
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ContactMonitoring, VaccinationRecord, QuarantineRecord

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ContactMonitoring)
def handle_symptomatic_contact(sender, instance, created, **kwargs):
    """
    When a new monitoring record records symptoms, update the contact status
    and notify the assigned tracer.
    """
    if not created or not instance.has_symptoms:
        return

    contact = instance.contact
    if contact.status not in ('SYMPTOMATIC', 'BECAME_CASE', 'CLEARED'):
        contact.flag_symptomatic()
        logger.info(
            "Contact %s flagged as symptomatic via monitoring record %s",
            contact.contact_id, instance.pk,
        )

    if contact.assigned_to:
        _notify(
            user=contact.assigned_to,
            title=f"Symptomatic Contact: {contact.contact_name}",
            message=(
                f"{contact.contact_name} has reported symptoms "
                f"on {instance.monitoring_date}. Immediate follow-up required."
            ),
            notification_type='ALERT',
        )


@receiver(post_save, sender=VaccinationRecord)
def handle_vaccination_campaign_counters(sender, instance, created, **kwargs):
    """Atomically update campaign dose/people counters on each new record."""
    if not created:
        return
    from .models import VaccinationCampaign
    VaccinationCampaign.objects.filter(pk=instance.campaign_id).update(
        doses_administered=F('doses_administered') + 1,
        people_vaccinated=F('people_vaccinated') + 1,
    )


@receiver(post_save, sender=VaccinationRecord)
def handle_adverse_event_alert(sender, instance, created, **kwargs):
    """Notify campaign manager when an adverse event is reported."""
    if not instance.adverse_event_reported:
        return

    manager = instance.campaign.campaign_manager
    if manager:
        _notify(
            user=manager,
            title=f"Adverse Event: {instance.patient_name}",
            message=(
                f"An adverse event ({instance.adverse_event_severity}) has been reported "
                f"for {instance.patient_name} — batch {instance.vaccine_batch}. "
                f"Details: {instance.adverse_event_details[:200]}"
            ),
            notification_type='ALERT',
        )


@receiver(post_save, sender=QuarantineRecord)
def handle_quarantine_admission(sender, instance, created, **kwargs):
    """Log facility occupancy change on new quarantine admission."""
    if not created:
        return
    logger.info(
        "QuarantineRecord %s created at facility %s (occupancy now: %s/%s)",
        instance.record_id,
        instance.facility.code,
        instance.facility.current_occupancy,
        instance.facility.total_capacity,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _notify(user, title: str, message: str, notification_type: str):
    try:
        from core.models import Notification
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
        )
    except Exception as exc:
        logger.warning("Signal notification failed: %s", exc)