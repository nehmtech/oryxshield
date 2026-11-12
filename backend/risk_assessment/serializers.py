"""
Serializers for risk_assessment app.
"""
from rest_framework import serializers

from .models import Alert, PredictiveModel, RiskFactor, RiskScore, Threshold, ThreatClassification


# ---------------------------------------------------------------------------
# RiskScore serializers
# ---------------------------------------------------------------------------

class RiskScoreListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = RiskScore
        fields = [
            "id", "location", "location_name", "disease_code", "disease_name",
            "overall_score", "risk_level", "r_naught", "case_fatality_rate",
            "assessment_date", "confidence_level", "is_active",
        ]


class RiskScoreSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = RiskScore
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class RiskScoreCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScore
        exclude = ["created_at", "updated_at", "is_deleted", "deleted_at"]


# ---------------------------------------------------------------------------
# ThreatClassification serializers
# ---------------------------------------------------------------------------

class ThreatClassificationListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = ThreatClassification
        fields = [
            "id", "disease_code", "disease_name", "location", "location_name",
            "threat_level", "threat_score", "pandemic_potential",
            "cross_border_risk", "assessment_date",
        ]


class ThreatClassificationSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    assessed_by_name = serializers.CharField(source="assessed_by.username", read_only=True)

    class Meta:
        model = ThreatClassification
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Alert serializers
# ---------------------------------------------------------------------------

class AlertListSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id", "alert_type", "severity", "status", "title",
            "location", "location_name", "disease_code", "disease_name",
            "triggered_at", "expires_at", "notification_sent",
        ]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


class AlertSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()
    acknowledged_by_name = serializers.CharField(
        source="acknowledged_by.username", read_only=True,
    )

    class Meta:
        model = Alert
        fields = "__all__"
        read_only_fields = [
            "created_at", "updated_at", "triggered_at",
            "acknowledged_at", "resolved_at",
        ]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


class AlertCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        exclude = [
            "created_at", "updated_at", "is_deleted", "deleted_at",
            "triggered_at", "acknowledged_at", "resolved_at",
            "acknowledged_by", "notification_sent",
        ]


# ---------------------------------------------------------------------------
# Threshold serializers
# ---------------------------------------------------------------------------

class ThresholdListSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = Threshold
        fields = [
            "id", "name", "threshold_type", "warning_value", "alert_value",
            "critical_value", "location", "location_name", "disease_code",
            "evaluation_period", "is_active",
        ]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


class ThresholdSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = Threshold
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None

    def validate(self, attrs):
        warning = attrs.get("warning_value", getattr(self.instance, "warning_value", None))
        alert = attrs.get("alert_value", getattr(self.instance, "alert_value", None))
        critical = attrs.get("critical_value", getattr(self.instance, "critical_value", None))
        if warning is not None and alert is not None and critical is not None:
            if not (warning <= alert <= critical):
                raise serializers.ValidationError(
                    "Threshold values must satisfy: warning ≤ alert ≤ critical."
                )
        return attrs


# ---------------------------------------------------------------------------
# RiskFactor serializers
# ---------------------------------------------------------------------------

class RiskFactorListSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = RiskFactor
        fields = [
            "id", "name", "category", "weight",
            "location", "location_name", "is_active", "last_updated",
        ]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


class RiskFactorSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = RiskFactor
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "last_updated"]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


# ---------------------------------------------------------------------------
# PredictiveModel serializers
# ---------------------------------------------------------------------------

class PredictiveModelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictiveModel
        fields = [
            "id", "name", "model_type", "algorithm", "version",
            "accuracy", "is_active", "is_deployed",
            "trained_at", "prediction_count",
        ]


class PredictiveModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictiveModel
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "prediction_count", "last_used"]


# ---------------------------------------------------------------------------
# Action / request serializers
# ---------------------------------------------------------------------------

class AlertAcknowledgeSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class AlertResolveSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField(required=False, allow_blank=True, default="")
    actions_taken = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )


class ThresholdCheckSerializer(serializers.Serializer):
    current_value = serializers.DecimalField(max_digits=12, decimal_places=4)


class RiskAssessmentRequestSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    disease_code = serializers.CharField(max_length=50)
    force_recalculation = serializers.BooleanField(default=False)


class OutbreakPredictionSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    disease_code = serializers.CharField(max_length=50)
    prediction_horizon = serializers.IntegerField(
        default=7,
        min_value=1,
        max_value=90,
        help_text="Number of days to forecast.",
    )


# ---------------------------------------------------------------------------
# Dashboard / analytics serializers
# ---------------------------------------------------------------------------

class RiskTrendSerializer(serializers.Serializer):
    date = serializers.DateField()
    average_score = serializers.FloatField()
    max_score = serializers.FloatField()
    alert_count = serializers.IntegerField()


class ComparativeRiskSerializer(serializers.Serializer):
    location_name = serializers.CharField()
    risk_score = serializers.FloatField()
    risk_level = serializers.CharField()
    disease_count = serializers.IntegerField()
    alert_count = serializers.IntegerField()


class RiskDashboardSerializer(serializers.Serializer):
    critical_risks = serializers.IntegerField()
    high_risks = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    unacknowledged_alerts = serializers.IntegerField()
    average_risk_score = serializers.FloatField()
    trending_threats = serializers.ListField()
    high_risk_locations = serializers.ListField()
    recent_alerts = serializers.ListField()
    generated_at = serializers.DateTimeField()