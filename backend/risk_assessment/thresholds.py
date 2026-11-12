"""
Threshold checking and automated alert generation for risk_assessment.
"""
import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

# Map threshold breach tier → Alert severity
_SEVERITY_MAP = {
    "WARNING": "WARNING",
    "ALERT": "ALERT",
    "CRITICAL": "CRITICAL",
}


def check_threshold_breach(threshold) -> dict | None:
    """
    Compute the current metric value for *threshold* and check it against
    the configured tiers.

    Returns a breach descriptor dict when a tier is exceeded, else None.
    """
    current_value = _current_value(threshold)
    if current_value is None:
        return None

    tier = threshold.evaluate(current_value)
    if tier == "NORMAL":
        return None

    threshold_value = _tier_value(threshold, tier)
    return {
        "threshold_id": str(threshold.id),
        "threshold_name": threshold.name,
        "breach_level": tier,
        "current_value": float(current_value),
        "threshold_value": float(threshold_value),
        "severity": _SEVERITY_MAP[tier],
        "description": _breach_description(threshold, current_value, tier),
    }


def monitor_all_thresholds() -> list:
    """
    Iterate all active thresholds and create Alert objects for any that are
    breached and do not already have an active alert.

    Returns the list of newly created Alert objects.
    """
    from .models import Alert, Threshold

    active_thresholds = Threshold.objects.filter(
        is_active=True, is_deleted=False,
    ).select_related("location")

    created_alerts = []

    for threshold in active_thresholds:
        breach = check_threshold_breach(threshold)
        if not breach or not threshold.auto_generate_alert:
            continue

        # Idempotency: skip if an active threshold alert already exists
        existing = Alert.objects.filter(
            alert_type="THRESHOLD",
            status="ACTIVE",
            is_deleted=False,
            disease_code=threshold.disease_code or "",
            metadata__threshold_id=breach["threshold_id"],
        )
        if threshold.location:
            existing = existing.filter(location=threshold.location)
        if existing.exists():
            continue

        alert = Alert.objects.create(
            alert_type="THRESHOLD",
            severity=breach["severity"],
            title=f"Threshold Breach: {breach['threshold_name']}",
            description=breach["description"],
            location=threshold.location,
            disease_code=threshold.disease_code or "",
            recipients=threshold.notification_recipients,
            metadata={
                "threshold_id": breach["threshold_id"],
                "current_value": breach["current_value"],
                "threshold_value": breach["threshold_value"],
                "breach_level": breach["breach_level"],
            },
        )
        created_alerts.append(alert)
        logger.info("Threshold alert created: %s", alert.title)

    return created_alerts


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _current_value(threshold):
    """Return the current metric value for the threshold type, or None."""
    from surveillance.models import HealthData
    from .models import RiskScore

    start = timezone.now() - timedelta(days=threshold.evaluation_period)

    t = threshold.threshold_type

    if t == "CASE_COUNT":
        qs = HealthData.objects.filter(date_recorded__gte=start, is_deleted=False)
        if threshold.disease_code:
            qs = qs.filter(disease_code=threshold.disease_code)
        if threshold.location:
            qs = qs.filter(location=threshold.location)
        return qs.count()

    if t == "INCIDENCE_RATE":
        qs = HealthData.objects.filter(date_recorded__gte=start, is_deleted=False)
        if threshold.disease_code:
            qs = qs.filter(disease_code=threshold.disease_code)
        if threshold.location:
            qs = qs.filter(location=threshold.location)
            population = max(threshold.location.population or 1_000, 1)
        else:
            population = 1_000_000
        return (qs.count() / population) * 100_000

    if t == "RISK_SCORE":
        qs = RiskScore.objects.filter(
            is_active=True, is_deleted=False, assessment_date__gte=start.date(),
        )
        if threshold.disease_code:
            qs = qs.filter(disease_code=threshold.disease_code)
        if threshold.location:
            qs = qs.filter(location=threshold.location)
        latest = qs.order_by("-assessment_date").first()
        return float(latest.overall_score) if latest else None

    if t == "R_NAUGHT":
        qs = RiskScore.objects.filter(
            is_active=True, is_deleted=False,
            r_naught__isnull=False,
            assessment_date__gte=start.date(),
        )
        if threshold.disease_code:
            qs = qs.filter(disease_code=threshold.disease_code)
        if threshold.location:
            qs = qs.filter(location=threshold.location)
        latest = qs.order_by("-assessment_date").first()
        return float(latest.r_naught) if latest else None

    if t == "MORTALITY_RATE":
        qs = HealthData.objects.filter(date_recorded__gte=start, is_deleted=False)
        if threshold.disease_code:
            qs = qs.filter(disease_code=threshold.disease_code)
        if threshold.location:
            qs = qs.filter(location=threshold.location)
        total = qs.count()
        if total == 0:
            return None
        deaths = qs.filter(outcome="DEATH").count()
        return (deaths / total) * 100

    # CAPACITY and any future types
    return None


def _tier_value(threshold, tier: str) -> float:
    if tier == "CRITICAL":
        return float(threshold.critical_value)
    if tier == "ALERT":
        return float(threshold.alert_value)
    return float(threshold.warning_value)


def _breach_description(threshold, current_value: float, tier: str) -> str:
    threshold_value = _tier_value(threshold, tier)
    parts = [
        f"Threshold '{threshold.name}' breached at {tier} level.",
        f"Current value: {current_value:.2f}, threshold: {threshold_value:.2f}.",
    ]
    if threshold.location:
        parts.append(f"Location: {threshold.location.name}.")
    if threshold.disease_code:
        parts.append(f"Disease code: {threshold.disease_code}.")
    return " ".join(parts)