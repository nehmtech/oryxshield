"""
Celery background tasks for response app.

All tasks use:
  bind=True            — access to self for retry
  max_retries=3
  default_retry_delay  — seconds before retry
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# check_escalation_triggers
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="response.tasks.check_escalation_triggers",
)
def check_escalation_triggers(self):
    """
    Evaluate all active escalation triggers against active responses.
    Auto-escalates when trigger.auto_escalate is True.
    Otherwise creates an Alert for manual review.
    Runs every minute via Celery Beat.
    """
    from .models import ResponseActivation, EscalationTrigger
    from .escalation import evaluate_escalation_trigger

    try:
        active_responses = ResponseActivation.objects.filter(
            status__in=["ACTIVE", "ESCALATED"]
        ).select_related("response_level", "location")

        active_triggers = EscalationTrigger.objects.filter(
            is_active=True
        ).select_related("from_level", "to_level")

        escalations_triggered = 0
        alerts_created = 0

        for response in active_responses:
            applicable = active_triggers.filter(from_level=response.response_level)

            for trigger in applicable:
                try:
                    should_escalate = evaluate_escalation_trigger(trigger, response)

                    if not should_escalate:
                        continue

                    if trigger.auto_escalate:
                        response.escalate(
                            trigger.to_level,
                            user=None,
                            reason=f"Auto-escalated via trigger: {trigger.name}",
                        )
                        escalations_triggered += 1
                        logger.info(
                            "Auto-escalated %s to Level %s via trigger '%s'",
                            response.activation_code,
                            trigger.to_level.level,
                            trigger.name,
                        )
                    else:
                        from risk_assessment.models import Alert

                        Alert.objects.get_or_create(
                            alert_type="ESCALATION",
                            severity="ALERT",
                            location=response.location,
                            is_acknowledged=False,
                            defaults={
                                "title": f"Escalation Recommended: {response.activation_code}",
                                "description": (
                                    f"Trigger '{trigger.name}' met for "
                                    f"{response.activation_code}."
                                ),
                                "metadata": {
                                    "response_activation_id": str(response.id),
                                    "trigger_id": str(trigger.id),
                                    "recommended_level": trigger.to_level.level,
                                },
                            },
                        )
                        alerts_created += 1

                except Exception as exc:
                    logger.error(
                        "Error evaluating trigger '%s' for %s: %s",
                        trigger.name,
                        response.activation_code,
                        exc,
                    )

        logger.info(
            "Escalation check complete. Responses checked: %d, "
            "Auto-escalations: %d, Alerts created: %d",
            active_responses.count(),
            escalations_triggered,
            alerts_created,
        )

        return {
            "status": "completed",
            "responses_checked": active_responses.count(),
            "escalations_triggered": escalations_triggered,
            "alerts_created": alerts_created,
        }

    except Exception as exc:
        logger.error("check_escalation_triggers failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# generate_daily_reports
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="response.tasks.generate_daily_reports",
)
def generate_daily_reports(self):
    """
    Generate daily situation reports for all active responses.
    Runs daily at 08:00 via Celery Beat.
    """
    from .models import ResponseActivation, ResponseReport
    from .decision_support import calculate_response_effectiveness

    try:
        active_responses = ResponseActivation.objects.filter(
            status__in=["ACTIVE", "ESCALATED"]
        ).select_related("response_level", "location")

        today = timezone.now().date()
        reports_generated = 0

        for response in active_responses:
            already_exists = ResponseReport.objects.filter(
                response_activation=response,
                report_type="DAILY",
                report_date=today,
                is_deleted=False,
            ).exists()

            if already_exists:
                continue

            try:
                effectiveness = calculate_response_effectiveness(response)
                pending_actions = response.action_items.filter(status="PENDING").count()
                completed_actions = response.action_items.filter(status="COMPLETED").count()
                overdue_actions = response.action_items.filter(
                    status__in=["PENDING", "IN_PROGRESS"],
                    due_date__lt=timezone.now(),
                ).count()

                ResponseReport.objects.create(
                    response_activation=response,
                    report_type="DAILY",
                    title=f"Daily Report – {response.activation_code} – {today}",
                    report_date=today,
                    executive_summary=(
                        f"Daily situation report for {response.activation_code}. "
                        f"Effectiveness score: {round(effectiveness, 1)}%. "
                        f"Completion: {response.completion_percentage}%."
                    ),
                    situation_overview=(
                        f"Response Level {response.response_level.level} active at "
                        f"{response.location.name} for disease {response.disease_name}."
                    ),
                    actions_taken=[
                        {
                            "summary": f"{completed_actions} actions completed today."
                        }
                    ],
                    challenges=(
                        [{"issue": f"{overdue_actions} action(s) overdue."}]
                        if overdue_actions
                        else []
                    ),
                    recommendations=[
                        {"text": "Continue monitoring and update action statuses."}
                    ],
                    personnel_deployed=response.personnel_deployed,
                    resources_consumed=response.resources_allocated,
                    metadata={
                        "pending_actions": pending_actions,
                        "completed_actions": completed_actions,
                        "overdue_actions": overdue_actions,
                        "effectiveness_score": round(effectiveness, 2),
                        "auto_generated": True,
                    },
                )
                reports_generated += 1

            except Exception as exc:
                logger.error(
                    "Failed to generate daily report for %s: %s",
                    response.activation_code,
                    exc,
                )

        logger.info("Daily reports generated: %d", reports_generated)
        return {"status": "completed", "reports_generated": reports_generated}

    except Exception as exc:
        logger.error("generate_daily_reports failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# check_overdue_actions
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name="response.tasks.check_overdue_actions",
)
def check_overdue_actions(self):
    """
    Detect overdue action items and send notifications to assignees.
    Marks metadata so each item receives only one notification per overdue period.
    Runs hourly via Celery Beat.
    """
    from .models import ActionItem
    from core.models import Notification

    try:
        overdue = ActionItem.objects.filter(
            status__in=["PENDING", "IN_PROGRESS"],
            due_date__lt=timezone.now(),
            is_deleted=False,
        ).select_related("assigned_to", "response_activation")

        notifications_sent = 0

        for action in overdue:
            # Guard: only notify once per overdue period (reset when action updated)
            if action.metadata.get("overdue_notification_sent"):
                continue

            if action.assigned_to:
                Notification.objects.create(
                    user=action.assigned_to,
                    title=f"Overdue Action: {action.title}",
                    message=(
                        f"Action '{action.title}' on response "
                        f"{action.response_activation.activation_code} is overdue. "
                        f"Due: {action.due_date.strftime('%Y-%m-%d %H:%M')}. "
                        f"Priority: {action.priority}."
                    ),
                    notification_type="WARNING",
                    metadata={"action_item_id": str(action.id)},
                )

            action.metadata["overdue_notification_sent"] = True
            action.save(update_fields=["metadata", "updated_at"])
            notifications_sent += 1

        logger.info(
            "Overdue check complete. Overdue: %d, Notifications sent: %d",
            overdue.count(),
            notifications_sent,
        )

        return {
            "status": "completed",
            "overdue_found": overdue.count(),
            "notifications_sent": notifications_sent,
        }

    except Exception as exc:
        logger.error("check_overdue_actions failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# auto_complete_expired_responses
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=600,
    name="response.tasks.auto_complete_expired_responses",
)
def auto_complete_expired_responses(self):
    """
    Auto-complete responses that have passed their expected_completion time.
    Runs daily via Celery Beat.
    """
    from .models import ResponseActivation

    try:
        expired = ResponseActivation.objects.filter(
            status="ACTIVE",
            expected_completion__lt=timezone.now(),
            is_deleted=False,
        )

        completed_count = 0

        for response in expired:
            response.metadata["auto_completed"] = True
            response.metadata["completion_reason"] = "Expected duration exceeded"
            response.save(update_fields=["metadata", "updated_at"])
            response.complete()
            completed_count += 1
            logger.info("Auto-completed expired response: %s", response.activation_code)

        return {"status": "completed", "responses_completed": completed_count}

    except Exception as exc:
        logger.error("auto_complete_expired_responses failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# update_response_progress
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="response.tasks.update_response_progress",
)
def update_response_progress(self, activation_id=None):
    """
    Recalculate completion_percentage for active responses from action item states.
    When activation_id is provided, only updates that one response.
    Otherwise updates all active responses.
    Runs hourly via Celery Beat, and on-demand after action completions.
    """
    from .models import ResponseActivation

    try:
        if activation_id:
            qs = ResponseActivation.objects.filter(
                id=activation_id, is_deleted=False
            )
        else:
            qs = ResponseActivation.objects.filter(
                status__in=["ACTIVE", "ESCALATED"],
                is_deleted=False,
            )

        updated_count = 0

        for response in qs:
            actions = response.action_items.filter(is_deleted=False)
            total = actions.count()

            if total == 0:
                continue

            completed = actions.filter(status="COMPLETED").count()
            new_percentage = int((completed / total) * 100)

            if response.completion_percentage != new_percentage:
                response.completion_percentage = new_percentage
                response.save(update_fields=["completion_percentage", "updated_at"])
                updated_count += 1

        logger.info("Progress update complete. Responses updated: %d", updated_count)
        return {"status": "completed", "responses_updated": updated_count}

    except Exception as exc:
        logger.error("update_response_progress failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# auto_escalate_stalled_responses
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="response.tasks.auto_escalate_stalled_responses",
)
def auto_escalate_stalled_responses(self):
    """
    Escalate responses that have been active for > 7 days with < 20% completion.
    Only escalates responses not already at Level 5.
    Runs daily via Celery Beat.
    """
    from .models import ResponseActivation, ResponseLevel

    try:
        week_ago = timezone.now() - timedelta(days=7)

        stalled = ResponseActivation.objects.filter(
            status="ACTIVE",
            activated_at__lt=week_ago,
            completion_percentage__lt=20,
            response_level__level__lt=5,
            is_deleted=False,
        ).select_related("response_level")

        escalated_count = 0

        for response in stalled:
            try:
                next_level = ResponseLevel.objects.get(
                    level=response.response_level.level + 1
                )
                response.escalate(
                    next_level,
                    user=None,
                    reason=(
                        f"Auto-escalated: less than 20% completion after "
                        f"{(timezone.now() - response.activated_at).days} days."
                    ),
                )
                escalated_count += 1
                logger.info(
                    "Stalled response %s escalated to Level %s",
                    response.activation_code,
                    next_level.level,
                )

            except ResponseLevel.DoesNotExist:
                logger.warning(
                    "No higher level available for stalled response %s",
                    response.activation_code,
                )
            except Exception as exc:
                logger.error(
                    "Error escalating stalled response %s: %s",
                    response.activation_code,
                    exc,
                )

        return {"status": "completed", "stalled_escalated": escalated_count}

    except Exception as exc:
        logger.error("auto_escalate_stalled_responses failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# cleanup_old_completed_responses
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=600,
    name="response.tasks.cleanup_old_completed_responses",
)
def cleanup_old_completed_responses(self):
    """
    Soft-delete response activations completed more than 1 year ago.
    Runs weekly via Celery Beat.
    """
    from .models import ResponseActivation

    try:
        one_year_ago = timezone.now() - timedelta(days=365)
        old = ResponseActivation.objects.filter(
            status="COMPLETED",
            completed_at__lt=one_year_ago,
            is_deleted=False,
        )

        count = old.count()
        old.update(is_deleted=True, deleted_at=timezone.now())

        logger.info("Archived %d old completed responses.", count)
        return {"status": "completed", "responses_archived": count}

    except Exception as exc:
        logger.error("cleanup_old_completed_responses failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# send_response_summary
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="response.tasks.send_response_summary",
)
def send_response_summary(self, activation_id: str):
    """
    Send a response summary email to the incident commander and stakeholders.
    Called on-demand after key events.
    """
    from .models import ResponseActivation
    from .decision_support import calculate_response_effectiveness

    try:
        try:
            activation = ResponseActivation.objects.select_related(
                "response_level", "location", "incident_commander"
            ).get(id=activation_id, is_deleted=False)
        except ResponseActivation.DoesNotExist:
            logger.error("Activation %s not found for summary.", activation_id)
            return {"status": "error", "message": "Activation not found."}

        effectiveness = calculate_response_effectiveness(activation)
        total_actions = activation.action_items.filter(is_deleted=False).count()
        completed_actions = activation.action_items.filter(
            status="COMPLETED", is_deleted=False
        ).count()

        subject = f"Response Summary: {activation.activation_code}"
        body = (
            f"Response Summary\n"
            f"{'=' * 40}\n"
            f"Code:        {activation.activation_code}\n"
            f"Level:       {activation.response_level.level} – "
            f"{activation.response_level.name}\n"
            f"Location:    {activation.location.name}\n"
            f"Disease:     {activation.disease_name}\n"
            f"Status:      {activation.status}\n"
            f"Completion:  {activation.completion_percentage}%\n"
            f"Effectiveness: {round(effectiveness, 1)}%\n"
            f"Actions:     {completed_actions}/{total_actions} completed\n"
            f"Activated:   {activation.activated_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
        if activation.completed_at:
            body += f"Completed:   {activation.completed_at.strftime('%Y-%m-%d %H:%M')}\n"

        if activation.incident_commander and activation.incident_commander.email:
            from communications.tasks import send_email_notification

            send_email_notification.delay(
                activation.incident_commander.email,
                subject,
                body,
            )

        logger.info("Summary sent for %s", activation.activation_code)
        return {"status": "completed", "activation_code": activation.activation_code}

    except Exception as exc:
        logger.error("send_response_summary failed for %s: %s", activation_id, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# update_escalation_probabilities
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="response.tasks.update_escalation_probabilities",
)
def update_escalation_probabilities(self):
    """
    Pre-compute escalation probability for all active responses and cache
    in metadata so API responses are fast.
    Runs every 30 minutes via Celery Beat.
    """
    from .models import ResponseActivation
    from .escalation import calculate_escalation_probability

    try:
        active = ResponseActivation.objects.filter(
            status__in=["ACTIVE", "ESCALATED"],
            is_deleted=False,
        )

        updated = 0
        for response in active:
            probability = calculate_escalation_probability(response)
            response.metadata["escalation_probability"] = round(probability, 4)
            response.save(update_fields=["metadata", "updated_at"])
            updated += 1

        logger.info("Updated escalation probability for %d responses.", updated)
        return {"status": "completed", "responses_updated": updated}

    except Exception as exc:
        logger.error("update_escalation_probabilities failed: %s", exc)
        raise self.retry(exc=exc)