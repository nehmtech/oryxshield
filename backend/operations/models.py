"""
Operations models for OryxShield.
Covers: Case management, contact tracing, testing coordination,
vaccination campaigns, quarantine management.
"""
import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import TimeStampedModel, Location
from surveillance.models import HealthData


# ---------------------------------------------------------------------------
# Case Management
# ---------------------------------------------------------------------------

class Case(TimeStampedModel):
    """Individual disease case record."""

    CLASSIFICATION_SUSPECT = 'SUSPECT'
    CLASSIFICATION_PROBABLE = 'PROBABLE'
    CLASSIFICATION_CONFIRMED = 'CONFIRMED'
    CLASSIFICATION_NOT_A_CASE = 'NOT_A_CASE'
    CASE_CLASSIFICATIONS = [
        (CLASSIFICATION_SUSPECT, 'Suspect'),
        (CLASSIFICATION_PROBABLE, 'Probable'),
        (CLASSIFICATION_CONFIRMED, 'Confirmed'),
        (CLASSIFICATION_NOT_A_CASE, 'Not a Case'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_RECOVERED = 'RECOVERED'
    STATUS_DECEASED = 'DECEASED'
    STATUS_LOST = 'LOST_TO_FOLLOWUP'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_RECOVERED, 'Recovered'),
        (STATUS_DECEASED, 'Deceased'),
        (STATUS_LOST, 'Lost to Follow-up'),
    ]

    # Identifiers
    case_id = models.CharField(max_length=50, unique=True, db_index=True)

    # Patient demographics
    patient_name = models.CharField(max_length=200)
    patient_age = models.IntegerField(null=True, blank=True)
    patient_gender = models.CharField(max_length=10, blank=True)
    patient_contact = models.CharField(max_length=200, blank=True)
    patient_id_number = models.CharField(max_length=50, blank=True)

    # Geography
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='cases'
    )
    address = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # Disease
    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)

    # Classification & status
    classification = models.CharField(
        max_length=20, choices=CASE_CLASSIFICATIONS,
        default=CLASSIFICATION_SUSPECT, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_ACTIVE, db_index=True
    )

    # Key dates
    symptom_onset_date = models.DateField(null=True, blank=True)
    diagnosis_date = models.DateField(null=True, blank=True)
    hospitalization_date = models.DateField(null=True, blank=True)
    recovery_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)

    # Clinical
    symptoms = models.JSONField(default=list, blank=True)
    comorbidities = models.JSONField(default=list, blank=True)
    clinical_notes = models.TextField(blank=True)

    # Isolation
    is_isolated = models.BooleanField(default=False)
    isolation_location = models.CharField(max_length=200, blank=True)
    isolation_start_date = models.DateField(null=True, blank=True)
    isolation_end_date = models.DateField(null=True, blank=True)

    # Linkage
    health_data = models.ForeignKey(
        HealthData, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cases'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='managed_cases'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case_id']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['location', 'status']),
            models.Index(fields=['disease_code', 'status']),
            models.Index(fields=['classification', 'status']),
        ]

    def __str__(self):
        return f"{self.case_id} — {self.patient_name}"

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def resolve(self, outcome: str, date=None):
        """
        Close a case with a terminal outcome.
        outcome: 'RECOVERED' | 'DECEASED' | 'NOT_A_CASE'
        """
        assert outcome in (
            self.STATUS_RECOVERED, self.STATUS_DECEASED,
            self.CLASSIFICATION_NOT_A_CASE
        ), f"Invalid outcome: {outcome}"
        today = date or timezone.now().date()
        if outcome == self.STATUS_RECOVERED:
            self.status = self.STATUS_RECOVERED
            self.recovery_date = today
        elif outcome == self.STATUS_DECEASED:
            self.status = self.STATUS_DECEASED
            self.death_date = today
        else:
            self.classification = self.CLASSIFICATION_NOT_A_CASE
            self.status = self.STATUS_RECOVERED  # effectively close
        self.save(update_fields=[
            'status', 'classification', 'recovery_date',
            'death_date', 'updated_at'
        ])

    def start_isolation(self, location: str, start_date=None):
        today = start_date or timezone.now().date()
        self.is_isolated = True
        self.isolation_location = location
        self.isolation_start_date = today
        self.save(update_fields=[
            'is_isolated', 'isolation_location',
            'isolation_start_date', 'updated_at'
        ])

    def end_isolation(self, end_date=None):
        today = end_date or timezone.now().date()
        self.is_isolated = False
        self.isolation_end_date = today
        self.save(update_fields=['is_isolated', 'isolation_end_date', 'updated_at'])


