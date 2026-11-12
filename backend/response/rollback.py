"""
Rollback and de-escalation utilities for the response app.

Provides safe mechanisms to revert a response activation to a prior state,
cancel activations, and reverse auto-escalations when conditions improve.
"""
import logging

from django.utils import timezone

from core.models import AuditLog

logger = logging.getLogger(__name__)


def rollback_response_to_level(response_activation, target_level, user, reason: str) -> dict:
    """
    Roll back *response_activation* to *target_level* (must be lower than current).

    This is a controlled de-escalation:
      - Calls response_activation.deescalate() which appends to escalation_history.
      - Cancels any PENDING action items that were generated for the higher level.
      - Writes an AuditLog entry.

    Args:
        response_activation: ResponseActivation instance.
        target_level:        ResponseLevel instance to de-escalate to.
        user:                User performing the rollback.
        reason:              Human-readable justification string.

    Returns:
        Dict with status and summary.
    """
    from .models import ActionItem

    if response_activation.status in ("COMPLETED", "CANCELLED"):
        return {
            "success": False,
            "error": f"Cannot rollback a {response_activation.status} response.",
        }

    if target_level.level >= response_activation.response_level.level:
        return {
            "success": False,
            "error": (
                f"Target level {target_level.level} is not lower than "
                f"current level {response_activation.response_level.level}."
            ),
        }

    previous_level = response_activation.response_level.level

    try:
        response_activation.deescalate(target_level, user, reason)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    # Cancel pending actions that belong to the rolled-back level
    # (identified by metadata tag set during protocol-generated action creation)
    cancelled_actions = ActionItem.objects.filter(
        response_activation=response_activation,
        status="PENDING",
        metadata__level=previous_level,
        is_deleted=False,
    )
    cancelled_count = cancelled_actions.count()
    cancelled_actions.update(
        status="CANCELLED",
        metadata={"cancellation_reason": f"Rollback from Level {previous_level}", "level": previous_level},
        updated_at=timezone.now(),
    )

    AuditLog.log(
        action="RESPONSE_ROLLBACK",
        actor=user,
        target_object_id=str(response_activation.id),
        target_content_type="response.ResponseActivation",
        details={
            "activation_code": response_activation.activation_code,
            "from_level": previous_level,
            "to_level": target_level.level,
            "cancelled_actions": cancelled_count,
            "reason": reason,
        },
    )

    logger.info(
        "Response %s rolled back from Level %s to Level %s by %s. "
        "%d pending actions cancelled.",
        response_activation.activation_code,
        previous_level,
        target_level.level,
        user.username if user else "system",
        cancelled_count,
    )

    return {
        "success": True,
        "activation_code": response_activation.activation_code,
        "from_level": previous_level,
        "to_level": target_level.level,
        "cancelled_actions": cancelled_count,
    }


def cancel_response_activation(response_activation, user, reason: str) -> dict:
    """
    Cancel a response activation.

    Sets status to CANCELLED, cancels all non-completed action items,
    and writes an AuditLog entry.

    Args:
        response_activation: ResponseActivation instance.
        user:                User performing the cancellation.
        reason:              Justification.

    Returns:
        Dict with status and summary.
    """
    from .models import ActionItem

    if response_activation.status == "COMPLETED":
        return {
            "success": False,
            "error": "Cannot cancel a completed response.",
        }

    if response_activation.status == "CANCELLED":
        return {
            "success": False,
            "error": "Response is already cancelled.",
        }

    # Cancel all non-terminal action items
    open_actions = ActionItem.objects.filter(
        response_activation=response_activation,
        status__in=["PENDING", "IN_PROGRESS", "BLOCKED"],
        is_deleted=False,
    )
    cancelled_action_count = open_actions.count()
    open_actions.update(status="CANCELLED", updated_at=timezone.now())

    response_activation.status = "CANCELLED"
    response_activation.metadata["cancellation_reason"] = reason
    response_activation.metadata["cancelled_by"] = user.username if user else "system"
    response_activation.metadata["cancelled_at"] = timezone.now().isoformat()
    response_activation.save(update_fields=["status", "metadata", "updated_at"])

    AuditLog.log(
        action="RESPONSE_CANCELLED",
        actor=user,
        target_object_id=str(response_activation.id),
        target_content_type="response.ResponseActivation",
        details={
            "activation_code": response_activation.activation_code,
            "reason": reason,
            "cancelled_actions": cancelled_action_count,
        },
    )

    logger.info(
        "Response %s cancelled by %s. %d actions cancelled.",
        response_activation.activation_code,
        user.username if user else "system",
        cancelled_action_count,
    )

    return {
        "success": True,
        "activation_code": response_activation.activation_code,
        "cancelled_actions": cancelled_action_count,
    }


def reverse_auto_escalations(location, disease_code: str, user, reason: str) -> dict:
    """
    Identify and roll back all auto-escalated responses at *location* for
    *disease_code* to their pre-escalation level.

    This is intended for use when an automated escalation is found to have
    triggered incorrectly (e.g., data quality issue).

    Args:
        location:      Location ORM object.
        disease_code:  Disease code string.
        user:          User authorising the reversal.
        reason:        Justification string.

    Returns:
        Dict with count of reversed responses and any errors.
    """
    from .models import ResponseActivation, ResponseLevel

    escalated = ResponseActivation.objects.filter(
        location=location,
        disease_code=disease_code,
        status="ESCALATED",
        is_deleted=False,
    )

    reversed_count = 0
    errors = []

    for response in escalated:
        history = response.escalation_history
        if not history:
            continue

        # Find the most recent auto-escalation entry
        auto_entries = [
            e for e in reversed(history)
            if "auto-escalated" in e.get("reason", "").lower()
        ]
        if not auto_entries:
            continue

        last_auto = auto_entries[0]
        target_level_num = last_auto.get("from_level")
        if target_level_num is None:
            continue

        try:
            target_level = ResponseLevel.objects.get(level=target_level_num)
        except ResponseLevel.DoesNotExist:
            errors.append(
                f"Level {target_level_num} not found for {response.activation_code}"
            )
            continue

        result = rollback_response_to_level(
            response, target_level, user,
            f"Auto-escalation reversal: {reason}",
        )

        if result["success"]:
            reversed_count += 1
        else:
            errors.append(
                f"{response.activation_code}: {result.get('error', 'unknown error')}"
            )

    return {
        "reversed": reversed_count,
        "errors": errors,
        "location": location.name,
        "disease_code": disease_code,
    }