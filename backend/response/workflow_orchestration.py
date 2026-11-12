"""
Workflow orchestration for the response app.

Provides high-level orchestration functions that coordinate multiple
models, tasks, and decisions in a single transactional flow.
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone

from core.models import AuditLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full response activation workflow
# ---------------------------------------------------------------------------

@transaction.atomic
def activate_response_workflow(
    location,
    disease_code: str,
    disease_name: str,
    justification: str,
    activated_by,
    incident_commander=None,
    triggered_by_alert=None,
    triggered_by_risk_score=None,
    objectives: list = None,
    override_level: int = None,
) -> dict:
    """
    End-to-end response activation workflow:

    1. Determine recommended response level (or use override_level).
    2. Select the best matching protocol.
    3. Create the ResponseActivation record.
    4. Generate action items from the protocol.
    5. Notify the incident commander.
    6. Write AuditLog.
    7. Dispatch background tasks.

    All database writes are wrapped in a single atomic transaction.

    Args:
        location:               Location ORM object.
        disease_code:           ICD disease code string.
        disease_name:           Human-readable disease name.
        justification:          Reason for activation.
        activated_by:           User initiating the activation.
        incident_commander:     User who will lead the response (optional).
        triggered_by_alert:     Alert ORM object that triggered this (optional).
        triggered_by_risk_score: RiskScore object that triggered this (optional).
        objectives:             List of objective strings (optional).
        override_level:         Force a specific level 1–5 (optional).

    Returns:
        Dict with activation details and generated action item count.
    """
    from .models import ResponseLevel, ResponseActivation
    from .decision_support import (
        recommend_response_level,
        select_appropriate_protocol,
        generate_action_items_from_protocol,
    )

    objectives = objectives or []

    # 1. Determine level
    if override_level:
        level_num = max(1, min(5, override_level))
    else:
        current_situation = {}
        if triggered_by_risk_score:
            current_situation["risk_score"] = float(triggered_by_risk_score.overall_score)
        level_num = recommend_response_level(location, disease_code, current_situation)

    try:
        response_level = ResponseLevel.objects.get(level=level_num)
    except ResponseLevel.DoesNotExist:
        raise ValueError(f"ResponseLevel {level_num} does not exist in the database.")

    # 2. Select protocol
    protocol = select_appropriate_protocol(disease_code, location, level_num)

    # 3. Create activation
    activation_code = f"RSP-{uuid.uuid4().hex[:8].upper()}"

    activation = ResponseActivation.objects.create(
        activation_code=activation_code,
        response_level=response_level,
        protocol=protocol,
        location=location,
        disease_code=disease_code,
        disease_name=disease_name,
        justification=justification,
        objectives=objectives,
        status="ACTIVE",
        activated_by=activated_by,
        incident_commander=incident_commander,
        triggered_by_alert=triggered_by_alert,
        triggered_by_risk_score=triggered_by_risk_score,
        expected_completion=(
            timezone.now() + timezone.timedelta(
                days=response_level.estimated_duration_days or 30
            )
        ),
    )

    # 4. Generate action items
    action_count = 0
    if protocol:
        items = generate_action_items_from_protocol(protocol, activation)
        action_count = len(items)

    # 5. Notify incident commander
    if incident_commander:
        try:
            from core.models import Notification

            Notification.objects.create(
                user=incident_commander,
                title=f"Response Activated: {activation_code}",
                message=(
                    f"You have been assigned as Incident Commander for {activation_code} "
                    f"(Level {level_num}) at {location.name} for {disease_name}."
                ),
                notification_type="ALERT",
                metadata={
                    "response_activation_id": str(activation.id),
                    "level": level_num,
                },
            )
        except Exception as exc:
            logger.warning(
                "Incident commander notification failed for %s: %s", activation_code, exc
            )

    # 6. AuditLog
    AuditLog.log(
        action="RESPONSE_WORKFLOW_ACTIVATED",
        actor=activated_by,
        target_object_id=str(activation.id),
        target_content_type="response.ResponseActivation",
        details={
            "activation_code": activation_code,
            "level": level_num,
            "location": location.name,
            "disease_code": disease_code,
            "protocol": protocol.code if protocol else None,
            "action_items_generated": action_count,
        },
    )

    logger.info(
        "Activation workflow complete: %s | Level %s | Location: %s | "
        "Protocol: %s | Actions: %d",
        activation_code,
        level_num,
        location.name,
        protocol.code if protocol else "none",
        action_count,
    )

    # 7. Async tasks (outside transaction boundary but after commit)
    try:
        from .tasks import send_response_summary

        transaction.on_commit(
            lambda: send_response_summary.delay(str(activation.id))
        )
    except Exception as exc:
        logger.warning("Could not schedule summary task for %s: %s", activation_code, exc)

    return {
        "activation_code": activation_code,
        "response_activation_id": str(activation.id),
        "level": level_num,
        "protocol": protocol.code if protocol else None,
        "action_items_generated": action_count,
        "location": location.name,
        "disease_code": disease_code,
        "status": "ACTIVE",
    }


# ---------------------------------------------------------------------------
# Response completion workflow
# ---------------------------------------------------------------------------

@transaction.atomic
def complete_response_workflow(response_activation, user, completion_notes: str = "") -> dict:
    """
    Orchestrate orderly response completion:

    1. Verify all CRITICAL actions are resolved (completed or cancelled).
    2. Auto-complete any remaining IN_PROGRESS actions.
    3. Complete the response activation.
    4. Generate an after-action report stub.
    5. Write AuditLog.
    6. Dispatch summary task.

    Raises ValueError if critical actions are still pending.
    """
    from .models import ActionItem, ResponseReport

    # 1. Check for unresolved critical actions
    critical_pending = response_activation.action_items.filter(
        priority="CRITICAL",
        status__in=["PENDING", "BLOCKED"],
        is_deleted=False,
    )
    if critical_pending.exists():
        titles = list(critical_pending.values_list("title", flat=True))
        raise ValueError(
            f"Cannot complete response: {critical_pending.count()} critical action(s) "
            f"are still unresolved: {titles}"
        )

    # 2. Auto-complete any lingering IN_PROGRESS actions
    in_progress = response_activation.action_items.filter(
        status="IN_PROGRESS",
        is_deleted=False,
    )
    in_progress_count = in_progress.count()
    in_progress.update(
        status="COMPLETED",
        completed_at=timezone.now(),
        completion_notes="Auto-completed during response closure.",
        updated_at=timezone.now(),
    )

    # 3. Complete the activation
    response_activation.complete(user=user)

    # 4. After-action report stub
    today = timezone.now().date()
    duration_days = (response_activation.completed_at - response_activation.activated_at).days

    ResponseReport.objects.get_or_create(
        response_activation=response_activation,
        report_type="AFTER_ACTION",
        defaults={
            "title": f"After Action Review – {response_activation.activation_code}",
            "report_date": today,
            "executive_summary": (
                f"Response {response_activation.activation_code} completed after "
                f"{duration_days} days at Level {response_activation.response_level.level}. "
                f"{completion_notes}"
            ).strip(),
            "submitted_by": user,
        },
    )

    # 5. AuditLog
    AuditLog.log(
        action="RESPONSE_WORKFLOW_COMPLETED",
        actor=user,
        target_object_id=str(response_activation.id),
        target_content_type="response.ResponseActivation",
        details={
            "activation_code": response_activation.activation_code,
            "duration_days": duration_days,
            "auto_completed_actions": in_progress_count,
        },
    )

    logger.info(
        "Completion workflow finished for %s. Duration: %d days.",
        response_activation.activation_code,
        duration_days,
    )

    # 6. Dispatch summary
    try:
        from .tasks import send_response_summary

        transaction.on_commit(
            lambda: send_response_summary.delay(str(response_activation.id))
        )
    except Exception as exc:
        logger.warning(
            "Could not dispatch completion summary for %s: %s",
            response_activation.activation_code,
            exc,
        )

    return {
        "success": True,
        "activation_code": response_activation.activation_code,
        "duration_days": duration_days,
        "auto_completed_actions": in_progress_count,
    }


# ---------------------------------------------------------------------------
# Coordinated multi-location response
# ---------------------------------------------------------------------------

def activate_multi_location_response(
    locations: list,
    disease_code: str,
    disease_name: str,
    justification: str,
    activated_by,
    override_level: int = None,
) -> dict:
    """
    Activate a response simultaneously across multiple locations.

    Each location gets its own ResponseActivation.  Failures for individual
    locations are captured and returned without aborting the others.

    Args:
        locations:      List of Location ORM objects.
        disease_code:   ICD disease code.
        disease_name:   Human-readable disease name.
        justification:  Reason for activation.
        activated_by:   User initiating the activation.
        override_level: Force a specific response level (optional).

    Returns:
        Dict with successful activations list and errors list.
    """
    successful = []
    errors = []

    for location in locations:
        try:
            result = activate_response_workflow(
                location=location,
                disease_code=disease_code,
                disease_name=disease_name,
                justification=justification,
                activated_by=activated_by,
                override_level=override_level,
            )
            successful.append(result)
            logger.info(
                "Multi-location activation success: %s @ %s",
                result["activation_code"],
                location.name,
            )
        except Exception as exc:
            errors.append({"location": location.name, "error": str(exc)})
            logger.error(
                "Multi-location activation failed for %s: %s",
                location.name,
                exc,
            )

    return {
        "successful": successful,
        "errors": errors,
        "total_locations": len(locations),
        "success_count": len(successful),
        "error_count": len(errors),
    }