# ---------------------------------------------------------------------------
# Contact Tracing
# ---------------------------------------------------------------------------

class Contact(TimeStampedModel):
    """Contacts identified through case contact tracing."""

    TYPE_HOUSEHOLD = 'HOUSEHOLD'
    TYPE_WORKPLACE = 'WORKPLACE'
    TYPE_SOCIAL = 'SOCIAL'
    TYPE_HEALTHCARE = 'HEALTHCARE'
    TYPE_TRAVEL = 'TRAVEL'
    TYPE_OTHER = 'OTHER'
    CONTACT_TYPES = [
        (TYPE_HOUSEHOLD, 'Household Contact'),
        (TYPE_WORKPLACE, 'Workplace Contact'),
        (TYPE_SOCIAL, 'Social Contact'),
        (TYPE_HEALTHCARE, 'Healthcare Setting'),
        (TYPE_TRAVEL, 'Travel-related'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_IDENTIFIED = 'IDENTIFIED'
    STATUS_MONITORING = 'UNDER_MONITORING'
    STATUS_QUARANTINED = 'QUARANTINED'
    STATUS_SYMPTOMATIC = 'SYMPTOMATIC'
    STATUS_NEGATIVE = 'TESTED_NEGATIVE'
    STATUS_BECAME_CASE = 'BECAME_CASE'
    STATUS_CLEARED = 'CLEARED'
    STATUS_CHOICES = [
        (STATUS_IDENTIFIED, 'Identified'),
        (STATUS_MONITORING, 'Under Monitoring'),
        (STATUS_QUARANTINED, 'Quarantined'),
        (STATUS_SYMPTOMATIC, 'Developed Symptoms'),
        (STATUS_NEGATIVE, 'Tested Negative'),
        (STATUS_BECAME_CASE, 'Became Case'),
        (STATUS_CLEARED, 'Cleared'),
    ]

    contact_id = models.CharField(max_length=50, unique=True, db_index=True)

    # Source
    source_case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name='contacts'
    )

    # Contact demographics
    contact_name = models.CharField(max_length=200)
    contact_age = models.IntegerField(null=True, blank=True)
    contact_gender = models.CharField(max_length=10, blank=True)
    contact_phone = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)

    # Geography
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='contacts'
    )
    address = models.TextField(blank=True)

    # Exposure details
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    exposure_date = models.DateField()
    last_contact_date = models.DateField()
    exposure_setting = models.CharField(max_length=200, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_IDENTIFIED, db_index=True
    )

    # Monitoring window
    monitoring_start_date = models.DateField(null=True, blank=True)
    monitoring_end_date = models.DateField(null=True, blank=True)

    # Quarantine
    is_quarantined = models.BooleanField(default=False, db_index=True)
    quarantine_location = models.CharField(max_length=200, blank=True)
    quarantine_start_date = models.DateField(null=True, blank=True)
    quarantine_end_date = models.DateField(null=True, blank=True)

    # Testing
    test_recommended = models.BooleanField(default=False)
    test_date = models.DateField(null=True, blank=True)
    test_result = models.CharField(max_length=20, blank=True)

    # Case conversion
    became_case = models.ForeignKey(
        Case, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='originated_from_contact'
    )

    # Assignment
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_contacts'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contact_id']),
            models.Index(fields=['status', 'source_case']),
            models.Index(fields=['location', 'status']),
            models.Index(fields=['is_quarantined', 'status']),
        ]

    def __str__(self):
        return f"{self.contact_id} — {self.contact_name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.last_contact_date and self.exposure_date and self.last_contact_date < self.exposure_date:
            raise ValidationError(
                {'last_contact_date': 'Last contact date cannot be before exposure date.'}
            )

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def start_monitoring(self, period_days: int = 14, start_date=None):
        today = start_date or timezone.now().date()
        from datetime import timedelta
        self.status = self.STATUS_MONITORING
        self.monitoring_start_date = today
        self.monitoring_end_date = today + timedelta(days=period_days)
        self.save(update_fields=[
            'status', 'monitoring_start_date',
            'monitoring_end_date', 'updated_at'
        ])

    def flag_symptomatic(self):
        self.status = self.STATUS_SYMPTOMATIC
        self.save(update_fields=['status', 'updated_at'])

    def convert_to_case(self, case: 'Case'):
        self.status = self.STATUS_BECAME_CASE
        self.became_case = case
        self.save(update_fields=['status', 'became_case', 'updated_at'])

    def clear(self):
        self.status = self.STATUS_CLEARED
        self.is_quarantined = False
        self.save(update_fields=['status', 'is_quarantined', 'updated_at'])


