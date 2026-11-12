"""
Signal handlers for resources app.
"""
import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='resources.Inventory')
def sync_inventory_status(sender, instance, **kwargs):
    """
    Auto-update inventory status before save based on quantity and expiry.
    Does not call save() — mutates instance in place for the pre_save pipeline.
    """
    from .models import Inventory  # local import to avoid circular at module level

    today = timezone.now().date()

    # Expiry takes precedence
    if instance.expiry_date and instance.expiry_date < today:
        instance.status = 'EXPIRED'
        return

    if instance.quantity_available <= 0:
        instance.status = 'OUT_OF_STOCK'
    elif instance.quantity_available <= instance.resource_item.reorder_point:
        instance.status = 'LOW_STOCK'
    else:
        # Only reset to AVAILABLE if it is not currently RESERVED
        if instance.status not in ('RESERVED',):
            instance.status = 'AVAILABLE'


@receiver(post_save, sender='resources.ProcurementRequest')
def on_procurement_status_change(sender, instance, created, **kwargs):
    """
    When a procurement request transitions to APPROVED, enqueue the ordering task.
    """
    if created:
        return

    if instance.status == 'APPROVED':
        try:
            from .tasks import process_procurement_request
            process_procurement_request.delay(str(instance.id))
            logger.info(
                "on_procurement_status_change: enqueued process_procurement_request for %s",
                instance.request_number
            )
        except Exception:
            logger.exception(
                "on_procurement_status_change: failed to enqueue task for %s",
                instance.request_number
            )


@receiver(post_save, sender='resources.FacilityCapacity')
def on_capacity_recorded(sender, instance, created, **kwargs):
    """
    When a new capacity snapshot is saved, generate a risk_assessment Alert
    if occupancy rate is at or above 90%.
    """
    if not created:
        return

    if instance.occupancy_rate is None or instance.occupancy_rate < 90:
        return

    try:
        from risk_assessment.models import Alert

        severity = 'CRITICAL' if instance.occupancy_rate >= 95 else 'WARNING'
        Alert.objects.get_or_create(
            alert_type='CAPACITY',
            severity=severity,
            title=f"High Occupancy Alert: {instance.facility.name}",
            defaults={
                'description': (
                    f"{instance.facility.name} has reached {instance.occupancy_rate}% bed occupancy "
                    f"({instance.beds_occupied} of "
                    f"{instance.beds_occupied + instance.beds_available} beds occupied). "
                    f"Recorded at {instance.recorded_at.strftime('%Y-%m-%d %H:%M UTC')}."
                ),
                'location': instance.facility.location,
            }
        )
        logger.warning(
            "on_capacity_recorded: %s occupancy=%s — alert created",
            instance.facility.name, instance.occupancy_rate
        )
    except Exception:
        logger.exception(
            "on_capacity_recorded: failed to create alert for facility %s",
            instance.facility_id
        )