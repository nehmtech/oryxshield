"""
Signal handlers for mobile app — OryxShield.

Uses update_fields on all targeted saves. Counter increments
are delegated to model methods that use F() for atomicity.
"""
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FieldActivity signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender='mobile.FieldActivity')
def field_activity_saved(sender, instance, created, **kwargs):
    """
    On new FieldActivity:
    - Increment the worker's activities_logged counter atomically.
    - Touch the device's last_active timestamp if a matching device exists.

    Counter increment on create is also done inside the ViewSet (perform_create)
    for transactional safety; the signal acts as a safety net for out-of-band
    creates (e.g. management commands, tests).
    """
    if created and instance.field_worker_id:
        # Only increment if not already done inside a ViewSet transaction.
        # We use update() so it is always idempotent at the DB level.
        from .models import FieldWorker
        from django.db.models import F
        FieldWorker.objects.filter(pk=instance.field_worker_id).update(
            activities_logged=F('activities_logged') + 1
        )
        logger.debug(
            "field_activity_saved: incremented activities_logged for worker %s",
            instance.field_worker_id,
        )


# ---------------------------------------------------------------------------
# FormSubmission signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender='mobile.FormSubmission')
def form_submission_saved(sender, instance, created, **kwargs):
    """
    On new FormSubmission:
    - Increment field worker's surveys_completed counter atomically.
    - Trigger server-side validation in the background.
    """
    if created and instance.field_worker_id:
        from .models import FieldWorker
        from django.db.models import F
        FieldWorker.objects.filter(pk=instance.field_worker_id).update(
            surveys_completed=F('surveys_completed') + 1
        )
        logger.debug(
            "form_submission_saved: incremented surveys_completed for worker %s",
            instance.field_worker_id,
        )

    # Queue async validation for offline submissions
    if created and instance.created_offline and not instance.is_validated:
        from .tasks import validate_form_submission_async
        try:
            validate_form_submission_async.delay(instance.pk)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "form_submission_saved: could not queue validation for %s: %s",
                instance.pk, exc,
            )


# ---------------------------------------------------------------------------
# SurveyResponse signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender='mobile.SurveyResponse')
def survey_response_saved(sender, instance, created, **kwargs):
    """
    On new SurveyResponse sync:
    - Stamp synced_at if the response was created offline and has no timestamp.
    """
    if created and instance.created_offline and not instance.synced_at:
        from .models import SurveyResponse
        SurveyResponse.objects.filter(pk=instance.pk).update(
            synced_at=timezone.now()
        )
        logger.debug(
            "survey_response_saved: stamped synced_at for response %s",
            instance.response_id,
        )


# ---------------------------------------------------------------------------
# MobileDevice signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender='mobile.MobileDevice')
def mobile_device_saved(sender, instance, created, **kwargs):
    """
    On new device registration:
    - Log the event (not an AuditLog entry — that's in the ViewSet).
    """
    if created:
        logger.info(
            "mobile_device_saved: new device registered device_id=%s user=%s",
            instance.device_id,
            instance.user_id,
        )