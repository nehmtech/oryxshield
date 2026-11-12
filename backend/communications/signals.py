"""
Signal handlers for communications app.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Broadcast, Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def on_message_delivered(sender, instance, created, **kwargs):
    """
    When a Message transitions to DELIVERED, increment the parent Broadcast's
    delivered counter (if the message belongs to a broadcast via campaign).
    Uses F() expression to avoid race conditions.
    """
    if created or instance.status != 'DELIVERED':
        return

    # Messages can belong to a broadcast indirectly through campaign;
    # a direct broadcast FK may exist in extended implementations.
    # Here we check via metadata for a broadcast_id hint.
    broadcast_id = instance.metadata.get('broadcast_id')
    if not broadcast_id:
        return

    try:
        from django.db.models import F
        Broadcast.objects.filter(id=broadcast_id, is_deleted=False).update(
            messages_delivered=F('messages_delivered') + 1,
            updated_at=timezone.now(),
        )
    except Exception as exc:
        logger.error("Failed to update broadcast delivery count: %s", exc)


@receiver(post_save, sender=Broadcast)
def on_broadcast_approved(sender, instance, created, **kwargs):
    """
    When a Broadcast is approved (status APPROVED), immediately queue
    for sending if no scheduled_for time is set or if it is in the past.
    """
    if created:
        return
    if instance.status != 'APPROVED':
        return
    if instance.scheduled_for and instance.scheduled_for > timezone.now():
        return  # Will be triggered by the scheduled_for eta in Celery

    try:
        from .tasks import process_broadcast
        process_broadcast.delay(str(instance.id))
        logger.info("Broadcast %s queued for immediate send", instance.id)
    except Exception as exc:
        logger.error("Failed to queue broadcast %s: %s", instance.id, exc)