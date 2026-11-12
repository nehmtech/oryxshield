"""
Serializers for the surveillance app.
"""
from rest_framework import serializers
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


# ---------------------------------------------------------------------------
# DataSource
# ---------------------------------------------------------------------------

class DataSourceListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = DataSource
        fields = [
            "id", "name", "source_type", "location", "location_name",
            "is_active", "last_sync", "sync_frequency", "created_at",
        ]


class DataSourceSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = DataSource
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "last_sync"]
        extra_kwargs = {"api_key": {"write_only": True}}


# ---------------------------------------------------------------------------
# HealthData
# ---------------------------------------------------------------------------

class HealthDataListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)

    class Meta:
        model = HealthData
        fields = [
            "id", "data_type", "disease_name", "disease_code",
            "location", "location_name", "data_source_name",
            "date_recorded", "severity", "processed", "created_at",
        ]


class HealthDataSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = HealthData
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "processed", "processing_errors"]


class HealthDataCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthData
        exclude = ["created_at", "updated_at", "processed", "processing_errors"]

    def validate_age(self, value):
        if value is not None and value > 150:
            raise serializers.ValidationError("Age must be ≤ 150.")
        return value


# ---------------------------------------------------------------------------
# DiseaseProfile
# ---------------------------------------------------------------------------

class DiseaseProfileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiseaseProfile
        fields = [
            "id", "disease_code", "disease_name", "category",
            "is_notifiable", "alert_threshold", "epidemic_threshold", "is_active",
        ]


class DiseaseProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiseaseProfile
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# ---------------------------------------------------------------------------
# AnomalyDetection
# ---------------------------------------------------------------------------

class AnomalyDetectionListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = AnomalyDetection
        fields = [
            "id", "anomaly_type", "disease_name", "disease_code", "severity",
            "location", "location_name", "actual_cases", "expected_cases",
            "confidence_score", "is_verified", "is_false_positive", "detected_at",
        ]


class AnomalyDetectionSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.get_full_name", read_only=True)

    class Meta:
        model = AnomalyDetection
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "detected_at", "verified_at"]


# ---------------------------------------------------------------------------
# CaseCluster
# ---------------------------------------------------------------------------

class CaseClusterListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = CaseCluster
        fields = [
            "id", "name", "disease_name", "disease_code",
            "location", "location_name", "case_count",
            "start_date", "end_date", "is_active", "attack_rate", "created_at",
        ]


class CaseClusterSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    related_anomaly_severity = serializers.CharField(
        source="related_anomaly.severity", read_only=True
    )

    class Meta:
        model = CaseCluster
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Hotspot
# ---------------------------------------------------------------------------

class HotspotListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Hotspot
        fields = [
            "id", "disease_name", "disease_code", "location", "location_name",
            "risk_level", "case_count", "latitude", "longitude",
            "radius_km", "start_date", "is_active",
        ]


class HotspotSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    related_cluster_name = serializers.CharField(source="related_cluster.name", read_only=True)

    class Meta:
        model = Hotspot
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# ---------------------------------------------------------------------------
# SurveillanceReport
# ---------------------------------------------------------------------------

class SurveillanceReportListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = SurveillanceReport
        fields = [
            "id", "report_type", "title", "location", "location_name",
            "start_date", "end_date", "total_cases", "new_cases",
            "is_published", "published_at", "created_at",
        ]


class SurveillanceReportSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.get_full_name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True)

    class Meta:
        model = SurveillanceReport
        fields = "__all__"
        read_only_fields = [
            "created_at", "updated_at", "generated_by",
            "published_at",
        ]


# ---------------------------------------------------------------------------
# DataQualityCheck
# ---------------------------------------------------------------------------

class DataQualityCheckSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)

    class Meta:
        model = DataQualityCheck
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "check_date"]


# ---------------------------------------------------------------------------
# Action / utility serializers
# ---------------------------------------------------------------------------

class AnomalyVerificationSerializer(serializers.Serializer):
    is_verified = serializers.BooleanField()
    is_false_positive = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class DataSourceSyncSerializer(serializers.Serializer):
    force_sync = serializers.BooleanField(default=False)


class BulkDataUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    data_source_id = serializers.UUIDField()
    data_type = serializers.ChoiceField(choices=HealthData.DATA_TYPES)


# ---------------------------------------------------------------------------
# Dashboard serializers
# ---------------------------------------------------------------------------

class SurveillanceDashboardSerializer(serializers.Serializer):
    total_cases_today = serializers.IntegerField()
    total_cases_week = serializers.IntegerField()
    total_cases_month = serializers.IntegerField()
    active_anomalies = serializers.IntegerField()
    active_clusters = serializers.IntegerField()
    active_hotspots = serializers.IntegerField()
    high_risk_locations = serializers.ListField(child=serializers.CharField())
    trending_diseases = serializers.ListField()
    recent_alerts = serializers.ListField()


class SurveillanceStatisticsSerializer(serializers.Serializer):
    period = serializers.CharField()
    total_data_points = serializers.IntegerField()
    unique_diseases = serializers.IntegerField()
    affected_locations = serializers.IntegerField()
    average_cases_per_day = serializers.FloatField()
    case_trend = serializers.CharField()
    top_diseases = serializers.ListField()
    geographic_distribution = serializers.DictField()