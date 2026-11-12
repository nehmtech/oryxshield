"""
Serializers for mobile app — OryxShield.
"""
import hashlib
import json

from rest_framework import serializers
from django.utils import timezone

from .models import (
    MobileDevice, OfflineData, FieldWorker, FieldActivity, MobileSurvey,
    SurveyResponse, DataCollectionForm, FormSubmission, MobileNotification,
)


# ---------------------------------------------------------------------------
# MobileDevice
# ---------------------------------------------------------------------------

class MobileDeviceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = MobileDevice
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'last_active', 'is_deleted')

    def validate_device_id(self, value):
        if not value.strip():
            raise serializers.ValidationError("device_id must not be blank.")
        return value.strip()


class MobileDeviceLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_latitude(self, value):
        if not (-90 <= float(value) <= 90):
            raise serializers.ValidationError("latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if not (-180 <= float(value) <= 180):
            raise serializers.ValidationError("longitude must be between -180 and 180.")
        return value


# ---------------------------------------------------------------------------
# OfflineData
# ---------------------------------------------------------------------------

class OfflineDataSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True)

    class Meta:
        model = OfflineData
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_deleted',
            'sync_status', 'sync_attempts', 'synced_at', 'error_message',
            'server_record_id', 'checksum',
        )

    def create(self, validated_data):
        payload = validated_data.get('data_payload', {})
        validated_data['checksum'] = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# FieldWorker
# ---------------------------------------------------------------------------

class FieldWorkerSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    location_name = serializers.CharField(
        source='assigned_location.name', read_only=True, default=None
    )

    class Meta:
        model = FieldWorker
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_deleted',
            'cases_managed', 'contacts_traced', 'surveys_completed',
            'activities_logged', 'current_geojson', 'last_location_update',
        )


class FieldWorkerLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_latitude(self, value):
        if not (-90 <= float(value) <= 90):
            raise serializers.ValidationError("latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if not (-180 <= float(value) <= 180):
            raise serializers.ValidationError("longitude must be between -180 and 180.")
        return value


# ---------------------------------------------------------------------------
# FieldActivity
# ---------------------------------------------------------------------------

class FieldActivitySerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(
        source='field_worker.user.get_full_name', read_only=True
    )
    worker_id = serializers.CharField(
        source='field_worker.worker_id', read_only=True
    )
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = FieldActivity
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_deleted', 'visit_geojson')

    def validate(self, attrs):
        start = attrs.get('start_time')
        end = attrs.get('end_time')
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs

    def validate_people_reached(self, value):
        if value < 0:
            raise serializers.ValidationError("people_reached must be non-negative.")
        return value


# ---------------------------------------------------------------------------
# MobileSurvey
# ---------------------------------------------------------------------------

class MobileSurveySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, default=None
    )
    response_count = serializers.SerializerMethodField()

    class Meta:
        model = MobileSurvey
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_deleted')

    def get_response_count(self, obj):
        return obj.responses.filter(is_deleted=False).count()

    def validate_questions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("questions must be a list.")
        for idx, q in enumerate(value):
            if not isinstance(q, dict):
                raise serializers.ValidationError(
                    f"Question at index {idx} must be an object."
                )
            if 'id' not in q or 'label' not in q or 'type' not in q:
                raise serializers.ValidationError(
                    f"Question at index {idx} must have 'id', 'label', and 'type'."
                )
        return value


# ---------------------------------------------------------------------------
# SurveyResponse
# ---------------------------------------------------------------------------

class SurveyResponseSerializer(serializers.ModelSerializer):
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    survey_code = serializers.CharField(source='survey.survey_code', read_only=True)
    worker_id = serializers.CharField(
        source='field_worker.worker_id', read_only=True, default=None
    )
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = SurveyResponse
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_deleted', 'response_geojson',
        )

    def validate_responses(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("responses must be a JSON object.")
        if not value:
            raise serializers.ValidationError("responses must not be empty.")
        return value


# ---------------------------------------------------------------------------
# DataCollectionForm
# ---------------------------------------------------------------------------

class DataCollectionFormSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, default=None
    )
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = DataCollectionForm
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_deleted')

    def get_submission_count(self, obj):
        return obj.submissions.filter(is_deleted=False).count()

    def validate_form_fields(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("form_fields must be a list.")
        for idx, field in enumerate(value):
            if not isinstance(field, dict):
                raise serializers.ValidationError(
                    f"Field at index {idx} must be an object."
                )
            if 'name' not in field or 'type' not in field:
                raise serializers.ValidationError(
                    f"Field at index {idx} must have 'name' and 'type'."
                )
        return value


# ---------------------------------------------------------------------------
# FormSubmission
# ---------------------------------------------------------------------------

class FormSubmissionSerializer(serializers.ModelSerializer):
    form_title = serializers.CharField(source='form.title', read_only=True)
    form_code = serializers.CharField(source='form.form_code', read_only=True)
    worker_id = serializers.CharField(
        source='field_worker.worker_id', read_only=True, default=None
    )
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = FormSubmission
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_deleted',
            'submission_geojson', 'is_validated', 'validation_errors',
        )

    def validate_form_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("form_data must be a JSON object.")
        if not value:
            raise serializers.ValidationError("form_data must not be empty.")
        return value


# ---------------------------------------------------------------------------
# MobileNotification
# ---------------------------------------------------------------------------

class MobileNotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    device_id = serializers.CharField(source='device.device_id', read_only=True)

    class Meta:
        model = MobileNotification
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_deleted',
            'is_sent', 'sent_at', 'is_read', 'read_at',
            'fcm_message_id', 'delivery_error',
        )


# ---------------------------------------------------------------------------
# Bulk / special-purpose serializers
# ---------------------------------------------------------------------------

class SyncItemSerializer(serializers.Serializer):
    """Single item in an offline sync batch."""

    DATA_TYPES = [item[0] for item in OfflineData.DATA_TYPES]

    data_type = serializers.ChoiceField(choices=DATA_TYPES)
    payload = serializers.DictField()
    created_at = serializers.DateTimeField(default=timezone.now)


class SyncRequestSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=200)
    last_sync = serializers.DateTimeField()
    pending_data = SyncItemSerializer(many=True, required=False, default=list)

    def validate_device_id(self, value):
        from .models import MobileDevice
        if not MobileDevice.objects.filter(device_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Device not registered.")
        return value


class BulkNotificationSerializer(serializers.Serializer):
    """Dispatch the same notification to multiple users."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=500
    )
    notification_type = serializers.ChoiceField(
        choices=[item[0] for item in MobileNotification.NOTIFICATION_TYPES]
    )
    priority = serializers.ChoiceField(
        choices=[item[0] for item in MobileNotification.PRIORITY_LEVELS],
        default='NORMAL',
    )
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    action_url = serializers.CharField(max_length=500, required=False, default='')
    action_data = serializers.DictField(required=False, default=dict)
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)