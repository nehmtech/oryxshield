"""
Signal handlers for response app.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ResponseActivation, ActionItem

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ResponseActivation)
def response_activated_handler(sender, instance, created, **kwargs):
    """
    On new ResponseActivation:
      - Broadcast WebSocket notification.
      - Generate action items if a protocol is attached.
      - Notify the incident commander.
    """
    if not created:
        return

    logger.info("Signal: ResponseActivation created – %s", instance.activation_code)

    # WebSocket broadcast
    try:
        from websockets.utils import send_response_update

        send_response_update(
            {
                "type": "activation",
                "activation_code": instance.activation_code,
                "level": instance.response_level.level,
                "location": instance.location.name,
                "disease": instance.disease_name,
                "status": instance.status,
            }
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed for %s: %s", instance.activation_code, exc)

    # Generate action items from protocol
    if instance.protocol_id:
        try:
            from .decision_support import generate_action_items_from_protocol

            generate_action_items_from_protocol(instance.protocol, instance)
        except Exception as exc:
            logger.error(
                "Action item generation failed for %s: %s",
                instance.activation_code,
                exc,
            )

    # Notify incident commander
    if instance.incident_commander_id:
        try:
            from core.models import Notification

            Notification.objects.create(
                user=instance.incident_commander,
                title=f"Response Activated: {instance.activation_code}",
                message=(
                    f"You have been assigned as Incident Commander for "
                    f"{instance.activation_code} (Level {instance.response_level.level}) "
                    f"at {instance.location.name}."
                ),
                notification_type="ALERT",
                metadata={
                    "response_activation_id": str(instance.id),
                    "level": instance.response_level.level,
                },
            )
        except Exception as exc:
            logger.error(
                "Incident commander notification failed for %s: %s",
                instance.activation_code,
                exc,
            )


@receiver(post_save, sender=ActionItem)
def action_item_assigned_handler(sender, instance, created, **kwargs):
    """
    Notify the assignee when an ActionItem is first created with an assignment.
    """
    if not created:
        return
    if not instance.assigned_to_id:
        return

    try:
        from core.models import Notification

        Notification.objects.create(
            user=instance.assigned_to,
            title=f"Action Assigned: {instance.title}",
            message=(
                f"You have been assigned action: '{instance.title}'. "
                f"Priority: {instance.priority}. "
                f"Due: {instance.due_date.strftime('%Y-%m-%d %H:%M') if instance.due_date else 'TBD'}."
            ),
            notification_type="INFO",
            metadata={
                "action_item_id": str(instance.id),
                "response_activation_id": str(instance.response_activation_id),
                "priority": instance.priority,
            },
        )
    except Exception as exc:
        logger.error(
            "Action assignment notification failed for action %s: %s",
            instance.id,
            exc,
        )


@receiver(post_save, sender=ActionItem)
def action_completed_handler(sender, instance, created, update_fields, **kwargs):
    """
    When an ActionItem is marked COMPLETED, trigger an async progress
    recalculation for the parent response activation.
    """
    if created:
        return

    # Only react when status is explicitly updated
    if update_fields is None or "status" not in update_fields:
        return

    if instance.status != "COMPLETED":
        return

    logger.debug("Signal: ActionItem %s completed — triggering progress update", instance.id)

    try:
        from .tasks import update_response_progress

        update_response_progress.delay(activation_id=str(instance.response_activation_id))
    except Exception as exc:
        logger.error(
            "Progress update task dispatch failed for activation %s: %s",
            instance.response_activation_id,
            exc,
        )