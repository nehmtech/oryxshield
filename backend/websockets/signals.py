"""
Django signals for the websockets app.

Wires up downstream apps (risk_assessment, surveillance, response, etc.) to
push real-time updates via WebSocket without those apps importing from
websockets directly — keeping the dependency direction clean.

Each signal handler calls the appropriate websockets.utils helper.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# risk_assessment → AlertConsumer
# ---------------------------------------------------------------------------

def _connect_risk_assessment():
    try:
        from risk_assessment.models import Alert

        @receiver(post_save, sender=Alert, dispatch_uid='ws_alert_post_save')
        def on_alert_save(sender, instance, created, **kwargs):
            from websockets.utils import send_alert
            try:
                send_alert(
                    {
                        'alert_id':   str(instance.pk),
                        'title':      instance.title,
                        'severity':   instance.severity,
                        'status':     instance.status,
                        'created_at': instance.created_at.isoformat(),
                    },
                    severity=instance.severity,
                )
            except Exception as exc:
                logger.error('ws signal on_alert_save: %s', exc)

    except ImportError:
        logger.debug('risk_assessment not installed; skipping alert signal')


# ---------------------------------------------------------------------------
# surveillance → SurveillanceConsumer
# ---------------------------------------------------------------------------

def _connect_surveillance():
    try:
        from surveillance.models import HealthData, Hotspot

        @receiver(post_save, sender=HealthData, dispatch_uid='ws_healthdata_post_save')
        def on_health_data_save(sender, instance, created, **kwargs):
            from websockets.utils import send_surveillance_update
            try:
                send_surveillance_update({
                    'event':      'health_data',
                    'record_id':  str(instance.pk),
                    'source_id':  str(instance.data_source_id),
                    'created_at': instance.created_at.isoformat(),
                })
            except Exception as exc:
                logger.error('ws signal on_health_data_save: %s', exc)

        @receiver(post_save, sender=Hotspot, dispatch_uid='ws_hotspot_post_save')
        def on_hotspot_save(sender, instance, created, **kwargs):
            from websockets.utils import send_hotspot_update
            try:
                send_hotspot_update({
                    'hotspot_id':   str(instance.pk),
                    'disease_name': instance.disease_name,
                    'risk_level':   instance.risk_level,
                    'created_at':   instance.created_at.isoformat(),
                })
            except Exception as exc:
                logger.error('ws signal on_hotspot_save: %s', exc)

    except ImportError:
        logger.debug('surveillance not installed; skipping health_data signal')


# ---------------------------------------------------------------------------
# response → ResponseConsumer
# ---------------------------------------------------------------------------

def _connect_response():
    try:
        from response.models import ResponseActivation

        @receiver(post_save, sender=ResponseActivation, dispatch_uid='ws_activation_post_save')
        def on_activation_save(sender, instance, created, **kwargs):
            from websockets.utils import send_response_update, send_escalation_alert
            try:
                payload = {
                    'activation_id': str(instance.pk),
                    'status':        instance.status,
                    'level':         str(instance.response_level_id),
                    'updated_at':    instance.updated_at.isoformat(),
                }
                send_response_update(payload)
                if instance.status == 'escalated':
                    send_escalation_alert(payload)
            except Exception as exc:
                logger.error('ws signal on_activation_save: %s', exc)

    except ImportError:
        logger.debug('response not installed; skipping activation signal')


# ---------------------------------------------------------------------------
# core.Notification → NotificationConsumer
# ---------------------------------------------------------------------------

def _connect_core_notifications():
    try:
        from core.models import Notification

        @receiver(post_save, sender=Notification, dispatch_uid='ws_notification_post_save')
        def on_notification_save(sender, instance, created, **kwargs):
            if not created:
                return
            from websockets.utils import send_notification_to_user
            try:
                send_notification_to_user(instance.user_id, {
                    'notification_id': str(instance.pk),
                    'title':           instance.title,
                    'message':         instance.message,
                    'created_at':      instance.created_at.isoformat(),
                })
            except Exception as exc:
                logger.error('ws signal on_notification_save: %s', exc)

    except (ImportError, AttributeError):
        logger.debug('core.Notification not available; skipping signal')


# ---------------------------------------------------------------------------
# Wire everything up
# ---------------------------------------------------------------------------

_connect_risk_assessment()
_connect_surveillance()
_connect_response()
_connect_core_notifications()