"""
Serializers for resources app.
"""
from rest_framework import serializers
from django.db import transaction
from .models import (
    ResourceCategory, ResourceItem, Facility, Inventory, StockMovement,
    ProcurementRequest, ProcurementItem, FacilityCapacity, Supplier, DemandForecast
)


# ─── Resource Category ────────────────────────────────────────────────────────

class ResourceCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent_category.name', read_only=True)

    class Meta:
        model = ResourceCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ─── Resource Item ────────────────────────────────────────────────────────────

class ResourceItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = ResourceItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResourceItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = ResourceItem
        fields = [
            'id', 'name', 'code', 'category', 'category_name',
            'unit_of_measure', 'is_critical', 'is_active',
            'reorder_point', 'minimum_stock_level',
        ]


# ─── Facility ─────────────────────────────────────────────────────────────────

class FacilitySerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    managing_agency_name = serializers.CharField(source='managing_agency.name', read_only=True)

    class Meta:
        model = Facility
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FacilityListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = Facility
        fields = [
            'id', 'name', 'code', 'facility_type', 'location',
            'location_name', 'is_operational', 'total_beds',
            'contact_phone', 'contact_email',
        ]


# ─── Inventory ────────────────────────────────────────────────────────────────

class InventorySerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    resource_name = serializers.CharField(source='resource_item.name', read_only=True)
    resource_code = serializers.CharField(source='resource_item.code', read_only=True)
    is_critical = serializers.BooleanField(source='resource_item.is_critical', read_only=True)

    class Meta:
        model = Inventory
        fields = '__all__'
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class InventoryListSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource_item.name', read_only=True)
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    is_critical = serializers.BooleanField(source='resource_item.is_critical', read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'facility', 'facility_name', 'resource_item', 'resource_name',
            'is_critical', 'quantity_available', 'status',
            'expiry_date', 'batch_number',
        ]


# ─── Stock Movement ───────────────────────────────────────────────────────────

class StockMovementSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource_item.name', read_only=True)
    from_facility_name = serializers.CharField(source='from_facility.name', read_only=True)
    to_facility_name = serializers.CharField(source='to_facility.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)

    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = ['id', 'movement_date', 'created_at', 'updated_at']

    def validate(self, data):
        movement_type = data.get('movement_type')
        from_facility = data.get('from_facility')
        to_facility = data.get('to_facility')

        if movement_type in ('TRANSFER', 'ISSUE') and not from_facility:
            raise serializers.ValidationError(
                {'from_facility': f"Required for {movement_type} movements."}
            )
        if movement_type in ('RECEIPT', 'TRANSFER') and not to_facility:
            raise serializers.ValidationError(
                {'to_facility': f"Required for {movement_type} movements."}
            )
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError({'quantity': "Quantity must be positive."})
        return data


# ─── Procurement ──────────────────────────────────────────────────────────────

class ProcurementItemSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource_item.name', read_only=True)
    resource_unit = serializers.CharField(source='resource_item.unit_of_measure', read_only=True)

    class Meta:
        model = ProcurementItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProcurementRequestSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='requesting_facility.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    items = ProcurementItemSerializer(many=True, read_only=True)

    class Meta:
        model = ProcurementRequest
        fields = '__all__'
        read_only_fields = [
            'id', 'requested_date', 'approved_by', 'reviewed_by',
            'rejection_reason', 'created_at', 'updated_at',
        ]


class ProcurementRequestListSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='requesting_facility.name', read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = ProcurementRequest
        fields = [
            'id', 'request_number', 'requesting_facility', 'facility_name',
            'priority', 'status', 'requested_date', 'required_by_date',
            'estimated_cost', 'item_count',
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class ProcurementRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10)


class ProcurementDeliverSerializer(serializers.Serializer):
    actual_cost = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)


# ─── Facility Capacity ────────────────────────────────────────────────────────

class FacilityCapacitySerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)

    class Meta:
        model = FacilityCapacity
        fields = '__all__'
        read_only_fields = ['id', 'occupancy_rate', 'recorded_at', 'created_at', 'updated_at']


# ─── Supplier ─────────────────────────────────────────────────────────────────

class SupplierSerializer(serializers.ModelSerializer):
    supplied_items_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_supplied_items_count(self, obj):
        return obj.supplies.count()


# ─── Demand Forecast ──────────────────────────────────────────────────────────

class DemandForecastSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource_item.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    variance_pct = serializers.SerializerMethodField()

    class Meta:
        model = DemandForecast
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_variance_pct(self, obj):
        if obj.actual_demand and obj.predicted_demand:
            return round(
                ((obj.actual_demand - obj.predicted_demand) / obj.predicted_demand) * 100, 2
            )
        return None


# ─── Utility / Action serializers ────────────────────────────────────────────

class StockAdjustmentSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(help_text="Positive to add, negative to subtract.")
    reason = serializers.CharField(min_length=5)
    batch_number = serializers.CharField(required=False, allow_blank=True)


class ResourceDashboardSerializer(serializers.Serializer):
    total_facilities = serializers.IntegerField()
    operational_facilities = serializers.IntegerField()
    critical_items_low_stock = serializers.IntegerField()
    pending_procurement_requests = serializers.IntegerField()
    average_occupancy_rate = serializers.FloatField()
    facilities_above_80_percent = serializers.IntegerField()
    total_stock_movements_today = serializers.IntegerField()
    expiring_within_30_days = serializers.IntegerField()
    recent_movements = serializers.ListField()