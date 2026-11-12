"""Admin configuration for mobile app — OryxShield."""
from django.contrib import admin
from .models import (
    MobileDevice, OfflineData, FieldWorker, FieldActivity, MobileSurvey,
    SurveyResponse, DataCollectionForm, FormSubmission, MobileNotification,
)


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'user', 'device_type', 'app_version', 'is_active', 'last_active']
    list_filter = ['device_type', 'is_active']
    search_fields = ['device_id', 'device_name', 'user__username', 'user__email']
    readonly_fields = ['last_active', 'created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(OfflineData)
class OfflineDataAdmin(admin.ModelAdmin):
    list_display = ['data_type', 'sync_status', 'sync_attempts', 'device', 'created_offline_at', 'synced_at']
    list_filter = ['data_type', 'sync_status']
    search_fields = ['device__device_id', 'server_record_id']
    readonly_fields = ['checksum', 'created_at', 'updated_at']


@admin.register(FieldWorker)
class FieldWorkerAdmin(admin.ModelAdmin):
    list_display = ['worker_id', 'user', 'worker_type', 'assigned_location', 'is_active',
                    'cases_managed', 'contacts_traced', 'surveys_completed']
    list_filter = ['worker_type', 'is_active']
    search_fields = ['worker_id', 'user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['cases_managed', 'contacts_traced', 'surveys_completed',
                       'activities_logged', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'assigned_location']
    filter_horizontal = ['coverage_areas']


@admin.register(FieldActivity)
class FieldActivityAdmin(admin.ModelAdmin):
    list_display = ['activity_id', 'field_worker', 'activity_type', 'location',
                    'activity_date', 'people_reached']
    list_filter = ['activity_type', 'activity_date']
    search_fields = ['activity_id', 'description']
    readonly_fields = ['visit_geojson', 'created_at', 'updated_at']
    date_hierarchy = 'activity_date'


@admin.register(MobileSurvey)
class MobileSurveyAdmin(admin.ModelAdmin):
    list_display = ['title', 'survey_code', 'survey_type', 'version', 'is_active', 'created_by']
    list_filter = ['survey_type', 'is_active']
    search_fields = ['title', 'survey_code']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['target_locations']


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ['response_id', 'survey', 'field_worker', 'location', 'response_date', 'created_offline']
    list_filter = ['survey', 'created_offline', 'response_date']
    search_fields = ['response_id']
    readonly_fields = ['response_geojson', 'synced_at', 'created_at', 'updated_at']
    date_hierarchy = 'response_date'


@admin.register(DataCollectionForm)
class DataCollectionFormAdmin(admin.ModelAdmin):
    list_display = ['title', 'form_code', 'form_type', 'is_active', 'created_by']
    list_filter = ['form_type', 'is_active']
    search_fields = ['title', 'form_code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['submission_id', 'form', 'field_worker', 'submission_date',
                    'is_validated', 'created_offline']
    list_filter = ['form', 'is_validated', 'created_offline', 'submission_date']
    search_fields = ['submission_id']
    readonly_fields = ['submission_geojson', 'is_validated', 'validation_errors',
                       'synced_at', 'created_at', 'updated_at']
    date_hierarchy = 'submission_date'


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_id', 'user', 'notification_type', 'priority',
                    'is_sent', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_sent', 'is_read']
    search_fields = ['notification_id', 'title', 'user__username']
    readonly_fields = ['is_sent', 'sent_at', 'fcm_message_id', 'delivery_error',
                       'created_at', 'updated_at']
    raw_id_fields = ['user', 'device']