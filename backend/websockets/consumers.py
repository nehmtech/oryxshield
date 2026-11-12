"""
WebSocket consumers for OryxShield.

All consumers:
  - Reject unauthenticated connections (close 4401).
  - Log connects / disconnects to WebSocketConnection (immutable).
  - Maintain RoomPresence rows for each group.
  - Log all inbound messages to BroadcastMessage when appropriate.
  - Route typed inbound messages to handle_<type> methods.

Consumers
---------
  AlertConsumer          – real-time risk alerts  (group: alerts, alerts:<severity>)
  SurveillanceConsumer   – live case / hotspot feed (group: surveillance, surveillance:<location_id>)
  DashboardConsumer      – aggregated live stats, per-user  (group: dashboard_<user_id>)
  NotificationConsumer   – per-user notifications  (group: notifications_<user_id>)
  ResponseConsumer       – response activation events  (group: response_coordination)
  ResourceConsumer       – resource updates / capacity alerts (group: resources)
  OperationsConsumer     – contact tracing / quarantine events (group: operations)
  SystemStatusConsumer   – system health (staff only)  (group: system_status)
"""

import json
import logging
import uuid
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BaseConsumer
# ---------------------------------------------------------------------------

class BaseConsumer(AsyncWebsocketConsumer):
    """
    Shared base with:
      - Auth guard (4401)
      - Group join / leave
      - Immutable WebSocketConnection log
      - RoomPresence upsert / cleanup
      - Typed message dispatch via handle_<type>()
      - send_message / send_error helpers
    """

    # Subclasses set this (or override connect() to set self.group_name dynamically)
    group_name: str = ''

    # ---------- lifecycle --------------------------------------------------

    async def connect(self):
        self.user = self.scope['user']

        if not getattr(self.user, 'is_authenticated', False):
            await self._log_connection('auth_fail')
            await self.close(code=4401)
            return

        # Access-control check against ChannelGroup model (if group is registered)
        if self.group_name:
            allowed = await self._check_group_access(self.group_name)
            if not allowed:
                await self._log_connection('denied')
                await self.close(code=4403)
                return

        if self.group_name:
            await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()
        await self._log_connection('connect')
        await self._upsert_presence(join=True)
        logger.info('WS connected: %s group=%s', self.user.username, self.group_name)

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        user = getattr(self, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            await self._log_connection('disconnect', close_code=close_code)
            await self._upsert_presence(join=False)

        logger.info(
            'WS disconnected: %s group=%s code=%s',
            getattr(self.user, 'username', 'unknown'),
            self.group_name,
            close_code,
        )

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        try:
            data: dict[str, Any] = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON payload.')
            return

        message_type: str = data.get('type', '')
        if not message_type:
            await self.send_error('Missing message type.')
            return

        handler = getattr(self, f'handle_{message_type}', None)
        if handler:
            try:
                await handler(data)
            except Exception as exc:
                logger.error(
                    'WS handler error type=%s user=%s err=%s',
                    message_type,
                    getattr(self.user, 'username', '?'),
                    exc,
                    exc_info=True,
                )
                await self.send_error('Internal server error.')
        else:
            await self.send_error(f'Unknown message type: {message_type}')

    # ---------- helpers ----------------------------------------------------

    async def send_message(self, data: dict):
        await self.send(text_data=json.dumps(data))

    async def send_error(self, message: str, code: str = 'error'):
        await self.send_message({'type': 'error', 'code': code, 'message': message})

    # ---------- DB helpers -------------------------------------------------

    @database_sync_to_async
    def _log_connection(self, event_type: str, close_code: int | None = None):
        from websockets.models import WebSocketConnection, ChannelGroup
        group = None
        if self.group_name:
            group = ChannelGroup.objects.filter(name=self.group_name, is_deleted=False).first()

        headers = dict(self.scope.get('headers', []))
        ip = headers.get(b'x-forwarded-for', b'').decode().split(',')[0].strip() \
            or (self.scope.get('client') or [''])[0]
        user_agent = headers.get(b'user-agent', b'').decode()

        WebSocketConnection.objects.create(
            user=self.user if getattr(self.user, 'is_authenticated', False) else None,
            channel_name=self.channel_name,
            group=group,
            event_type=event_type,
            ip_address=ip or None,
            user_agent=user_agent,
            close_code=close_code,
        )

    @database_sync_to_async
    def _check_group_access(self, group_name: str) -> bool:
        from websockets.models import ChannelGroup
        group = ChannelGroup.objects.filter(name=group_name, is_deleted=False).first()
        if group is None:
            # Group not registered — allow by default (open group)
            return True
        return group.can_access(self.user)

    @database_sync_to_async
    def _upsert_presence(self, join: bool):
        from websockets.models import ChannelGroup, RoomPresence
        if not self.group_name:
            return
        group = ChannelGroup.objects.filter(name=self.group_name, is_deleted=False).first()
        if group is None:
            return
        if join:
            RoomPresence.objects.update_or_create(
                channel_name=self.channel_name,
                defaults={
                    'group': group,
                    'user': self.user,
                    'connected_at': timezone.now(),
                    'last_seen': timezone.now(),
                },
            )
        else:
            RoomPresence.objects.filter(channel_name=self.channel_name).delete()

    @database_sync_to_async
    def _get_presence_count(self, group_name: str) -> int:
        from websockets.models import RoomPresence
        return RoomPresence.objects.filter(group__name=group_name).count()


# ---------------------------------------------------------------------------
# AlertConsumer
# ---------------------------------------------------------------------------

class AlertConsumer(BaseConsumer):
    """
    Real-time risk alert feed.

    Groups:
      alerts            – all alerts
      alerts:<severity> – filtered by severity (critical / high / medium / low)

    Inbound:
      subscribe_severity  { severity: str }
      unsubscribe_severity { severity: str }
      ping
    """

    group_name = 'alerts'

    async def connect(self):
        self._severity_groups: list[str] = []
        await super().connect()

    async def disconnect(self, close_code):
        # Leave all severity sub-groups
        for grp in self._severity_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
        await super().disconnect(close_code)

    # ---------- inbound handlers ------------------------------------------

    async def handle_subscribe_severity(self, data: dict):
        severity = data.get('severity', '').lower()
        if severity not in ('critical', 'high', 'medium', 'low'):
            await self.send_error('Invalid severity level.', code='invalid_severity')
            return
        grp = f'alerts_{severity}'
        if grp not in self._severity_groups:
            await self.channel_layer.group_add(grp, self.channel_name)
            self._severity_groups.append(grp)
        await self.send_message({'type': 'subscribed', 'severity': severity})

    async def handle_unsubscribe_severity(self, data: dict):
        severity = data.get('severity', '').lower()
        grp = f'alerts_{severity}'
        if grp in self._severity_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
            self._severity_groups.remove(grp)
        await self.send_message({'type': 'unsubscribed', 'severity': severity})

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def alert_message(self, event: dict):
        await self.send_message({'type': 'alert', 'data': event['data']})


# ---------------------------------------------------------------------------
# SurveillanceConsumer
# ---------------------------------------------------------------------------

class SurveillanceConsumer(BaseConsumer):
    """
    Live case / hotspot feed.

    Groups:
      surveillance                      – all updates
      surveillance_location_<id>        – per-location filter

    Inbound:
      subscribe_location   { location_id: str }
      unsubscribe_location { location_id: str }
      ping
    """

    group_name = 'surveillance'

    async def connect(self):
        self._location_groups: list[str] = []
        await super().connect()

    async def disconnect(self, close_code):
        for grp in self._location_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
        await super().disconnect(close_code)

    # ---------- inbound handlers ------------------------------------------

    async def handle_subscribe_location(self, data: dict):
        location_id = str(data.get('location_id', '')).strip()
        if not location_id:
            await self.send_error('location_id required.')
            return
        grp = f'surveillance_location_{location_id}'
        if grp not in self._location_groups:
            await self.channel_layer.group_add(grp, self.channel_name)
            self._location_groups.append(grp)
        await self.send_message({'type': 'subscribed_location', 'location_id': location_id})

    async def handle_unsubscribe_location(self, data: dict):
        location_id = str(data.get('location_id', '')).strip()
        grp = f'surveillance_location_{location_id}'
        if grp in self._location_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
            self._location_groups.remove(grp)
        await self.send_message({'type': 'unsubscribed_location', 'location_id': location_id})

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def surveillance_update(self, event: dict):
        await self.send_message({'type': 'surveillance_update', 'data': event['data']})

    async def hotspot_update(self, event: dict):
        await self.send_message({'type': 'hotspot_update', 'data': event['data']})

    async def anomaly_detected(self, event: dict):
        await self.send_message({'type': 'anomaly_detected', 'data': event['data']})


# ---------------------------------------------------------------------------
# DashboardConsumer
# ---------------------------------------------------------------------------

class DashboardConsumer(BaseConsumer):
    """
    Aggregated live stats, scoped per-user.

    Groups:
      dashboard_<user_id>

    Inbound:
      request_snapshot – triggers an immediate snapshot push
      ping
    """

    async def connect(self):
        self.group_name = f'dashboard_{self.scope["user"].id}'
        await super().connect()

    # ---------- inbound handlers ------------------------------------------

    async def handle_request_snapshot(self, data: dict):
        """Push the latest dashboard snapshot on demand."""
        snapshot = await self._build_snapshot()
        await self.send_message({'type': 'dashboard_snapshot', 'data': snapshot})

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def dashboard_update(self, event: dict):
        await self.send_message({'type': 'dashboard_update', 'data': event['data']})

    async def metric_update(self, event: dict):
        await self.send_message({'type': 'metric_update', 'data': event['data']})

    # ---------- DB helpers ------------------------------------------------

    @database_sync_to_async
    def _build_snapshot(self) -> dict:
        """Return a lightweight aggregated snapshot for the connected user."""
        from core.models import Notification
        from risk_assessment.models import Alert as RiskAlert

        unread_notifs = Notification.objects.filter(
            user=self.user,
            is_read=False,
            is_deleted=False,
        ).count()

        active_alerts = RiskAlert.objects.filter(
            status='open',
            is_deleted=False,
        ).count()

        return {
            'unread_notifications': unread_notifs,
            'active_alerts': active_alerts,
            'snapshot_at': timezone.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# NotificationConsumer
# ---------------------------------------------------------------------------

class NotificationConsumer(BaseConsumer):
    """
    Per-user notification stream.

    Groups:
      notifications_<user_id>

    Inbound:
      mark_read  { notification_id: str }
      mark_all_read
      ping
    """

    async def connect(self):
        self.group_name = f'notifications_{self.scope["user"].id}'
        await super().connect()

    # ---------- inbound handlers ------------------------------------------

    async def handle_mark_read(self, data: dict):
        notification_id = data.get('notification_id')
        if not notification_id:
            await self.send_error('notification_id required.')
            return
        success = await self._mark_read(notification_id)
        if success:
            await self.send_message({'type': 'notification_marked_read', 'notification_id': notification_id})
        else:
            await self.send_error('Notification not found.', code='not_found')

    async def handle_mark_all_read(self, data: dict):
        count = await self._mark_all_read()
        await self.send_message({'type': 'all_notifications_read', 'count': count})

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def notification(self, event: dict):
        await self.send_message({'type': 'notification', 'data': event['data']})

    # ---------- DB helpers ------------------------------------------------

    @database_sync_to_async
    def _mark_read(self, notification_id: str) -> bool:
        from core.models import Notification
        updated = Notification.objects.filter(
            pk=notification_id,
            user=self.user,
            is_deleted=False,
        ).update(is_read=True, read_at=timezone.now())
        return updated > 0

    @database_sync_to_async
    def _mark_all_read(self) -> int:
        from core.models import Notification
        return Notification.objects.filter(
            user=self.user,
            is_read=False,
            is_deleted=False,
        ).update(is_read=True, read_at=timezone.now())


# ---------------------------------------------------------------------------
# ResponseConsumer
# ---------------------------------------------------------------------------

class ResponseConsumer(BaseConsumer):
    """
    Response activation / escalation events.

    Groups:
      response_coordination
      response_activation_<activation_id>

    Inbound:
      subscribe_activation   { activation_id: str }
      unsubscribe_activation { activation_id: str }
      ping
    """

    group_name = 'response_coordination'

    async def connect(self):
        self._activation_groups: list[str] = []
        await super().connect()

    async def disconnect(self, close_code):
        for grp in self._activation_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
        await super().disconnect(close_code)

    # ---------- inbound handlers ------------------------------------------

    async def handle_subscribe_activation(self, data: dict):
        activation_id = str(data.get('activation_id', '')).strip()
        if not activation_id:
            await self.send_error('activation_id required.')
            return
        grp = f'response_activation_{activation_id}'
        if grp not in self._activation_groups:
            await self.channel_layer.group_add(grp, self.channel_name)
            self._activation_groups.append(grp)
        await self.send_message({'type': 'subscribed_activation', 'activation_id': activation_id})

    async def handle_unsubscribe_activation(self, data: dict):
        activation_id = str(data.get('activation_id', '')).strip()
        grp = f'response_activation_{activation_id}'
        if grp in self._activation_groups:
            await self.channel_layer.group_discard(grp, self.channel_name)
            self._activation_groups.remove(grp)
        await self.send_message({'type': 'unsubscribed_activation', 'activation_id': activation_id})

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def response_update(self, event: dict):
        await self.send_message({'type': 'response_update', 'data': event['data']})

    async def escalation_alert(self, event: dict):
        await self.send_message({'type': 'escalation_alert', 'data': event['data']})

    async def deescalation_event(self, event: dict):
        await self.send_message({'type': 'deescalation_event', 'data': event['data']})

    async def action_item_update(self, event: dict):
        await self.send_message({'type': 'action_item_update', 'data': event['data']})


# ---------------------------------------------------------------------------
# ResourceConsumer
# ---------------------------------------------------------------------------

class ResourceConsumer(BaseConsumer):
    """
    Resource management updates and capacity alerts.

    Group: resources
    """

    group_name = 'resources'

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def resource_update(self, event: dict):
        await self.send_message({'type': 'resource_update', 'data': event['data']})

    async def capacity_alert(self, event: dict):
        await self.send_message({'type': 'capacity_alert', 'data': event['data']})

    async def allocation_update(self, event: dict):
        await self.send_message({'type': 'allocation_update', 'data': event['data']})


# ---------------------------------------------------------------------------
# OperationsConsumer
# ---------------------------------------------------------------------------

class OperationsConsumer(BaseConsumer):
    """
    Contact tracing, quarantine, and case management events.

    Group: operations
    """

    group_name = 'operations'

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def case_update(self, event: dict):
        await self.send_message({'type': 'case_update', 'data': event['data']})

    async def contact_tracing_update(self, event: dict):
        await self.send_message({'type': 'contact_tracing_update', 'data': event['data']})

    async def quarantine_update(self, event: dict):
        await self.send_message({'type': 'quarantine_update', 'data': event['data']})


# ---------------------------------------------------------------------------
# SystemStatusConsumer  (staff only)
# ---------------------------------------------------------------------------

class SystemStatusConsumer(BaseConsumer):
    """
    System health monitoring.  Only staff users may connect.

    Group: system_status
    """

    group_name = 'system_status'

    async def connect(self):
        user = self.scope.get('user')
        if not getattr(user, 'is_staff', False):
            await self.close(code=4403)
            return
        await super().connect()

    async def handle_ping(self, data: dict):
        await self.send_message({'type': 'pong', 'ts': timezone.now().isoformat()})

    # ---------- channel-layer handlers ------------------------------------

    async def system_status_update(self, event: dict):
        await self.send_message({'type': 'system_status', 'data': event['data']})

    async def health_check_update(self, event: dict):
        await self.send_message({'type': 'health_check', 'data': event['data']})

    async def celery_worker_update(self, event: dict):
        await self.send_message({'type': 'celery_worker', 'data': event['data']})