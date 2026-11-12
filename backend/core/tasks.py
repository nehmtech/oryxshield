"""
OryxShield — Celery Tasks (core app)
=============================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

All tasks use shared_task so they work without a hard app reference.
Task names are explicit (name=...) so routing in config/celery.py works.

Task groups
-----------
Data maintenance   — cleanup_old_data, cleanup_expired_api_keys, unlock_expired_account_locks
Notifications      — send_notification_email, send_bulk_notifications, send_report_to_admins
Monitoring         — generate_system_report, calculate_system_metrics,
                     process_audit_log_analytics, health_check_services
User management    — check_inactive_users
Backup             — backup_database
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alert_admins(subject: str, body: str) -> None:
    """Send a plain-text alert email to all active staff members."""
    from django.core.mail import send_mail
    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not staff_emails:
        return
    try:
        send_mail(
            subject=f"[OryxShield ALERT] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=staff_emails,
            fail_silently=True,
        )
    except Exception as exc:
        logger.error("Failed to send admin alert: %s", exc)


# ---------------------------------------------------------------------------
# Data maintenance
# ---------------------------------------------------------------------------

@shared_task(
    name="core.cleanup_old_data",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def cleanup_old_data(self) -> dict:
    """
    Remove stale records:
      - Audit logs beyond retention window
      - Read notifications older than 90 days
      - Expired notifications
      - Soft-deleted API keys inactive for > 1 year

    Runs: daily at 02:00 (configured in config/celery.py beat_schedule).
    """
    from .models import APIKey, AuditLog, Notification

    logger.info("cleanup_old_data: starting")
    results = {
        "audit_logs_deleted": 0,
        "notifications_deleted": 0,
        "expired_notifications_deleted": 0,
        "api_keys_deleted": 0,
    }

    try:
        # Audit logs
        retention_days = getattr(settings, "DATA_RETENTION_DAYS", 365)
        cutoff = timezone.now() - timedelta(days=retention_days)
        count, _ = AuditLog.objects.filter(timestamp__lt=cutoff).delete()
        results["audit_logs_deleted"] = count
        logger.info("cleanup_old_data: deleted %d audit logs", count)

        # Read notifications (90 days)
        three_months = timezone.now() - timedelta(days=90)
        count, _ = Notification.objects.filter(
            is_read=True, read_at__lt=three_months
        ).delete()
        results["notifications_deleted"] = count

        # Expired notifications
        count, _ = Notification.objects.filter(expires_at__lt=timezone.now()).delete()
        results["expired_notifications_deleted"] = count

        # Soft-deleted API keys older than 1 year
        one_year_ago = timezone.now() - timedelta(days=365)
        count, _ = APIKey.objects.filter(
            is_deleted=True, is_active=False, updated_at__lt=one_year_ago
        ).delete()
        results["api_keys_deleted"] = count

        logger.info("cleanup_old_data: completed %s", results)
        return results

    except Exception as exc:
        logger.error("cleanup_old_data: error — %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name="core.cleanup_expired_api_keys",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def cleanup_expired_api_keys(self) -> dict:
    """Deactivate API keys that have passed their expiry date. Runs: daily at 01:00."""
    from .models import APIKey

    try:
        count = APIKey.objects.filter(
            is_active=True,
            is_deleted=False,
            expires_at__lt=timezone.now(),
        ).update(is_active=False)
        logger.info("cleanup_expired_api_keys: deactivated %d keys", count)
        return {"expired_keys_deactivated": count}
    except Exception as exc:
        logger.error("cleanup_expired_api_keys: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(name="core.unlock_expired_account_locks")
def unlock_expired_account_locks() -> dict:
    """Auto-unlock accounts whose lockout window has elapsed. Runs: hourly."""
    from .models import UserProfile

    now = timezone.now()
    qs = UserProfile.objects.filter(
        account_locked_until__lt=now,
        account_locked_until__isnull=False,
    )
    count = qs.count()
    qs.update(account_locked_until=None, failed_login_attempts=0)
    logger.info("unlock_expired_account_locks: unlocked %d accounts", count)
    return {"accounts_unlocked": count}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@shared_task(
    name="core.send_notification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification_email(self, notification_id: str) -> bool:
    """Send an HTML email for a single Notification record."""
    from .models import Notification

    try:
        notif = Notification.objects.select_related("user").get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.warning("send_notification_email: notification %s not found", notification_id)
        return False

    user = notif.user
    if not user.email:
        logger.warning("send_notification_email: user %s has no email", user.username)
        return False

    try:
        from django.core.mail import send_mail

        body = notif.message
        if notif.action_url:
            body += f"\n\nAction required: {notif.action_url}"

        send_mail(
            subject=f"[OryxShield] {notif.title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        notif.metadata.update({
            "email_sent": True,
            "email_sent_at": timezone.now().isoformat(),
        })
        notif.save(update_fields=["metadata"])
        logger.info("send_notification_email: sent to %s", user.email)
        return True

    except Exception as exc:
        logger.error("send_notification_email: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(name="core.send_bulk_notifications")
def send_bulk_notifications(
    user_ids: list,
    title: str,
    message: str,
    notification_type: str = "INFO",
    priority: str = "NORMAL",
) -> dict:
    """Bulk-create Notification records for a list of user IDs (batched, 1 000/chunk)."""
    from .models import Notification

    logger.info("send_bulk_notifications: %d users", len(user_ids))
    total = 0
    BATCH = 1000
    for i in range(0, len(user_ids), BATCH):
        batch = user_ids[i : i + BATCH]
        objects = [
            Notification(
                user_id=uid,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
            )
            for uid in batch
        ]
        created = Notification.objects.bulk_create(objects, ignore_conflicts=True)
        total += len(created)

    logger.info("send_bulk_notifications: created %d notifications", total)
    return {"notifications_created": total, "users_targeted": len(user_ids)}


@shared_task(name="core.send_report_to_admins")
def send_report_to_admins(subject: str, body: str) -> dict:
    """Send a plain-text report to all active staff users."""
    _alert_admins(subject, body)
    return {"status": "sent"}


# ---------------------------------------------------------------------------
# Monitoring & reporting
# ---------------------------------------------------------------------------

@shared_task(
    name="core.generate_system_report",
    bind=True,
    max_retries=2,
)
def generate_system_report(self) -> dict:
    """Generate and cache a daily system activity report. Runs: daily at 00:00."""
    from .models import AuditLog

    try:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        report = {
            "date": str(timezone.localdate()),
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
                "staff": User.objects.filter(is_staff=True).count(),
            },
            "activity": {
                "total_actions_today": AuditLog.objects.filter(timestamp__gte=today_start).count(),
                "logins_today": AuditLog.objects.filter(
                    timestamp__gte=today_start,
                    action=AuditLog.ActionType.LOGIN,
                ).count(),
                "failed_logins_today": AuditLog.objects.filter(
                    timestamp__gte=today_start,
                    action=AuditLog.ActionType.LOGIN_FAILED,
                ).count(),
            },
            "generated_at": timezone.now().isoformat(),
        }

        cache.set("daily_system_report", report, 86400)
        logger.info("generate_system_report: completed for %s", report["date"])
        return report

    except Exception as exc:
        logger.error("generate_system_report: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(name="core.calculate_system_metrics")
def calculate_system_metrics() -> dict:
    """Cache system metrics snapshot. Runs: every 15 minutes."""
    from .models import APIKey, AuditLog, Notification

    try:
        metrics = {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
                "staff": User.objects.filter(is_staff=True).count(),
            },
            "notifications": {
                "total": Notification.objects.count(),
                "unread": Notification.objects.filter(is_read=False).count(),
            },
            "api_keys": {
                "active": APIKey.objects.filter(is_active=True, is_deleted=False).count(),
            },
            "audit_logs": {
                "total": AuditLog.objects.count(),
                "last_hour": AuditLog.objects.filter(
                    timestamp__gte=timezone.now() - timedelta(hours=1)
                ).count(),
            },
            "timestamp": timezone.now().isoformat(),
        }
        cache.set("system_metrics", metrics, 900)  # 15 min TTL
        logger.info("calculate_system_metrics: updated")
        return metrics

    except Exception as exc:
        logger.error("calculate_system_metrics: %s", exc, exc_info=True)
        return {}


@shared_task(name="core.process_audit_log_analytics")
def process_audit_log_analytics() -> dict:
    """Aggregate audit log analytics for the last 24 hours. Runs: hourly."""
    from .models import AuditLog

    try:
        since = timezone.now() - timedelta(hours=24)

        by_action = list(
            AuditLog.objects.filter(timestamp__gte=since)
            .values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        top_users = list(
            AuditLog.objects.filter(timestamp__gte=since)
            .values("user__username")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        analytics = {
            "period_hours": 24,
            "by_action": by_action,
            "top_users": top_users,
            "generated_at": timezone.now().isoformat(),
        }
        cache.set("audit_log_analytics", analytics, 3600)
        logger.info("process_audit_log_analytics: completed")
        return analytics

    except Exception as exc:
        logger.error("process_audit_log_analytics: %s", exc, exc_info=True)
        return {}


@shared_task(name="core.health_check_services")
def health_check_services() -> dict:
    """Probe core service dependencies and cache results. Runs: every 5 minutes."""
    results: dict = {}

    # Database
    try:
        User.objects.count()
        results["database"] = "ok"
    except Exception as exc:
        results["database"] = f"error: {exc}"

    # Cache
    try:
        test_key = "health_check_probe"
        cache.set(test_key, "ok", 10)
        assert cache.get(test_key) == "ok"
        cache.delete(test_key)
        results["cache"] = "ok"
    except Exception as exc:
        results["cache"] = f"error: {exc}"

    # Celery (self-check: if we're running, Celery is alive)
    results["celery"] = "ok"

    results["timestamp"] = timezone.now().isoformat()
    overall_ok = all(v == "ok" for k, v in results.items() if k != "timestamp")
    results["overall"] = "ok" if overall_ok else "degraded"

    cache.set("service_health", results, 300)

    if not overall_ok:
        _alert_admins(
            "Service health degraded",
            f"Health check detected issues:\n{results}",
        )
        logger.warning("health_check_services: degraded — %s", results)
    else:
        logger.debug("health_check_services: all ok")

    return results


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@shared_task(name="core.check_inactive_users")
def check_inactive_users() -> dict:
    """
    Notify users who have not logged in for 30 days.
    Runs: daily at 09:00.
    """
    from .models import Notification

    cutoff = timezone.now() - timedelta(days=30)
    recent_notif_cutoff = timezone.now() - timedelta(days=30)

    users = (
        User.objects.filter(is_active=True, last_login__lt=cutoff)
        .exclude(
            notifications__title="Inactive Account Reminder",
            notifications__created_at__gte=recent_notif_cutoff,
        )
    )

    notifications = [
        Notification(
            user=user,
            title="Inactive Account Reminder",
            message=(
                "Your OryxShield account has been inactive for 30 days. "
                "Please log in to keep it active."
            ),
            notification_type=Notification.NotificationType.WARNING,
            priority=Notification.Priority.NORMAL,
        )
        for user in users
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    count = len(notifications)
    logger.info("check_inactive_users: notified %d users", count)
    return {"inactive_users_notified": count}


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

@shared_task(name="core.backup_database")
def backup_database() -> dict:
    """
    Trigger database backup procedure.
    On Railway this can invoke a management command or call a backup API.
    Runs: daily at 03:00.
    """
    logger.info("backup_database: initiating backup")
    # Extend this to call: management.call_command('dbbackup') or a Railway API.
    result = {
        "status": "initiated",
        "timestamp": timezone.now().isoformat(),
    }
    cache.set("last_backup_attempt", result, 86400)
    return result