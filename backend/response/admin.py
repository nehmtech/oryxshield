"""
Admin configuration for response app.
"""
from django.contrib import admin

from .models import (
    ResponseLevel,
    ResponseProtocol,
    ResponseActivation,
    EscalationTrigger,
    ActionItem,
    ResponseReport,
    DecisionLog,
)


@admin.register(ResponseLevel)
class ResponseLevelAdmin(admin.ModelAdmin):
    list_display = ["level", "name", "risk_score_threshold", "is_active", "estimated_duration_days"]
    list_filter = ["is_active"]
    ordering = ["level"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ResponseProtocol)
class ResponseProtocolAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "protocol_type", "version", "is_active", "last_reviewed"]
    list_filter = ["protocol_type", "is_active"]
    search_fields = ["name", "code", "description"]
    filter_horizontal = ["applicable_locations"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ResponseActivation)
class ResponseActivationAdmin(admin.ModelAdmin):
    list_display = [
        "activation_code", "response_level", "location", "disease_name",
        "status", "activated_at", "completion_percentage",
    ]
    list_filter = ["status", "response_level", "activated_at"]
    search_fields = ["activation_code", "disease_name", "disease_code"]
    date_hierarchy = "activated_at"
    readonly_fields = [
        "activation_code", "activated_at", "completed_at",
        "escalation_history", "created_at", "updated_at",
    ]
    fieldsets = (
        ("Identification", {"fields": ("activation_code", "response_level", "protocol")}),
        ("Location & Disease", {"fields": ("location", "disease_code", "disease_name")}),
        ("Status", {"fields": ("status", "completion_percentage")}),
        ("Timing", {"fields": ("activated_at", "completed_at", "expected_completion")}),
        ("Personnel", {"fields": ("incident_commander", "activated_by", "personnel_deployed")}),
        ("Triggers", {"fields": ("triggered_by_alert", "triggered_by_risk_score")}),
        ("Details", {"fields": ("justification", "objectives", "resources_allocated")}),
        ("Escalation History", {"fields": ("escalation_history",), "classes": ("collapse",)}),
    )


@admin.register(EscalationTrigger)
class EscalationTriggerAdmin(admin.ModelAdmin):
    list_display = [
        "name", "trigger_type", "from_level", "to_level",
        "threshold_value", "auto_escalate", "is_active",
    ]
    list_filter = ["trigger_type", "auto_escalate", "is_active"]
    search_fields = ["name", "description"]
    filter_horizontal = ["locations"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = [
        "title", "response_activation", "priority", "status",
        "assigned_to", "due_date", "is_overdue",
    ]
    list_filter = ["priority", "status"]
    search_fields = ["title", "description", "response_activation__activation_code"]
    date_hierarchy = "due_date"
    readonly_fields = ["started_at", "completed_at", "created_at", "updated_at"]
    filter_horizontal = ["depends_on"]

    @admin.display(boolean=True, description="Overdue?")
    def is_overdue(self, obj):
        return obj.is_overdue


@admin.register(ResponseReport)
class ResponseReportAdmin(admin.ModelAdmin):
    list_display = [
        "title", "response_activation", "report_type",
        "report_date", "is_published", "submitted_by",
    ]
    list_filter = ["report_type", "is_published"]
    search_fields = ["title", "executive_summary"]
    date_hierarchy = "report_date"
    readonly_fields = ["created_at", "updated_at"]

    actions = ["publish_selected"]

    @admin.action(description="Publish selected reports")
    def publish_selected(self, request, queryset):
        updated = queryset.filter(is_published=False).update(
            is_published=True, reviewed_by=request.user
        )
        self.message_user(request, f"{updated} report(s) published.")


@admin.register(DecisionLog)
class DecisionLogAdmin(admin.ModelAdmin):
    list_display = [
        "decision_title", "response_activation", "decided_by",
        "decision_date", "reviewed",
    ]
    list_filter = ["reviewed", "decision_date"]
    search_fields = ["decision_title", "decision_description", "decision_made"]
    date_hierarchy = "decision_date"
    readonly_fields = ["decision_date", "created_at", "updated_at"]