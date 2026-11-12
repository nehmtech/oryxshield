"""
OryxShield - Celery Configuration
==========================================

Configures Celery for asynchronous task processing, periodic scheduling,
and result tracking.

Task queues (priority order):
  high_priority   — anomaly detection, escalation, emergency alerts, lab results
  default         — risk scores, inventory, dashboard, contact tracing
  ml_tasks        — ML model training, forecasting, predictive analysis
  notifications   — SMS, email, push notification sending
  low_priority    — cleanup, archival, external syncs

To start workers in development (after installing Redis):
    celery -A config worker -l info --pool=solo

To start workers in production (Railway Procfile):
    celery -A config worker -l info -Q high_priority,default -c 4
    celery -A config worker -l info -Q ml_tasks -c 2
    celery -A config worker -l info -Q notifications -c 4
    celery -A config worker -l info -Q low_priority -c 1
    celery -A config beat -l info

Monitor with Flower:
    celery -A config flower --port=5555
"""

import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_success,
    task_retry,
    worker_ready,
    worker_shutdown,
)
from kombu import Queue, Exchange
from decouple import config

logger = logging.getLogger("celery")

# =============================================================================
# DJANGO SETTINGS MODULE
# =============================================================================

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    config("DJANGO_SETTINGS_MODULE", default="config.settings.production"),
)

# =============================================================================
# CELERY APP
# =============================================================================

app = Celery("oryxshield")

# Load config from Django settings (all CELERY_* keys)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every registered Django app
app.autodiscover_tasks()


# =============================================================================
# TASK QUEUES
# =============================================================================

app.conf.task_queues = (
    Queue(
        "high_priority",
        Exchange("high_priority", type="direct"),
        routing_key="high_priority",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "default",
        Exchange("default", type="direct"),
        routing_key="default",
        queue_arguments={"x-max-priority": 5},
    ),
    Queue(
        "ml_tasks",
        Exchange("ml_tasks", type="direct"),
        routing_key="ml_tasks",
        queue_arguments={"x-max-priority": 5},
    ),
    Queue(
        "notifications",
        Exchange("notifications", type="direct"),
        routing_key="notifications",
        queue_arguments={"x-max-priority": 7},
    ),
    Queue(
        "low_priority",
        Exchange("low_priority", type="direct"),
        routing_key="low_priority",
        queue_arguments={"x-max-priority": 1},
    ),
)

app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"


# =============================================================================
# TASK ROUTING
# =============================================================================

