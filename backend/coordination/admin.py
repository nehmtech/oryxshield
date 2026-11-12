"""
Admin configuration for coordination app — OryxShield.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Agency, CoordinationTeam, TeamMembership, Task, Meeting,
    MeetingAttendance, CommunicationChannel, InformationProduct,
    CoordinationDashboard,
)


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    fields = ['agency', 'role', 'primary_representative', 'is_active']
    autocomplete_fields = ['agency', 'primary_representative']


class MeetingAttendanceInline(admin.TabularInline):
    model = MeetingAttendance
    extra = 0
    fields = ['attendee', 'representing_agency', 'status']
    autocomplete_fields = ['attendee', 'representing_agency']


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'acronym', 'agency_type', 'primary_contact', 'is_active', 'created_at']
    list_filter = ['agency_type', 'is_active']
    search_fields = ['name', 'acronym', 'primary_contact', 'contact_email']
    filter_horizontal = ['operating_locations']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Identity', {'fields': ['name', 'acronym', 'agency_type', 'description']}),
        ('Contact', {'fields': ['primary_contact', 'contact_email', 'contact_phone', 'website']}),
        ('Locations', {'fields': ['headquarters_location', 'operating_locations']}),
        ('Capabilities', {'fields': ['capabilities', 'resources_available', 'surge_capacity']}),
        ('Status', {'fields': ['is_active', 'activation_date', 'notes']}),
        ('Metadata', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(CoordinationTeam)
class CoordinationTeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'team_type', 'lead_agency', 'is_active', 'activated_at']
    list_filter = ['team_type', 'is_active']
    search_fields = ['name', 'code']
    autocomplete_fields = ['lead_agency', 'team_leader', 'deputy_leader']
    readonly_fields = ['created_at', 'updated_at', 'activated_at', 'deactivated_at']
    inlines = [TeamMembershipInline]
    fieldsets = [
        ('Identity', {'fields': ['name', 'code', 'team_type', 'mandate', 'objectives']}),
        ('Leadership', {'fields': ['lead_agency', 'team_leader', 'deputy_leader']}),
        ('Operations', {'fields': ['meeting_frequency', 'reporting_line', 'response_activation_id']}),
        ('Status', {'fields': ['is_active', 'activated_at', 'deactivated_at', 'notes']}),
        ('Metadata', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'coordination_team', 'assigned_to_agency',
        'priority_badge', 'status', 'due_date', 'progress_percentage'
    ]
    list_filter = ['priority', 'status', 'coordination_team']
    search_fields = ['title', 'description']
    autocomplete_fields = ['coordination_team', 'assigned_to_agency', 'assigned_to_user', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at', 'assigned_at', 'started_at', 'completed_at']
    fieldsets = [
        ('Task', {'fields': ['title', 'description', 'coordination_team', 'parent_task']}),
        ('Assignment', {'fields': ['assigned_to_agency', 'assigned_to_user', 'assigned_by']}),
        ('Priority & Status', {'fields': ['priority', 'status', 'due_date']}),
        ('Progress', {'fields': ['progress_percentage', 'progress_notes', 'blockers', 'deliverables']}),
        ('Metadata', {'fields': ['created_at', 'updated_at', 'assigned_at', 'started_at', 'completed_at'],
                      'classes': ['collapse']}),
    ]

    @admin.display(description='Priority')
    def priority_badge(self, obj):
        colours = {
            'CRITICAL': '#dc2626', 'URGENT': '#ea580c',
            'HIGH': '#d97706', 'MEDIUM': '#2563eb', 'LOW': '#6b7280',
        }
        colour = colours.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colour, obj.get_priority_display()
        )


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'coordination_team', 'meeting_type', 'status', 'scheduled_start', 'is_virtual']
    list_filter = ['meeting_type', 'status', 'is_virtual']
    search_fields = ['title']
    autocomplete_fields = ['coordination_team', 'chair', 'secretary']
    readonly_fields = ['created_at', 'updated_at', 'actual_start', 'actual_end']
    inlines = [MeetingAttendanceInline]
    fieldsets = [
        ('Meeting', {'fields': ['title', 'meeting_type', 'status', 'coordination_team']}),
        ('Chair', {'fields': ['chair', 'secretary']}),
        ('Schedule', {'fields': ['scheduled_start', 'scheduled_end', 'actual_start', 'actual_end']}),
        ('Venue', {'fields': ['is_virtual', 'meeting_link', 'venue']}),
        ('Content', {'fields': ['agenda', 'pre_read_documents', 'minutes', 'decisions_made', 'action_points']}),
        ('Notes', {'fields': ['notes']}),
        ('Metadata', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(CommunicationChannel)
class CommunicationChannelAdmin(admin.ModelAdmin):
    list_display = ['name', 'channel_type', 'coordination_team', 'is_active', 'is_primary']
    list_filter = ['channel_type', 'is_active', 'is_primary']
    search_fields = ['name']
    autocomplete_fields = ['coordination_team']
    filter_horizontal = ['members']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InformationProduct)
class InformationProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'product_type', 'version', 'effective_date', 'is_current', 'is_public', 'download_count']
    list_filter = ['product_type', 'is_current', 'is_public']
    search_fields = ['title', 'description']
    autocomplete_fields = ['coordination_team', 'produced_by_agency', 'author']
    readonly_fields = ['created_at', 'updated_at', 'download_count']
    filter_horizontal = ['shared_with_agencies']
    fieldsets = [
        ('Product', {'fields': ['title', 'product_type', 'description', 'version', 'effective_date']}),
        ('Origin', {'fields': ['coordination_team', 'produced_by_agency', 'author']}),
        ('File', {'fields': ['file_url', 'file_size_bytes', 'content_summary', 'tags']}),
        ('Sharing', {'fields': ['is_public', 'shared_with_agencies', 'is_current', 'superseded_by']}),
        ('Stats', {'fields': ['download_count']}),
        ('Metadata', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(CoordinationDashboard)
class CoordinationDashboardAdmin(admin.ModelAdmin):
    list_display = ['coordination_team', 'title', 'is_public', 'last_refreshed_at']
    autocomplete_fields = ['coordination_team']
    filter_horizontal = ['shared_with']
    readonly_fields = ['created_at', 'updated_at', 'last_refreshed_at']