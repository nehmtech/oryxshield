"""
Integrations models for OryxShield.

External system connectivity, data mapping, webhooks, API keys,
integration jobs, data transfers, and full audit logging.
"""
import uuid
import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import TimeStampedModel

User = get_user_model()


class ExternalSystem(TimeStampedModel):
    """
    External systems connected to OryxShield.
    Stores connection details, auth credentials (encrypted), health state.
    """
    SYSTEM_TYPES = [
        ('DHIS2', 'DHIS2'),
        ('SORMAS', 'SORMAS'),
        ('WHO_EIOS', 'WHO EIOS'),
        ('AFRICA_CDC', 'Africa CDC'),
        ('LIS', 'Laboratory Information System'),
        ('EMR', 'Electronic Medical Record'),
        ('HMIS', 'Health Management Information System'),
        ('CUSTOM', 'Custom System'),
    ]

    AUTH_TYPES = [
        ('API_KEY', 'API Key'),
        ('OAUTH2', 'OAuth 2.0'),
        ('BASIC', 'Basic Auth'),
        ('TOKEN', 'Token Auth'),
    ]

    HEALTH_STATUS = [
        ('UNKNOWN', 'Unknown'),
        ('HEALTHY', 'Healthy'),
        ('DEGRADED', 'Degraded'),
        ('UNHEALTHY', 'Unhealthy'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    system_code = models.CharField(max_length=50, unique=True, db_index=True)
    system_type = models.CharField(max_length=20, choices=SYSTEM_TYPES, db_index=True)
    description = models.TextField(blank=True)

    # Connection
    base_url = models.URLField(max_length=500)
    api_version = models.CharField(max_length=20, blank=True)
    timeout_seconds = models.IntegerField(default=30)

    # Auth
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES)
    credentials = models.JSONField(default=dict, blank=True, help_text="Encrypted credential store")

    # Runtime configuration
    configuration = models.JSONField(default=dict, blank=True)
    sync_interval_minutes = models.IntegerField(default=60)
    batch_size = models.IntegerField(default=100)

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_enabled = models.BooleanField(default=True)

    # Health
    health_status = models.CharField(max_length=20, choices=HEALTH_STATUS, default='UNKNOWN', db_index=True)
    health_message = models.TextField(blank=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)

    # Stats (updated via F())
    total_sync_count = models.IntegerField(default=0)
    successful_sync_count = models.IntegerField(default=0)
    failed_sync_count = models.IntegerField(default=0)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['system_type', 'is_active']),
            models.Index(fields=['health_status', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.system_type})"

    # ------------------------------------------------------------------
    # Credential encryption helpers
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        """Encrypt credentials before writing to DB."""
        from .encryption import encrypt_credentials, is_encrypted
        if self.credentials and not is_encrypted(self.credentials):
            self.credentials = encrypt_credentials(self.credentials)
        super().save(*args, **kwargs)

    def get_credentials(self) -> dict:
        """Return the decrypted credentials dict."""
        from .encryption import decrypt_credentials
        return decrypt_credentials(self.credentials)

    def set_credentials(self, data: dict) -> None:
        """Encrypt and store credentials (call save() afterwards)."""
        from .encryption import encrypt_credentials
        self.credentials = encrypt_credentials(data)

    def mark_healthy(self, message=""):
        self.health_status = 'HEALTHY'
        self.health_message = message
        self.last_health_check = timezone.now()
        self.consecutive_failures = 0
        self.save(update_fields=[
            'health_status', 'health_message', 'last_health_check',
            'consecutive_failures', 'updated_at'
        ])

    def mark_unhealthy(self, message=""):
        from django.db.models import F
        self.health_status = 'UNHEALTHY'
        self.health_message = message
        self.last_health_check = timezone.now()
        self.save(update_fields=['health_status', 'health_message', 'last_health_check', 'updated_at'])
        ExternalSystem.objects.filter(pk=self.pk).update(
            consecutive_failures=F('consecutive_failures') + 1
        )

    def record_sync_success(self):
        from django.db.models import F
        ExternalSystem.objects.filter(pk=self.pk).update(
            total_sync_count=F('total_sync_count') + 1,
            successful_sync_count=F('successful_sync_count') + 1,
            last_sync=timezone.now()
        )

    def record_sync_failure(self):
        from django.db.models import F
        ExternalSystem.objects.filter(pk=self.pk).update(
            total_sync_count=F('total_sync_count') + 1,
            failed_sync_count=F('failed_sync_count') + 1
        )


