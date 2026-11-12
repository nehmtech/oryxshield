"""
Inventory tracking utilities for resources app.

Provides helpers for receiving stock, issuing stock, computing valuation,
and generating facility-level inventory summary reports.
"""
import uuid
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def receive_stock(
    resource_item,
    facility,
    quantity: int,
    actor,
    batch_number: str = '',
    expiry_date=None,
    unit_cost=None,
    storage_location: str = '',
    notes: str = '',
) -> dict:
    """
    Record a stock receipt: creates/updates an Inventory record and a RECEIPT StockMovement.

    Returns:
        {'success': True, 'reference_number': str, 'new_quantity': int}
    """
    from .models import Inventory, StockMovement
    from core.models import AuditLog

    if quantity <= 0:
        raise ValueError("Receipt quantity must be positive.")

    with transaction.atomic():
        inv, _ = Inventory.objects.get_or_create(
            facility=facility,
            resource_item=resource_item,
            batch_number=batch_number,
            defaults={
                'quantity_available': 0,
                'expiry_date': expiry_date,
                'unit_cost': unit_cost,
                'storage_location': storage_location,
            }
        )
        # Lock the row
        inv = Inventory.objects.select_for_update().get(pk=inv.pk)
        inv.quantity_available += quantity
        if unit_cost is not None:
            inv.unit_cost = unit_cost
        if expiry_date is not None:
            inv.expiry_date = expiry_date
        if storage_location:
            inv.storage_location = storage_location
        if inv.unit_cost and inv.quantity_available:
            inv.total_value = inv.unit_cost * inv.quantity_available
        inv.last_stock_check = timezone.now()
        inv.save(update_fields=[
            'quantity_available', 'unit_cost', 'expiry_date',
            'storage_location', 'total_value', 'last_stock_check', 'updated_at'
        ])

        ref = f"RCP-{uuid.uuid4().hex[:8].upper()}"
        StockMovement.objects.create(
            movement_type='RECEIPT',
            resource_item=resource_item,
            to_facility=facility,
            quantity=quantity,
            batch_number=batch_number,
            reference_number=ref,
            notes=notes or f"Stock received at {facility.name}",
            recorded_by=actor,
        )

        AuditLog.log(
            actor=actor,
            action='STOCK_RECEIVED',
            target_object_id=str(inv.id),
            target_content_type='Inventory',
            details={
                'item': resource_item.name,
                'facility': facility.name,
                'quantity': quantity,
                'batch': batch_number,
                'reference': ref,
            }
        )

    logger.info(
        "receive_stock: +%d × %s at %s (batch=%s, ref=%s)",
        quantity, resource_item.name, facility.name, batch_number, ref
    )
    return {'success': True, 'reference_number': ref, 'new_quantity': inv.quantity_available}


def issue_stock(
    resource_item,
    facility,
    quantity: int,
    actor,
    notes: str = '',
    batch_number: str = '',
) -> dict:
    """
    Issue (deduct) `quantity` of `resource_item` from `facility` inventory.
    FIFO: prefers records with the earliest expiry date.

    Returns:
        {'success': True, 'reference_number': str, 'new_quantity': int}
    """
    from .models import Inventory, StockMovement
    from core.models import AuditLog

    if quantity <= 0:
        raise ValueError("Issue quantity must be positive.")

    with transaction.atomic():
        qs = (
            Inventory.objects
            .select_for_update()
            .filter(
                is_deleted=False,
                facility=facility,
                resource_item=resource_item,
                quantity_available__gt=0,
            )
            .order_by('expiry_date', 'created_at')
        )
        if batch_number:
            qs = qs.filter(batch_number=batch_number)

        total_available = sum(inv.quantity_available for inv in qs)
        if total_available < quantity:
            raise ValueError(
                f"Insufficient stock at {facility.name}: "
                f"requested {quantity}, available {total_available}."
            )

        remaining = quantity
        for inv in qs:
            if remaining <= 0:
                break
            deduct = min(inv.quantity_available, remaining)
            inv.quantity_available -= deduct
            inv.save(update_fields=['quantity_available', 'updated_at'])
            remaining -= deduct

        ref = f"ISS-{uuid.uuid4().hex[:8].upper()}"
        movement = StockMovement.objects.create(
            movement_type='ISSUE',
            resource_item=resource_item,
            from_facility=facility,
            quantity=quantity,
            batch_number=batch_number,
            reference_number=ref,
            notes=notes or f"Stock issued from {facility.name}",
            recorded_by=actor,
        )

        AuditLog.log(
            actor=actor,
            action='STOCK_ISSUED',
            target_object_id=str(movement.id),
            target_content_type='StockMovement',
            details={
                'item': resource_item.name,
                'facility': facility.name,
                'quantity': quantity,
                'reference': ref,
            }
        )

    # Recompute remaining qty for return value
    remaining_qty = (
        Inventory.objects
        .filter(is_deleted=False, facility=facility, resource_item=resource_item)
        .aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('quantity_available'))['total'] or 0
    )
    logger.info(
        "issue_stock: -%d × %s from %s (ref=%s)",
        quantity, resource_item.name, facility.name, ref
    )
    return {'success': True, 'reference_number': ref, 'new_quantity': remaining_qty}


