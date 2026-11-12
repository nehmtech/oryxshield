"""
Escalation logic for response app.

All public functions are fully implemented — no stubs.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trigger evaluation — dispatcher
# ---------------------------------------------------------------------------

def evaluate_escalation_trigger(trigger, response_activation) -> bool:
    """
    Evaluate whether the conditions of *trigger* are met for *response_activation*.

    Returns True if the trigger threshold has been breached.
    """
    evaluation_start = timezone.now() - timedelta(days=trigger.evaluation_period_days)

    dispatch = {
        "CASE_COUNT": _check_case_count,
        "RISK_SCORE": _check_risk_score,
        "TIME_ELAPSED": _check_time_elapsed,
        "CAPACITY": _check_capacity,
        "MORTALITY": _check_mortality,
    }

    checker = dispatch.get(trigger.trigger_type)
    if checker is None:
        logger.warning("Unknown trigger type: %s", trigger.trigger_type)
        return False

    try:
        return checker(trigger, response_activation, evaluation_start)
    except Exception as exc:
        logger.error(
            "Error evaluating trigger '%s' (type=%s): %s",
            trigger.name,
            trigger.trigger_type,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# Individual checkers
# ---------------------------------------------------------------------------

def _check_case_count(trigger, response, evaluation_start) -> bool:
    """Case count within evaluation_period exceeds threshold_value."""
    from surveillance.models import HealthData

    count = HealthData.objects.filter(
        location=response.location,
        disease_code=response.disease_code,
        date_recorded__gte=evaluation_start,
        is_deleted=False,
    ).count()

    return count >= float(trigger.threshold_value)


def _check_risk_score(trigger, response, evaluation_start) -> bool:
    """Latest active risk score equals or exceeds threshold_value."""
    from risk_assessment.models import RiskScore

    latest = (
        RiskScore.objects.filter(
            location=response.location,
            disease_code=response.disease_code,
            is_active=True,
            is_deleted=False,
        )
        .order_by("-assessment_date")
        .first()
    )

    if latest is None:
        return False

    return float(latest.overall_score) >= float(trigger.threshold_value)


def _check_time_elapsed(trigger, response, evaluation_start) -> bool:
    """Days since response activation equals or exceeds threshold_value."""
    elapsed_days = (timezone.now() - response.activated_at).days
    return elapsed_days >= float(trigger.threshold_value)


def _check_capacity(trigger, response, evaluation_start) -> bool:
    """
    Average occupancy rate across facilities at response location
    equals or exceeds threshold_value (percentage, 0–100).
    """
    try:
        from resources.models import FacilityCapacity

        facilities = FacilityCapacity.objects.filter(
            facility__location=response.location,
            is_deleted=False,
        )

        if not facilities.exists():
            return False

        avg_occupancy = sum(f.occupancy_rate for f in facilities) / facilities.count()
        return avg_occupancy >= float(trigger.threshold_value)

    except Exception as exc:
        logger.warning("Capacity check skipped (resources app unavailable?): %s", exc)
        return False


def _check_mortality(trigger, response, evaluation_start) -> bool:
    """
    Case-fatality rate (%) within evaluation_period equals or exceeds threshold_value.
    """
    from surveillance.models import HealthData

    total = HealthData.objects.filter(
        location=response.location,
        disease_code=response.disease_code,
        date_recorded__gte=evaluation_start,
        is_deleted=False,
    ).count()

    if total == 0:
        return False

    deaths = HealthData.objects.filter(
        location=response.location,
        disease_code=response.disease_code,
        date_recorded__gte=evaluation_start,
        outcome="DEATH",
        is_deleted=False,
    ).count()

    mortality_rate = (deaths / total) * 100
    return mortality_rate >= float(trigger.threshold_value)


# ---------------------------------------------------------------------------
# Recommendation helper
# ---------------------------------------------------------------------------

def recommend_escalation(response_activation) -> dict:
    """
    Evaluate all triggers applicable to *response_activation*'s current level
    and return a recommendation dict.

    Returns:
        {
            "should_escalate": bool,
            "recommended_level": int | None,
            "triggered_conditions": [...],
            "urgency": "HIGH" | "MEDIUM" | None,
        }
    """
    from .models import EscalationTrigger

    triggers = EscalationTrigger.objects.filter(
        from_level=response_activation.response_level,
        is_active=True,
        is_deleted=False,
    ).select_related("from_level", "to_level")

    triggered_conditions = []

    for trigger in triggers:
        if evaluate_escalation_trigger(trigger, response_activation):
            triggered_conditions.append(
                {
                    "trigger_name": trigger.name,
                    "trigger_type": trigger.trigger_type,
                    "to_level": trigger.to_level.level,
                    "threshold": float(trigger.threshold_value),
                    "auto_escalate": trigger.auto_escalate,
                }
            )

    if not triggered_conditions:
        return {
            "should_escalate": False,
            "recommended_level": None,
            "current_level": response_activation.response_level.level,
            "triggered_conditions": [],
            "urgency": None,
        }

    max_level = max(t["to_level"] for t in triggered_conditions)
    urgency = "HIGH" if len(triggered_conditions) >= 2 else "MEDIUM"

    return {
        "should_escalate": True,
        "recommended_level": max_level,
        "current_level": response_activation.response_level.level,
        "triggered_conditions": triggered_conditions,
        "urgency": urgency,
    }


# ---------------------------------------------------------------------------
# Auto-escalation of stalled responses (called from tasks)
# ---------------------------------------------------------------------------

def auto_escalate_stalled_responses() -> int:
    """
    Find responses stalled for > 7 days with < 20% completion and escalate them.
    Returns the number of responses escalated.
    """
    from .models import ResponseActivation, ResponseLevel

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
                    f"Auto-escalated: stalled at {response.completion_percentage}% "
                    f"after {(timezone.now() - response.activated_at).days} days."
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
                "Failed to escalate stalled response %s: %s",
                response.activation_code,
                exc,
            )

    return escalated_count


# ---------------------------------------------------------------------------
# Probability estimator
# ---------------------------------------------------------------------------

def calculate_escalation_probability(response_activation) -> float:
    """
    Estimate the probability (0.0–1.0) that *response_activation* will be
    escalated in the near future based on time active, progress, and risk score.
    """
    factors = []

    # --- Time factor ---
    days_active = (timezone.now() - response_activation.activated_at).days
    if days_active > 14:
        factors.append(0.80)
    elif days_active > 7:
        factors.append(0.50)
    elif days_active > 3:
        factors.append(0.30)
    else:
        factors.append(0.10)

    # --- Progress factor ---
    pct = response_activation.completion_percentage
    if pct < 10:
        factors.append(0.80)
    elif pct < 25:
        factors.append(0.60)
    elif pct < 50:
        factors.append(0.35)
    elif pct < 75:
        factors.append(0.15)
    else:
        factors.append(0.05)

    # --- Risk score factor ---
    try:
        from risk_assessment.models import RiskScore

        latest = (
            RiskScore.objects.filter(
                location=response_activation.location,
                disease_code=response_activation.disease_code,
                is_active=True,
                is_deleted=False,
            )
            .order_by("-assessment_date")
            .first()
        )

        if latest:
            risk_map = {
                "CRITICAL": 0.95,
                "VERY_HIGH": 0.80,
                "HIGH": 0.60,
                "MEDIUM": 0.35,
                "LOW": 0.15,
            }
            factors.append(risk_map.get(latest.risk_level, 0.35))

    except Exception as exc:
        logger.debug("Risk score unavailable for probability calc: %s", exc)

    # --- Trigger proximity factor ---
    try:
        from .models import EscalationTrigger

        active_triggers = EscalationTrigger.objects.filter(
            from_level=response_activation.response_level,
            is_active=True,
            is_deleted=False,
        ).count()

        if active_triggers >= 3:
            factors.append(0.70)
        elif active_triggers >= 1:
            factors.append(0.40)
        else:
            factors.append(0.10)

    except Exception:
        pass

    return round(sum(factors) / len(factors), 4) if factors else 0.50