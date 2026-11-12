"""
Views for resources app.
"""
import uuid
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta, date

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from core.models import AuditLog
from core.pagination import CustomPagination
from .models import (
    ResourceCategory, ResourceItem, Facility, Inventory, StockMovement,
    ProcurementRequest, ProcurementItem, FacilityCapacity, Supplier, DemandForecast
)
from .serializers import (
    ResourceCategorySerializer,
    ResourceItemSerializer, ResourceItemListSerializer,
    FacilitySerializer, FacilityListSerializer,
    InventorySerializer, InventoryListSerializer,
    StockMovementSerializer,
    ProcurementRequestSerializer, ProcurementRequestListSerializer,
    ProcurementRejectSerializer, ProcurementDeliverSerializer,
    ProcurementItemSerializer,
    FacilityCapacitySerializer,
    SupplierSerializer,
    DemandForecastSerializer,
    StockAdjustmentSerializer,
    ResourceDashboardSerializer,
)


class ResourceCategoryViewSet(viewsets.ModelViewSet):
    queryset = ResourceCategory.objects.filter(is_deleted=False)
    serializer_class = ResourceCategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent_category']

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='RESOURCE_CATEGORY_DELETED',
            target_object_id=str(instance.id),
            target_content_type='ResourceCategory',
            details={'name': instance.name}
        )


