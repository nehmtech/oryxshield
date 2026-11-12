"""
Django signal handlers for the surveillance app.
All external task calls are wrapped in try/except so a missing dependency
(e.g. websockets app not yet registered) does not break record saves.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AnomalyDetection, CaseCluster, HealthData, Hotspot

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AnomalyDetection)
def on_anomaly_created(sender, instance, created, **kwargs):
    """
    When a new anomaly is detected:
    - Send a real-time WebSocket alert.
    - For CRITICAL severity, trigger response escalation.
    """
    if not created:
        return

    logger.info(
        "Anomaly created: %s — %s @ %s",
        instance.severity, instance.disease_name, instance.location.name,
    )

    _send_ws({
        "type": "anomaly",
        "severity": instance.severity,
        "disease": instance.disease_name,
        "location": instance.location.name,
        "cases": instance.actual_cases,
        "anomaly_id": str(instance.id),
    })

    # Enqueue risk score recalculation for the affected location/disease pair
    try:
        from risk_assessment.tasks import calculate_risk_score  # type: ignore
        calculate_risk_score.apply_async(
            kwargs={
                "location_id": str(instance.location_id),
                "disease_code": instance.disease_code,
            },
            countdown=5,
        )
    except Exception:  # noqa: BLE001
        logger.debug("risk_assessment.tasks not available — risk score recalc skipped")

    if instance.severity == "CRITICAL":
        try:
            from response.tasks import check_escalation_triggers  # type: ignore
            check_escalation_triggers.delay()
        except Exception:  # noqa: BLE001
            logger.debug("response.tasks not available — escalation skipped")


@receiver(post_save, sender=CaseCluster)
def on_cluster_created(sender, instance, created, **kwargs):
    """Broadcast new cluster to connected clients."""
    if not created:
        return

    logger.info("Cluster created: %s — %s", instance.name, instance.location.name)

    _send_ws({
        "type": "cluster",
        "name": instance.name,
        "disease": instance.disease_name,
        "location": instance.location.name,
        "cases": instance.case_count,
        "cluster_id": str(instance.id),
    })


@receiver(post_save, sender=Hotspot)
def on_hotspot_created(sender, instance, created, **kwargs):
    """
    Broadcast new hotspot.
    For HIGH/CRITICAL risk, enqueue a push-alert notification.
    """
    if not created:
        return

    logger.info(
        "Hotspot created: %s risk — %s @ %s",
        instance.risk_level, instance.disease_name, instance.location.name,
    )

    _send_ws({
        "type": "hotspot",
        "risk_level": instance.risk_level,
        "disease": instance.disease_name,
        "location": instance.location.name,
        "cases": instance.case_count,
        "hotspot_id": str(instance.id),
    })

    if instance.risk_level in ("HIGH", "CRITICAL"):
        try:
            from communications.tasks import send_hotspot_alert  # type: ignore
            send_hotspot_alert.delay(str(instance.id))
        except Exception:  # noqa: BLE001
            logger.debug("communications.tasks not available — hotspot alert skipped")


@receiver(post_save, sender=HealthData)
def on_health_data_created(sender, instance, created, **kwargs):
    """Schedule anomaly detection 60 s after a new CASE or LAB_RESULT is saved."""
    if not created:
        return
    if instance.data_type not in ("CASE", "LAB_RESULT"):
        return

    try:
        from .tasks import run_anomaly_detection
        run_anomaly_detection.apply_async(countdown=60)
    except Exception:  # noqa: BLE001
        logger.debug("Could not schedule run_anomaly_detection after HealthData save")


@receiver(pre_save, sender=HealthData)
def validate_health_data(sender, instance, **kwargs):
    """
    Pre-save validation: populate processing_errors for records missing
    mandatory fields so the pipeline can quarantine them without raising.
    """
    errors = []
    if not instance.disease_code:
        errors.append("Missing disease_code")
    if not instance.date_recorded:
        errors.append("Missing date_recorded")
    if errors:
        instance.processing_errors = "; ".join(errors)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _send_ws(payload: dict) -> None:
    """Fire-and-forget WebSocket emission — never raises."""
    try:
        from websockets.utils import send_surveillance_update  # type: ignore
        send_surveillance_update(payload)
    except Exception:  # noqa: BLE001
        pass