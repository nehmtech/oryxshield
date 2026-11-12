"""
Celery tasks for mobile app — OryxShield.

All tasks: bind=True, max_retries=3, default_retry_delay set per task.
"""
import hashlib
import json
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Offline sync
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_offline_sync(self, device_id: str, pending_data: list) -> dict:
    """
    Process a batch of offline records submitted by a field device.

    For each item:
    1. Create an OfflineData record (SYNCING).
    2. Dispatch to the relevant app's model.
    3. Mark SYNCED or FAILED.

    Returns a summary dict.
    """
    from .models import MobileDevice, OfflineData

    try:
        device = MobileDevice.objects.get(device_id=device_id, is_deleted=False)
    except MobileDevice.DoesNotExist:
        logger.error("process_offline_sync: device %s not found.", device_id)
        return {'status': 'error', 'message': 'Device not registered.'}

    logger.info(
        "process_offline_sync: device=%s items=%d", device_id, len(pending_data)
    )

    synced, failed, conflicts = 0, 0, 0

    for item in pending_data:
        offline_record = None
        try:
            checksum = hashlib.sha256(
                json.dumps(item.get('payload', {}), sort_keys=True).encode()
            ).hexdigest()

            # Idempotency: skip if already synced with same checksum
            if OfflineData.objects.filter(
                device=device,
                checksum=checksum,
                sync_status='SYNCED',
            ).exists():
                synced += 1
                continue

            with transaction.atomic():
                offline_record = OfflineData.objects.create(
                    device=device,
                    data_type=item['data_type'],
                    data_payload=item.get('payload', {}),
                    sync_status='SYNCING',
                    created_offline_at=item.get('created_at', timezone.now()),
                    checksum=checksum,
                )

                server_id = _dispatch_sync_item(item['data_type'], item.get('payload', {}))

                offline_record.sync_status = 'SYNCED'
                offline_record.synced_at = timezone.now()
                offline_record.server_record_id = str(server_id) if server_id else ''
                offline_record.save(update_fields=[
                    'sync_status', 'synced_at', 'server_record_id',
                ])
                synced += 1

        except Exception as exc:
            failed += 1
            logger.exception(
                "process_offline_sync: failed item type=%s device=%s: %s",
                item.get('data_type'), device_id, exc,
            )
            if offline_record and offline_record.pk:
                offline_record.sync_status = 'FAILED'
                offline_record.error_message = str(exc)
                offline_record.save(update_fields=['sync_status', 'error_message'])
                offline_record.increment_attempts()

    result = {
        'status': 'completed',
        'device_id': device_id,
        'synced': synced,
        'failed': failed,
        'conflicts': conflicts,
    }
    logger.info("process_offline_sync result: %s", result)
    return result


def _dispatch_sync_item(data_type: str, payload: dict):
    """
    Route a sync payload to the correct model.
    Returns the created object's PK (or None).

    CASE / CONTACT / MONITORING: schema mapping awaiting government data model
    confirmation. These types are logged as unhandled so no data is silently
    dropped — operators can see them in the logs and replay once mapping is done.
    """
    try:
        if data_type == 'CASE':
            logger.warning(
                "mobile sync: CASE type not yet mapped — payload keys=%s. "
                "Implement _dispatch_sync_item CASE branch when operations.Case "
                "field mapping is confirmed.",
                list(payload.keys()),
            )
            return None
        elif data_type == 'CONTACT':
            logger.warning(
                "mobile sync: CONTACT type not yet mapped — payload keys=%s. "
                "Implement _dispatch_sync_item CONTACT branch when "
                "operations.Contact field mapping is confirmed.",
                list(payload.keys()),
            )
            return None
        elif data_type == 'MONITORING':
            logger.warning(
                "mobile sync: MONITORING type not yet mapped — payload keys=%s. "
                "Implement _dispatch_sync_item MONITORING branch when "
                "operations.ContactMonitoring field mapping is confirmed.",
                list(payload.keys()),
            )
            return None
        elif data_type == 'SURVEY':
            from .models import SurveyResponse
            obj = SurveyResponse.objects.create(**payload)
            return obj.pk
        elif data_type == 'HEALTH_DATA':
            from surveillance.models import HealthData
            obj = HealthData.objects.create(**payload)
            return obj.pk
        else:
            logger.warning(
                "mobile sync: unknown data_type=%r — payload keys=%s. "
                "Add a handler branch for this type.",
                data_type, list(payload.keys()),
            )
    except Exception as exc:
        raise exc
    return None


