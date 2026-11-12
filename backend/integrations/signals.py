"""
Django signal handlers for OryxShield integrations app.

Fires webhooks on surveillance and risk_assessment events.
All webhook delivery is deferred to Celery (fire-and-forget, non-blocking).
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='surveillance.HealthData')
def on_health_data_created(sender, instance, created, **kwargs):
    """
    Trigger CASE_CREATED webhooks when a new HealthData record is persisted.
    """
    if not created:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='CASE_CREATED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    location_name = ''
    if hasattr(instance, 'location') and instance.location:
        location_name = instance.location.name

    payload = {
        'event': 'case_created',
        'case_id': str(instance.id),
        'disease_code': getattr(instance, 'disease_code', ''),
        'case_status': getattr(instance, 'case_status', ''),
        'location': location_name,
        'report_date': str(getattr(instance, 'report_date', '')),
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue CASE_CREATED webhook {webhook_id}: {e}")


@receiver(post_save, sender='surveillance.HealthData')
def on_health_data_updated(sender, instance, created, **kwargs):
    """
    Trigger CASE_UPDATED webhooks when a HealthData record is modified.
    """
    if created:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='CASE_UPDATED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    payload = {
        'event': 'case_updated',
        'case_id': str(instance.id),
        'disease_code': getattr(instance, 'disease_code', ''),
        'case_status': getattr(instance, 'case_status', ''),
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue CASE_UPDATED webhook {webhook_id}: {e}")


@receiver(post_save, sender='risk_assessment.Alert')
def on_alert_created(sender, instance, created, **kwargs):
    """
    Trigger ALERT_GENERATED webhooks on new risk_assessment Alerts.
    """
    if not created:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='ALERT_GENERATED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    location_name = ''
    if hasattr(instance, 'location') and instance.location:
        location_name = instance.location.name

    payload = {
        'event': 'alert_generated',
        'alert_id': str(instance.id),
        'alert_type': getattr(instance, 'alert_type', ''),
        'severity': getattr(instance, 'severity', ''),
        'location': location_name,
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue ALERT_GENERATED webhook {webhook_id}: {e}")


@receiver(post_save, sender='risk_assessment.Alert')
def on_alert_resolved(sender, instance, created, **kwargs):
    """
    Trigger ALERT_RESOLVED webhooks when an Alert changes to a resolved state.
    """
    if created:
        return

    resolved_statuses = ('RESOLVED', 'CLOSED', 'FALSE_POSITIVE')
    if getattr(instance, 'status', '') not in resolved_statuses:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='ALERT_RESOLVED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    payload = {
        'event': 'alert_resolved',
        'alert_id': str(instance.id),
        'status': getattr(instance, 'status', ''),
        'severity': getattr(instance, 'severity', ''),
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue ALERT_RESOLVED webhook {webhook_id}: {e}")


@receiver(post_save, sender='surveillance.CaseCluster')
def on_outbreak_detected(sender, instance, created, **kwargs):
    """
    Trigger OUTBREAK_DETECTED webhooks when a new CaseCluster is created.
    """
    if not created:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='OUTBREAK_DETECTED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    payload = {
        'event': 'outbreak_detected',
        'cluster_id': str(instance.id),
        'disease_code': getattr(instance, 'disease_code', ''),
        'case_count': getattr(instance, 'case_count', 0),
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue OUTBREAK_DETECTED webhook {webhook_id}: {e}")


@receiver(post_save, sender='response.ResponseActivation')
def on_response_activated(sender, instance, created, **kwargs):
    """
    Trigger RESPONSE_ACTIVATED webhooks when a new ResponseActivation is created.
    """
    if not created:
        return

    from .models import Webhook
    from .tasks import trigger_webhook

    webhooks = Webhook.objects.filter(
        event_type='RESPONSE_ACTIVATED',
        is_active=True,
        is_deleted=False,
    ).values_list('id', flat=True)

    if not webhooks:
        return

    payload = {
        'event': 'response_activated',
        'activation_id': str(instance.id),
        'level': str(getattr(instance, 'response_level', '')),
    }

    for webhook_id in webhooks:
        try:
            trigger_webhook.delay(str(webhook_id), payload)
        except Exception as e:
            logger.error(f"Failed to queue RESPONSE_ACTIVATED webhook {webhook_id}: {e}")