"""
Procurement utilities for resources app.

Provides helpers for estimating costs, selecting suppliers, validating requests,
and computing procurement analytics. Consumed by views, tasks, and admin workflows.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg, Count

logger = logging.getLogger(__name__)


def estimate_request_cost(procurement_request) -> Decimal:
    """
    Estimate total cost of a ProcurementRequest from its line items.

    Uses unit_cost from ProcurementItem where set, else falls back to
    the ResourceItem default unit_cost.

    Saves the estimated_cost on the request and returns the value.
    """
    total = Decimal('0.00')
    for item in procurement_request.items.all():
        unit_price = item.unit_cost or item.resource_item.unit_cost or Decimal('0.00')
        qty = item.quantity_approved if item.quantity_approved is not None else item.quantity_requested
        line_total = unit_price * qty
        item.total_cost = line_total
        item.save(update_fields=['total_cost', 'updated_at'])
        total += line_total

    procurement_request.estimated_cost = total
    procurement_request.save(update_fields=['estimated_cost', 'updated_at'])
    return total


def find_best_supplier(resource_item) -> object | None:
    """
    Return the best approved, active supplier for `resource_item`,
    ranked by reliability_rating (descending), then name.

    Returns None if no approved supplier is found.
    """
    from .models import Supplier

    return (
        Supplier.objects
        .filter(
            is_deleted=False,
            is_approved=True,
            is_active=True,
            supplies=resource_item,
        )
        .order_by('-reliability_rating', 'name')
        .first()
    )


def validate_procurement_request(procurement_request) -> list[str]:
    """
    Run validation checks on a ProcurementRequest before submission.

    Returns a list of error strings. Empty list means valid.
    """
    errors = []

    if not procurement_request.items.exists():
        errors.append("Procurement request has no line items.")

    if procurement_request.required_by_date < timezone.now().date():
        errors.append("Required-by date is in the past.")

    if not procurement_request.justification.strip():
        errors.append("Justification is required.")

    for item in procurement_request.items.all():
        if item.quantity_requested <= 0:
            errors.append(
                f"Item '{item.resource_item.name}' has invalid quantity: {item.quantity_requested}."
            )

    return errors


def get_procurement_analytics(days: int = 90) -> dict:
    """
    Return procurement statistics for the last `days` days.

    Returns a dict with counts, averages, and breakdowns by status and priority.
    """
    from .models import ProcurementRequest

    since = timezone.now() - __import__('datetime').timedelta(days=days)
    qs = ProcurementRequest.objects.filter(
        is_deleted=False,
        requested_date__gte=since,
    )

    total = qs.count()
    if total == 0:
        return {
            'period_days': days,
            'total_requests': 0,
            'total_estimated_cost': '0.00',
            'total_actual_cost': '0.00',
            'by_status': {},
            'by_priority': {},
            'avg_days_to_approval': None,
        }

    total_estimated = qs.aggregate(s=Sum('estimated_cost'))['s'] or Decimal('0.00')
    total_actual = qs.aggregate(s=Sum('actual_cost'))['s'] or Decimal('0.00')

    by_status = dict(
        qs.values('status').annotate(count=Count('id')).values_list('status', 'count')
    )
    by_priority = dict(
        qs.values('priority').annotate(count=Count('id')).values_list('priority', 'count')
    )

    # Days from requested_date to approval (for APPROVED/ORDERED/DELIVERED)
    approved_qs = qs.filter(status__in=('APPROVED', 'ORDERED', 'DELIVERED'))
    avg_days = None
    if approved_qs.exists():
        durations = []
        for req in approved_qs:
            # updated_at approximates approval time for now (no separate approved_at field)
            delta = (req.updated_at.date() - req.requested_date.date()).days
            durations.append(delta)
        avg_days = round(sum(durations) / len(durations), 1) if durations else None

    return {
        'period_days': days,
        'total_requests': total,
        'total_estimated_cost': str(total_estimated),
        'total_actual_cost': str(total_actual),
        'by_status': by_status,
        'by_priority': by_priority,
        'avg_days_to_approval': avg_days,
    }