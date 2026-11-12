"""
Celery tasks for operations app.

Schedule (suggested celery beat config):
  check_contact_monitoring         — every hour
  check_quarantine_completions     — daily 06:00
  send_vaccination_reminders       — daily 08:00
  sync_testing_center_load         — every 30 min
  flag_overdue_monitoring          — daily 09:00
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_contact_monitoring(self):
    """
    Notify assigned tracers of contacts due for daily monitoring.
    Runs hourly.
    """
    from .models import Contact, ContactMonitoring
    from core.models import AuditLog

    try:
        today = timezone.now().date()
        due_contacts = Contact.objects.filter(
            status=Contact.STATUS_MONITORING,
            monitoring_end_date__gte=today,
            is_deleted=False,
        ).select_related('assigned_to')

        notified = 0
        for contact in due_contacts:
            already_done = ContactMonitoring.objects.filter(
                contact=contact,
                monitoring_date=today,
                is_deleted=False,
            ).exists()
            if already_done or not contact.assigned_to:
                continue

            _create_notification(
                user=contact.assigned_to,
                title=f"Monitoring Due: {contact.contact_name}",
                message=(
                    f"Daily monitoring for {contact.contact_name} "
                    f"(contact of {contact.source_case.case_id}) is due today."
                ),
                notification_type='WARNING',
            )
            notified += 1

        logger.info("check_contact_monitoring: notified %d tracers", notified)
        return {'status': 'completed', 'contacts_due': due_contacts.count(), 'notified': notified}

    except Exception as exc:
        logger.exception("check_contact_monitoring failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def check_quarantine_completions(self):
    """
    Auto-complete quarantine records whose expected release date is today.
    Runs daily.
    """
    from .models import QuarantineRecord

    try:
        today = timezone.now().date()
        releasing = QuarantineRecord.objects.filter(
            status=QuarantineRecord.STATUS_IN_QUARANTINE,
            expected_release_date=today,
            is_deleted=False,
        ).select_related('facility')

        completed = 0
        for record in releasing:
            record.complete_quarantine(release_date=today)
            completed += 1

        logger.info("check_quarantine_completions: completed %d records", completed)
        return {'status': 'completed', 'records_completed': completed}

    except Exception as exc:
        logger.exception("check_quarantine_completions failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_vaccination_reminders(self):
    """
    Send SMS reminders for next vaccine doses due tomorrow.
    Runs daily.
    """
    from .models import VaccinationRecord

    try:
        tomorrow = timezone.now().date() + timedelta(days=1)
        due = VaccinationRecord.objects.filter(
            next_dose_due=tomorrow,
            is_deleted=False,
        )

        sent = 0
        for record in due:
            if not record.patient_contact:
                continue
            try:
                from communications.tasks import send_sms_notification
                send_sms_notification.delay(
                    record.patient_contact,
                    "Vaccination Reminder",
                    (
                        f"Reminder: Your {record.vaccine_name} dose {record.dose_number + 1} "
                        f"is due tomorrow ({tomorrow}). Please attend your scheduled session."
                    ),
                )
                sent += 1
            except Exception as sms_exc:
                logger.warning(
                    "SMS reminder failed for VaccinationRecord %s: %s",
                    record.record_id, sms_exc
                )

        logger.info("send_vaccination_reminders: sent %d reminders", sent)
        return {'status': 'completed', 'reminders_sent': sent}

    except Exception as exc:
        logger.exception("send_vaccination_reminders failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_testing_center_load(self):
    """
    Recalculate current_load for each testing center based on today's appointments.
    Runs every 30 minutes.
    """
    from .models import TestingCenter, TestingAppointment
    from django.db.models import Count

    try:
        today = timezone.now().date()
        center_loads = (
            TestingAppointment.objects
            .filter(appointment_date=today, is_deleted=False)
            .exclude(status__in=[
                TestingAppointment.STATUS_CANCELLED,
                TestingAppointment.STATUS_NO_SHOW,
            ])
            .values('testing_center_id')
            .annotate(load=Count('id'))
        )

        load_map = {entry['testing_center_id']: entry['load'] for entry in center_loads}

        updated = 0
        for center in TestingCenter.objects.filter(is_operational=True, is_deleted=False):
            new_load = load_map.get(center.pk, 0)
            if center.current_load != new_load:
                center.current_load = new_load
                center.save(update_fields=['current_load', 'updated_at'])
                updated += 1

        logger.info("sync_testing_center_load: updated %d centers", updated)
        return {'status': 'completed', 'centers_updated': updated}

    except Exception as exc:
        logger.exception("sync_testing_center_load failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def flag_overdue_monitoring(self):
    """
    Flag contacts whose monitoring window has ended but are still UNDER_MONITORING.
    Generates an alert and updates status to CLEARED if no symptoms reported.
    Runs daily.
    """
    from .models import Contact

    try:
        today = timezone.now().date()
        overdue = Contact.objects.filter(
            status=Contact.STATUS_MONITORING,
            monitoring_end_date__lt=today,
            is_deleted=False,
        ).select_related('assigned_to')

        cleared = 0
        alerted = 0
        for contact in overdue:
            # Check if any symptoms were recorded during monitoring
            had_symptoms = contact.monitoring_records.filter(
                has_symptoms=True, is_deleted=False
            ).exists()

            if had_symptoms:
                # Leave for manual review; notify tracer
                if contact.assigned_to:
                    _create_notification(
                        user=contact.assigned_to,
                        title=f"Overdue Monitoring Review: {contact.contact_name}",
                        message=(
                            f"{contact.contact_name}'s monitoring window has ended "
                            f"but symptoms were recorded. Manual review required."
                        ),
                        notification_type='ALERT',
                    )
                alerted += 1
            else:
                contact.clear()
                cleared += 1

        logger.info(
            "flag_overdue_monitoring: cleared=%d alerted=%d", cleared, alerted
        )
        return {'status': 'completed', 'cleared': cleared, 'alerted': alerted}

    except Exception as exc:
        logger.exception("flag_overdue_monitoring failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_notification(user, title: str, message: str, notification_type: str):
    """Create a core Notification, swallowing import errors gracefully."""
    try:
        from core.models import Notification
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
        )
    except Exception as exc:
        logger.warning("Notification creation failed: %s", exc)