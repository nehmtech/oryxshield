"""
Admin configuration for the surveillance app.
"""
from django.contrib import admin

from .models import (
    DataSource,
    HealthData,
    AnomalyDetection,
    CaseCluster,
    Hotspot,
    SurveillanceReport,
    DiseaseProfile,
    DataQualityCheck,
)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "source_type", "location", "is_active", "last_sync", "created_at"]
    list_filter = ["source_type", "is_active"]
    search_fields = ["name", "contact_person", "contact_email"]
    readonly_fields = ["last_sync", "created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ["name", "source_type", "location", "is_active"]}),
        ("API", {"fields": ["api_endpoint", "api_key", "sync_frequency", "last_sync"]}),
        ("Contact", {"fields": ["contact_person", "contact_email", "contact_phone"]}),
        ("Meta", {"fields": ["metadata", "created_at", "updated_at"]}),
    )


@admin.register(HealthData)
class HealthDataAdmin(admin.ModelAdmin):
    list_display = ["disease_name", "data_type", "location", "date_recorded", "severity", "processed"]
    list_filter = ["data_type", "processed", "severity", "date_recorded"]
    search_fields = ["disease_name", "patient_id", "disease_code"]
    date_hierarchy = "date_recorded"
    readonly_fields = ["processed", "processing_errors", "created_at", "updated_at"]


@admin.register(DiseaseProfile)
class DiseaseProfileAdmin(admin.ModelAdmin):
    list_display = ["disease_name", "disease_code", "category", "is_notifiable", "alert_threshold", "is_active"]
    list_filter = ["category", "is_notifiable", "is_active"]
    search_fields = ["disease_name", "disease_code"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    list_display = ["disease_name", "anomaly_type", "severity", "location", "actual_cases", "is_verified", "detected_at"]
    list_filter = ["anomaly_type", "severity", "is_verified", "is_false_positive"]
    search_fields = ["disease_name", "disease_code"]
    date_hierarchy = "detected_at"
    readonly_fields = ["detected_at", "verified_at", "created_at", "updated_at"]


@admin.register(CaseCluster)
class CaseClusterAdmin(admin.ModelAdmin):
    list_display = ["name", "disease_name", "location", "case_count", "start_date", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "disease_name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    list_display = ["location", "disease_name", "risk_level", "case_count", "start_date", "is_active"]
    list_filter = ["risk_level", "is_active"]
    search_fields = ["disease_name", "location__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SurveillanceReport)
class SurveillanceReportAdmin(admin.ModelAdmin):
    list_display = ["title", "report_type", "location", "start_date", "end_date", "is_published"]
    list_filter = ["report_type", "is_published"]
    search_fields = ["title"]
    date_hierarchy = "start_date"
    readonly_fields = ["generated_by", "published_at", "created_at", "updated_at"]


@admin.register(DataQualityCheck)
class DataQualityCheckAdmin(admin.ModelAdmin):
    list_display = ["data_source", "check_type", "check_date", "pass_rate", "status"]
    list_filter = ["check_type", "status"]
    search_fields = ["data_source__name"]
    date_hierarchy = "check_date"
    readonly_fields = ["check_date", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False  # created exclusively by background tasks