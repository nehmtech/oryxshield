"""
Resources models for OryxShield.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Location
from coordination.models import Agency


class ResourceCategory(TimeStampedModel):
    """
    Hierarchical categories for resources/supplies.
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)

    parent_category = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    standard_unit = models.CharField(max_length=50, help_text="e.g., pieces, liters, kg")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Resource Categories'

    def __str__(self):
        return f"{self.name} ({self.code})"


class ResourceItem(TimeStampedModel):
    """
    Individual resource items/supplies with thresholds.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    category = models.ForeignKey(
        ResourceCategory,
        on_delete=models.PROTECT,
        related_name='items'
    )

    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)

    unit_of_measure = models.CharField(max_length=50)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    track_expiry = models.BooleanField(default=False)
    track_serial_numbers = models.BooleanField(default=False)

    minimum_stock_level = models.IntegerField(default=0)
    reorder_point = models.IntegerField(default=0)
    maximum_stock_level = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_critical = models.BooleanField(default=False, help_text="Critical supply item")

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Facility(TimeStampedModel):
    """
    Healthcare and storage facilities with capacity data.
    """
    FACILITY_TYPES = [
        ('HOSPITAL', 'Hospital'),
        ('CLINIC', 'Clinic/Health Center'),
        ('LABORATORY', 'Laboratory'),
        ('WAREHOUSE', 'Warehouse'),
        ('PHARMACY', 'Pharmacy'),
        ('QUARANTINE', 'Quarantine Facility'),
        ('ISOLATION', 'Isolation Center'),
        ('TESTING', 'Testing Center'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPES, db_index=True)

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='facilities'
    )
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    managing_agency = models.ForeignKey(
        Agency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_facilities'
    )
    facility_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_facilities'
    )

    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    # Healthcare capacity
    total_beds = models.IntegerField(null=True, blank=True)
    icu_beds = models.IntegerField(null=True, blank=True)
    isolation_beds = models.IntegerField(null=True, blank=True)
    ventilators = models.IntegerField(null=True, blank=True)

    # Storage capacity
    storage_capacity_sqm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cold_storage_capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    is_operational = models.BooleanField(default=True, db_index=True)
    operational_status = models.CharField(max_length=100, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Facilities'
        indexes = [
            models.Index(fields=['facility_type', 'is_operational']),
            models.Index(fields=['location', 'facility_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.facility_type})"


class Inventory(TimeStampedModel):
    """
    Inventory tracking per facility per item per batch.
    """
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('EXPIRED', 'Expired'),
    ]

    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    resource_item = models.ForeignKey(
        ResourceItem,
        on_delete=models.PROTECT,
        related_name='inventory_records'
    )

    quantity_available = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)
    quantity_in_transit = models.IntegerField(default=0)

    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)

    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    storage_location = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE',
        db_index=True
    )

    last_stock_check = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['facility', 'resource_item']
        verbose_name_plural = 'Inventories'
        indexes = [
            models.Index(fields=['facility', 'status']),
            models.Index(fields=['resource_item', 'facility']),
        ]
        unique_together = ['facility', 'resource_item', 'batch_number']

    def __str__(self):
        return f"{self.resource_item.name} at {self.facility.name}: {self.quantity_available}"

    def get_total_quantity(self):
        """Return sum of available + reserved + in-transit."""
        return self.quantity_available + self.quantity_reserved + self.quantity_in_transit


class StockMovement(TimeStampedModel):
    """
    Immutable audit trail of all stock movements.
    """
    MOVEMENT_TYPES = [
        ('RECEIPT', 'Receipt/Delivery'),
        ('ISSUE', 'Issue/Distribution'),
        ('TRANSFER', 'Transfer'),
        ('ADJUSTMENT', 'Inventory Adjustment'),
        ('RETURN', 'Return'),
        ('DISPOSAL', 'Disposal'),
    ]

    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, db_index=True)
    movement_date = models.DateTimeField(auto_now_add=True, db_index=True)

    resource_item = models.ForeignKey(
        ResourceItem,
        on_delete=models.PROTECT,
        related_name='movements'
    )
    quantity = models.IntegerField()

    from_facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='outgoing_movements'
    )
    to_facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incoming_movements'
    )

    batch_number = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, unique=True, db_index=True)
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_movements'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_movements'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-movement_date']
        indexes = [
            models.Index(fields=['movement_type', '-movement_date']),
            models.Index(fields=['resource_item', '-movement_date']),
        ]

    def __str__(self):
        return f"{self.movement_type}: {self.resource_item.name} x{self.quantity}"


class ProcurementRequest(TimeStampedModel):
    """
    Multi-level approval procurement request.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ORDERED', 'Ordered'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
        ('CRITICAL', 'Critical'),
    ]

    request_number = models.CharField(max_length=50, unique=True, db_index=True)

    requesting_facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='procurement_requests'
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='procurement_requests'
    )

    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)

    requested_date = models.DateTimeField(auto_now_add=True)
    required_by_date = models.DateField()

    justification = models.TextField()

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests'
    )
    rejection_reason = models.TextField(blank=True)

    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-requested_date']
        indexes = [
            models.Index(fields=['status', '-requested_date']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self):
        return f"{self.request_number} - {self.requesting_facility.name}"

    def submit(self, user):
        """Submit draft request for review."""
        self.status = 'SUBMITTED'
        self.save(update_fields=['status', 'updated_at'])
        from core.models import AuditLog
        AuditLog.log(
            actor=user,
            action='PROCUREMENT_SUBMITTED',
            target_object_id=str(self.id),
            target_content_type='ProcurementRequest',
            details={'request_number': self.request_number}
        )

    def approve(self, user):
        """Approve submitted request."""
        self.status = 'APPROVED'
        self.approved_by = user
        self.save(update_fields=['status', 'approved_by', 'updated_at'])
        from core.models import AuditLog
        AuditLog.log(
            actor=user,
            action='PROCUREMENT_APPROVED',
            target_object_id=str(self.id),
            target_content_type='ProcurementRequest',
            details={'request_number': self.request_number}
        )

    def reject(self, user, reason):
        """Reject request with reason."""
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.reviewed_by = user
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'updated_at'])
        from core.models import AuditLog
        AuditLog.log(
            actor=user,
            action='PROCUREMENT_REJECTED',
            target_object_id=str(self.id),
            target_content_type='ProcurementRequest',
            details={'request_number': self.request_number, 'reason': reason}
        )

    def cancel(self, user):
        """Cancel request."""
        self.status = 'CANCELLED'
        self.save(update_fields=['status', 'updated_at'])
        from core.models import AuditLog
        AuditLog.log(
            actor=user,
            action='PROCUREMENT_CANCELLED',
            target_object_id=str(self.id),
            target_content_type='ProcurementRequest',
            details={'request_number': self.request_number}
        )

    def mark_delivered(self, user, actual_cost=None):
        """Mark request as delivered."""
        self.status = 'DELIVERED'
        if actual_cost is not None:
            self.actual_cost = actual_cost
        self.save(update_fields=['status', 'actual_cost', 'updated_at'])
        from core.models import AuditLog
        AuditLog.log(
            actor=user,
            action='PROCUREMENT_DELIVERED',
            target_object_id=str(self.id),
            target_content_type='ProcurementRequest',
            details={'request_number': self.request_number, 'actual_cost': str(actual_cost)}
        )


