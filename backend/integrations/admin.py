"""Admin configuration for OryxShield integrations app."""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ExternalSystem, DataMapping, IntegrationJob, Webhook, WebhookLog,
    APIKey, IntegrationLog, DataTransfer
)


@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'system_code', 'system_type', 'is_active',
        'health_badge', 'last_sync', 'consecutive_failures'
    ]
    list_filter = ['system_type', 'is_active', 'health_status', 'auth_type']
    search_fields = ['name', 'system_code', 'base_url']
    readonly_fields = [
        'id', 'health_status', 'health_message', 'last_health_check',
        'consecutive_failures', 'total_sync_count', 'successful_sync_count',
        'failed_sync_count', 'last_sync', 'created_at', 'updated_at',
    ]
    fieldsets = (
        ('Identity', {'fields': ('id', 'name', 'system_code', 'system_type', 'description')}),
        ('Connection', {'fields': ('base_url', 'api_version', 'timeout_seconds', 'auth_type', 'credentials')}),
        ('Sync Config', {'fields': ('sync_enabled', 'sync_interval_minutes', 'batch_size', 'configuration')}),
        ('Status', {'fields': ('is_active', 'health_status', 'health_message', 'last_health_check', 'consecutive_failures')}),
        ('Stats', {'fields': ('total_sync_count', 'successful_sync_count', 'failed_sync_count', 'last_sync')}),
        ('Meta', {'fields': ('metadata', 'created_at', 'updated_at')}),
    )

    def health_badge(self, obj):
        colours = {'HEALTHY': 'green', 'DEGRADED': 'orange', 'UNHEALTHY': 'red', 'UNKNOWN': 'grey'}
        colour = colours.get(obj.health_status, 'grey')
        return format_html('<span style="color:{}">{}</span>', colour, obj.health_status)
    health_badge.short_description = 'Health'


@admin.register(DataMapping)
class DataMappingAdmin(admin.ModelAdmin):
    list_display = ['external_system', 'entity_type', 'source_field', 'target_field', 'direction', 'is_active', 'priority']
    list_filter = ['external_system', 'entity_type', 'direction', 'transform_type', 'is_active']
    search_fields = ['source_field', 'target_field', 'entity_type']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(IntegrationJob)
class IntegrationJobAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'external_system', 'job_type', 'entity_type',
        'status', 'priority', 'progress_percent', 'started_at', 'triggered_by'
    ]
    list_filter = ['job_type', 'status', 'priority', 'external_system']
    search_fields = ['job_id', 'entity_type', 'celery_task_id']
    readonly_fields = [
        'id', 'job_id', 'status', 'celery_task_id', 'started_at', 'completed_at',
        'processed_records', 'successful_records', 'failed_records', 'skipped_records',
        'progress_percent', 'retry_count', 'result_summary', 'error_log',
        'triggered_by', 'created_at', 'updated_at',
    ]


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'event_type', 'is_active', 'is_verified',
        'total_calls', 'successful_calls', 'failed_calls', 'last_triggered'
    ]
    list_filter = ['event_type', 'is_active', 'is_verified', 'signing_algorithm']
    search_fields = ['name', 'webhook_url']
    readonly_fields = [
        'id', 'total_calls', 'successful_calls', 'failed_calls',
        'last_triggered', 'last_success', 'last_failure', 'average_response_ms',
        'created_by', 'created_at', 'updated_at',
    ]


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = [
        'webhook', 'event_type', 'response_status_code',
        'is_successful', 'response_time_ms', 'attempt_number', 'created_at'
    ]
    list_filter = ['is_successful', 'event_type', 'webhook']
    search_fields = ['entity_id', 'error_message']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'key_prefix', 'owner', 'scope', 'is_active',
        'total_requests', 'last_used', 'expires_at', 'revoked_at'
    ]
    list_filter = ['is_active', 'scope']
    search_fields = ['name', 'key_prefix', 'owner__username']
    readonly_fields = [
        'id', 'key_prefix', 'key_hash', 'total_requests', 'successful_requests',
        'failed_requests', 'last_used', 'last_used_ip',
        'revoked_at', 'revoked_by', 'created_at', 'updated_at',
    ]


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = [
        'log_level', 'category', 'external_system', 'operation',
        'entity_type', 'duration_ms', 'created_at'
    ]
    list_filter = ['log_level', 'category', 'external_system']
    search_fields = ['message', 'operation', 'error_code', 'entity_id']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(DataTransfer)
class DataTransferAdmin(admin.ModelAdmin):
    list_display = [
        'transfer_id', 'source_system', 'target_system', 'transfer_type',
        'status', 'record_count', 'transferred_records', 'started_at'
    ]
    list_filter = ['status', 'transfer_type', 'source_system']
    search_fields = ['transfer_id', 'entity_type']
    readonly_fields = [
        'id', 'transfer_id', 'status', 'started_at', 'completed_at',
        'transferred_records', 'failed_records', 'skipped_records',
        'error_message', 'validation_errors', 'created_at', 'updated_at',
    ]