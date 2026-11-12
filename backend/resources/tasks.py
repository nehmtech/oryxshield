"""
Celery background tasks for resources app.
"""
import logging
from celery import shared_task
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_stock_levels(self):
    """
    Scan all AVAILABLE inventory and flag records below reorder point.
    Generates risk_assessment Alerts for critical items.
    Runs hourly.
    """
    from .models import Inventory
    from risk_assessment.models import Alert

    try:
        logger.info("check_stock_levels: starting")
        alerts_generated = 0
        updated = 0

        for inventory in Inventory.objects.filter(is_deleted=False, status='AVAILABLE').select_related(
            'resource_item', 'facility__location'
        ):
            item = inventory.resource_item
            if inventory.quantity_available <= 0:
                new_status = 'OUT_OF_STOCK'
            elif inventory.quantity_available <= item.reorder_point:
                new_status = 'LOW_STOCK'
            else:
                continue  # still AVAILABLE, no change needed

            inventory.status = new_status
            inventory.save(update_fields=['status', 'updated_at'])
            updated += 1

            if item.is_critical:
                severity = 'CRITICAL' if new_status == 'OUT_OF_STOCK' else 'WARNING'
                Alert.objects.get_or_create(
                    alert_type='CAPACITY',
                    severity=severity,
                    title=f"Low Stock: {item.name} at {inventory.facility.name}",
                    defaults={
                        'description': (
                            f"{item.name} ({item.code}) at {inventory.facility.name} "
                            f"has {inventory.quantity_available} units remaining "
                            f"(reorder point: {item.reorder_point}). Status: {new_status}."
                        ),
                        'location': inventory.facility.location,
                    }
                )
                alerts_generated += 1

        logger.info(
            "check_stock_levels: done — %d records updated, %d alerts generated",
            updated, alerts_generated
        )
        return {'status': 'completed', 'updated': updated, 'alerts_generated': alerts_generated}

    except Exception as exc:
        logger.exception("check_stock_levels failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_expiring_items(self):
    """
    Notify facility managers of inventory expiring within 30 days.
    Marks inventory as EXPIRED where expiry_date has passed.
    Runs daily.
    """
    from .models import Inventory
    from core.models import Notification

    try:
        logger.info("check_expiring_items: starting")

        today = date.today()
        thirty_days = today + timedelta(days=30)

        # Mark already-expired records
        expired_count = Inventory.objects.filter(
            is_deleted=False,
            expiry_date__lt=today,
        ).exclude(status='EXPIRED').update(status='EXPIRED')

        # Notify about upcoming expiry
        expiring_qs = Inventory.objects.filter(
            is_deleted=False,
            expiry_date__isnull=False,
            expiry_date__gte=today,
            expiry_date__lte=thirty_days,
        ).select_related('resource_item', 'facility__facility_manager')

        notifications_sent = 0
        for inventory in expiring_qs:
            manager = inventory.facility.facility_manager
            if not manager:
                continue
            days_left = (inventory.expiry_date - today).days
            Notification.objects.create(
                user=manager,
                title=f"Expiring Stock: {inventory.resource_item.name}",
                message=(
                    f"{inventory.resource_item.name} (batch {inventory.batch_number or 'N/A'}) "
                    f"at {inventory.facility.name} expires on {inventory.expiry_date} "
                    f"({days_left} days remaining). Quantity: {inventory.quantity_available} "
                    f"{inventory.resource_item.unit_of_measure}."
                ),
                notification_type='WARNING',
            )
            notifications_sent += 1

        logger.info(
            "check_expiring_items: done — %d expired, %d notifications sent",
            expired_count, notifications_sent
        )
        return {
            'status': 'completed',
            'newly_expired': expired_count,
            'notifications_sent': notifications_sent,
        }

    except Exception as exc:
        logger.exception("check_expiring_items failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_capacity_metrics(self):
    """
    Recalculate occupancy_rate for the latest capacity record of each facility.
    Generates CRITICAL alerts for facilities at or above 90% occupancy.
    Runs every 4 hours.
    """
    from .models import FacilityCapacity, Facility
    from risk_assessment.models import Alert

    try:
        logger.info("update_capacity_metrics: starting")

        # Get the latest capacity record per facility
        facility_ids = Facility.objects.filter(
            is_deleted=False, is_operational=True
        ).values_list('id', flat=True)

        records_updated = 0
        alerts_generated = 0

        for fid in facility_ids:
            record = (
                FacilityCapacity.objects
                .filter(is_deleted=False, facility_id=fid)
                .order_by('-recorded_at')
                .select_related('facility__location')
                .first()
            )
            if not record:
                continue

            old_rate = record.occupancy_rate
            record.calculate_occupancy_rate()

            if record.occupancy_rate != old_rate:
                record.save(update_fields=['occupancy_rate', 'updated_at'])
                records_updated += 1

            if record.occupancy_rate is not None and record.occupancy_rate >= 90:
                severity = 'CRITICAL' if record.occupancy_rate >= 95 else 'WARNING'
                Alert.objects.get_or_create(
                    alert_type='CAPACITY',
                    severity=severity,
                    title=f"High Occupancy: {record.facility.name}",
                    defaults={
                        'description': (
                            f"{record.facility.name} is at {record.occupancy_rate}% bed occupancy "
                            f"({record.beds_occupied}/{record.beds_occupied + record.beds_available} beds)."
                        ),
                        'location': record.facility.location,
                    }
                )
                alerts_generated += 1

        logger.info(
            "update_capacity_metrics: done — %d records updated, %d alerts",
            records_updated, alerts_generated
        )
        return {
            'status': 'completed',
            'records_updated': records_updated,
            'alerts_generated': alerts_generated,
        }

    except Exception as exc:
        logger.exception("update_capacity_metrics failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_demand_forecasts(self):
    """
    Generate 30-day demand forecasts for all critical items at each location,
    based on actual issue movements over the past 30 days (×1.2 buffer).
    Supersedes previous current forecasts.
    Runs weekly.
    """
    from .models import DemandForecast, ResourceItem, StockMovement
    from core.models import Location

    try:
        logger.info("generate_demand_forecasts: starting")

        thirty_days_ago = timezone.now() - timedelta(days=30)
        forecast_date = date.today()
        critical_items = ResourceItem.objects.filter(is_deleted=False, is_critical=True)
        locations = Location.objects.filter(is_deleted=False)

        forecasts_generated = 0

        for item in critical_items:
            for location in locations:
                historical_usage = (
                    StockMovement.objects
                    .filter(
                        is_deleted=False,
                        resource_item=item,
                        movement_type='ISSUE',
                        movement_date__gte=thirty_days_ago,
                        from_facility__location=location,
                    )
                    .aggregate(total=Sum('quantity'))['total'] or 0
                )

                if historical_usage == 0:
                    continue

                predicted_demand = int(historical_usage * 1.2)

                # Supersede old current forecasts
                DemandForecast.objects.filter(
                    resource_item=item,
                    location=location,
                    is_current=True,
                    is_deleted=False,
                ).update(is_current=False)

                DemandForecast.objects.create(
                    resource_item=item,
                    location=location,
                    forecast_date=forecast_date,
                    forecast_period_days=30,
                    predicted_demand=predicted_demand,
                    confidence_level=75.0,
                    forecast_model='Historical Average +20%',
                    is_current=True,
                )
                forecasts_generated += 1

        logger.info("generate_demand_forecasts: done — %d forecasts created", forecasts_generated)
        return {'status': 'completed', 'forecasts_generated': forecasts_generated}

    except Exception as exc:
        logger.exception("generate_demand_forecasts failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_procurement_request(self, request_id):
    """
    Advance an APPROVED procurement request to ORDERED and notify the facility manager.
    Triggered by signal on approval.
    """
    from .models import ProcurementRequest
    from core.models import Notification

    try:
        try:
            proc = ProcurementRequest.objects.select_related(
                'requesting_facility__facility_manager', 'approved_by'
            ).get(id=request_id, is_deleted=False)
        except ProcurementRequest.DoesNotExist:
            logger.error("process_procurement_request: request %s not found", request_id)
            return {'status': 'error', 'message': f"Request {request_id} not found."}

        if proc.status != 'APPROVED':
            logger.warning(
                "process_procurement_request: request %s is not APPROVED (status=%s)",
                request_id, proc.status
            )
            return {'status': 'skipped', 'reason': f"Status is '{proc.status}', expected 'APPROVED'."}

        proc.status = 'ORDERED'
        proc.save(update_fields=['status', 'updated_at'])

        from core.models import AuditLog
        AuditLog.log(
            actor=proc.approved_by,
            action='PROCUREMENT_ORDERED',
            target_object_id=str(proc.id),
            target_content_type='ProcurementRequest',
            details={'request_number': proc.request_number}
        )

        manager = proc.requesting_facility.facility_manager
        if manager:
            Notification.objects.create(
                user=manager,
                title=f"Procurement Order Placed: {proc.request_number}",
                message=(
                    f"Your procurement request {proc.request_number} has been approved and "
                    f"the order has been placed. Required by: {proc.required_by_date}."
                ),
                notification_type='INFO',
            )

        logger.info(
            "process_procurement_request: request %s advanced to ORDERED",
            proc.request_number
        )
        return {'status': 'completed', 'request_number': proc.request_number}

    except Exception as exc:
        logger.exception("process_procurement_request failed for %s: %s", request_id, exc)
        raise self.retry(exc=exc)