app.conf.task_routes = {
    # ---- HIGH PRIORITY ----
    "surveillance.tasks.run_anomaly_detection":      {"queue": "high_priority", "priority": 9},
    "surveillance.tasks.process_incoming_data":      {"queue": "high_priority", "priority": 9},
    "surveillance.tasks.process_critical_alert":     {"queue": "high_priority", "priority": 10},
    "risk_assessment.tasks.calculate_all_risk_scores":{"queue": "high_priority", "priority": 8},
    "risk_assessment.tasks.monitor_alert_thresholds":{"queue": "high_priority", "priority": 9},
    "response.tasks.check_escalation_triggers":      {"queue": "high_priority", "priority": 10},
    "response.tasks.execute_protocol_action":        {"queue": "high_priority", "priority": 9},
    "communications.tasks.send_emergency_alert":     {"queue": "high_priority", "priority": 10},
    "communications.tasks.process_pending_notifications": {"queue": "high_priority", "priority": 8},
    "operations.tasks.process_lab_results":          {"queue": "high_priority", "priority": 8},
    "resources.tasks.check_critical_stock_levels":   {"queue": "high_priority", "priority": 7},

    # ---- DEFAULT ----
    "surveillance.tasks.update_hotspot_analysis":    {"queue": "default", "priority": 7},
    "risk_assessment.tasks.generate_risk_forecasts": {"queue": "default", "priority": 5},
    "response.tasks.monitor_protocol_execution":     {"queue": "default", "priority": 7},
    "response.tasks.check_de_escalation_conditions": {"queue": "default", "priority": 6},
    "resources.tasks.monitor_facility_capacity":     {"queue": "default", "priority": 6},
    "resources.tasks.update_inventory_levels":       {"queue": "default", "priority": 5},
    "analytics.tasks.update_dashboard_metrics":      {"queue": "default", "priority": 6},
    "analytics.tasks.generate_epidemiological_curves":{"queue": "default", "priority": 4},
    "analytics.tasks.generate_daily_situation_report":{"queue": "default", "priority": 5},
    "operations.tasks.update_contact_tracing_status":{"queue": "default", "priority": 7},
    "operations.tasks.monitor_quarantine_compliance":{"queue": "default", "priority": 5},
    "operations.tasks.update_vaccination_coverage":  {"queue": "default", "priority": 4},
    "coordination.tasks.check_task_deadlines":       {"queue": "default", "priority": 6},
    "coordination.tasks.send_agency_status_updates": {"queue": "default", "priority": 5},

    # ---- ML TASKS ----
    "risk_assessment.tasks.update_predictive_models":{"queue": "ml_tasks", "priority": 5},
    "resources.tasks.predict_resource_demand":       {"queue": "ml_tasks", "priority": 4},
    "analytics.tasks.run_ml_analysis":              {"queue": "ml_tasks", "priority": 4},
    "analytics.tasks.generate_weekly_trend_analysis":{"queue": "ml_tasks", "priority": 3},

    # ---- NOTIFICATIONS ----
    "communications.tasks.send_sms":                 {"queue": "notifications", "priority": 7},
    "communications.tasks.send_email":               {"queue": "notifications", "priority": 6},
    "communications.tasks.send_push_notification":   {"queue": "notifications", "priority": 7},
    "communications.tasks.broadcast_public_alert":   {"queue": "notifications", "priority": 9},

    # ---- LOW PRIORITY ----
    "core.tasks.cleanup_old_data":                   {"queue": "low_priority", "priority": 1},
    "core.tasks.optimize_database":                  {"queue": "low_priority", "priority": 1},
    "core.tasks.export_archive":                     {"queue": "low_priority", "priority": 2},
    "integrations.tasks.sync_all_data_sources":      {"queue": "low_priority", "priority": 3},
    "integrations.tasks.sync_dhis2_data":            {"queue": "low_priority", "priority": 3},
    "integrations.tasks.sync_sormas_data":           {"queue": "low_priority", "priority": 3},
    "integrations.tasks.submit_who_report":          {"queue": "low_priority", "priority": 2},
    "communications.tasks.cleanup_old_notifications":{"queue": "low_priority", "priority": 2},
    "analytics.tasks.archive_old_reports":           {"queue": "low_priority", "priority": 1},
}


# =============================================================================
# BEAT SCHEDULE  — Periodic Tasks
# =============================================================================

