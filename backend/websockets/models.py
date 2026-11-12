"""
WebSocket models for OryxShield.

Models:
  - ChannelGroup     : Named broadcast groups with membership / access rules
  - WebSocketConnection : Immutable log of connect / disconnect events
  - BroadcastMessage : Outbound message log for audit and replay
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import TimeStampedModel

User = get_user_model()


# ---------------------------------------------------------------------------
# ChannelGroup
# ---------------------------------------------------------------------------

class ChannelGroup(TimeStampedModel):
    """
    Named channel-layer group.  Consumers add/remove themselves; the model
    keeps the authoritative list of rules so we can enforce access and replay
    missed messages on reconnect.
    """

    class AccessPolicy(models.TextChoices):
        PUBLIC = 'public', 'Public'          # Any authenticated user
        ROLE   = 'role',   'Role-restricted' # Users whose role is in allowed_roles
        USER   = 'user',   'User-restricted' # Explicit membership list
        STAFF  = 'staff',  'Staff only'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=128, unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    description  = models.TextField(blank=True)
    access_policy = models.CharField(
        max_length=16,
        choices=AccessPolicy.choices,
        default=AccessPolicy.PUBLIC,
    )
    # Comma-separated role names for ROLE policy, e.g. "admin,coordinator"
    allowed_roles = models.CharField(max_length=512, blank=True)
    # Explicit member list for USER policy
    members       = models.ManyToManyField(User, blank=True, related_name='channel_group_memberships')
    is_persistent = models.BooleanField(
        default=True,
        help_text='Persistent groups survive server restarts; ephemeral groups are re-created on demand.',
    )
    is_deleted    = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'is_deleted']),
        ]

    def __str__(self):
        return self.display_name or self.name

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])

    def can_access(self, user) -> bool:
        """Return True if *user* is allowed to join this group."""
        if not user or not user.is_authenticated:
            return False
        if self.is_deleted:
            return False
        policy = self.access_policy
        if policy == self.AccessPolicy.PUBLIC:
            return True
        if policy == self.AccessPolicy.STAFF:
            return user.is_staff
        if policy == self.AccessPolicy.ROLE:
            allowed = [r.strip() for r in self.allowed_roles.split(',') if r.strip()]
            user_roles = list(
                user.groups.values_list('name', flat=True)
            )
            return bool(set(allowed) & set(user_roles))
        if policy == self.AccessPolicy.USER:
            return self.members.filter(pk=user.pk).exists()
        return False


# ---------------------------------------------------------------------------
# WebSocketConnection  (immutable connection log)
# ---------------------------------------------------------------------------

class WebSocketConnection(models.Model):
    """
    Immutable log entry created on every connect and disconnect.
    Never updated after creation.
    """

    class EventType(models.TextChoices):
        CONNECT    = 'connect',    'Connect'
        DISCONNECT = 'disconnect', 'Disconnect'
        AUTH_FAIL  = 'auth_fail',  'Auth Failure'
        DENIED     = 'denied',     'Access Denied'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user         = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ws_connections',
    )
    channel_name = models.CharField(max_length=255)
    group        = models.ForeignKey(
        ChannelGroup,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='connection_logs',
    )
    event_type   = models.CharField(max_length=16, choices=EventType.choices)
    timestamp    = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.TextField(blank=True)
    close_code   = models.IntegerField(null=True, blank=True)
    metadata     = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['group', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp']),
        ]

    def __str__(self):
        user_label = self.user.username if self.user else 'anon'
        return f'{self.event_type} | {user_label} | {self.timestamp:%Y-%m-%d %H:%M:%S}'

    # Immutable — no save() override needed; just never call save() with update_fields
    def save(self, *args, **kwargs):
        if self.pk and WebSocketConnection.objects.filter(pk=self.pk).exists():
            raise ValueError('WebSocketConnection records are immutable.')
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# BroadcastMessage  (outbound message log)
# ---------------------------------------------------------------------------

class BroadcastMessage(TimeStampedModel):
    """
    Outbound message log.  Every message sent to a channel group is recorded
    here for audit purposes and to enable replay on reconnect.
    """

    class MessageType(models.TextChoices):
        ALERT                  = 'alert',                  'Alert'
        SURVEILLANCE_UPDATE    = 'surveillance_update',    'Surveillance Update'
        DASHBOARD_UPDATE       = 'dashboard_update',       'Dashboard Update'
        METRIC_UPDATE          = 'metric_update',          'Metric Update'
        NOTIFICATION           = 'notification',           'Notification'
        RESPONSE_UPDATE        = 'response_update',        'Response Update'
        ESCALATION_ALERT       = 'escalation_alert',       'Escalation Alert'
        RESOURCE_UPDATE        = 'resource_update',        'Resource Update'
        CAPACITY_ALERT         = 'capacity_alert',         'Capacity Alert'
        CASE_UPDATE            = 'case_update',            'Case Update'
        CONTACT_TRACING_UPDATE = 'contact_tracing_update', 'Contact Tracing Update'
        SYSTEM_STATUS          = 'system_status_update',   'System Status'
        HEALTH_CHECK           = 'health_check_update',    'Health Check'
        CUSTOM                 = 'custom',                 'Custom'

    class DeliveryStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        SENT      = 'sent',      'Sent'
        FAILED    = 'failed',    'Failed'
        REPLAYED  = 'replayed',  'Replayed'

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group          = models.ForeignKey(
        ChannelGroup,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='broadcast_messages',
    )
    # For user-targeted messages (NotificationConsumer / DashboardConsumer)
    target_user    = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='targeted_ws_messages',
    )
    message_type   = models.CharField(max_length=64, choices=MessageType.choices)
    payload        = models.JSONField(default=dict)
    delivery_status = models.CharField(
        max_length=16,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
    )
    sent_at        = models.DateTimeField(null=True, blank=True)
    # Originating source (e.g. 'risk_assessment.tasks.run_alert_engine')
    source         = models.CharField(max_length=255, blank=True)
    # Number of recipients at send time (best-effort)
    recipient_count = models.PositiveIntegerField(default=0)
    is_deleted     = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'delivery_status']),
            models.Index(fields=['target_user', 'delivery_status']),
            models.Index(fields=['message_type', 'created_at']),
        ]

    def __str__(self):
        target = self.group.name if self.group else f'user:{self.target_user_id}'
        return f'{self.message_type} → {target} [{self.delivery_status}]'

    def mark_sent(self, recipient_count: int = 0):
        self.delivery_status = self.DeliveryStatus.SENT
        self.sent_at = timezone.now()
        self.recipient_count = recipient_count
        self.save(update_fields=['delivery_status', 'sent_at', 'recipient_count', 'updated_at'])

    def mark_failed(self):
        self.delivery_status = self.DeliveryStatus.FAILED
        self.save(update_fields=['delivery_status', 'updated_at'])

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])


# ---------------------------------------------------------------------------
# RoomPresence  (in-memory state mirrored to DB for observability)
# ---------------------------------------------------------------------------

class RoomPresence(models.Model):
    """
    Tracks which users are currently connected to a given ChannelGroup.
    Rows are upserted on connect and deleted on disconnect.
    This table should be treated as ephemeral — it may be stale after a
    server restart.  Use for UI presence indicators only.
    """

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group        = models.ForeignKey(
        ChannelGroup,
        on_delete=models.CASCADE,
        related_name='presence_entries',
    )
    user         = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='room_presences',
    )
    channel_name = models.CharField(max_length=255, unique=True)
    connected_at = models.DateTimeField(default=timezone.now)
    last_seen    = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('group', 'user', 'channel_name')]
        ordering = ['group', 'user']
        indexes = [
            models.Index(fields=['group', 'user']),
        ]

    def __str__(self):
        return f'{self.user.username} in {self.group.name}'

    def touch(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])