# ---------------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notifications(self) -> dict:
    """
    Dispatch all pending, non-expired push notifications via FCM / APNS.
    Runs on a beat schedule every 5 minutes.
    """
    from .models import MobileNotification

    now = timezone.now()
    pending = MobileNotification.objects.filter(
        is_sent=False,
        is_deleted=False,
    ).filter(
        # not expired (expires_at is null OR expires_at > now)
        expires_at__isnull=True,
    ) | MobileNotification.objects.filter(
        is_sent=False,
        is_deleted=False,
        expires_at__gt=now,
    )

    sent, failed = 0, 0

    for notification in pending.select_related('device', 'user'):
        try:
            if notification.device and notification.device.fcm_token:
                message_id = _send_fcm(
                    token=notification.device.fcm_token,
                    title=notification.title,
                    body=notification.body,
                    data={
                        'action_url': notification.action_url,
                        'notification_id': notification.notification_id,
                        'priority': notification.priority,
                        **notification.action_data,
                    },
                )
                notification.is_sent = True
                notification.sent_at = now
                notification.fcm_message_id = message_id
                notification.save(update_fields=[
                    'is_sent', 'sent_at', 'fcm_message_id', 'updated_at',
                ])
                sent += 1

            elif notification.device and notification.device.apns_token:
                _send_apns(
                    token=notification.device.apns_token,
                    title=notification.title,
                    body=notification.body,
                )
                notification.is_sent = True
                notification.sent_at = now
                notification.save(update_fields=['is_sent', 'sent_at', 'updated_at'])
                sent += 1

            else:
                # No token — mark sent to prevent repeated retries
                notification.is_sent = True
                notification.sent_at = now
                notification.delivery_error = 'No push token available.'
                notification.save(update_fields=[
                    'is_sent', 'sent_at', 'delivery_error', 'updated_at',
                ])
                sent += 1

        except Exception as exc:
            failed += 1
            logger.exception(
                "send_push_notifications: failed for notification %s: %s",
                notification.notification_id, exc,
            )
            notification.delivery_error = str(exc)
            notification.save(update_fields=['delivery_error', 'updated_at'])

    result = {'status': 'completed', 'sent': sent, 'failed': failed}
    logger.info("send_push_notifications: %s", result)
    return result


def _send_fcm(token: str, title: str, body: str, data: dict = None) -> str:
    """
    Send a Firebase Cloud Messaging push notification.

    Requires GOOGLE_APPLICATION_CREDENTIALS or FCM_SERVER_KEY in settings.
    Returns the FCM message ID.
    """
    import requests
    from django.conf import settings

    server_key = getattr(settings, 'FCM_SERVER_KEY', '')
    if not server_key:
        logger.warning("_send_fcm: FCM_SERVER_KEY not configured.")
        return ''

    payload = {
        'to': token,
        'notification': {'title': title, 'body': body},
        'data': data or {},
        'priority': 'high',
    }

    response = requests.post(
        'https://fcm.googleapis.com/fcm/send',
        json=payload,
        headers={
            'Authorization': f'key={server_key}',
            'Content-Type': 'application/json',
        },
        timeout=10,
    )
    response.raise_for_status()
    result = response.json()

    if result.get('failure', 0) > 0:
        error = result.get('results', [{}])[0].get('error', 'Unknown FCM error')
        raise RuntimeError(f"FCM delivery failed: {error}")

    return result.get('results', [{}])[0].get('message_id', '')


def _send_apns(token: str, title: str, body: str) -> None:
    """
    Send an Apple Push Notification.
    Placeholder — integrate with PyAPNs2 or the HTTP/2 APNS endpoint.
    """
    logger.info("_send_apns: APNS delivery not yet configured for token %s.", token[:8])


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_old_offline_data(self) -> dict:
    """
    Hard-delete SYNCED OfflineData records older than 30 days.
    Runs on a weekly beat schedule.
    """
    from .models import OfflineData

    cutoff = timezone.now() - timezone.timedelta(days=30)
    qs = OfflineData.objects.filter(sync_status='SYNCED', synced_at__lt=cutoff)
    count = qs.count()
    qs.delete()

    logger.info("cleanup_old_offline_data: deleted %d records.", count)
    return {'status': 'completed', 'deleted': count}


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def retry_failed_syncs(self) -> dict:
    """
    Re-queue FAILED OfflineData records that haven't exceeded max_attempts.
    Runs hourly.
    """
    from .models import OfflineData

    MAX_ATTEMPTS = 5
    failed_items = OfflineData.objects.filter(
        sync_status='FAILED',
        sync_attempts__lt=MAX_ATTEMPTS,
        is_deleted=False,
    ).select_related('device')

    queued = 0
    for item in failed_items:
        try:
            process_offline_sync.delay(
                item.device.device_id,
                [{
                    'data_type': item.data_type,
                    'payload': item.data_payload,
                    'created_at': item.created_offline_at.isoformat(),
                }],
            )
            item.sync_status = 'PENDING'
            item.save(update_fields=['sync_status', 'updated_at'])
            queued += 1
        except Exception as exc:
            logger.exception(
                "retry_failed_syncs: could not re-queue item %s: %s", item.pk, exc
            )

    logger.info("retry_failed_syncs: re-queued %d items.", queued)
    return {'status': 'completed', 'queued': queued}


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def expire_old_notifications(self) -> dict:
    """
    Mark unsent, expired notifications as deleted.
    Runs daily.
    """
    from .models import MobileNotification

    now = timezone.now()
    qs = MobileNotification.objects.filter(
        is_sent=False,
        expires_at__lte=now,
        is_deleted=False,
    )
    count = qs.count()
    qs.update(is_deleted=True, updated_at=now)

    logger.info("expire_old_notifications: expired %d notifications.", count)
    return {'status': 'completed', 'expired': count}