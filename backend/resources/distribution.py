"""
Distribution utilities for resources app.

Provides allocation and transfer logic for moving supplies between facilities,
used by views (manual transfers) and by operational planning workflows.
"""
import uuid
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def transfer_stock(
    resource_item,
    from_facility,
    to_facility,
    quantity: int,
    actor,
    batch_number: str = '',
    notes: str = '',
) -> dict:
    """
    Transfer `quantity` units of `resource_item` from `from_facility` to `to_facility`.

    Atomically:
        1. Deducts from the source inventory record.
        2. Adds to the destination inventory record (creates if absent).
        3. Creates a StockMovement TRANSFER record.
        4. Creates an AuditLog entry.

    Returns:
        {'success': True, 'reference_number': str, 'new_from_qty': int, 'new_to_qty': int}

    Raises:
        ValueError  if quantity <= 0 or insufficient stock at source.
    """
    from .models import Inventory, StockMovement
    from core.models import AuditLog

    if quantity <= 0:
        raise ValueError("Transfer quantity must be positive.")

    with transaction.atomic():
        # Source inventory
        source = (
            Inventory.objects
            .select_for_update()
            .filter(
                is_deleted=False,
                facility=from_facility,
                resource_item=resource_item,
            )
            .order_by('-quantity_available')
            .first()
        )
        if not source or source.quantity_available < quantity:
            available = source.quantity_available if source else 0
            raise ValueError(
                f"Insufficient stock at {from_facility.name}: "
                f"requested {quantity}, available {available}."
            )

        source.quantity_available -= quantity
        source.save(update_fields=['quantity_available', 'updated_at'])

        # Destination inventory — get-or-create for the same item+batch
        dest, _ = Inventory.objects.get_or_create(
            facility=to_facility,
            resource_item=resource_item,
            batch_number=batch_number or source.batch_number,
            defaults={
                'quantity_available': 0,
                'unit_cost': source.unit_cost,
                'expiry_date': source.expiry_date,
                'storage_location': '',
            }
        )
        dest_qs = Inventory.objects.filter(pk=dest.pk).select_for_update()
        dest = dest_qs.get()
        dest.quantity_available += quantity
        dest.save(update_fields=['quantity_available', 'updated_at'])

        ref = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        movement = StockMovement.objects.create(
            movement_type='TRANSFER',
            resource_item=resource_item,
            from_facility=from_facility,
            to_facility=to_facility,
            quantity=quantity,
            batch_number=batch_number or source.batch_number,
            reference_number=ref,
            notes=notes or f"Transfer from {from_facility.name} to {to_facility.name}",
            recorded_by=actor,
        )

        AuditLog.log(
            actor=actor,
            action='STOCK_TRANSFERRED',
            target_object_id=str(movement.id),
            target_content_type='StockMovement',
            details={
                'item': resource_item.name,
                'from': from_facility.name,
                'to': to_facility.name,
                'quantity': quantity,
                'reference': ref,
            }
        )

    logger.info(
        "transfer_stock: %d × %s transferred %s → %s (ref=%s)",
        quantity, resource_item.name, from_facility.name, to_facility.name, ref
    )
    return {
        'success': True,
        'reference_number': ref,
        'new_from_qty': source.quantity_available,
        'new_to_qty': dest.quantity_available,
    }


def allocate_supplies_to_facilities(resource_item, available_qty: int, facilities: list, actor) -> list[dict]:
    """
    Distribute `available_qty` units of `resource_item` proportionally across `facilities`,
    weighted by each facility's current deficit (reorder_point - quantity_available, floor 0).

    Creates ISSUE movements from the first warehouse that holds the item.

    Returns a list of allocation dicts:
        [{'facility': str, 'allocated': int, 'reference': str}, ...]

    Facilities with no deficit receive nothing.
    """
    from .models import Inventory, Facility, StockMovement
    from core.models import AuditLog

    if available_qty <= 0 or not facilities:
        return []

    # Compute deficits
    deficits = {}
    for facility in facilities:
        inv = (
            Inventory.objects
            .filter(is_deleted=False, facility=facility, resource_item=resource_item)
            .order_by('-quantity_available')
            .first()
        )
        current_qty = inv.quantity_available if inv else 0
        deficit = max(0, resource_item.reorder_point - current_qty)
        if deficit > 0:
            deficits[facility] = deficit

    if not deficits:
        logger.info("allocate_supplies_to_facilities: no facilities have a deficit for %s", resource_item.name)
        return []

    total_deficit = sum(deficits.values())
    allocations = []

    with transaction.atomic():
        remaining = available_qty
        for facility, deficit in deficits.items():
            if remaining <= 0:
                break
            share = int((deficit / total_deficit) * available_qty)
            share = min(share, remaining)
            if share <= 0:
                continue

            ref = f"ISS-{uuid.uuid4().hex[:8].upper()}"
            StockMovement.objects.create(
                movement_type='ISSUE',
                resource_item=resource_item,
                to_facility=facility,
                quantity=share,
                reference_number=ref,
                notes=f"Proportional allocation — system distribution",
                recorded_by=actor,
            )

            # Update destination inventory
            dest, _ = Inventory.objects.get_or_create(
                facility=facility,
                resource_item=resource_item,
                batch_number='',
                defaults={'quantity_available': 0}
            )
            Inventory.objects.filter(pk=dest.pk).update(
                quantity_available=dest.quantity_available + share
            )

            AuditLog.log(
                actor=actor,
                action='STOCK_ALLOCATED',
                target_object_id=str(dest.id),
                target_content_type='Inventory',
                details={
                    'item': resource_item.name,
                    'facility': facility.name,
                    'quantity': share,
                    'reference': ref,
                }
            )

            allocations.append({
                'facility': facility.name,
                'allocated': share,
                'reference': ref,
            })
            remaining -= share

    logger.info(
        "allocate_supplies_to_facilities: distributed %d × %s across %d facilities",
        available_qty - remaining, resource_item.name, len(allocations)
    )
    return allocations