class ContactMonitoring(TimeStampedModel):
    """Daily symptom-check record for a monitored contact."""

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name='monitoring_records'
    )
    monitoring_date = models.DateField(db_index=True)

    # Symptoms
    has_symptoms = models.BooleanField(default=False)
    symptoms = models.JSONField(default=list, blank=True)
    temperature = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )

    # Compliance
    is_reachable = models.BooleanField(default=True)
    is_compliant = models.BooleanField(default=True)

    # Follow-up
    notes = models.TextField(blank=True)
    action_taken = models.CharField(max_length=200, blank=True)

    monitored_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='monitoring_records'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-monitoring_date']
        unique_together = ['contact', 'monitoring_date']

    def __str__(self):
        return f"{self.contact.contact_name} — {self.monitoring_date}"


# ---------------------------------------------------------------------------
# Testing Coordination
# ---------------------------------------------------------------------------

class TestingCenter(TimeStampedModel):
    """Disease testing facility."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, db_index=True)

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='testing_centers'
    )
    address = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    daily_capacity = models.IntegerField(default=100)
    current_load = models.IntegerField(default=0)

    test_types = models.JSONField(default=list, blank=True)
    operating_hours = models.JSONField(default=dict, blank=True)

    is_operational = models.BooleanField(default=True, db_index=True)

    managed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='managed_testing_centers'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def available_slots(self):
        return max(0, self.daily_capacity - self.current_load)

    @property
    def is_at_capacity(self):
        return self.current_load >= self.daily_capacity


class TestingAppointment(TimeStampedModel):
    """Scheduled testing appointment."""

    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_NO_SHOW = 'NO_SHOW'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'No Show'),
    ]

    RESULT_POSITIVE = 'POSITIVE'
    RESULT_NEGATIVE = 'NEGATIVE'
    RESULT_INCONCLUSIVE = 'INCONCLUSIVE'
    RESULT_PENDING = 'PENDING'
    RESULT_CHOICES = [
        (RESULT_POSITIVE, 'Positive'),
        (RESULT_NEGATIVE, 'Negative'),
        (RESULT_INCONCLUSIVE, 'Inconclusive'),
        (RESULT_PENDING, 'Pending'),
    ]

    appointment_id = models.CharField(max_length=50, unique=True, db_index=True)

    testing_center = models.ForeignKey(
        TestingCenter, on_delete=models.CASCADE, related_name='appointments'
    )

    patient_name = models.CharField(max_length=200)
    patient_contact = models.CharField(max_length=200)
    patient_id_number = models.CharField(max_length=50, blank=True)

    # Linkage
    case = models.ForeignKey(
        Case, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='testing_appointments'
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='testing_appointments'
    )

    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField()
    test_type = models.CharField(max_length=100)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, db_index=True
    )

    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES,
        default=RESULT_PENDING, blank=True
    )
    result_date = models.DateField(null=True, blank=True)
    lab_reference = models.CharField(max_length=100, blank=True)

    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        indexes = [
            models.Index(fields=['appointment_date', 'testing_center']),
            models.Index(fields=['status', 'appointment_date']),
        ]

    def __str__(self):
        return f"{self.appointment_id} — {self.patient_name}"

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def record_result(self, result: str, result_date=None, lab_ref: str = ''):
        assert result in (
            self.RESULT_POSITIVE, self.RESULT_NEGATIVE, self.RESULT_INCONCLUSIVE
        ), f"Invalid result: {result}"
        self.result = result
        self.result_date = result_date or timezone.now().date()
        self.status = self.STATUS_COMPLETED
        if lab_ref:
            self.lab_reference = lab_ref
        self.save(update_fields=[
            'result', 'result_date', 'status', 'lab_reference', 'updated_at'
        ])

    def cancel(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def mark_no_show(self):
        self.status = self.STATUS_NO_SHOW
        self.save(update_fields=['status', 'updated_at'])


# ---------------------------------------------------------------------------
# Vaccination Campaigns
# ---------------------------------------------------------------------------

class VaccinationCampaign(TimeStampedModel):
    """Coordinated vaccination drive."""

    STATUS_PLANNING = 'PLANNING'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_PLANNING, 'Planning'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    campaign_code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)

    vaccine_name = models.CharField(max_length=200)
    vaccine_type = models.CharField(max_length=100, blank=True)
    total_doses_per_person = models.IntegerField(default=1)

    target_disease = models.CharField(max_length=200)
    target_population = models.IntegerField()
    target_locations = models.ManyToManyField(
        Location, related_name='vaccination_campaigns'
    )

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PLANNING, db_index=True
    )

    # Progress counters — updated by signals/tasks
    doses_administered = models.IntegerField(default=0)
    people_vaccinated = models.IntegerField(default=0)

    campaign_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='vaccination_campaigns'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.campaign_code})"

    @property
    def coverage_rate(self):
        if self.target_population:
            return round(
                (self.people_vaccinated / self.target_population) * 100, 2
            )
        return 0.0

    def activate(self):
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=['status', 'updated_at'])

    def pause(self):
        self.status = self.STATUS_PAUSED
        self.save(update_fields=['status', 'updated_at'])

    def complete(self):
        self.status = self.STATUS_COMPLETED
        self.save(update_fields=['status', 'updated_at'])


class VaccinationRecord(TimeStampedModel):
    """Individual vaccination dose record."""

    record_id = models.CharField(max_length=50, unique=True, db_index=True)

    campaign = models.ForeignKey(
        VaccinationCampaign, on_delete=models.CASCADE,
        related_name='vaccination_records'
    )

    patient_name = models.CharField(max_length=200)
    patient_age = models.IntegerField()
    patient_gender = models.CharField(max_length=10)
    patient_id_number = models.CharField(max_length=50, blank=True, db_index=True)
    patient_contact = models.CharField(max_length=200, blank=True)

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='vaccination_records'
    )
    vaccination_site = models.CharField(max_length=200, blank=True)

    vaccine_name = models.CharField(max_length=200)
    vaccine_batch = models.CharField(max_length=100)
    dose_number = models.IntegerField()
    vaccination_date = models.DateField(db_index=True)

    next_dose_due = models.DateField(null=True, blank=True)

    adverse_event_reported = models.BooleanField(default=False)
    adverse_event_details = models.TextField(blank=True)
    adverse_event_severity = models.CharField(max_length=20, blank=True)

    administered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='administered_vaccinations'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-vaccination_date']
        indexes = [
            models.Index(fields=['campaign', 'vaccination_date']),
            models.Index(fields=['patient_id_number']),
            models.Index(fields=['next_dose_due']),
        ]

    def __str__(self):
        return f"{self.record_id} — {self.patient_name} (dose {self.dose_number})"

    def report_adverse_event(self, details: str, severity: str = 'MILD'):
        self.adverse_event_reported = True
        self.adverse_event_details = details
        self.adverse_event_severity = severity
        self.save(update_fields=[
            'adverse_event_reported', 'adverse_event_details',
            'adverse_event_severity', 'updated_at'
        ])


# ---------------------------------------------------------------------------
# Quarantine Management
# ---------------------------------------------------------------------------

class QuarantineFacility(TimeStampedModel):
    """Quarantine / isolation facility."""

    TYPE_QUARANTINE = 'QUARANTINE'
    TYPE_ISOLATION = 'ISOLATION'
    TYPE_HOTEL = 'HOTEL'
    FACILITY_TYPES = [
        (TYPE_QUARANTINE, 'Quarantine Facility'),
        (TYPE_ISOLATION, 'Isolation Center'),
        (TYPE_HOTEL, 'Quarantine Hotel'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPES)

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='quarantine_facilities'
    )
    address = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    total_capacity = models.IntegerField()
    current_occupancy = models.IntegerField(default=0)

    amenities = models.JSONField(default=list, blank=True)

    contact_person = models.CharField(max_length=200, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    is_operational = models.BooleanField(default=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Quarantine Facilities'

    def __str__(self):
        return f"{self.name} ({self.get_facility_type_display()})"

    @property
    def available_beds(self):
        return max(0, self.total_capacity - self.current_occupancy)

    @property
    def occupancy_rate(self):
        if self.total_capacity:
            return round((self.current_occupancy / self.total_capacity) * 100, 2)
        return 0.0

    @property
    def is_full(self):
        return self.current_occupancy >= self.total_capacity

    def increment_occupancy(self):
        if self.is_full:
            raise ValueError(f"Facility {self.name} is at full capacity.")
        self.current_occupancy = models.F('current_occupancy') + 1
        self.save(update_fields=['current_occupancy', 'updated_at'])
        self.refresh_from_db(fields=['current_occupancy'])

    def decrement_occupancy(self):
        if self.current_occupancy <= 0:
            return
        self.current_occupancy = models.F('current_occupancy') - 1
        self.save(update_fields=['current_occupancy', 'updated_at'])
        self.refresh_from_db(fields=['current_occupancy'])


class QuarantineRecord(TimeStampedModel):
    """Individual quarantine / isolation record."""

    STATUS_ADMITTED = 'ADMITTED'
    STATUS_IN_QUARANTINE = 'IN_QUARANTINE'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_RELEASED_EARLY = 'RELEASED_EARLY'
    STATUS_TRANSFERRED = 'TRANSFERRED'
    STATUS_CHOICES = [
        (STATUS_ADMITTED, 'Admitted'),
        (STATUS_IN_QUARANTINE, 'In Quarantine'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_RELEASED_EARLY, 'Released Early'),
        (STATUS_TRANSFERRED, 'Transferred'),
    ]

    record_id = models.CharField(max_length=50, unique=True, db_index=True)

    facility = models.ForeignKey(
        QuarantineFacility, on_delete=models.CASCADE, related_name='quarantine_records'
    )

    individual_name = models.CharField(max_length=200)
    individual_contact = models.CharField(max_length=200, blank=True)
    individual_id_number = models.CharField(max_length=50, blank=True)

    # Linkage
    case = models.ForeignKey(
        Case, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quarantine_records'
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quarantine_records'
    )

    admission_date = models.DateField()
    expected_release_date = models.DateField()
    actual_release_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_ADMITTED, db_index=True
    )

    room_number = models.CharField(max_length=50, blank=True)
    daily_monitoring = models.BooleanField(default=True)

    release_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-admission_date']
        indexes = [
            models.Index(fields=['facility', 'status']),
            models.Index(fields=['expected_release_date', 'status']),
        ]

    def __str__(self):
        return f"{self.record_id} — {self.individual_name}"

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def start_quarantine(self):
        self.status = self.STATUS_IN_QUARANTINE
        self.save(update_fields=['status', 'updated_at'])

    def complete_quarantine(self, release_date=None):
        today = release_date or timezone.now().date()
        self.status = self.STATUS_COMPLETED
        self.actual_release_date = today
        self.save(update_fields=['status', 'actual_release_date', 'updated_at'])
        self.facility.decrement_occupancy()

    def release_early(self, reason: str, release_date=None):
        today = release_date or timezone.now().date()
        self.status = self.STATUS_RELEASED_EARLY
        self.actual_release_date = today
        self.release_reason = reason
        self.save(update_fields=[
            'status', 'actual_release_date', 'release_reason', 'updated_at'
        ])
        self.facility.decrement_occupancy()

    def transfer(self, new_facility: QuarantineFacility, reason: str = ''):
        """Transfer individual to another facility."""
        old_facility = self.facility
        self.status = self.STATUS_TRANSFERRED
        self.release_reason = reason or f"Transferred to {new_facility.name}"
        self.actual_release_date = timezone.now().date()
        self.save(update_fields=[
            'status', 'release_reason', 'actual_release_date', 'updated_at'
        ])
        old_facility.decrement_occupancy()

        # Create new record at new facility
        new_record = QuarantineRecord.objects.create(
            record_id=f"{self.record_id}-{uuid.uuid4().hex[:6]}",
            facility=new_facility,
            individual_name=self.individual_name,
            individual_contact=self.individual_contact,
            individual_id_number=self.individual_id_number,
            case=self.case,
            contact=self.contact,
            admission_date=timezone.now().date(),
            expected_release_date=self.expected_release_date,
            status=self.STATUS_ADMITTED,
            daily_monitoring=self.daily_monitoring,
            notes=f"Transferred from {old_facility.name}.",
        )
        new_facility.increment_occupancy()
        return new_record