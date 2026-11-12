"""
Mobile models for OryxShield.

Patterns: TimeStampedModel, soft-delete (is_deleted), F() for counters,
no PostGIS (lat/lng DecimalFields + GeoJSON JSONField).
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import F
from core.models import TimeStampedModel, Location


class MobileDevice(TimeStampedModel):
    """Registered mobile devices with push notification support."""

    DEVICE_TYPES = [
        ('ANDROID', 'Android'),
        ('IOS', 'iOS'),
        ('TABLET', 'Tablet'),
        ('OTHER', 'Other'),
    ]

    device_id = models.CharField(max_length=200, unique=True, db_index=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mobile_devices'
    )

    device_name = models.CharField(max_length=200, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=50, blank=True)

    # Push notifications
    fcm_token = models.CharField(max_length=500, blank=True)
    apns_token = models.CharField(max_length=500, blank=True)
    push_enabled = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True, db_index=True)
    last_active = models.DateTimeField(auto_now=True)

    last_known_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_known_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_known_geojson = models.JSONField(default=dict, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-last_active']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_id', 'is_active']),
        ]

    def __str__(self):
        return f"{self.device_name or self.device_id} ({self.user.username})"

    def update_location(self, latitude, longitude):
        """Atomically update last known location."""
        self.last_known_latitude = latitude
        self.last_known_longitude = longitude
        self.last_known_geojson = {
            'type': 'Point',
            'coordinates': [float(longitude), float(latitude)],
        }
        self.save(update_fields=[
            'last_known_latitude', 'last_known_longitude',
            'last_known_geojson', 'last_active',
        ])


class OfflineData(TimeStampedModel):
    """
    Offline data sync queue.

    Items move through: PENDING → SYNCING → SYNCED | FAILED | CONFLICT.
    """

    SYNC_STATUS = [
        ('PENDING', 'Pending'),
        ('SYNCING', 'Syncing'),
        ('SYNCED', 'Synced'),
        ('FAILED', 'Failed'),
        ('CONFLICT', 'Conflict'),
    ]

    DATA_TYPES = [
        ('CASE', 'Case Data'),
        ('CONTACT', 'Contact Data'),
        ('MONITORING', 'Monitoring Record'),
        ('SURVEY', 'Survey Response'),
        ('HEALTH_DATA', 'Health Data'),
    ]

    device = models.ForeignKey(
        MobileDevice, on_delete=models.CASCADE, related_name='offline_data'
    )

    data_type = models.CharField(max_length=20, choices=DATA_TYPES, db_index=True)
    data_payload = models.JSONField()
    checksum = models.CharField(max_length=64, blank=True)

    sync_status = models.CharField(
        max_length=20, choices=SYNC_STATUS, default='PENDING', db_index=True
    )
    sync_attempts = models.PositiveSmallIntegerField(default=0)

    created_offline_at = models.DateTimeField()
    synced_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    # After successful sync, store the server-side PK for reference
    server_record_id = models.CharField(max_length=200, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sync_status', 'device']),
            models.Index(fields=['data_type', 'sync_status']),
            models.Index(fields=['device', 'sync_status', 'created_offline_at']),
        ]

    def __str__(self):
        return f"{self.data_type} [{self.sync_status}] — {self.device.device_id}"

    def increment_attempts(self):
        OfflineData.objects.filter(pk=self.pk).update(
            sync_attempts=F('sync_attempts') + 1
        )


class FieldWorker(TimeStampedModel):
    """Community health workers and field staff."""

    WORKER_TYPES = [
        ('CHW', 'Community Health Worker'),
        ('NURSE', 'Nurse'),
        ('CONTACT_TRACER', 'Contact Tracer'),
        ('VACCINATOR', 'Vaccinator'),
        ('SURVEILLANCE_OFFICER', 'Surveillance Officer'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='field_worker'
    )

    worker_id = models.CharField(max_length=50, unique=True, db_index=True)
    worker_type = models.CharField(max_length=30, choices=WORKER_TYPES, db_index=True)

    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    assigned_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_workers',
    )
    coverage_areas = models.ManyToManyField(
        Location, related_name='covered_by_workers', blank=True
    )

    # Performance counters — incremented atomically with F()
    cases_managed = models.PositiveIntegerField(default=0)
    contacts_traced = models.PositiveIntegerField(default=0)
    surveys_completed = models.PositiveIntegerField(default=0)
    activities_logged = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True, db_index=True)

    current_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    current_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    current_geojson = models.JSONField(default=dict, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['worker_id']
        indexes = [
            models.Index(fields=['worker_type', 'is_active']),
            models.Index(fields=['assigned_location', 'is_active']),
        ]

    def __str__(self):
        return f"{self.worker_id} — {self.user.get_full_name()}"

    def increment_counter(self, field: str):
        """Atomically increment a performance counter."""
        FieldWorker.objects.filter(pk=self.pk).update(**{field: F(field) + 1})

    def update_location(self, latitude, longitude):
        from django.utils import timezone
        FieldWorker.objects.filter(pk=self.pk).update(
            current_latitude=latitude,
            current_longitude=longitude,
            current_geojson={
                'type': 'Point',
                'coordinates': [float(longitude), float(latitude)],
            },
            last_location_update=timezone.now(),
        )


class FieldActivity(TimeStampedModel):
    """Field activities and visits with geolocation."""

    ACTIVITY_TYPES = [
        ('CASE_VISIT', 'Case Visit'),
        ('CONTACT_TRACING', 'Contact Tracing'),
        ('SURVEILLANCE', 'Surveillance'),
        ('VACCINATION', 'Vaccination'),
        ('HEALTH_EDUCATION', 'Health Education'),
        ('SAMPLE_COLLECTION', 'Sample Collection'),
    ]

    activity_id = models.CharField(max_length=50, unique=True, db_index=True)

    field_worker = models.ForeignKey(
        FieldWorker, on_delete=models.CASCADE, related_name='activities'
    )

    activity_type = models.CharField(
        max_length=20, choices=ACTIVITY_TYPES, db_index=True
    )

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='field_activities'
    )
    visit_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    visit_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    visit_geojson = models.JSONField(default=dict, blank=True)

    activity_date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    description = models.TextField()
    findings = models.JSONField(default=dict, blank=True)

    people_reached = models.PositiveIntegerField(default=0)

    # Stored as list of relative paths / S3 keys
    photos = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        verbose_name_plural = 'Field Activities'
        indexes = [
            models.Index(fields=['field_worker', '-activity_date']),
            models.Index(fields=['activity_type', '-activity_date']),
            models.Index(fields=['location', '-activity_date']),
        ]

    def __str__(self):
        return f"{self.activity_id} — {self.get_activity_type_display()}"

    def save(self, *args, **kwargs):
        if self.visit_latitude and self.visit_longitude and not self.visit_geojson:
            self.visit_geojson = {
                'type': 'Point',
                'coordinates': [float(self.visit_longitude), float(self.visit_latitude)],
            }
        super().save(*args, **kwargs)


class MobileSurvey(TimeStampedModel):
    """Mobile survey forms with versioning."""

    SURVEY_TYPES = [
        ('SCREENING', 'Health Screening'),
        ('ASSESSMENT', 'Risk Assessment'),
        ('FEEDBACK', 'Feedback Survey'),
        ('KNOWLEDGE', 'Knowledge Assessment'),
        ('SATISFACTION', 'Satisfaction Survey'),
    ]

    title = models.CharField(max_length=200)
    survey_code = models.CharField(max_length=50, unique=True, db_index=True)
    survey_type = models.CharField(max_length=20, choices=SURVEY_TYPES, db_index=True)

    description = models.TextField(blank=True)

    # JSON schema: list of {id, type, label, required, options, validation}
    questions = models.JSONField(default=list)

    target_locations = models.ManyToManyField(
        Location, related_name='mobile_surveys', blank=True
    )

    is_active = models.BooleanField(default=True, db_index=True)

    version = models.CharField(max_length=20, default='1.0')

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_surveys',
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['survey_type', 'title']
        indexes = [
            models.Index(fields=['survey_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.title} v{self.version} ({self.survey_code})"


class SurveyResponse(TimeStampedModel):
    """Survey responses collected in the field."""

    response_id = models.CharField(max_length=50, unique=True, db_index=True)

    survey = models.ForeignKey(
        MobileSurvey, on_delete=models.CASCADE, related_name='responses'
    )

    field_worker = models.ForeignKey(
        FieldWorker,
        on_delete=models.SET_NULL,
        null=True,
        related_name='survey_responses',
    )

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='survey_responses'
    )
    response_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    response_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    response_geojson = models.JSONField(default=dict, blank=True)

    # {question_id: answer_value}
    responses = models.JSONField()

    response_date = models.DateField(db_index=True)
    response_time = models.TimeField(null=True, blank=True)

    created_offline = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-response_date', '-created_at']
        indexes = [
            models.Index(fields=['survey', '-response_date']),
            models.Index(fields=['field_worker', '-response_date']),
            models.Index(fields=['location', '-response_date']),
        ]

    def __str__(self):
        return f"{self.response_id} — {self.survey.title}"


class DataCollectionForm(TimeStampedModel):
    """Custom data collection forms with field-level validation rules."""

    FORM_TYPES = [
        ('CASE_INVESTIGATION', 'Case Investigation'),
        ('CONTACT_TRACING', 'Contact Tracing'),
        ('OUTBREAK_INVESTIGATION', 'Outbreak Investigation'),
        ('HOUSEHOLD_SURVEY', 'Household Survey'),
        ('FACILITY_ASSESSMENT', 'Facility Assessment'),
    ]

    title = models.CharField(max_length=200)
    form_code = models.CharField(max_length=50, unique=True, db_index=True)
    form_type = models.CharField(max_length=30, choices=FORM_TYPES, db_index=True)

    description = models.TextField(blank=True)

    # List of {name, label, type, required, options, validation}
    form_fields = models.JSONField(default=list)

    # {field_name: {rule: value}}
    validation_rules = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forms',
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['form_type', 'title']
        indexes = [
            models.Index(fields=['form_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.title} ({self.form_code})"


class FormSubmission(TimeStampedModel):
    """Form submissions from mobile devices."""

    submission_id = models.CharField(max_length=50, unique=True, db_index=True)

    form = models.ForeignKey(
        DataCollectionForm, on_delete=models.CASCADE, related_name='submissions'
    )

    field_worker = models.ForeignKey(
        FieldWorker,
        on_delete=models.SET_NULL,
        null=True,
        related_name='form_submissions',
    )

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='form_submissions'
    )
    submission_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    submission_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    submission_geojson = models.JSONField(default=dict, blank=True)

    form_data = models.JSONField()

    # List of {name, url, mime_type, size_bytes}
    attachments = models.JSONField(default=list, blank=True)

    submission_date = models.DateField(db_index=True)
    submission_time = models.TimeField(null=True, blank=True)

    is_validated = models.BooleanField(default=False, db_index=True)
    validation_errors = models.JSONField(default=list, blank=True)

    created_offline = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-submission_date', '-created_at']
        indexes = [
            models.Index(fields=['form', '-submission_date']),
            models.Index(fields=['field_worker', '-submission_date']),
            models.Index(fields=['is_validated', '-submission_date']),
        ]

    def __str__(self):
        return f"{self.submission_id} — {self.form.title}"

    def validate_against_form(self):
        """
        Run server-side validation using the form's validation_rules.
        Returns (is_valid: bool, errors: list[str]).
        """
        errors = []
        rules = self.form.validation_rules

        for field_name, field_rules in rules.items():
            value = self.form_data.get(field_name)

            if field_rules.get('required') and (value is None or value == ''):
                errors.append(f"'{field_name}' is required.")
                continue

            if value is not None:
                if 'min_length' in field_rules and len(str(value)) < field_rules['min_length']:
                    errors.append(
                        f"'{field_name}' must be at least {field_rules['min_length']} characters."
                    )
                if 'max_length' in field_rules and len(str(value)) > field_rules['max_length']:
                    errors.append(
                        f"'{field_name}' must not exceed {field_rules['max_length']} characters."
                    )
                if 'allowed_values' in field_rules and value not in field_rules['allowed_values']:
                    errors.append(
                        f"'{field_name}' must be one of {field_rules['allowed_values']}."
                    )

        is_valid = len(errors) == 0
        FormSubmission.objects.filter(pk=self.pk).update(
            is_validated=is_valid,
            validation_errors=errors,
        )
        return is_valid, errors


class MobileNotification(TimeStampedModel):
    """Push notifications for mobile devices."""

    NOTIFICATION_TYPES = [
        ('ALERT', 'Alert'),
        ('TASK', 'Task Assignment'),
        ('REMINDER', 'Reminder'),
        ('UPDATE', 'Update'),
        ('MESSAGE', 'Message'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    notification_id = models.CharField(max_length=50, unique=True, db_index=True)

    device = models.ForeignKey(
        MobileDevice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mobile_notifications'
    )

    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, db_index=True
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_LEVELS, default='NORMAL', db_index=True
    )
    title = models.CharField(max_length=200)
    body = models.TextField()

    action_url = models.CharField(max_length=500, blank=True)
    action_data = models.JSONField(default=dict, blank=True)

    is_sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # FCM / APNS message IDs for delivery tracking
    fcm_message_id = models.CharField(max_length=200, blank=True)
    delivery_error = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['device', 'is_read']),
            models.Index(fields=['is_sent', 'expires_at']),
            models.Index(fields=['priority', 'is_sent']),
        ]

    def __str__(self):
        return f"[{self.priority}] {self.title} → {self.user.username}"