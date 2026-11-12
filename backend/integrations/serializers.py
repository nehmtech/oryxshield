"""Serializers for OryxShield integrations app."""
from rest_framework import serializers
from django.utils import timezone
from .models import (
    ExternalSystem, DataMapping, IntegrationJob, Webhook, WebhookLog,
    APIKey, IntegrationLog, DataTransfer
)


class ExternalSystemSerializer(serializers.ModelSerializer):
    sync_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ExternalSystem
        fields = '__all__'
        read_only_fields = [
            'id', 'health_status', 'health_message', 'last_health_check',
            'consecutive_failures', 'total_sync_count', 'successful_sync_count',
            'failed_sync_count', 'last_sync', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'credentials': {'write_only': True},
        }

    def get_sync_overdue(self, obj) -> bool:
        if not obj.last_sync or not obj.sync_enabled:
            return obj.sync_enabled
        from datetime import timedelta
        return timezone.now() > obj.last_sync + timedelta(minutes=obj.sync_interval_minutes)


class ExternalSystemSummarySerializer(serializers.ModelSerializer):
    """Lightweight read-only summary for nested references."""
    class Meta:
        model = ExternalSystem
        fields = ['id', 'name', 'system_code', 'system_type', 'health_status', 'is_active']
        read_only_fields = fields


class DataMappingSerializer(serializers.ModelSerializer):
    system_name = serializers.CharField(source='external_system.name', read_only=True)
    system_type = serializers.CharField(source='external_system.system_type', read_only=True)

    class Meta:
        model = DataMapping
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IntegrationJobSerializer(serializers.ModelSerializer):
    external_system_detail = ExternalSystemSummarySerializer(
        source='external_system', read_only=True
    )
    triggered_by_username = serializers.CharField(
        source='triggered_by.username', read_only=True
    )
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = IntegrationJob
        fields = '__all__'
        read_only_fields = [
            'id', 'job_id', 'status', 'celery_task_id',
            'started_at', 'completed_at', 'progress_percent',
            'processed_records', 'successful_records', 'failed_records',
            'skipped_records', 'total_records', 'result_summary', 'error_log',
            'retry_count', 'last_cursor', 'last_page',
            'triggered_by', 'created_at', 'updated_at',
        ]

    def get_duration_seconds(self, obj) -> float | None:
        if obj.started_at and obj.completed_at:
            return round((obj.completed_at - obj.started_at).total_seconds(), 2)
        return None


class TriggerJobSerializer(serializers.Serializer):
    external_system_id = serializers.UUIDField()
    job_type = serializers.ChoiceField(choices=IntegrationJob.JOB_TYPES)
    entity_type = serializers.CharField(max_length=100)
    priority = serializers.ChoiceField(choices=IntegrationJob.PRIORITY_CHOICES, default=3)
    filters = serializers.DictField(required=False, default=dict)
    job_config = serializers.DictField(required=False, default=dict)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True, default=None)


class WebhookSerializer(serializers.ModelSerializer):
    success_rate = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Webhook
        fields = '__all__'
        read_only_fields = [
            'id', 'total_calls', 'successful_calls', 'failed_calls',
            'last_triggered', 'last_success', 'last_failure',
            'average_response_ms', 'is_verified', 'last_verification_at',
            'created_by', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'secret_key': {'write_only': True},
        }

    def get_success_rate(self, obj) -> float:
        if obj.total_calls == 0:
            return 0.0
        return round(obj.successful_calls / obj.total_calls * 100, 2)


class WebhookLogSerializer(serializers.ModelSerializer):
    webhook_name = serializers.CharField(source='webhook.name', read_only=True)
    webhook_url = serializers.URLField(source='webhook.webhook_url', read_only=True)

    class Meta:
        model = WebhookLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class APIKeySerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    raw_key = serializers.SerializerMethodField()
    last_used_ip = serializers.CharField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = APIKey
        fields = '__all__'
        read_only_fields = [
            'id', 'key_prefix', 'total_requests',
            'successful_requests', 'failed_requests',
            'last_used', 'last_used_ip', 'revoked_at', 'revoked_by',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'key_hash': {'write_only': True},
        }

    def get_raw_key(self, obj) -> str | None:
        """Only present immediately after creation, stored in instance._raw_key."""
        return getattr(obj, '_raw_key', None)

    def create(self, validated_data):
        raw, prefix, key_hash = APIKey.generate_key()
        validated_data['key_prefix'] = prefix
        validated_data['key_hash'] = key_hash
        instance = super().create(validated_data)
        instance._raw_key = raw
        return instance


class APIKeyRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, default='')


class IntegrationLogSerializer(serializers.ModelSerializer):
    system_name = serializers.CharField(source='external_system.name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)

    class Meta:
        model = IntegrationLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DataTransferSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source_system.name', read_only=True)
    target_name = serializers.CharField(source='target_system.name', read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    initiated_by_username = serializers.CharField(source='initiated_by.username', read_only=True)

    class Meta:
        model = DataTransfer
        fields = '__all__'
        read_only_fields = [
            'id', 'transfer_id', 'status', 'started_at', 'completed_at',
            'transferred_records', 'failed_records', 'skipped_records',
            'error_message', 'validation_errors', 'created_at', 'updated_at',
        ]