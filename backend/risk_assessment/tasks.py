"""
Celery tasks for risk_assessment.

Beat schedule (add to CELERY_BEAT_SCHEDULE in settings):
    calculate_all_risk_scores   — every 10 minutes
    check_thresholds            — every 5 minutes
    generate_alerts_from_anomalies — every 2 minutes
    auto_acknowledge_expired_alerts — hourly
    update_threat_classifications — daily
    cleanup_old_alerts          — weekly
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def calculate_all_risk_scores(self):
    """
    Recalculate risk scores for every (location, disease) combination that
    has HealthData records in the past 7 days.
    """
    from django.db.models import Count
    from surveillance.models import HealthData
    from .calculations import calculate_risk_for_location_disease
    from .models import RiskScore

    logger.info("calculate_all_risk_scores: starting")
    week_ago = timezone.now() - timedelta(days=7)

    combos = (
        HealthData.objects.filter(date_recorded__gte=week_ago, is_deleted=False)
        .values("location_id", "disease_code")
        .distinct()
    )

    calculated = 0
    errors = 0
    for combo in combos:
        try:
            rs = calculate_risk_for_location_disease(
                combo["location_id"], combo["disease_code"],
            )
            if rs:
                calculated += 1
        except Exception as exc:
            errors += 1
            logger.exception(
                "calculate_all_risk_scores: error for %s/%s: %s",
                combo["location_id"], combo["disease_code"], exc,
            )

    # Broadcast summary via WebSocket
    high_risk_count = RiskScore.objects.filter(
        is_deleted=False,
        risk_level__in=["CRITICAL", "VERY_HIGH"],
        is_active=True,
        assessment_date__gte=(timezone.now() - timedelta(minutes=15)).date(),
    ).count()

    if high_risk_count:
        try:
            from websockets.utils import send_alert
            send_alert({
                "type": "high_risk_detected",
                "count": high_risk_count,
                "timestamp": timezone.now().isoformat(),
            })
        except Exception as exc:
            logger.warning("calculate_all_risk_scores: WebSocket send failed: %s", exc)

    logger.info(
        "calculate_all_risk_scores: done — %d calculated, %d errors, %d high-risk",
        calculated, errors, high_risk_count,
    )
    return {"status": "completed", "calculated": calculated, "errors": errors, "high_risk": high_risk_count}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def check_thresholds(self):
    """
    Evaluate all active thresholds and create Alert objects for breaches.
    Runs every 5 minutes.
    """
    from .models import Alert, Threshold
    from .thresholds import check_threshold_breach

    logger.info("check_thresholds: starting")
    thresholds = Threshold.objects.filter(is_active=True, is_deleted=False)

    generated = 0
    for threshold in thresholds:
        try:
            breach = check_threshold_breach(threshold)
            if not breach or not threshold.auto_generate_alert:
                continue

            # Idempotency: one active alert per threshold
            if Alert.objects.filter(
                alert_type="THRESHOLD",
                status="ACTIVE",
                is_deleted=False,
                metadata__threshold_id=breach["threshold_id"],
            ).exists():
                continue

            Alert.objects.create(
                alert_type="THRESHOLD",
                severity=breach["severity"],
                title=f"Threshold Breach: {threshold.name}",
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
            generated += 1

        except Exception as exc:
            logger.exception("check_thresholds: error for %s: %s", threshold.name, exc)

    logger.info("check_thresholds: done — %d alerts generated", generated)
    return {"status": "completed", "thresholds_checked": thresholds.count(), "alerts_generated": generated}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_alerts_from_anomalies(self):
    """
    Create Alerts for unprocessed HIGH / CRITICAL anomalies that have no
    linked alert yet. Capped at 50 anomalies per run.
    """
    from surveillance.models import AnomalyDetection
    from .alert_engine import generate_alert_from_anomaly

    logger.info("generate_alerts_from_anomalies: starting")

    anomalies = (
        AnomalyDetection.objects.filter(
            is_deleted=False,
            is_verified=False,
            is_false_positive=False,
            severity__in=["HIGH", "CRITICAL"],
            alerts__isnull=True,
        )
        .select_related("location")[:50]
    )

    created = 0
    for anomaly in anomalies:
        try:
            alert = generate_alert_from_anomaly(anomaly)
            if alert:
                created += 1
        except Exception as exc:
            logger.exception("generate_alerts_from_anomalies: anomaly %s: %s", anomaly.id, exc)

    logger.info("generate_alerts_from_anomalies: done — %d alerts created", created)
    return {"status": "completed", "alerts_created": created}


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def auto_acknowledge_expired_alerts(self):
    """
    Close ACTIVE alerts whose expires_at has passed. Runs hourly.
    """
    from .models import Alert

    logger.info("auto_acknowledge_expired_alerts: starting")

    expired = Alert.objects.filter(
        is_deleted=False,
        status="ACTIVE",
        expires_at__lt=timezone.now(),
    )
    count = expired.count()

    for alert in expired.iterator(chunk_size=200):
        alert.close(reason="Expired — auto-closed by scheduled task.")

    logger.info("auto_acknowledge_expired_alerts: closed %d alerts", count)
    return {"status": "completed", "alerts_closed": count}


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def update_threat_classifications(self):
    """
    Refresh ThreatClassification rows from recent VERY_HIGH / CRITICAL
    RiskScores. Runs daily.
    """
    from .calculations import calculate_threat_level
    from .models import RiskScore, ThreatClassification

    logger.info("update_threat_classifications: starting")

    high_scores = RiskScore.objects.filter(
        is_deleted=False,
        risk_level__in=["VERY_HIGH", "CRITICAL"],
        is_active=True,
        assessment_date__gte=(timezone.now() - timedelta(days=1)).date(),
    ).select_related("location")

    updated = 0
    for rs in high_scores:
        try:
            threat_data = calculate_threat_level(rs)
            ThreatClassification.objects.update_or_create(
                disease_code=rs.disease_code,
                location=rs.location,
                assessment_date=timezone.now().date(),
                defaults={
                    "disease_name": rs.disease_name,
                    "threat_level": threat_data["level"],
                    "threat_score": threat_data["score"],
                    "pandemic_potential": threat_data["pandemic_potential"],
                    "justification": threat_data["justification"],
                    "related_risk_score": rs,
                },
            )
            updated += 1
        except Exception as exc:
            logger.exception(
                "update_threat_classifications: error for %s/%s: %s",
                rs.location_id, rs.disease_code, exc,
            )

    logger.info("update_threat_classifications: updated %d", updated)
    return {"status": "completed", "classifications_updated": updated}


@shared_task(bind=True)
def cleanup_old_alerts(self):
    """
    Soft-delete RESOLVED/CLOSED alerts older than 90 days. Runs weekly.
    """
    from .models import Alert

    logger.info("cleanup_old_alerts: starting")
    cutoff = timezone.now() - timedelta(days=90)

    old = Alert.objects.filter(
        is_deleted=False,
        status__in=["RESOLVED", "CLOSED"],
        resolved_at__lt=cutoff,
    )
    count = old.count()
    old.update(is_deleted=True, deleted_at=timezone.now())

    logger.info("cleanup_old_alerts: archived %d alerts", count)
    return {"status": "completed", "alerts_archived": count}


# ---------------------------------------------------------------------------
# On-demand tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def calculate_risk_score(self, location_id: str, disease_code: str, force: bool = False):
    """
    Calculate a risk score for a single (location, disease_code).

    Skips if a score was computed within the last hour and force=False.
    """
    from .calculations import calculate_risk_for_location_disease
    from .models import RiskScore
    from core.models import Location

    logger.info("calculate_risk_score: %s / %s (force=%s)", location_id, disease_code, force)

    try:
        location = Location.objects.get(id=location_id, is_deleted=False)
    except Location.DoesNotExist:
        return {"status": "error", "message": "Location not found."}

    if not force:
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent = RiskScore.objects.filter(
            location=location,
            disease_code=disease_code,
            is_active=True,
            is_deleted=False,
            assessment_date__gte=one_hour_ago.date(),
        ).first()
        if recent:
            return {
                "status": "skipped",
                "message": "Recent score exists.",
                "score_id": str(recent.id),
            }

    rs = calculate_risk_for_location_disease(location_id, disease_code)
    if rs:
        return {
            "status": "completed",
            "score_id": str(rs.id),
            "overall_score": float(rs.overall_score),
            "risk_level": rs.risk_level,
        }
    return {"status": "error", "message": "Insufficient data to calculate score."}


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def predict_outbreak(self, model_id: str, location_id: str, disease_code: str, horizon: int = 7):
    """
    Run an outbreak prediction using the specified PredictiveModel.
    """
    from .models import PredictiveModel
    from .predictive_models import run_prediction

    logger.info("predict_outbreak: model=%s loc=%s disease=%s horizon=%d",
                model_id, location_id, disease_code, horizon)

    try:
        model = PredictiveModel.objects.get(id=model_id, is_active=True, is_deleted=False)
    except PredictiveModel.DoesNotExist:
        return {"status": "error", "message": "Model not found or inactive."}

    try:
        result = run_prediction(model, location_id, disease_code, horizon)
        model.prediction_count += 1
        model.last_used = timezone.now()
        model.save(update_fields=["prediction_count", "last_used"])
        return {"status": "completed", "prediction": result}
    except Exception as exc:
        logger.exception("predict_outbreak: error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_alert_notifications(self, alert_id: str):
    """
    Dispatch SMS / email notifications for an Alert to its recipients list.
    """
    from .models import Alert

    logger.info("send_alert_notifications: alert=%s", alert_id)

    try:
        alert = Alert.objects.get(id=alert_id, is_deleted=False)
    except Alert.DoesNotExist:
        return {"status": "error", "message": "Alert not found."}

    sent = 0
    for recipient in alert.recipients:
        try:
            rtype = recipient.get("type")
            if rtype == "sms":
                from communications.tasks import send_sms_notification
                send_sms_notification.delay(
                    recipient["phone"], alert.title, alert.description,
                )
                sent += 1
            elif rtype == "email":
                from communications.tasks import send_email_notification
                send_email_notification.delay(
                    recipient["email"], alert.title, alert.description,
                )
                sent += 1
            else:
                logger.warning(
                    "send_alert_notifications: unknown recipient type '%s'", rtype,
                )
        except Exception as exc:
            logger.exception(
                "send_alert_notifications: failed for recipient %s: %s", recipient, exc,
            )

    alert.notification_sent = True
    alert.save(update_fields=["notification_sent"])

    logger.info("send_alert_notifications: sent %d notifications for '%s'", sent, alert.title)
    return {"status": "completed", "notifications_sent": sent}