class ProcurementItem(TimeStampedModel):
    """
    Line items within a procurement request.
    """
    procurement_request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )
    resource_item = models.ForeignKey(
        ResourceItem,
        on_delete=models.PROTECT,
        related_name='procurement_items'
    )

    quantity_requested = models.IntegerField()
    quantity_approved = models.IntegerField(null=True, blank=True)
    quantity_delivered = models.IntegerField(default=0)

    specifications = models.TextField(blank=True)

    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['procurement_request', 'resource_item']

    def __str__(self):
        return f"{self.resource_item.name} x{self.quantity_requested}"


class FacilityCapacity(TimeStampedModel):
    """
    Point-in-time capacity snapshot for a facility.
    """
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='capacity_records'
    )

    beds_occupied = models.IntegerField(default=0)
    beds_available = models.IntegerField(default=0)
    icu_occupied = models.IntegerField(default=0)
    icu_available = models.IntegerField(default=0)
    isolation_occupied = models.IntegerField(default=0)
    isolation_available = models.IntegerField(default=0)

    ventilators_in_use = models.IntegerField(default=0)
    ventilators_available = models.IntegerField(default=0)

    occupancy_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage of beds occupied"
    )

    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='capacity_records'
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name_plural = 'Facility Capacities'
        indexes = [
            models.Index(fields=['facility', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.facility.name} - {self.recorded_at.date()} ({self.occupancy_rate}%)"

    def calculate_occupancy_rate(self):
        """Calculate and set overall bed occupancy rate."""
        total = self.beds_occupied + self.beds_available
        self.occupancy_rate = round((self.beds_occupied / total) * 100, 2) if total > 0 else 0


class Supplier(TimeStampedModel):
    """
    Approved suppliers and vendors for procurement.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, db_index=True)

    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)

    address = models.TextField(blank=True)

    supplies = models.ManyToManyField(
        ResourceItem,
        related_name='suppliers',
        blank=True
    )

    reliability_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DemandForecast(TimeStampedModel):
    """
    Demand forecast for a resource item at a location.
    """
    resource_item = models.ForeignKey(
        ResourceItem,
        on_delete=models.CASCADE,
        related_name='demand_forecasts'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='demand_forecasts'
    )

    forecast_date = models.DateField(db_index=True)
    forecast_period_days = models.IntegerField(default=30)

    predicted_demand = models.IntegerField()
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2)

    actual_demand = models.IntegerField(null=True, blank=True)

    forecast_model = models.CharField(max_length=100, blank=True)
    is_current = models.BooleanField(default=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-forecast_date']
        indexes = [
            models.Index(fields=['resource_item', '-forecast_date']),
            models.Index(fields=['location', '-forecast_date']),
            models.Index(fields=['is_current', 'resource_item']),
        ]

    def __str__(self):
        return f"{self.resource_item.name} @ {self.location.name} — {self.forecast_date}"