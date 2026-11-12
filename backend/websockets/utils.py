"""
Utility functions for sending WebSocket messages from synchronous Django code
(views, Celery tasks, signals, management commands).

All public functions are synchronous wrappers around async channel-layer calls.
They also write a BroadcastMessage log entry for audit and replay.

Usage
-----
    from websockets.utils import send_alert, send_notification_to_user

    send_alert({'alert_id': str(alert.pk), 'severity': 'critical', ...})
    send_notification_to_user(user.pk, {'title': 'New report', ...})
"""
import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core send helper
# ---------------------------------------------------------------------------

def send_to_group(
    group_name: str,
    message_type: str,
    data: dict[str, Any],
    *,
    source: str = '',
    target_user_id: int | None = None,
    log: bool = True,
) -> bool:
    """
    Send *data* to every consumer in *group_name* via the channel layer,
    and write an audit log row to BroadcastMessage.

    Returns True on success, False on error.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.error('send_to_group: no channel layer configured.')
        return False

    # Write audit log before sending (so it exists even if send fails)
    broadcast_id = _log_broadcast(
        group_name=group_name,
        message_type=message_type,
        data=data,
        source=source,
        target_user_id=target_user_id,
    ) if log else None

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': message_type, 'data': data},
        )
        if broadcast_id:
            _mark_broadcast_sent(broadcast_id)
        logger.debug('WS send OK: group=%s type=%s', group_name, message_type)
        return True
    except Exception as exc:
        logger.error('WS send FAIL: group=%s type=%s err=%s', group_name, message_type, exc)
        if broadcast_id:
            _mark_broadcast_failed(broadcast_id)
        return False


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

def send_alert(alert_data: dict, *, severity: str = '') -> bool:
    """Broadcast an alert to all alert subscribers (and optional severity group)."""
    ok = send_to_group('alerts', 'alert_message', alert_data, source='send_alert')
    if severity and severity.lower() in ('critical', 'high', 'medium', 'low'):
        send_to_group(
            f'alerts_{severity.lower()}',
            'alert_message',
            alert_data,
            source='send_alert',
            log=False,  # Already logged above
        )
    return ok


# ---------------------------------------------------------------------------
# Surveillance
# ---------------------------------------------------------------------------

def send_surveillance_update(data: dict) -> bool:
    return send_to_group('surveillance', 'surveillance_update', data, source='send_surveillance_update')


def send_surveillance_location_update(location_id: str | int, data: dict) -> bool:
    return send_to_group(
        f'surveillance_location_{location_id}',
        'surveillance_update',
        data,
        source='send_surveillance_location_update',
    )


def send_hotspot_update(data: dict) -> bool:
    return send_to_group('surveillance', 'hotspot_update', data, source='send_hotspot_update')


def send_anomaly_detected(data: dict) -> bool:
    return send_to_group('surveillance', 'anomaly_detected', data, source='send_anomaly_detected')


# ---------------------------------------------------------------------------
# Dashboard (per-user)
# ---------------------------------------------------------------------------

def send_dashboard_update(user_id: int, data: dict) -> bool:
    return send_to_group(
        f'dashboard_{user_id}',
        'dashboard_update',
        data,
        source='send_dashboard_update',
        target_user_id=user_id,
    )


def send_metric_update(user_id: int, metric_data: dict) -> bool:
    return send_to_group(
        f'dashboard_{user_id}',
        'metric_update',
        metric_data,
        source='send_metric_update',
        target_user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Notifications (per-user)
# ---------------------------------------------------------------------------

def send_notification_to_user(user_id: int, notification_data: dict) -> bool:
    return send_to_group(
        f'notifications_{user_id}',
        'notification',
        notification_data,
        source='send_notification_to_user',
        target_user_id=user_id,
    )


def notify_user_group(user_ids: list[int], notification_data: dict) -> None:
    """Send the same notification to multiple users."""
    for uid in user_ids:
        send_notification_to_user(uid, notification_data)


# ---------------------------------------------------------------------------
# Response coordination
# ---------------------------------------------------------------------------

def send_response_update(data: dict) -> bool:
    return send_to_group('response_coordination', 'response_update', data, source='send_response_update')


def send_escalation_alert(data: dict) -> bool:
    return send_to_group('response_coordination', 'escalation_alert', data, source='send_escalation_alert')


def send_deescalation_event(data: dict) -> bool:
    return send_to_group('response_coordination', 'deescalation_event', data, source='send_deescalation_event')


def send_response_activation_update(activation_id: str | int, data: dict) -> bool:
    return send_to_group(
        f'response_activation_{activation_id}',
        'response_update',
        data,
        source='send_response_activation_update',
    )


def send_action_item_update(data: dict) -> bool:
    return send_to_group('response_coordination', 'action_item_update', data, source='send_action_item_update')


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

def send_resource_update(data: dict) -> bool:
    return send_to_group('resources', 'resource_update', data, source='send_resource_update')


def send_capacity_alert(data: dict) -> bool:
    return send_to_group('resources', 'capacity_alert', data, source='send_capacity_alert')


def send_allocation_update(data: dict) -> bool:
    return send_to_group('resources', 'allocation_update', data, source='send_allocation_update')


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def send_case_update(data: dict) -> bool:
    return send_to_group('operations', 'case_update', data, source='send_case_update')


def send_contact_tracing_update(data: dict) -> bool:
    return send_to_group('operations', 'contact_tracing_update', data, source='send_contact_tracing_update')


def send_quarantine_update(data: dict) -> bool:
    return send_to_group('operations', 'quarantine_update', data, source='send_quarantine_update')


# ---------------------------------------------------------------------------
# System status (admin)
# ---------------------------------------------------------------------------

def send_system_status(data: dict) -> bool:
    return send_to_group('system_status', 'system_status_update', data, source='send_system_status')


def send_health_check(data: dict) -> bool:
    return send_to_group('system_status', 'health_check_update', data, source='send_health_check')


def send_celery_worker_update(data: dict) -> bool:
    return send_to_group('system_status', 'celery_worker_update', data, source='send_celery_worker_update')


# ---------------------------------------------------------------------------
# Broadcast to all operational groups
# ---------------------------------------------------------------------------

def broadcast_to_all(message_type: str, data: dict) -> None:
    """
    Broadcast to all operational groups.
    Used for system-wide announcements (maintenance, emergency shutdown, etc.).
    """
    groups = [
        'alerts',
        'surveillance',
        'response_coordination',
        'resources',
        'operations',
    ]
    for grp in groups:
        send_to_group(grp, message_type, data, source='broadcast_to_all', log=False)

    # Single audit log entry for the whole broadcast
    _log_broadcast(
        group_name='<broadcast_all>',
        message_type=message_type,
        data=data,
        source='broadcast_to_all',
    )


# ---------------------------------------------------------------------------
# Presence helpers
# ---------------------------------------------------------------------------

def get_presence_count(group_name: str) -> int:
    """Return how many users are currently connected to *group_name*."""
    from websockets.models import RoomPresence
    return RoomPresence.objects.filter(group__name=group_name).count()


def get_online_users(group_name: str) -> list[int]:
    """Return a list of user PKs currently connected to *group_name*."""
    from websockets.models import RoomPresence
    return list(
        RoomPresence.objects.filter(group__name=group_name)
        .values_list('user_id', flat=True)
        .distinct()
    )


# ---------------------------------------------------------------------------
# Replay helpers
# ---------------------------------------------------------------------------

def replay_missed_messages(user_id: int, group_name: str, since_iso: str) -> int:
    """
    Re-send BroadcastMessage rows for *group_name* created after *since_iso*
    directly to the user's notification group.

    Returns the number of messages replayed.
    """
    from django.utils.dateparse import parse_datetime
    from websockets.models import BroadcastMessage

    since = parse_datetime(since_iso)
    if not since:
        return 0

    messages = BroadcastMessage.objects.filter(
        group__name=group_name,
        delivery_status=BroadcastMessage.DeliveryStatus.SENT,
        created_at__gt=since,
        is_deleted=False,
    ).order_by('created_at')

    count = 0
    for msg in messages:
        send_notification_to_user(user_id, {
            'replayed': True,
            'original_type': msg.message_type,
            'original_at': msg.created_at.isoformat(),
            **msg.payload,
        })
        count += 1
    return count


# ---------------------------------------------------------------------------
# Private DB helpers (called synchronously from within this module)
# ---------------------------------------------------------------------------

def _log_broadcast(
    group_name: str,
    message_type: str,
    data: dict,
    source: str = '',
    target_user_id: int | None = None,
) -> str | None:
    """
    Write a BroadcastMessage row.  Returns the PK string on success, None on failure.
    """
    try:
        from websockets.models import BroadcastMessage, ChannelGroup
        group = ChannelGroup.objects.filter(name=group_name, is_deleted=False).first()
        target_user = None
        if target_user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = User.objects.filter(pk=target_user_id).first()

        msg = BroadcastMessage.objects.create(
            group=group,
            target_user=target_user,
            message_type=message_type,
            payload=data,
            source=source,
            delivery_status=BroadcastMessage.DeliveryStatus.PENDING,
        )
        return str(msg.pk)
    except Exception as exc:
        logger.error('_log_broadcast error: %s', exc)
        return None


def _mark_broadcast_sent(broadcast_id: str, recipient_count: int = 0) -> None:
    try:
        from websockets.models import BroadcastMessage
        BroadcastMessage.objects.filter(pk=broadcast_id).update(
            delivery_status=BroadcastMessage.DeliveryStatus.SENT,
            recipient_count=recipient_count,
        )
    except Exception as exc:
        logger.error('_mark_broadcast_sent error: %s', exc)


def _mark_broadcast_failed(broadcast_id: str) -> None:
    try:
        from websockets.models import BroadcastMessage
        BroadcastMessage.objects.filter(pk=broadcast_id).update(
            delivery_status=BroadcastMessage.DeliveryStatus.FAILED,
        )
    except Exception as exc:
        logger.error('_mark_broadcast_failed error: %s', exc)


# ---------------------------------------------------------------------------
# Context manager helper
# ---------------------------------------------------------------------------

class WebSocketNotifier:
    """
    Context manager that sends a WebSocket message on clean exit.

    Usage::

        with WebSocketNotifier('response_coordination', 'response_update') as n:
            n.update_data(activation_id=str(activation.pk), status='escalated')
            # … do other work …
        # message sent here on __exit__ (only if no exception)
    """

    def __init__(self, group_name: str, message_type: str, source: str = ''):
        self.group_name   = group_name
        self.message_type = message_type
        self.source       = source
        self._data: dict  = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            send_to_group(self.group_name, self.message_type, self._data, source=self.source)

    def set_data(self, data: dict):
        self._data = data

    def update_data(self, **kwargs):
        self._data.update(kwargs)