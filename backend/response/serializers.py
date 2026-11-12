"""
Serializers for response app.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import (
    ResponseLevel,
    ResponseProtocol,
    ResponseActivation,
    EscalationTrigger,
    ActionItem,
    ResponseReport,
    DecisionLog,
)


# ---------------------------------------------------------------------------
# ResponseLevel
# ---------------------------------------------------------------------------

class ResponseLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseLevel
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


# ---------------------------------------------------------------------------
# ResponseProtocol
# ---------------------------------------------------------------------------

class ResponseProtocolSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = ResponseProtocol
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ResponseProtocolListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseProtocol
        fields = [
            "id", "name", "code", "protocol_type", "is_active",
            "version", "response_time_hours",
        ]


# ---------------------------------------------------------------------------
# ResponseActivation
# ---------------------------------------------------------------------------

class ResponseActivationSerializer(serializers.ModelSerializer):
    response_level_name = serializers.CharField(source="response_level.name", read_only=True)
    response_level_number = serializers.IntegerField(source="response_level.level", read_only=True)
    protocol_name = serializers.CharField(source="protocol.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    incident_commander_name = serializers.CharField(
        source="incident_commander.username", read_only=True
    )
    activated_by_name = serializers.CharField(source="activated_by.username", read_only=True)
    days_active = serializers.SerializerMethodField()
    escalation_probability = serializers.SerializerMethodField()

    class Meta:
        model = ResponseActivation
        fields = "__all__"
        read_only_fields = [
            "created_at", "updated_at", "activated_at",
            "completed_at", "activation_code",
        ]

    def get_days_active(self, obj) -> int:
        end = obj.completed_at or timezone.now()
        return (end - obj.activated_at).days

    def get_escalation_probability(self, obj) -> float:
        """Return cached probability or 0.0 — computed by background task."""
        return obj.metadata.get("escalation_probability", 0.0)


class ResponseActivationListSerializer(serializers.ModelSerializer):
    response_level_name = serializers.CharField(source="response_level.name", read_only=True)
    response_level_number = serializers.IntegerField(source="response_level.level", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = ResponseActivation
        fields = [
            "id", "activation_code",
            "response_level", "response_level_name", "response_level_number",
            "location", "location_name",
            "disease_code", "disease_name",
            "status", "activated_at", "completion_percentage",
        ]


class ActivationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseActivation
        fields = [
            "response_level", "protocol", "location",
            "disease_code", "disease_name", "justification", "objectives",
            "incident_commander", "expected_completion",
            "triggered_by_alert", "triggered_by_risk_score",
        ]

    def validate(self, data):
        level = data.get("response_level")
        if level and not level.is_active:
            raise serializers.ValidationError(
                {"response_level": "Selected response level is not active."}
            )
        protocol = data.get("protocol")
        if protocol and not protocol.is_active:
            raise serializers.ValidationError(
                {"protocol": "Selected protocol is not active."}
            )
        return data


# ---------------------------------------------------------------------------
# EscalationTrigger
# ---------------------------------------------------------------------------

class EscalationTriggerSerializer(serializers.ModelSerializer):
    from_level_name = serializers.CharField(source="from_level.name", read_only=True)
    to_level_name = serializers.CharField(source="to_level.name", read_only=True)

    class Meta:
        model = EscalationTrigger
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        from_level = data.get("from_level") or (self.instance and self.instance.from_level)
        to_level = data.get("to_level") or (self.instance and self.instance.to_level)
        if from_level and to_level and to_level.level <= from_level.level:
            raise serializers.ValidationError(
                {"to_level": "Escalation must target a higher response level."}
            )
        return data


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------

class ActionItemSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True)
    activation_code = serializers.CharField(
        source="response_activation.activation_code", read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = ActionItem
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "started_at", "completed_at"]


class ActionItemListSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = ActionItem
        fields = [
            "id", "title", "priority", "status",
            "assigned_to", "assigned_to_name",
            "due_date", "is_overdue", "response_activation",
        ]


# ---------------------------------------------------------------------------
# ResponseReport
# ---------------------------------------------------------------------------

class ResponseReportSerializer(serializers.ModelSerializer):
    activation_code = serializers.CharField(
        source="response_activation.activation_code", read_only=True
    )
    submitted_by_name = serializers.CharField(source="submitted_by.username", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)

    class Meta:
        model = ResponseReport
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        period_start = data.get("period_start")
        period_end = data.get("period_end")
        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError(
                {"period_end": "period_end must be on or after period_start."}
            )
        return data


class ResponseReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseReport
        fields = [
            "id", "report_type", "title", "report_date",
            "response_activation", "is_published",
        ]


# ---------------------------------------------------------------------------
# DecisionLog
# ---------------------------------------------------------------------------

class DecisionLogSerializer(serializers.ModelSerializer):
    activation_code = serializers.CharField(
        source="response_activation.activation_code", read_only=True
    )
    decided_by_name = serializers.CharField(source="decided_by.username", read_only=True)

    class Meta:
        model = DecisionLog
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "decision_date"]


# ---------------------------------------------------------------------------
# Action serializers (simple request bodies)
# ---------------------------------------------------------------------------

class EscalationSerializer(serializers.Serializer):
    new_level_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=10, max_length=2000)


class DeescalationSerializer(serializers.Serializer):
    new_level_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=10, max_length=2000)


class SuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=2000)


class ActionCompleteSerializer(serializers.Serializer):
    completion_notes = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class ActionStartSerializer(serializers.Serializer):
    pass  # No body needed; presence of the call is the signal


class PublishReportSerializer(serializers.Serializer):
    pass  # Reviewer captured from request.user


# ---------------------------------------------------------------------------
# Dashboard / Statistics
# ---------------------------------------------------------------------------

class ResponseDashboardSerializer(serializers.Serializer):
    active_responses = serializers.IntegerField()
    level_5_responses = serializers.IntegerField()
    pending_actions = serializers.IntegerField()
    overdue_actions = serializers.IntegerField()
    responses_by_level = serializers.DictField()
    recent_activations = serializers.ListField()
    critical_actions = serializers.ListField()


class ResponseStatisticsSerializer(serializers.Serializer):
    total_activations = serializers.IntegerField()
    active_activations = serializers.IntegerField()
    completed_activations = serializers.IntegerField()
    escalated_activations = serializers.IntegerField()
    average_response_time_hours = serializers.FloatField()
    average_completion_time_hours = serializers.FloatField()
    escalation_rate_pct = serializers.FloatField()
    completion_rate_pct = serializers.FloatField()
    by_level = serializers.DictField()
    action_stats = serializers.DictField()