class ResourceItemViewSet(viewsets.ModelViewSet):
    queryset = ResourceItem.objects.filter(is_deleted=False).select_related('category')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_critical', 'is_active']
    search_fields = ['name', 'code', 'description']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ResourceItemListSerializer
        return ResourceItemSerializer

    def perform_create(self, serializer):
        item = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='RESOURCE_ITEM_CREATED',
            target_object_id=str(item.id),
            target_content_type='ResourceItem',
            details={'name': item.name, 'code': item.code, 'is_critical': item.is_critical}
        )

    def perform_update(self, serializer):
        item = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='RESOURCE_ITEM_UPDATED',
            target_object_id=str(item.id),
            target_content_type='ResourceItem',
            details={'name': item.name}
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='RESOURCE_ITEM_DELETED',
            target_object_id=str(instance.id),
            target_content_type='ResourceItem',
            details={'name': instance.name, 'code': instance.code}
        )

    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Return all critical resource items."""
        qs = self.get_queryset().filter(is_critical=True)
        page = self.paginate_queryset(qs)
        serializer = ResourceItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock_summary(self, request):
        """Critical items that are currently low or out of stock across all facilities."""
        qs = (
            Inventory.objects
            .filter(
                is_deleted=False,
                resource_item__is_critical=True,
                status__in=['LOW_STOCK', 'OUT_OF_STOCK'],
            )
            .select_related('resource_item', 'facility')
        )
        data = [
            {
                'inventory_id': str(inv.id),
                'item': inv.resource_item.name,
                'item_code': inv.resource_item.code,
                'facility': inv.facility.name,
                'quantity_available': inv.quantity_available,
                'status': inv.status,
            }
            for inv in qs
        ]
        return Response(data)


class FacilityViewSet(viewsets.ModelViewSet):
    queryset = Facility.objects.filter(is_deleted=False).select_related('location', 'managing_agency')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['facility_type', 'is_operational', 'location']
    search_fields = ['name', 'code', 'address']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return FacilityListSerializer
        return FacilitySerializer

    def perform_create(self, serializer):
        facility = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='FACILITY_CREATED',
            target_object_id=str(facility.id),
            target_content_type='Facility',
            details={'name': facility.name, 'type': facility.facility_type}
        )

    def perform_update(self, serializer):
        facility = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='FACILITY_UPDATED',
            target_object_id=str(facility.id),
            target_content_type='Facility',
            details={'name': facility.name}
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='FACILITY_DELETED',
            target_object_id=str(instance.id),
            target_content_type='Facility',
            details={'name': instance.name}
        )

    @action(detail=False, methods=['get'])
    def operational(self, request):
        """Return operational facilities."""
        qs = self.get_queryset().filter(is_operational=True)
        page = self.paginate_queryset(qs)
        serializer = FacilityListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'])
    def capacity(self, request, pk=None):
        """Return latest capacity snapshot for a facility."""
        facility = self.get_object()
        latest = facility.capacity_records.first()
        if not latest:
            return Response({'message': 'No capacity data recorded.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityCapacitySerializer(latest).data)

    @action(detail=True, methods=['get'])
    def inventory(self, request, pk=None):
        """Return all active inventory at this facility."""
        facility = self.get_object()
        qs = facility.inventory.filter(is_deleted=False).select_related('resource_item')
        page = self.paginate_queryset(qs)
        serializer = InventoryListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def decommission(self, request, pk=None):
        """Mark facility as non-operational."""
        facility = self.get_object()
        facility.is_operational = False
        facility.operational_status = request.data.get('reason', 'Decommissioned')
        facility.save(update_fields=['is_operational', 'operational_status', 'updated_at'])
        AuditLog.log(
            actor=request.user,
            action='FACILITY_DECOMMISSIONED',
            target_object_id=str(facility.id),
            target_content_type='Facility',
            details={'name': facility.name, 'reason': facility.operational_status}
        )
        return Response({'status': 'Facility marked as non-operational.'})


class InventoryViewSet(viewsets.ModelViewSet):
    queryset = (
        Inventory.objects
        .filter(is_deleted=False)
        .select_related('facility', 'resource_item')
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['facility', 'resource_item', 'status']
    search_fields = ['batch_number', 'storage_location']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return InventoryListSerializer
        return InventorySerializer

    def perform_create(self, serializer):
        inventory = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='INVENTORY_CREATED',
            target_object_id=str(inventory.id),
            target_content_type='Inventory',
            details={
                'item': inventory.resource_item.name,
                'facility': inventory.facility.name,
                'quantity': inventory.quantity_available,
            }
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='INVENTORY_DELETED',
            target_object_id=str(instance.id),
            target_content_type='Inventory',
            details={'item': instance.resource_item.name, 'facility': instance.facility.name}
        )

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Return items currently in LOW_STOCK status."""
        qs = self.get_queryset().filter(status='LOW_STOCK')
        page = self.paginate_queryset(qs)
        serializer = InventoryListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Return items expiring within the next 30 days."""
        cutoff = date.today() + timedelta(days=30)
        qs = self.get_queryset().filter(
            expiry_date__isnull=False,
            expiry_date__lte=cutoff,
            expiry_date__gte=date.today(),
        ).order_by('expiry_date')
        page = self.paginate_queryset(qs)
        serializer = InventoryListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Apply a quantity adjustment to this inventory record."""
        inventory = self.get_object()
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        reason = serializer.validated_data['reason']
        batch = serializer.validated_data.get('batch_number', inventory.batch_number)

        inventory.quantity_available += quantity
        if inventory.quantity_available < 0:
            inventory.quantity_available = 0
        inventory.save(update_fields=['quantity_available', 'updated_at'])

        ref = f"ADJ-{uuid.uuid4().hex[:8].upper()}"
        movement = StockMovement.objects.create(
            movement_type='ADJUSTMENT',
            resource_item=inventory.resource_item,
            to_facility=inventory.facility if quantity > 0 else None,
            from_facility=inventory.facility if quantity < 0 else None,
            quantity=abs(quantity),
            batch_number=batch,
            reference_number=ref,
            notes=reason,
            recorded_by=request.user,
        )

        AuditLog.log(
            actor=request.user,
            action='INVENTORY_ADJUSTED',
            target_object_id=str(inventory.id),
            target_content_type='Inventory',
            details={
                'item': inventory.resource_item.name,
                'facility': inventory.facility.name,
                'delta': quantity,
                'new_qty': inventory.quantity_available,
                'reason': reason,
                'reference': ref,
            }
        )

        return Response({
            'status': 'Inventory adjusted.',
            'new_quantity': inventory.quantity_available,
            'reference_number': ref,
        })


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = (
        StockMovement.objects
        .filter(is_deleted=False)
        .select_related('resource_item', 'from_facility', 'to_facility', 'recorded_by')
    )
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['movement_type', 'resource_item', 'from_facility', 'to_facility']
    search_fields = ['reference_number', 'batch_number', 'notes']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        movement = serializer.save(recorded_by=self.request.user)
        AuditLog.log(
            actor=self.request.user,
            action='STOCK_MOVEMENT_RECORDED',
            target_object_id=str(movement.id),
            target_content_type='StockMovement',
            details={
                'type': movement.movement_type,
                'item': movement.resource_item.name,
                'quantity': movement.quantity,
                'reference': movement.reference_number,
            }
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='STOCK_MOVEMENT_VOIDED',
            target_object_id=str(instance.id),
            target_content_type='StockMovement',
            details={'reference': instance.reference_number}
        )

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Return the 50 most recent movements."""
        qs = self.get_queryset().order_by('-movement_date')[:50]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Return movements recorded today."""
        today = timezone.now().date()
        qs = self.get_queryset().filter(movement_date__date=today)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    queryset = (
        ProcurementRequest.objects
        .filter(is_deleted=False)
        .select_related('requesting_facility', 'requested_by', 'approved_by')
        .prefetch_related('items__resource_item')
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'priority', 'requesting_facility']
    search_fields = ['request_number', 'justification']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ProcurementRequestListSerializer
        return ProcurementRequestSerializer

    def perform_create(self, serializer):
        proc = serializer.save(requested_by=self.request.user)
        AuditLog.log(
            actor=self.request.user,
            action='PROCUREMENT_REQUEST_CREATED',
            target_object_id=str(proc.id),
            target_content_type='ProcurementRequest',
            details={'request_number': proc.request_number, 'priority': proc.priority}
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='PROCUREMENT_REQUEST_DELETED',
            target_object_id=str(instance.id),
            target_content_type='ProcurementRequest',
            details={'request_number': instance.request_number}
        )

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Return requests awaiting review or approval."""
        qs = self.get_queryset().filter(status__in=['SUBMITTED', 'UNDER_REVIEW'])
        page = self.paginate_queryset(qs)
        serializer = ProcurementRequestListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a draft request for review."""
        proc = self.get_object()
        if proc.status != 'DRAFT':
            return Response(
                {'error': f"Cannot submit a request with status '{proc.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        proc.submit(request.user)
        return Response({'status': 'Request submitted for review.'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a submitted/under-review request."""
        proc = self.get_object()
        if proc.status not in ('SUBMITTED', 'UNDER_REVIEW'):
            return Response(
                {'error': f"Cannot approve a request with status '{proc.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        proc.approve(request.user)
        return Response({'status': 'Request approved.'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a request with a mandatory reason."""
        proc = self.get_object()
        if proc.status not in ('SUBMITTED', 'UNDER_REVIEW'):
            return Response(
                {'error': f"Cannot reject a request with status '{proc.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = ProcurementRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proc.reject(request.user, serializer.validated_data['reason'])
        return Response({'status': 'Request rejected.'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a request that has not yet been delivered."""
        proc = self.get_object()
        if proc.status in ('DELIVERED', 'CANCELLED'):
            return Response(
                {'error': f"Cannot cancel a request with status '{proc.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        proc.cancel(request.user)
        return Response({'status': 'Request cancelled.'})

    @action(detail=True, methods=['post'])
    def mark_delivered(self, request, pk=None):
        """Mark an ordered request as delivered."""
        proc = self.get_object()
        if proc.status != 'ORDERED':
            return Response(
                {'error': f"Only ORDERED requests can be marked delivered. Current: '{proc.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = ProcurementDeliverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proc.mark_delivered(request.user, serializer.validated_data.get('actual_cost'))
        return Response({'status': 'Request marked as delivered.'})

    @action(detail=True, methods=['get', 'post'])
    def items(self, request, pk=None):
        """List or add line items to a procurement request."""
        proc = self.get_object()
        if request.method == 'GET':
            serializer = ProcurementItemSerializer(proc.items.all(), many=True)
            return Response(serializer.data)

        serializer = ProcurementItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(procurement_request=proc)
        AuditLog.log(
            actor=request.user,
            action='PROCUREMENT_ITEM_ADDED',
            target_object_id=str(item.id),
            target_content_type='ProcurementItem',
            details={
                'request_number': proc.request_number,
                'item': item.resource_item.name,
                'qty': item.quantity_requested,
            }
        )
        return Response(ProcurementItemSerializer(item).data, status=status.HTTP_201_CREATED)


class FacilityCapacityViewSet(viewsets.ModelViewSet):
    queryset = (
        FacilityCapacity.objects
        .filter(is_deleted=False)
        .select_related('facility', 'recorded_by')
    )
    serializer_class = FacilityCapacitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['facility']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        capacity = serializer.save(recorded_by=self.request.user)
        capacity.calculate_occupancy_rate()
        capacity.save(update_fields=['occupancy_rate'])

        AuditLog.log(
            actor=self.request.user,
            action='CAPACITY_RECORDED',
            target_object_id=str(capacity.id),
            target_content_type='FacilityCapacity',
            details={
                'facility': capacity.facility.name,
                'occupancy_rate': str(capacity.occupancy_rate),
                'beds_occupied': capacity.beds_occupied,
            }
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='CAPACITY_RECORD_DELETED',
            target_object_id=str(instance.id),
            target_content_type='FacilityCapacity',
            details={'facility': instance.facility.name}
        )

    @action(detail=False, methods=['get'])
    def high_occupancy(self, request):
        """Return capacity records where occupancy rate >= 80%."""
        qs = self.get_queryset().filter(occupancy_rate__gte=80).order_by('-occupancy_rate')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.filter(is_deleted=False)
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_approved', 'is_active']
    search_fields = ['name', 'code', 'contact_email']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        supplier = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='SUPPLIER_CREATED',
            target_object_id=str(supplier.id),
            target_content_type='Supplier',
            details={'name': supplier.name, 'code': supplier.code}
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            actor=self.request.user,
            action='SUPPLIER_DELETED',
            target_object_id=str(instance.id),
            target_content_type='Supplier',
            details={'name': instance.name}
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Mark a supplier as approved."""
        supplier = self.get_object()
        supplier.is_approved = True
        supplier.save(update_fields=['is_approved', 'updated_at'])
        AuditLog.log(
            actor=request.user,
            action='SUPPLIER_APPROVED',
            target_object_id=str(supplier.id),
            target_content_type='Supplier',
            details={'name': supplier.name}
        )
        return Response({'status': 'Supplier approved.'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a supplier."""
        supplier = self.get_object()
        supplier.is_active = False
        supplier.save(update_fields=['is_active', 'updated_at'])
        AuditLog.log(
            actor=request.user,
            action='SUPPLIER_DEACTIVATED',
            target_object_id=str(supplier.id),
            target_content_type='Supplier',
            details={'name': supplier.name}
        )
        return Response({'status': 'Supplier deactivated.'})


class DemandForecastViewSet(viewsets.ModelViewSet):
    queryset = (
        DemandForecast.objects
        .filter(is_deleted=False)
        .select_related('resource_item', 'location')
    )
    serializer_class = DemandForecastSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['resource_item', 'location', 'is_current']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        # Supersede previous current forecasts for same item+location
        data = serializer.validated_data
        DemandForecast.objects.filter(
            resource_item=data['resource_item'],
            location=data['location'],
            is_current=True,
            is_deleted=False,
        ).update(is_current=False)
        forecast = serializer.save()
        AuditLog.log(
            actor=self.request.user,
            action='DEMAND_FORECAST_CREATED',
            target_object_id=str(forecast.id),
            target_content_type='DemandForecast',
            details={
                'item': forecast.resource_item.name,
                'location': forecast.location.name,
                'predicted': forecast.predicted_demand,
            }
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Return only current (active) forecasts."""
        qs = self.get_queryset().filter(is_current=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ResourceDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Aggregated resource management dashboard."""
        total_facilities = Facility.objects.filter(is_deleted=False).count()
        operational_facilities = Facility.objects.filter(is_deleted=False, is_operational=True).count()

        critical_low = Inventory.objects.filter(
            is_deleted=False,
            resource_item__is_critical=True,
            status__in=['LOW_STOCK', 'OUT_OF_STOCK'],
        ).count()

        pending_requests = ProcurementRequest.objects.filter(
            is_deleted=False,
            status__in=['SUBMITTED', 'UNDER_REVIEW'],
        ).count()

        avg_occupancy = FacilityCapacity.objects.filter(
            is_deleted=False
        ).aggregate(avg=Avg('occupancy_rate'))['avg'] or 0

        high_occupancy = (
            FacilityCapacity.objects
            .filter(is_deleted=False, occupancy_rate__gte=80)
            .values('facility')
            .distinct()
            .count()
        )

        today = timezone.now().date()
        movements_today = StockMovement.objects.filter(
            is_deleted=False,
            movement_date__date=today,
        ).count()

        cutoff = date.today() + timedelta(days=30)
        expiring_soon = Inventory.objects.filter(
            is_deleted=False,
            expiry_date__isnull=False,
            expiry_date__lte=cutoff,
            expiry_date__gte=date.today(),
        ).count()

        recent_movements = list(
            StockMovement.objects
            .filter(is_deleted=False)
            .order_by('-movement_date')[:10]
            .values(
                'id', 'movement_type',
                'resource_item__name', 'quantity',
                'movement_date', 'reference_number',
            )
        )
        # Stringify UUIDs for JSON safety
        for m in recent_movements:
            m['id'] = str(m['id'])

        data = {
            'total_facilities': total_facilities,
            'operational_facilities': operational_facilities,
            'critical_items_low_stock': critical_low,
            'pending_procurement_requests': pending_requests,
            'average_occupancy_rate': round(float(avg_occupancy), 2),
            'facilities_above_80_percent': high_occupancy,
            'total_stock_movements_today': movements_today,
            'expiring_within_30_days': expiring_soon,
            'recent_movements': recent_movements,
        }

        serializer = ResourceDashboardSerializer(data)
        return Response(serializer.data)