app.conf.beat_schedule = {

    # ── SURVEILLANCE ──────────────────────────────────────────────────────────
    "surveillance-anomaly-detection-every-5min": {
        "task": "surveillance.tasks.run_anomaly_detection",
        "schedule": 300.0,
        "options": {"queue": "high_priority", "priority": 9},
    },
    "surveillance-process-incoming-data-every-1min": {
        "task": "surveillance.tasks.process_incoming_data",
        "schedule": 60.0,
        "options": {"queue": "high_priority", "priority": 9},
    },
    "surveillance-update-hotspot-analysis-every-10min": {
        "task": "surveillance.tasks.update_hotspot_analysis",
        "schedule": 600.0,
        "options": {"queue": "default", "priority": 7},
    },

    # ── RISK ASSESSMENT ───────────────────────────────────────────────────────
    "risk-calculate-scores-every-10min": {
        "task": "risk_assessment.tasks.calculate_all_risk_scores",
        "schedule": 600.0,
        "options": {"queue": "high_priority", "priority": 8},
    },
    "risk-monitor-thresholds-every-2min": {
        "task": "risk_assessment.tasks.monitor_alert_thresholds",
        "schedule": 120.0,
        "options": {"queue": "high_priority", "priority": 9},
    },
    "risk-update-predictive-models-every-6h": {
        "task": "risk_assessment.tasks.update_predictive_models",
        "schedule": crontab(hour="*/6"),
        "options": {"queue": "ml_tasks", "priority": 5},
    },
    "risk-daily-forecast-at-3am": {
        "task": "risk_assessment.tasks.generate_risk_forecasts",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "ml_tasks", "priority": 5},
    },

    # ── RESPONSE ──────────────────────────────────────────────────────────────
    "response-check-escalation-every-1min": {
        "task": "response.tasks.check_escalation_triggers",
        "schedule": 60.0,
        "options": {"queue": "high_priority", "priority": 10},
    },
    "response-monitor-protocol-execution-every-2min": {
        "task": "response.tasks.monitor_protocol_execution",
        "schedule": 120.0,
        "options": {"queue": "default", "priority": 7},
    },
    "response-check-de-escalation-every-5min": {
        "task": "response.tasks.check_de_escalation_conditions",
        "schedule": 300.0,
        "options": {"queue": "default", "priority": 6},
    },

    # ── RESOURCES ─────────────────────────────────────────────────────────────
    "resources-monitor-capacity-every-15min": {
        "task": "resources.tasks.monitor_facility_capacity",
        "schedule": 900.0,
        "options": {"queue": "default", "priority": 6},
    },
    "resources-update-inventory-every-10min": {
        "task": "resources.tasks.update_inventory_levels",
        "schedule": 600.0,
        "options": {"queue": "default", "priority": 5},
    },
    "resources-check-critical-stock-every-5min": {
        "task": "resources.tasks.check_critical_stock_levels",
        "schedule": 300.0,
        "options": {"queue": "high_priority", "priority": 7},
    },
    "resources-predict-demand-every-4h": {
        "task": "resources.tasks.predict_resource_demand",
        "schedule": crontab(hour="*/4"),
        "options": {"queue": "ml_tasks", "priority": 4},
    },

    # ── COMMUNICATIONS ────────────────────────────────────────────────────────
    "comms-process-pending-notifications-every-2min": {
        "task": "communications.tasks.process_pending_notifications",
        "schedule": 120.0,
        "options": {"queue": "high_priority", "priority": 8},
    },
    "comms-retry-failed-messages-every-5min": {
        "task": "communications.tasks.retry_failed_messages",
        "schedule": 300.0,
        "options": {"queue": "default", "priority": 5},
    },
    "comms-cleanup-old-notifications-daily-1am": {
        "task": "communications.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=1, minute=0),
        "options": {"queue": "low_priority", "priority": 2},
    },

    # ── ANALYTICS ─────────────────────────────────────────────────────────────
    "analytics-daily-sitrep-at-6am": {
        "task": "analytics.tasks.generate_daily_situation_report",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "default", "priority": 5},
    },
    "analytics-weekly-trends-monday-7am": {
        "task": "analytics.tasks.generate_weekly_trend_analysis",
        "schedule": crontab(day_of_week=1, hour=7, minute=0),
        "options": {"queue": "ml_tasks", "priority": 3},
    },
    "analytics-update-dashboard-every-5min": {
        "task": "analytics.tasks.update_dashboard_metrics",
        "schedule": 300.0,
        "options": {"queue": "default", "priority": 6},
    },
    "analytics-epi-curves-hourly": {
        "task": "analytics.tasks.generate_epidemiological_curves",
        "schedule": 3600.0,
        "options": {"queue": "default", "priority": 4},
    },

    # ── OPERATIONS ────────────────────────────────────────────────────────────
    "operations-contact-tracing-status-every-5min": {
        "task": "operations.tasks.update_contact_tracing_status",
        "schedule": 300.0,
        "options": {"queue": "default", "priority": 7},
    },
    "operations-monitor-quarantine-hourly": {
        "task": "operations.tasks.monitor_quarantine_compliance",
        "schedule": 3600.0,
        "options": {"queue": "default", "priority": 5},
    },
    "operations-process-lab-results-every-5min": {
        "task": "operations.tasks.process_lab_results",
        "schedule": 300.0,
        "options": {"queue": "high_priority", "priority": 8},
    },
    "operations-vaccination-coverage-every-6h": {
        "task": "operations.tasks.update_vaccination_coverage",
        "schedule": crontab(hour="*/6"),
        "options": {"queue": "default", "priority": 4},
    },

    # ── COORDINATION ──────────────────────────────────────────────────────────
    "coordination-agency-status-hourly": {
        "task": "coordination.tasks.send_agency_status_updates",
        "schedule": 3600.0,
        "options": {"queue": "default", "priority": 5},
    },
    "coordination-check-task-deadlines-every-10min": {
        "task": "coordination.tasks.check_task_deadlines",
        "schedule": 600.0,
        "options": {"queue": "default", "priority": 6},
    },
    "coordination-daily-summary-at-8am": {
        "task": "coordination.tasks.generate_coordination_summary",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "default", "priority": 4},
    },

    # ── INTEGRATIONS ──────────────────────────────────────────────────────────
    "integrations-sync-all-sources-hourly": {
        "task": "integrations.tasks.sync_all_data_sources",
        "schedule": crontab(minute=5),   # :05 of every hour
        "options": {"queue": "low_priority", "priority": 3},
    },
    "integrations-submit-who-report-daily-midnight": {
        "task": "integrations.tasks.submit_who_report",
        "schedule": crontab(hour=0, minute=30),
        "options": {"queue": "low_priority", "priority": 2},
    },

    # ── MAINTENANCE ───────────────────────────────────────────────────────────
    "core-cleanup-old-data-sunday-2am": {
        "task": "core.tasks.cleanup_old_data",
        "schedule": crontab(day_of_week=0, hour=2, minute=0),
        "options": {"queue": "low_priority", "priority": 1},
    },
    "core-optimize-database-sunday-3am": {
        "task": "core.tasks.optimize_database",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
        "options": {"queue": "low_priority", "priority": 1},
    },
}


