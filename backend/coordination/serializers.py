"""
Serializers for coordination app — OryxShield.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Agency, CoordinationTeam, TeamMembership, Task, Meeting,
    MeetingAttendance, CommunicationChannel, InformationProduct,
    CoordinationDashboard,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------

class AgencySerializer(serializers.ModelSerializer):
    headquarters_location_name = serializers.CharField(
        source='headquarters_location.name', read_only=True
    )

    class Meta:
        model = Agency
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'is_deleted', 'deleted_at']


class AgencyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ['id', 'name', 'acronym', 'agency_type', 'is_active', 'contact_email']


# ---------------------------------------------------------------------------
# TeamMembership
# ---------------------------------------------------------------------------

class TeamMembershipSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    agency_acronym = serializers.CharField(source='agency.acronym', read_only=True)
    primary_representative_name = serializers.CharField(
        source='primary_representative.get_full_name', read_only=True
    )

    class Meta:
        model = TeamMembership
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'joined_at', 'is_deleted', 'deleted_at']


# ---------------------------------------------------------------------------
# CoordinationTeam
# ---------------------------------------------------------------------------

class CoordinationTeamSerializer(serializers.ModelSerializer):
    lead_agency_name = serializers.CharField(source='lead_agency.name', read_only=True)
    team_leader_name = serializers.CharField(source='team_leader.get_full_name', read_only=True)
    memberships = TeamMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = CoordinationTeam
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'activated_at', 'deactivated_at',
                            'is_deleted', 'deleted_at']


class CoordinationTeamListSerializer(serializers.ModelSerializer):
    lead_agency_name = serializers.CharField(source='lead_agency.name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = CoordinationTeam
        fields = ['id', 'name', 'code', 'team_type', 'lead_agency',
                  'lead_agency_name', 'is_active', 'activated_at', 'member_count']

    def get_member_count(self, obj) -> int:
        return obj.memberships.filter(is_active=True).count()


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)
    agency_name = serializers.CharField(source='assigned_to_agency.name', read_only=True)
    assigned_to_user_name = serializers.CharField(
        source='assigned_to_user.get_full_name', read_only=True
    )
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'assigned_at',
                            'started_at', 'completed_at', 'is_deleted', 'deleted_at']

    def get_is_overdue(self, obj) -> bool:
        from django.utils import timezone
        return (
            obj.due_date < timezone.now()
            and obj.status not in ('COMPLETED', 'CANCELLED')
        )


class TaskListSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='assigned_to_agency.name', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ['id', 'title', 'priority', 'status', 'assigned_to_agency',
                  'agency_name', 'due_date', 'progress_percentage', 'is_overdue']

    def get_is_overdue(self, obj) -> bool:
        from django.utils import timezone
        return (
            obj.due_date < timezone.now()
            and obj.status not in ('COMPLETED', 'CANCELLED')
        )


class TaskUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices, required=False)
    progress_percentage = serializers.IntegerField(min_value=0, max_value=100, required=False)
    progress_notes = serializers.CharField(required=False, allow_blank=True)
    blockers = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data


# ---------------------------------------------------------------------------
# MeetingAttendance
# ---------------------------------------------------------------------------

class MeetingAttendanceSerializer(serializers.ModelSerializer):
    attendee_name = serializers.CharField(source='attendee.get_full_name', read_only=True)
    agency_name = serializers.CharField(source='representing_agency.name', read_only=True)

    class Meta:
        model = MeetingAttendance
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'is_deleted', 'deleted_at']


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

class MeetingSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)
    chair_name = serializers.CharField(source='chair.get_full_name', read_only=True)
    attendances = MeetingAttendanceSerializer(many=True, read_only=True)
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'actual_start', 'actual_end',
                            'is_deleted', 'deleted_at']

    def get_duration_minutes(self, obj) -> int | None:
        if obj.actual_start and obj.actual_end:
            return int((obj.actual_end - obj.actual_start).total_seconds() / 60)
        return None


class MeetingListSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)

    class Meta:
        model = Meeting
        fields = ['id', 'title', 'meeting_type', 'status', 'scheduled_start',
                  'scheduled_end', 'is_virtual', 'coordination_team', 'team_name']


class MeetingMinutesSerializer(serializers.Serializer):
    minutes = serializers.CharField(min_length=10)
    decisions_made = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    action_points = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )


# ---------------------------------------------------------------------------
# CommunicationChannel
# ---------------------------------------------------------------------------

class CommunicationChannelSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = CommunicationChannel
        exclude = ['access_credentials']  # never expose credentials in API
        read_only_fields = ['created_at', 'updated_at', 'is_deleted', 'deleted_at']

    def get_member_count(self, obj) -> int:
        return obj.members.count()


# ---------------------------------------------------------------------------
# InformationProduct
# ---------------------------------------------------------------------------

class InformationProductSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)
    agency_name = serializers.CharField(source='produced_by_agency.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = InformationProduct
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'download_count',
                            'is_deleted', 'deleted_at']


class InformationProductListSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='produced_by_agency.name', read_only=True)

    class Meta:
        model = InformationProduct
        fields = ['id', 'title', 'product_type', 'produced_by_agency',
                  'agency_name', 'version', 'effective_date', 'is_current', 'is_public']


# ---------------------------------------------------------------------------
# CoordinationDashboard
# ---------------------------------------------------------------------------

class CoordinationDashboardSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='coordination_team.name', read_only=True)

    class Meta:
        model = CoordinationDashboard
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'last_refreshed_at',
                            'is_deleted', 'deleted_at']


# ---------------------------------------------------------------------------
# Dashboard data / metrics (non-model)
# ---------------------------------------------------------------------------

class CoordinationDashboardDataSerializer(serializers.Serializer):
    active_teams = serializers.IntegerField()
    active_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    upcoming_meetings = serializers.IntegerField()
    tasks_by_priority = serializers.DictField(child=serializers.IntegerField())
    tasks_by_agency = serializers.ListField(child=serializers.DictField())
    recent_products = serializers.ListField(child=serializers.DictField())
    critical_tasks = serializers.ListField(child=serializers.DictField())
    teams_summary = serializers.ListField(child=serializers.DictField())


class CoordinationMetricsSerializer(serializers.Serializer):
    total_teams = serializers.IntegerField()
    total_agencies = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    task_completion_rate = serializers.FloatField()
    average_task_duration_hours = serializers.FloatField()
    meetings_held = serializers.IntegerField()
    information_products_shared = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    critical_overdue_tasks = serializers.IntegerField()