def get_inventory_valuation(facility) -> dict:
    """
    Compute the total inventory value at a facility, broken down by category.

    Returns:
        {
            'facility': str,
            'total_value': float,
            'by_category': [{'category': str, 'value': float, 'item_count': int}, ...]
        }
    """
    from .models import Inventory

    records = (
        Inventory.objects
        .filter(is_deleted=False, facility=facility)
        .select_related('resource_item__category')
    )

    category_totals: dict = {}
    grand_total = 0.0

    for inv in records:
        cat_name = inv.resource_item.category.name
        value = float(inv.total_value or 0)
        grand_total += value

        if cat_name not in category_totals:
            category_totals[cat_name] = {'value': 0.0, 'item_count': 0}
        category_totals[cat_name]['value'] += value
        category_totals[cat_name]['item_count'] += 1

    by_category = [
        {'category': cat, 'value': round(data['value'], 2), 'item_count': data['item_count']}
        for cat, data in sorted(category_totals.items(), key=lambda x: x[1]['value'], reverse=True)
    ]

    return {
        'facility': facility.name,
        'total_value': round(grand_total, 2),
        'by_category': by_category,
    }


def generate_stock_report(facility) -> dict:
    """
    Generate a comprehensive stock status report for a facility.

    Returns counts and lists across all inventory status categories.
    """
    from .models import Inventory
    from datetime import date, timedelta

    records = (
        Inventory.objects
        .filter(is_deleted=False, facility=facility)
        .select_related('resource_item')
    )

    report = {
        'facility': facility.name,
        'generated_at': timezone.now().isoformat(),
        'totals': {
            'AVAILABLE': 0,
            'LOW_STOCK': 0,
            'OUT_OF_STOCK': 0,
            'EXPIRED': 0,
            'RESERVED': 0,
        },
        'critical_low_stock': [],
        'expiring_within_30_days': [],
        'valuation': get_inventory_valuation(facility),
    }

    cutoff = date.today() + timedelta(days=30)
    today = date.today()

    for inv in records:
        report['totals'][inv.status] = report['totals'].get(inv.status, 0) + 1

        if inv.status in ('LOW_STOCK', 'OUT_OF_STOCK') and inv.resource_item.is_critical:
            report['critical_low_stock'].append({
                'item': inv.resource_item.name,
                'code': inv.resource_item.code,
                'quantity': inv.quantity_available,
                'reorder_point': inv.resource_item.reorder_point,
                'status': inv.status,
            })

        if inv.expiry_date and today <= inv.expiry_date <= cutoff:
            report['expiring_within_30_days'].append({
                'item': inv.resource_item.name,
                'batch': inv.batch_number,
                'expiry_date': inv.expiry_date.isoformat(),
                'quantity': inv.quantity_available,
            })

    return report