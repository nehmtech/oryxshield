"""
Admin configuration for resources app.
"""
from django.contrib import admin
from .models import (
    ResourceCategory, ResourceItem, Facility, Inventory, StockMovement,
    ProcurementRequest, ProcurementItem, FacilityCapacity, Supplier, DemandForecast
)


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'standard_unit', 'parent_category', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(ResourceItem)
class ResourceItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'unit_of_measure', 'is_critical', 'is_active', 'reorder_point']
    list_filter = ['category', 'is_critical', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'facility_type', 'location', 'is_operational', 'total_beds']
    list_filter = ['facility_type', 'is_operational', 'location']
    search_fields = ['name', 'code', 'address']


class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 0
    fields = ['resource_item', 'quantity_available', 'status', 'batch_number', 'expiry_date']
    readonly_fields = ['status']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['resource_item', 'facility', 'quantity_available', 'status', 'expiry_date', 'batch_number']
    list_filter = ['status', 'facility', 'expiry_date']
    search_fields = ['resource_item__name', 'batch_number', 'storage_location']
    readonly_fields = ['status']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'movement_type', 'resource_item', 'quantity', 'movement_date', 'recorded_by']
    list_filter = ['movement_type', 'movement_date']
    search_fields = ['reference_number', 'batch_number', 'notes']
    readonly_fields = ['movement_date', 'reference_number']


class ProcurementItemInline(admin.TabularInline):
    model = ProcurementItem
    extra = 1
    fields = ['resource_item', 'quantity_requested', 'quantity_approved', 'quantity_delivered', 'unit_cost', 'total_cost']


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'requesting_facility', 'priority', 'status', 'requested_date', 'required_by_date']
    list_filter = ['priority', 'status', 'requesting_facility']
    search_fields = ['request_number', 'justification']
    readonly_fields = ['requested_date']
    inlines = [ProcurementItemInline]


@admin.register(FacilityCapacity)
class FacilityCapacityAdmin(admin.ModelAdmin):
    list_display = ['facility', 'beds_occupied', 'beds_available', 'occupancy_rate', 'recorded_at', 'recorded_by']
    list_filter = ['facility', 'recorded_at']
    readonly_fields = ['recorded_at', 'occupancy_rate']
    ordering = ['-recorded_at']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'contact_email', 'is_approved', 'is_active', 'reliability_rating']
    list_filter = ['is_approved', 'is_active']
    search_fields = ['name', 'code', 'contact_email']
    filter_horizontal = ['supplies']


@admin.register(DemandForecast)
class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ['resource_item', 'location', 'forecast_date', 'predicted_demand', 'confidence_level', 'is_current']
    list_filter = ['is_current', 'forecast_date', 'resource_item']
    search_fields = ['resource_item__name', 'location__name']