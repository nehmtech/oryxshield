"""
Signal handlers for coordination app — OryxShield.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Task, Meeting, TeamMembership

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Task)
def task_created_handler(sender, instance, created, **kwargs):
    """Notify the assigned user when a new task is created."""
    if not created:
        return
    if not instance.assigned_to_user:
        return

    try:
        from core.models import Notification
        Notification.objects.create(
            user=instance.assigned_to_user,
            title=f"New Task Assigned: {instance.title}",
            message=(
                f"You have been assigned a [{instance.get_priority_display()}] priority task: "
                f"'{instance.title}'. Due: {instance.due_date:%Y-%m-%d %H:%M} UTC."
            ),
            notification_type='INFO',
        )
    except Exception:
        logger.exception("task_created_handler: failed to create notification for task %s", instance.id)


@receiver(pre_save, sender=Task)
def task_status_change_handler(sender, instance, **kwargs):
    """
    Track IN_PROGRESS start time and COMPLETED completion time
    when status changes are applied directly (not via model methods).
    """
    if not instance.pk:
        return  # new instance — handled by post_save

    try:
        previous = Task.objects.get(pk=instance.pk)
    except Task.DoesNotExist:
        return

    if previous.status != instance.status:
        now = timezone.now()
        if instance.status == Task.Status.IN_PROGRESS and not instance.started_at:
            instance.started_at = now
        if instance.status == Task.Status.COMPLETED and not instance.completed_at:
            instance.completed_at = now
            instance.progress_percentage = 100


@receiver(post_save, sender=Meeting)
def meeting_created_handler(sender, instance, created, **kwargs):
    """Dispatch meeting invitations asynchronously when a meeting is created."""
    if not created:
        return

    try:
        from .tasks import send_meeting_invitations
        send_meeting_invitations.delay(str(instance.id))
    except Exception:
        logger.exception("meeting_created_handler: failed to queue invitations for meeting %s", instance.id)


@receiver(post_save, sender=TeamMembership)
def team_membership_handler(sender, instance, created, **kwargs):
    """Notify new team members when they are added to a coordination team."""
    if not created:
        return
    if not instance.primary_representative:
        return

    try:
        from core.models import Notification
        Notification.objects.create(
            user=instance.primary_representative,
            title=f"Added to Coordination Team: {instance.team.name}",
            message=(
                f"Your agency ({instance.agency.acronym}) has been added to "
                f"coordination team '{instance.team.name}' [{instance.team.code}] "
                f"with role: {instance.get_role_display()}."
            ),
            notification_type='INFO',
        )
    except Exception:
        logger.exception(
            "team_membership_handler: failed to notify representative for membership %s", instance.id
        )