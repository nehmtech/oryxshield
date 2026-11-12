"""
Admin configuration for risk_assessment app.
"""
from django.contrib import admin

from .models import Alert, PredictiveModel, RiskFactor, RiskScore, Threshold, ThreatClassification


@admin.register(RiskScore)
class RiskScoreAdmin(admin.ModelAdmin):
    list_display = [
        "disease_name", "location", "overall_score", "risk_level",
        "r_naught", "case_fatality_rate", "assessment_date", "is_active",
    ]
    list_filter = ["risk_level", "is_active", "assessment_date"]
    search_fields = ["disease_name", "disease_code", "location__name"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "assessment_date"


@admin.register(ThreatClassification)
class ThreatClassificationAdmin(admin.ModelAdmin):
    list_display = [
        "disease_name", "location", "threat_level", "threat_score",
        "pandemic_potential", "cross_border_risk", "assessment_date",
    ]
    list_filter = ["threat_level", "pandemic_potential", "cross_border_risk"]
    search_fields = ["disease_name", "disease_code", "location__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = [
        "title", "alert_type", "severity", "status",
        "location", "triggered_at", "acknowledged_by",
    ]
    list_filter = ["alert_type", "severity", "status", "triggered_at"]
    search_fields = ["title", "description", "disease_code"]
    date_hierarchy = "triggered_at"
    readonly_fields = ["triggered_at", "acknowledged_at", "resolved_at", "created_at", "updated_at"]


@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display = [
        "name", "threshold_type", "warning_value", "alert_value",
        "critical_value", "evaluation_period", "is_active",
    ]
    list_filter = ["threshold_type", "is_active"]
    search_fields = ["name", "description", "disease_code"]


@admin.register(RiskFactor)
class RiskFactorAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "weight", "location", "is_active", "last_updated"]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "description"]


@admin.register(PredictiveModel)
class PredictiveModelAdmin(admin.ModelAdmin):
    list_display = [
        "name", "model_type", "algorithm", "version",
        "accuracy", "is_active", "is_deployed",
        "prediction_count", "trained_at",
    ]
    list_filter = ["model_type", "is_active", "is_deployed"]
    search_fields = ["name", "algorithm", "description"]
    readonly_fields = ["prediction_count", "last_used", "created_at", "updated_at"]