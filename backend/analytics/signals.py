"""
OryxShield - Analytics Signal Handlers
===============================================

Signal handlers for automated analytics workflows.

Handlers:
    data_export_created_handler                   – queue async export on PENDING creation
    epidemiological_model_created_handler         – auto-calculate R0 on new model
    epidemiological_model_simulation_completed_handler – invalidate model cache on simulation done
    indicator_value_created_handler               – compute target variance on new value
    statistical_report_published_handler          – invalidate report caches on publish
    dashboard_updated_handler                     – invalidate dashboard cache on save
    dashboard_refresh_handler                     – stamp last_refreshed_at on auto-refresh save
    spatial_analysis_completed_handler            – invalidate spatial cache on results
    data_export_deleted_handler                   – clean up export file on delete
    statistical_report_deleted_handler            – clean up report file on delete
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DATA EXPORT
# =============================================================================

@receiver(post_save, sender='analytics.DataExport')
def data_export_created_handler(sender, instance, created, **kwargs):
    """Queue processing task when a new PENDING DataExport is created."""
    if not (created and instance.status == 'PENDING'):
        return
    try:
        from .tasks import process_data_export
        task = process_data_export.delay(str(instance.id))
        logger.info("Queued export processing: id=%s task=%s", instance.id, task.id)
    except ImportError:
        logger.error("Cannot queue export %s – Celery not available", instance.id)
    except Exception as exc:
        logger.error("Error queuing export %s: %s", instance.id, exc, exc_info=True)


@receiver(post_delete, sender='analytics.DataExport')
def data_export_deleted_handler(sender, instance, **kwargs):
    """Delete the associated file when a DataExport record is hard-deleted."""
    if instance.file:
        try:
            instance.file.delete(save=False)
            logger.info("Deleted export file for id=%s", instance.id)
        except Exception as exc:
            logger.warning("Could not delete export file for id=%s: %s", instance.id, exc)


# =============================================================================
# EPIDEMIOLOGICAL MODEL
# =============================================================================

@receiver(post_save, sender='analytics.EpidemiologicalModel')
def epidemiological_model_created_handler(sender, instance, created, **kwargs):
    """Auto-calculate R0 for compartmental models on creation."""
    if not created:
        return
    try:
        if instance.model_type in ('SIR', 'SEIR', 'SIRS', 'SEIRS', 'SIS'):
            beta  = instance.parameters.get('beta')
            gamma = instance.parameters.get('gamma')
            if beta and gamma and gamma > 0:
                from decimal import Decimal
                r0 = Decimal(str(beta / gamma))
                type(instance).objects.filter(pk=instance.pk).update(
                    basic_reproduction_number=r0)
                logger.info("R0 calculated for model %s: %s", instance.name, r0)

        logger.info("Created epi model: %s (type=%s)", instance.name, instance.model_type)

    except Exception as exc:
        logger.error("R0 calculation error for model %s: %s",
                     instance.id, exc, exc_info=True)


@receiver(post_save, sender='analytics.EpidemiologicalModel')
def epidemiological_model_simulation_completed_handler(sender, instance, created, **kwargs):
    """Invalidate model and dashboard caches when a simulation completes."""
    if created or not instance.simulation_completed_at:
        return
    try:
        cache.delete(f"analytics:model:{instance.id}:results")
        cache.delete('analytics:dashboard:overview')
        logger.debug("Cleared simulation cache for model id=%s", instance.id)
    except Exception as exc:
        logger.warning("Cache clear error for model %s: %s", instance.id, exc)


# =============================================================================
# INDICATOR VALUE
# =============================================================================

@receiver(post_save, sender='analytics.IndicatorValue')
def indicator_value_created_handler(sender, instance, created, **kwargs):
    """Compute variance_from_target and target_achieved on new IndicatorValue."""
    if not created:
        return
    try:
        indicator = instance.indicator
        if not indicator.target_value:
            return

        variance = instance.value - indicator.target_value
        direction = indicator.target_direction

        if direction == 'INCREASE':
            achieved = instance.value >= indicator.target_value
        elif direction == 'DECREASE':
            achieved = instance.value <= indicator.target_value
        else:  # MAINTAIN – within 10 % of target
            tolerance = abs(float(indicator.target_value) * 0.1)
            achieved  = abs(float(variance)) <= tolerance

        type(instance).objects.filter(pk=instance.pk).update(
            variance_from_target=variance,
            target_achieved=achieved,
        )

        logger.info(
            "Indicator value recorded: %s = %s (target=%s, achieved=%s)",
            indicator.name, instance.value, indicator.target_value, achieved)

    except Exception as exc:
        logger.error("Error processing indicator value %s: %s",
                     instance.id, exc, exc_info=True)


# =============================================================================
# STATISTICAL REPORT
# =============================================================================

@receiver(post_save, sender='analytics.StatisticalReport')
def statistical_report_published_handler(sender, instance, created, **kwargs):
    """Invalidate report caches when a report is published."""
    if created or not instance.is_published:
        return
    try:
        cache.delete('analytics:reports:published')
        cache.delete('analytics:dashboard:overview')
        logger.info("Published report: %s (id=%s)", instance.title, instance.id)
    except Exception as exc:
        logger.warning("Cache clear error after report publish %s: %s", instance.id, exc)


@receiver(post_delete, sender='analytics.StatisticalReport')
def statistical_report_deleted_handler(sender, instance, **kwargs):
    """Delete attached report file when a StatisticalReport is hard-deleted."""
    if instance.report_file:
        try:
            instance.report_file.delete(save=False)
            logger.info("Deleted report file for id=%s", instance.id)
        except Exception as exc:
            logger.warning("Could not delete report file for id=%s: %s", instance.id, exc)


# =============================================================================
# DASHBOARD
# =============================================================================

@receiver(post_save, sender='analytics.Dashboard')
def dashboard_updated_handler(sender, instance, created, **kwargs):
    """Invalidate per-dashboard and per-user dashboard list caches."""
    try:
        cache.delete(f"analytics:dashboard:{instance.id}")
        cache.delete(f"analytics:dashboards:user:{instance.owner_id}")
        action = 'Created' if created else 'Updated'
        logger.debug("%s dashboard: %s (id=%s)", action, instance.name, instance.id)
    except Exception as exc:
        logger.warning("Dashboard cache clear error id=%s: %s", instance.id, exc)


@receiver(post_save, sender='analytics.Dashboard')
def dashboard_refresh_handler(sender, instance, created, **kwargs):
    """Stamp last_refreshed_at for auto-refresh dashboards without re-triggering signals."""
    if created or not instance.auto_refresh:
        return
    try:
        type(instance).objects.filter(pk=instance.pk).update(
            last_refreshed_at=timezone.now())
    except Exception as exc:
        logger.warning("Refresh timestamp error for dashboard %s: %s", instance.id, exc)


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

@receiver(post_save, sender='analytics.SpatialAnalysis')
def spatial_analysis_completed_handler(sender, instance, created, **kwargs):
    """Invalidate spatial analysis cache when results are saved."""
    if created or not instance.results:
        return
    try:
        cache.delete(f"analytics:spatial:{instance.id}")
        logger.debug("Spatial analysis cache cleared: id=%s type=%s",
                     instance.id, instance.analysis_type)
    except Exception as exc:
        logger.warning("Spatial cache clear error id=%s: %s", instance.id, exc)