# =============================================================================
# GENERAL CELERY CONFIGURATION
# =============================================================================

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,         # 30 min hard limit
    task_soft_time_limit=25 * 60,    # 25 min soft limit (raises SoftTimeLimitExceeded)

    # Result
    result_expires=3600 * 24 * 7,   # 7 days
    result_extended=True,            # Store task name, args, kwargs in result

    # Worker
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,  # Restart after 1000 tasks (prevent leaks)
    worker_disable_rate_limits=False,

    # Reliability
    task_acks_late=True,              # Ack only after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker crashes

    # Retry
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,       # Max 10-min wait between retries
    task_retry_jitter=True,
    task_max_retries=3,

    # Rate limiting
    task_default_rate_limit="1000/m",

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Compression
    task_compression="gzip",
    result_compression="gzip",

    # Broker
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_heartbeat=30,
    broker_pool_limit=10,

    # Beat
    beat_max_loop_interval=5,
)


# =============================================================================
# SIGNALS
# =============================================================================

@task_failure.connect
def on_task_failure(
    sender=None, task_id=None, exception=None,
    args=None, kwargs=None, traceback=None, **_kw
):
    """Log failures and track failure rates per task."""
    from django.core.cache import cache

    logger.error(
        "Task %s [%s] FAILED — %s: %s",
        sender.name, task_id, type(exception).__name__, exception,
        exc_info=True,
        extra={"task_name": sender.name, "task_id": task_id},
    )

    # Increment failure counter (per task, rolling 1-hour window)
    key = f"celery:failures:{sender.name}"
    count = (cache.get(key) or 0) + 1
    cache.set(key, count, 3600)

    if count >= 10:
        logger.critical(
            "🚨 High failure rate: task %s has failed %d times in the last hour.",
            sender.name, count,
        )


@task_success.connect
def on_task_success(sender=None, result=None, **_kw):
    """Reset failure counter on success."""
    from django.core.cache import cache

    cache.delete(f"celery:failures:{sender.name}")


@task_retry.connect
def on_task_retry(sender=None, reason=None, **_kw):
    """Log retry attempts."""
    logger.warning(
        "Task %s is being retried — %s",
        sender.name, reason,
        extra={"task_name": sender.name},
    )


@worker_ready.connect
def on_worker_ready(sender=None, **_kw):
    logger.info("✅ Celery worker ready: %s", sender)


@worker_shutdown.connect
def on_worker_shutdown(sender=None, **_kw):
    logger.info("🛑 Celery worker shutting down: %s", sender)


# =============================================================================
# DEBUG TASK
# =============================================================================

@app.task(bind=True, name="debug.ping")
def debug_task(self):
    """
    Smoke-test task. Usage:
        from config.celery import debug_task
        result = debug_task.delay()
        print(result.get())
    """
    return {
        "status": "pong",
        "worker": self.request.hostname,
        "task_id": self.request.id,
    }