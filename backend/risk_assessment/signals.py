"""
Django signal handlers for risk_assessment.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Alert, RiskScore

logger = logging.getLogger(__name__)


@receiver(post_save, sender=RiskScore)
def on_risk_score_saved(sender, instance: RiskScore, created: bool, **kwargs):
    """
    After a new RiskScore is saved:
    - Emit a WebSocket notification for VERY_HIGH / CRITICAL levels.
    - Generate an Alert automatically for CRITICAL scores.
    """
    if not created:
        return

    if instance.risk_level not in ("VERY_HIGH", "CRITICAL"):
        return

    logger.info(
        "High risk score created: %s @ %s — %s",
        instance.disease_name, instance.location.name, instance.risk_level,
    )

    # WebSocket notification
    try:
        from websockets.utils import send_alert
        send_alert({
            "type": "high_risk",
            "disease": instance.disease_name,
            "location": instance.location.name,
            "risk_level": instance.risk_level,
            "score": float(instance.overall_score),
        })
    except Exception as exc:
        logger.warning("on_risk_score_saved: WebSocket send failed: %s", exc)

    # Auto-generate alert for CRITICAL only
    if instance.risk_level == "CRITICAL":
        try:
            from .alert_engine import generate_alert_from_risk_score
            generate_alert_from_risk_score(instance)
        except Exception as exc:
            logger.exception("on_risk_score_saved: alert generation failed: %s", exc)


@receiver(post_save, sender=Alert)
def on_alert_saved(sender, instance: Alert, created: bool, **kwargs):
    """
    After a new Alert is saved:
    - Emit a WebSocket notification.
    - Enqueue notification delivery for CRITICAL / EMERGENCY alerts with recipients.
    """
    if not created:
        return

    logger.info("Alert created: [%s] %s", instance.severity, instance.title)

    # WebSocket notification
    try:
        from websockets.utils import send_alert
        send_alert({
            "type": "new_alert",
            "alert_id": str(instance.id),
            "title": instance.title,
            "severity": instance.severity,
            "location": instance.location.name if instance.location else "Global",
        })
    except Exception as exc:
        logger.warning("on_alert_saved: WebSocket send failed: %s", exc)

    # Queue recipient notifications for high-severity alerts
    if instance.severity in ("CRITICAL", "EMERGENCY") and instance.recipients:
        try:
            from .tasks import send_alert_notifications
            send_alert_notifications.delay(str(instance.id))
        except Exception as exc:
            logger.exception("on_alert_saved: notification task failed: %s", exc)