class DataMapping(TimeStampedModel):
    """
    Field mappings between OryxShield and external systems.
    Supports transformation rules, validation, bidirectional sync.
    """
    DIRECTION_CHOICES = [
        ('INBOUND', 'Inbound (External → OryxShield)'),
        ('OUTBOUND', 'Outbound (OryxShield → External)'),
        ('BIDIRECTIONAL', 'Bidirectional'),
    ]

    TRANSFORM_TYPES = [
        ('NONE', 'No transformation'),
        ('UPPERCASE', 'Uppercase'),
        ('LOWERCASE', 'Lowercase'),
        ('DATE_FORMAT', 'Date format conversion'),
        ('CODE_LOOKUP', 'Code lookup table'),
        ('EXPRESSION', 'Custom expression'),
        ('CONCAT', 'Concatenate fields'),
        ('SPLIT', 'Split field'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.CASCADE,
        related_name='data_mappings'
    )

    entity_type = models.CharField(max_length=100, db_index=True)
    source_field = models.CharField(max_length=200)
    target_field = models.CharField(max_length=200)

    # Transformation
    transform_type = models.CharField(max_length=20, choices=TRANSFORM_TYPES, default='NONE')
    transformation_rule = models.TextField(blank=True)
    transform_params = models.JSONField(default=dict, blank=True)
    default_value = models.CharField(max_length=500, blank=True)

    # Validation
    is_required = models.BooleanField(default=False)
    validation_rule = models.TextField(blank=True)
    validation_error_action = models.CharField(
        max_length=20,
        choices=[('SKIP', 'Skip record'), ('FAIL', 'Fail job'), ('DEFAULT', 'Use default')],
        default='SKIP'
    )

    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='BIDIRECTIONAL')
    priority = models.IntegerField(default=0, help_text="Lower = applied first")
    is_active = models.BooleanField(default=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['external_system', 'entity_type', 'priority']
        indexes = [
            models.Index(fields=['external_system', 'entity_type', 'direction']),
        ]

    def __str__(self):
        return f"{self.entity_type}: {self.source_field} → {self.target_field} ({self.direction})"


class IntegrationJob(TimeStampedModel):
    """
    Integration jobs for data import, export, and bidirectional sync.
    Full lifecycle: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED.
    """
    JOB_TYPES = [
        ('IMPORT', 'Import Data'),
        ('EXPORT', 'Export Data'),
        ('SYNC', 'Bidirectional Sync'),
        ('WEBHOOK', 'Webhook Trigger'),
        ('VALIDATION', 'Data Validation'),
        ('MIGRATION', 'Data Migration'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('QUEUED', 'Queued'),
        ('RUNNING', 'Running'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('RETRYING', 'Retrying'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Critical'),
        (2, 'High'),
        (3, 'Normal'),
        (4, 'Low'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.CharField(max_length=50, unique=True, db_index=True)

    external_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.CASCADE,
        related_name='integration_jobs'
    )

    job_type = models.CharField(max_length=20, choices=JOB_TYPES, db_index=True)
    entity_type = models.CharField(max_length=100)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    celery_task_id = models.CharField(max_length=200, blank=True)

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Progress
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Pagination state (for resumable jobs)
    last_cursor = models.CharField(max_length=500, blank=True)
    last_page = models.IntegerField(default=0)

    # Filters and config
    filters = models.JSONField(default=dict, blank=True)
    job_config = models.JSONField(default=dict, blank=True)

    # Results
    result_summary = models.JSONField(default=dict, blank=True)
    error_log = models.TextField(blank=True)
    warnings = models.JSONField(default=list, blank=True)

    # Retry state
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_integration_jobs'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['external_system', 'job_type', 'status']),
            models.Index(fields=['priority', 'status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.job_id} — {self.job_type} ({self.status})"

    def start(self):
        self.status = 'RUNNING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

    def complete(self, summary=None):
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.progress_percent = 100
        if summary:
            self.result_summary = summary
        self.save(update_fields=[
            'status', 'completed_at', 'progress_percent', 'result_summary', 'updated_at'
        ])

    def fail(self, error_message):
        self.status = 'FAILED'
        self.completed_at = timezone.now()
        self.error_log = error_message
        self.save(update_fields=['status', 'completed_at', 'error_log', 'updated_at'])

    def cancel(self):
        self.status = 'CANCELLED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def update_progress(self, processed, successful, failed, skipped=0):
        from django.db.models import F
        self.processed_records = processed
        self.successful_records = successful
        self.failed_records = failed
        self.skipped_records = skipped
        if self.total_records > 0:
            self.progress_percent = round((processed / self.total_records) * 100, 2)
        self.save(update_fields=[
            'processed_records', 'successful_records', 'failed_records',
            'skipped_records', 'progress_percent', 'updated_at'
        ])


class Webhook(TimeStampedModel):
    """
    Webhook configurations for event-driven outbound notifications.
    Supports secret-key signing, retry policies, event filters.
    """
    EVENT_TYPES = [
        ('CASE_CREATED', 'Case Created'),
        ('CASE_UPDATED', 'Case Updated'),
        ('ALERT_GENERATED', 'Alert Generated'),
        ('ALERT_RESOLVED', 'Alert Resolved'),
        ('OUTBREAK_DETECTED', 'Outbreak Detected'),
        ('RESPONSE_ACTIVATED', 'Response Activated'),
        ('RESPONSE_COMPLETED', 'Response Completed'),
        ('THRESHOLD_BREACHED', 'Threshold Breached'),
        ('CUSTOM', 'Custom Event'),
    ]

    SIGNING_ALGORITHMS = [
        ('SHA256', 'HMAC-SHA256'),
        ('SHA512', 'HMAC-SHA512'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    webhook_url = models.URLField(max_length=500)

    # Events
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    event_filters = models.JSONField(default=dict, blank=True, help_text="Filter conditions for event triggering")

    # Auth
    secret_key = models.CharField(max_length=300, blank=True)
    signing_algorithm = models.CharField(max_length=10, choices=SIGNING_ALGORITHMS, default='SHA256')
    headers = models.JSONField(default=dict, blank=True)

    # Retry policy
    retry_attempts = models.IntegerField(default=3)
    retry_delay_seconds = models.IntegerField(default=60)
    retry_backoff_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=2.0)
    timeout_seconds = models.IntegerField(default=30)

    # Payload template
    payload_template = models.JSONField(default=dict, blank=True)
    include_full_object = models.BooleanField(default=True)

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    last_verification_at = models.DateTimeField(null=True, blank=True)

    # Stats (updated via F())
    total_calls = models.IntegerField(default=0)
    successful_calls = models.IntegerField(default=0)
    failed_calls = models.IntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    last_failure = models.DateTimeField(null=True, blank=True)
    average_response_ms = models.IntegerField(default=0)

    external_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhooks'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_webhooks'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['event_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.event_type})"

    def record_call(self, success, response_ms=0):
        from django.db.models import F
        now = timezone.now()
        update = {
            'total_calls': F('total_calls') + 1,
            'last_triggered': now,
        }
        if success:
            update['successful_calls'] = F('successful_calls') + 1
            update['last_success'] = now
        else:
            update['failed_calls'] = F('failed_calls') + 1
            update['last_failure'] = now
        Webhook.objects.filter(pk=self.pk).update(**update)


class WebhookLog(TimeStampedModel):
    """
    Immutable audit trail of all webhook call attempts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='logs')

    # Event
    event_type = models.CharField(max_length=30, blank=True)
    entity_id = models.CharField(max_length=200, blank=True)

    # Request
    request_payload = models.JSONField()
    request_headers = models.JSONField(default=dict, blank=True)
    signature = models.CharField(max_length=200, blank=True)

    # Response
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)

    # Outcome
    is_successful = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True)

    # Retry
    attempt_number = models.IntegerField(default=1)
    is_final_attempt = models.BooleanField(default=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', '-created_at']),
            models.Index(fields=['is_successful', '-created_at']),
        ]

    def __str__(self):
        return f"{self.webhook.name} attempt {self.attempt_number} — {'OK' if self.is_successful else 'FAIL'}"


class APIKey(TimeStampedModel):
    """
    API keys for external access to OryxShield.
    Supports permissions, IP whitelisting, rate limiting, usage tracking.
    """
    SCOPE_CHOICES = [
        ('READ', 'Read only'),
        ('WRITE', 'Read and write'),
        ('ADMIN', 'Full admin access'),
        ('WEBHOOK', 'Webhook delivery only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key_prefix = models.CharField(max_length=10, db_index=True)
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='oryxshield_api_keys'
    )

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='READ')
    permissions = models.JSONField(default=list, blank=True)
    allowed_endpoints = models.JSONField(default=list, blank=True, help_text="Restrict to specific endpoints")

    # IP restriction
    ip_whitelist = models.JSONField(default=list, blank=True)
    ip_blacklist = models.JSONField(default=list, blank=True)

    # Rate limiting
    rate_limit = models.IntegerField(default=1000, help_text="Requests per hour")
    burst_limit = models.IntegerField(default=100, help_text="Max burst requests per minute")

    # Usage (updated via F())
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_api_keys'
    )
    revocation_reason = models.TextField(blank=True)

    external_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_keys'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @classmethod
    def generate_key(cls):
        """Generate a new API key, returning (raw_key, prefix, hash)."""
        import hashlib
        raw = f"lk_{secrets.token_urlsafe(40)}"
        prefix = raw[:10]
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        return raw, prefix, key_hash

    def record_request(self, success=True, ip=None):
        from django.db.models import F
        update = {
            'total_requests': F('total_requests') + 1,
            'last_used': timezone.now(),
        }
        if success:
            update['successful_requests'] = F('successful_requests') + 1
        else:
            update['failed_requests'] = F('failed_requests') + 1
        if ip:
            self.last_used_ip = ip
            self.save(update_fields=['last_used_ip', 'updated_at'])
        APIKey.objects.filter(pk=self.pk).update(**update)

    @property
    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and not self.revoked_at


class IntegrationLog(TimeStampedModel):
    """
    Structured integration activity logs with request/response capture.
    """
    LOG_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    LOG_CATEGORIES = [
        ('SYNC', 'Sync operation'),
        ('WEBHOOK', 'Webhook event'),
        ('AUTH', 'Authentication'),
        ('MAPPING', 'Data mapping'),
        ('TRANSFORM', 'Transformation'),
        ('VALIDATION', 'Validation'),
        ('HEALTH', 'Health check'),
        ('GENERAL', 'General'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='integration_logs'
    )
    integration_job = models.ForeignKey(
        'IntegrationJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )

    log_level = models.CharField(max_length=20, choices=LOG_LEVELS, default='INFO', db_index=True)
    category = models.CharField(max_length=20, choices=LOG_CATEGORIES, default='GENERAL')
    message = models.TextField()

    # Context
    entity_type = models.CharField(max_length=100, blank=True)
    entity_id = models.CharField(max_length=200, blank=True)
    operation = models.CharField(max_length=100, blank=True)

    # Request/Response
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    # Error details
    error_code = models.CharField(max_length=50, blank=True)
    error_detail = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)

    # Actor
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integration_log_entries'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['log_level', '-created_at']),
            models.Index(fields=['external_system', 'category', '-created_at']),
            models.Index(fields=['integration_job', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.log_level}] {self.message[:80]}"


class DataTransfer(TimeStampedModel):
    """
    Data transfer records between systems with full metrics.
    """
    TRANSFER_TYPES = [
        ('BATCH', 'Batch Transfer'),
        ('REALTIME', 'Real-time Transfer'),
        ('SCHEDULED', 'Scheduled Transfer'),
        ('MANUAL', 'Manual Transfer'),
    ]

    STATUS_CHOICES = [
        ('QUEUED', 'Queued'),
        ('TRANSFERRING', 'Transferring'),
        ('VERIFYING', 'Verifying'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partially completed'),
        ('ROLLED_BACK', 'Rolled back'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_id = models.CharField(max_length=50, unique=True, db_index=True)

    source_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.CASCADE,
        related_name='outgoing_transfers'
    )
    target_system = models.ForeignKey(
        ExternalSystem,
        on_delete=models.CASCADE,
        related_name='incoming_transfers'
    )

    integration_job = models.ForeignKey(
        IntegrationJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='data_transfers'
    )

    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES, db_index=True)
    entity_type = models.CharField(max_length=100)

    # Volume
    record_count = models.IntegerField(default=0)
    data_size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=200, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='QUEUED', db_index=True)
    status_message = models.TextField(blank=True)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Results
    transferred_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    validation_errors = models.JSONField(default=list, blank=True)

    # Transfer config
    transfer_config = models.JSONField(default=dict, blank=True)

    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_transfers'
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['source_system', 'target_system', '-created_at']),
        ]

    def __str__(self):
        return f"{self.transfer_id}: {self.source_system} → {self.target_system} ({self.status})"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        if self.record_count > 0:
            return round(self.transferred_records / self.record_count * 100, 2)
        return 0