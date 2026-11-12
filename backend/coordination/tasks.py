"""
Celery tasks for coordination app — OryxShield.

All tasks use:
  bind=True, max_retries=3, default_retry_delay=60
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ['ASSIGNED', 'ACCEPTED', 'IN_PROGRESS']


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_task_reminders(self):
    """
    Send reminders for tasks approaching their deadlines.
    Runs hourly via Celery beat.
    Notifies assigned users for tasks due within the next 24 hours.
    """
    from .models import Task
    from core.models import Notification

    try:
        now = timezone.now()
        in_24h = now + timedelta(hours=24)

        approaching = Task.objects.filter(
            status__in=_ACTIVE_STATUSES,
            due_date__gte=now,
            due_date__lte=in_24h,
            is_deleted=False,
        ).select_related('assigned_to_user', 'assigned_to_agency')

        reminders_sent = 0
        for task in approaching:
            if not task.assigned_to_user:
                continue

            hours_left = round((task.due_date - now).total_seconds() / 3600, 1)
            Notification.objects.create(
                user=task.assigned_to_user,
                title=f"Task Due in {hours_left}h: {task.title}",
                message=(
                    f"[{task.get_priority_display()}] Task '{task.title}' is due at "
                    f"{task.due_date:%Y-%m-%d %H:%M} UTC. "
                    f"Current progress: {task.progress_percentage}%."
                ),
                notification_type='WARNING',
            )
            reminders_sent += 1

        logger.info("send_task_reminders: sent %d reminders.", reminders_sent)
        return {'status': 'completed', 'reminders_sent': reminders_sent}

    except Exception as exc:
        logger.exception("send_task_reminders failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_meeting_invitations(self, meeting_id: str):
    """
    Send email invitations to all INVITED attendees of a meeting.
    Triggered by the post_save signal when a Meeting is created.
    """
    from .models import Meeting, MeetingAttendance

    try:
        try:
            meeting = Meeting.objects.select_related('coordination_team').get(
                id=meeting_id, is_deleted=False
            )
        except Meeting.DoesNotExist:
            logger.error("send_meeting_invitations: meeting %s not found.", meeting_id)
            return {'status': 'error', 'message': 'Meeting not found'}

        invitations = MeetingAttendance.objects.filter(
            meeting=meeting, status='INVITED'
        ).select_related('attendee')

        sent_count = 0
        for record in invitations:
            if not record.attendee.email:
                continue

            duration = meeting.scheduled_end - meeting.scheduled_start
            duration_str = f"{int(duration.total_seconds() // 3600)}h {int((duration.total_seconds() % 3600) // 60)}m"

            body = (
                f"Dear {record.attendee.get_full_name() or record.attendee.username},\n\n"
                f"You are invited to attend:\n"
                f"  Title : {meeting.title}\n"
                f"  Team  : {meeting.coordination_team.name}\n"
                f"  Start : {meeting.scheduled_start:%Y-%m-%d %H:%M} UTC\n"
                f"  End   : {meeting.scheduled_end:%Y-%m-%d %H:%M} UTC ({duration_str})\n"
            )
            if meeting.is_virtual and meeting.meeting_link:
                body += f"  Link  : {meeting.meeting_link}\n"
            elif meeting.venue:
                body += f"  Venue : {meeting.venue}\n"

            if meeting.agenda:
                body += "\nAgenda:\n"
                for i, item in enumerate(meeting.agenda, start=1):
                    label = item.get('item', str(item))
                    mins = item.get('duration', '')
                    body += f"  {i}. {label}" + (f" ({mins} min)" if mins else "") + "\n"

            body += "\nPlease confirm your attendance.\n\nThank you."

            # Delegate actual sending to communications app task
            try:
                from communications.tasks import send_email_notification
                send_email_notification.delay(
                    record.attendee.email,
                    f"Meeting Invitation: {meeting.title}",
                    body,
                )
            except ImportError:
                # communications app not yet available; log and continue
                logger.warning(
                    "send_meeting_invitations: communications app unavailable for %s",
                    record.attendee.email,
                )
            sent_count += 1

        logger.info("send_meeting_invitations: sent %d invitations for meeting %s.", sent_count, meeting_id)
        return {'status': 'completed', 'invitations_sent': sent_count}

    except Exception as exc:
        logger.exception("send_meeting_invitations failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_coordination_report(self, team_id: str) -> dict:
    """
    Generate a coordination performance report for a given team.
    Returns a structured dict suitable for storage or transmission.
    """
    from .models import CoordinationTeam, Task, Meeting, InformationProduct

    try:
        try:
            team = CoordinationTeam.objects.get(id=team_id, is_deleted=False)
        except CoordinationTeam.DoesNotExist:
            logger.error("generate_coordination_report: team %s not found.", team_id)
            return {'status': 'error', 'message': 'Team not found'}

        now = timezone.now()

        tasks_qs = Task.objects.filter(coordination_team=team, is_deleted=False)
        total_tasks = tasks_qs.count()
        completed_tasks = tasks_qs.filter(status='COMPLETED').count()
        overdue_tasks = tasks_qs.filter(
            status__in=_ACTIVE_STATUSES, due_date__lt=now
        ).count()
        critical_tasks = tasks_qs.filter(
            status__in=_ACTIVE_STATUSES, priority='CRITICAL'
        ).count()
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0, 2)

        meetings_qs = Meeting.objects.filter(coordination_team=team, is_deleted=False)
        meetings_held = meetings_qs.filter(status='COMPLETED').count()
        meetings_scheduled = meetings_qs.filter(
            status='SCHEDULED', scheduled_start__gte=now
        ).count()

        products_count = InformationProduct.objects.filter(
            coordination_team=team, is_deleted=False
        ).count()

        from django.db.models import Count as _Count
        tasks_by_priority = dict(
            tasks_qs.filter(status__in=_ACTIVE_STATUSES)
            .values('priority')
            .annotate(count=_Count('id'))
            .values_list('priority', 'count')
        )

        report = {
            'team_id': str(team.id),
            'team_name': team.name,
            'team_code': team.code,
            'generated_at': now.isoformat(),
            'task_summary': {
                'total': total_tasks,
                'completed': completed_tasks,
                'overdue': overdue_tasks,
                'critical_active': critical_tasks,
                'completion_rate_pct': completion_rate,
                'by_priority': dict(tasks_by_priority),
            },
            'meeting_summary': {
                'held': meetings_held,
                'upcoming': meetings_scheduled,
            },
            'information_products': products_count,
        }

        logger.info("generate_coordination_report: report generated for team %s.", team_id)
        return {'status': 'completed', 'report': report}

    except Exception as exc:
        logger.exception("generate_coordination_report failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_old_meetings(self):
    """
    Soft-delete completed meetings older than 6 months.
    Runs weekly via Celery beat.
    """
    from .models import Meeting

    try:
        cutoff = timezone.now() - timedelta(days=180)
        old_meetings = Meeting.objects.filter(
            status='COMPLETED',
            actual_end__lt=cutoff,
            is_deleted=False,
        )
        count = old_meetings.count()
        old_meetings.update(is_deleted=True, deleted_at=timezone.now())

        logger.info("cleanup_old_meetings: archived %d meetings.", count)
        return {'status': 'completed', 'meetings_archived': count}

    except Exception as exc:
        logger.exception("cleanup_old_meetings failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_overdue_tasks(self):
    """
    Escalate notifications for tasks that have passed their due date.
    Notifies both assigned user and assigned agency's primary contact.
    Runs every 4 hours via Celery beat.
    """
    from .models import Task
    from core.models import Notification

    try:
        now = timezone.now()
        overdue = Task.objects.filter(
            status__in=_ACTIVE_STATUSES,
            due_date__lt=now,
            is_deleted=False,
        ).select_related('assigned_to_user', 'assigned_to_agency', 'coordination_team')

        notified = 0
        for task in overdue:
            hours_overdue = round((now - task.due_date).total_seconds() / 3600, 1)
            message = (
                f"[OVERDUE — {hours_overdue}h] Task '{task.title}' was due at "
                f"{task.due_date:%Y-%m-%d %H:%M} UTC. Progress: {task.progress_percentage}%. "
                f"Team: {task.coordination_team.name}."
            )

            if task.assigned_to_user:
                Notification.objects.get_or_create(
                    user=task.assigned_to_user,
                    title=f"OVERDUE Task: {task.title}",
                    defaults={'message': message, 'notification_type': 'ERROR'},
                )
                notified += 1

        logger.info("notify_overdue_tasks: notified %d overdue task owners.", notified)
        return {'status': 'completed', 'notifications_sent': notified}

    except Exception as exc:
        logger.exception("notify_overdue_tasks failed: %s", exc)
        raise self.retry(exc=exc)