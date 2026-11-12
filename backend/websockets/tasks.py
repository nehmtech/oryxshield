"""
Celery tasks for the websockets app.

Tasks
-----
  cleanup_stale_presence      – remove RoomPresence rows older than N minutes
  cleanup_old_connections     – purge WebSocketConnection rows older than N days
  cleanup_old_broadcasts      – soft-delete sent BroadcastMessage rows older than N days
  broadcast_system_heartbeat  – push a heartbeat to system_status group (admin monitors)
  retry_failed_broadcasts     – re-attempt FAILED BroadcastMessage rows
"""
import logging

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_stale_presence(self, max_age_minutes: int = 30):
    """
    Delete RoomPresence rows where last_seen is older than *max_age_minutes*.
    Stale rows can accumulate after abnormal disconnects.
    """
    try:
        from websockets.models import RoomPresence
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        deleted, _ = RoomPresence.objects.filter(last_seen__lt=cutoff).delete()
        logger.info('cleanup_stale_presence: deleted %d rows (age > %dm)', deleted, max_age_minutes)
        return {'deleted': deleted}
    except Exception as exc:
        logger.error('cleanup_stale_presence error: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_old_connections(self, days: int = 90):
    """
    Hard-delete WebSocketConnection rows older than *days* days.
    These are immutable audit rows — retention policy applied here.
    """
    try:
        from websockets.models import WebSocketConnection
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = WebSocketConnection.objects.filter(timestamp__lt=cutoff).delete()
        logger.info('cleanup_old_connections: deleted %d rows (age > %dd)', deleted, days)
        return {'deleted': deleted}
    except Exception as exc:
        logger.error('cleanup_old_connections error: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_old_broadcasts(self, days: int = 30):
    """
    Soft-delete BroadcastMessage rows with SENT status older than *days* days.
    FAILED rows are kept for investigation.
    """
    try:
        from websockets.models import BroadcastMessage
        cutoff = timezone.now() - timedelta(days=days)
        updated = BroadcastMessage.objects.filter(
            delivery_status=BroadcastMessage.DeliveryStatus.SENT,
            sent_at__lt=cutoff,
            is_deleted=False,
        ).update(is_deleted=True)
        logger.info('cleanup_old_broadcasts: soft-deleted %d rows (age > %dd)', updated, days)
        return {'soft_deleted': updated}
    except Exception as exc:
        logger.error('cleanup_old_broadcasts error: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def broadcast_system_heartbeat(self):
    """
    Push a heartbeat ping to the system_status channel group every minute
    so admin dashboards can detect loss of connectivity to the task queue.
    """
    try:
        from websockets.utils import send_health_check
        from websockets.models import RoomPresence

        online_count = RoomPresence.objects.count()
        send_health_check({
            'event': 'heartbeat',
            'timestamp': timezone.now().isoformat(),
            'online_connections': online_count,
        })
        return {'status': 'ok', 'online_connections': online_count}
    except Exception as exc:
        logger.error('broadcast_system_heartbeat error: %s', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def retry_failed_broadcasts(self, limit: int = 50):
    """
    Re-attempt the *limit* most-recent FAILED BroadcastMessage rows.
    Only retries messages with a registered group.
    """
    try:
        from websockets.models import BroadcastMessage
        from websockets.utils import send_to_group

        failed = BroadcastMessage.objects.filter(
            delivery_status=BroadcastMessage.DeliveryStatus.FAILED,
            group__isnull=False,
            is_deleted=False,
        ).select_related('group').order_by('-created_at')[:limit]

        retried = 0
        for msg in failed:
            ok = send_to_group(
                msg.group.name,
                msg.message_type,
                msg.payload,
                source=f'retry_failed_broadcasts:{msg.pk}',
                log=False,
            )
            if ok:
                msg.delivery_status = BroadcastMessage.DeliveryStatus.REPLAYED
                msg.sent_at = timezone.now()
                msg.save(update_fields=['delivery_status', 'sent_at', 'updated_at'])
                retried += 1

        logger.info('retry_failed_broadcasts: retried %d / %d', retried, len(list(failed)))
        return {'retried': retried}
    except Exception as exc:
        logger.error('retry_failed_broadcasts error: %s', exc)
        raise self.retry(exc=exc)