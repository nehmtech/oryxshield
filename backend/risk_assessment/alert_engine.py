"""
Alert generation engine for risk_assessment.

Two public entry points:
  generate_alert_from_anomaly(anomaly)   → Alert | None
  generate_alert_from_risk_score(risk_score) → Alert | None
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

_ANOMALY_SEVERITY_MAP = {
    "LOW": "INFO",
    "MEDIUM": "WARNING",
    "HIGH": "ALERT",
    "CRITICAL": "CRITICAL",
}

_RISK_SEVERITY_MAP = {
    "VERY_HIGH": "ALERT",
    "CRITICAL": "CRITICAL",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def generate_alert_from_anomaly(anomaly):
    """
    Create an Alert from an AnomalyDetection object.

    Returns the new Alert, or None if one already exists for this anomaly.
    """
    from .models import Alert

    # Idempotency guard
    if Alert.objects.filter(
        related_anomaly=anomaly, is_deleted=False,
    ).exists():
        return None

    severity = _ANOMALY_SEVERITY_MAP.get(anomaly.severity, "WARNING")
    alert_type = anomaly.anomaly_type if anomaly.anomaly_type in ("OUTBREAK", "EPIDEMIC") else "OUTBREAK"

    description = (
        f"Anomaly detected for {anomaly.disease_name} at {anomaly.location.name}. "
        f"Expected {anomaly.expected_cases} cases; observed {anomaly.actual_cases}. "
        f"Increase: {float(anomaly.percentage_increase):.1f}%. "
        f"Confidence: {anomaly.confidence_score}%."
    )

    alert = Alert.objects.create(
        alert_type=alert_type,
        severity=severity,
        title=f"Disease Anomaly: {anomaly.disease_name}",
        description=description,
        recommendation=_anomaly_recommendations(anomaly),
        location=anomaly.location,
        disease_code=anomaly.disease_code,
        disease_name=anomaly.disease_name,
        related_anomaly=anomaly,
        expires_at=timezone.now() + timedelta(days=7),
        metadata={
            "anomaly_id": str(anomaly.id),
            "confidence_score": float(anomaly.confidence_score),
            "percentage_increase": float(anomaly.percentage_increase),
        },
    )

    logger.info("Alert generated from anomaly %s: %s", anomaly.id, alert.title)
    return alert


def generate_alert_from_risk_score(risk_score):
    """
    Create an Alert from a high RiskScore.

    Only generates alerts for VERY_HIGH or CRITICAL risk levels.
    Returns the new Alert, or None if conditions not met or one already exists.
    """
    from .models import Alert

    if risk_score.risk_level not in ("VERY_HIGH", "CRITICAL"):
        return None

    # Idempotency guard
    if Alert.objects.filter(
        related_risk_score=risk_score, is_deleted=False,
    ).exists():
        return None

    severity = _RISK_SEVERITY_MAP[risk_score.risk_level]

    alert = Alert.objects.create(
        alert_type="ESCALATION",
        severity=severity,
        title=f"High Risk Alert: {risk_score.disease_name}",
        description=(
            f"High risk score for {risk_score.disease_name} "
            f"at {risk_score.location.name}. "
            f"Score: {float(risk_score.overall_score):.1f}/10. "
            f"Level: {risk_score.risk_level}."
        ),
        recommendation=_risk_recommendations(risk_score),
        location=risk_score.location,
        disease_code=risk_score.disease_code,
        disease_name=risk_score.disease_name,
        related_risk_score=risk_score,
        expires_at=timezone.now() + timedelta(days=7),
        metadata={
            "risk_score_id": str(risk_score.id),
            "overall_score": float(risk_score.overall_score),
            "r_naught": float(risk_score.r_naught) if risk_score.r_naught else None,
        },
    )

    logger.info("Alert generated from risk score %s: %s", risk_score.id, alert.title)
    return alert


def auto_escalate_alert(alert) -> bool:
    """
    Escalate an ALERT-severity alert to CRITICAL if it remains
    unacknowledged for more than 2 hours.

    Returns True if the alert was escalated.
    """
    if alert.severity != "ALERT" or alert.status != "ACTIVE":
        return False

    age = timezone.now() - alert.triggered_at
    if age <= timedelta(hours=2) or alert.acknowledged_at:
        return False

    alert.severity = "CRITICAL"
    alert.metadata["auto_escalated"] = True
    alert.metadata["escalation_reason"] = "Unacknowledged for more than 2 hours."
    alert.save(update_fields=["severity", "metadata"])

    logger.info("Alert auto-escalated to CRITICAL: %s", alert.title)
    return True


# ---------------------------------------------------------------------------
# Private recommendation builders
# ---------------------------------------------------------------------------

def _anomaly_recommendations(anomaly) -> str:
    lines = []
    if anomaly.severity in ("HIGH", "CRITICAL"):
        lines += [
            "Initiate enhanced surveillance.",
            "Activate response team.",
            "Prepare isolation facilities.",
        ]
    if float(anomaly.percentage_increase) > 100:
        lines += [
            "Consider declaring an outbreak.",
            "Implement contact tracing.",
        ]
    return " • ".join(lines)


def _risk_recommendations(risk_score) -> str:
    lines = []
    if risk_score.risk_level == "CRITICAL":
        lines += [
            "Activate emergency response protocols.",
            "Mobilise all available resources.",
            "Consider movement restrictions.",
        ]
    r0 = float(risk_score.r_naught) if risk_score.r_naught else 0
    if r0 > 2.0:
        lines += [
            "Implement strict social distancing.",
            "Accelerate vaccination if available.",
        ]
    cfr = float(risk_score.case_fatality_rate) if risk_score.case_fatality_rate else 0
    if cfr > 5.0:
        lines += [
            "Ensure adequate ICU capacity.",
            "Stock essential medicines.",
        ]
    return " • ".join(lines)