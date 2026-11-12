"""
Models for the coordination app — OryxShield.

All models extend TimeStampedModel (core.models) which provides:
  id (UUID), created_at, updated_at, is_deleted, deleted_at
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Location

User = get_user_model()


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------

class Agency(TimeStampedModel):
    """A participating organisation in multi-agency coordination."""

    class AgencyType(models.TextChoices):
        HEALTH = 'HEALTH', 'Health Authority'
        EMERGENCY = 'EMERGENCY', 'Emergency Services'
        MILITARY = 'MILITARY', 'Military / Defence'
        INTERNATIONAL = 'INTERNATIONAL', 'International Organisation'
        NGO = 'NGO', 'Non-Governmental Organisation'
        PRIVATE = 'PRIVATE', 'Private Sector'
        COMMUNITY = 'COMMUNITY', 'Community Organisation'
        GOVERNMENT = 'GOVERNMENT', 'Government Ministry / Dept'
        OTHER = 'OTHER', 'Other'

    name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=20)
    agency_type = models.CharField(max_length=20, choices=AgencyType.choices)
    description = models.TextField(blank=True)

    # Contact
    primary_contact = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    website = models.URLField(blank=True)

    # Location
    headquarters_location = models.ForeignKey(
        Location, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='headquartered_agencies'
    )
    operating_locations = models.ManyToManyField(
        Location, blank=True, related_name='operating_agencies'
    )

    # Capabilities
    capabilities = models.JSONField(default=list, blank=True)
    resources_available = models.JSONField(default=dict, blank=True)
    surge_capacity = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    # Status
    is_active = models.BooleanField(default=True)
    activation_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Agency'
        verbose_name_plural = 'Agencies'
        ordering = ['name']
        indexes = [
            models.Index(fields=['agency_type', 'is_active']),
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self):
        return f"{self.acronym} — {self.name}"


# ---------------------------------------------------------------------------
# CoordinationTeam
# ---------------------------------------------------------------------------

class CoordinationTeam(TimeStampedModel):
    """A cross-agency coordination team."""

    class TeamType(models.TextChoices):
        INCIDENT = 'INCIDENT', 'Incident Management Team'
        TASK_FORCE = 'TASK_FORCE', 'Task Force'
        WORKING_GROUP = 'WORKING_GROUP', 'Working Group'
        TECHNICAL = 'TECHNICAL', 'Technical Advisory Group'
        EOC = 'EOC', 'Emergency Operations Centre'
        LIAISON = 'LIAISON', 'Liaison Group'

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    team_type = models.CharField(max_length=20, choices=TeamType.choices)
    mandate = models.TextField()
    objectives = models.JSONField(default=list, blank=True)

    lead_agency = models.ForeignKey(
        Agency, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='led_teams'
    )
    team_leader = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='led_coordination_teams'
    )
    deputy_leader = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='deputy_coordination_teams'
    )

    # Linked response activation (lazy FK avoids circular import)
    response_activation = models.ForeignKey(
        'response.ResponseActivation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='coordination_teams',
    )

    # Status
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    meeting_frequency = models.CharField(max_length=100, blank=True)
    reporting_line = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Coordination Team'
        verbose_name_plural = 'Coordination Teams'
        ordering = ['-activated_at', 'name']
        indexes = [
            models.Index(fields=['is_active', '-activated_at']),
            models.Index(fields=['team_type', 'is_active']),
            models.Index(fields=['response_activation']),
        ]

    def __str__(self):
        return f"[{self.code}] {self.name}"

    def activate(self, activated_by: User) -> None:
        """Activate the team and write an audit log entry."""
        from django.utils import timezone
        from core.models import AuditLog

        self.is_active = True
        self.activated_at = timezone.now()
        self.save(update_fields=['is_active', 'activated_at', 'updated_at'])

        AuditLog.log(
            user=activated_by,
            action='COORDINATION_TEAM_ACTIVATED',
            content_type='CoordinationTeam',
            object_id=str(self.id),
            details={'team_code': self.code, 'team_name': self.name},
        )

    def deactivate(self, deactivated_by: User) -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=['is_active', 'deactivated_at', 'updated_at'])

        AuditLog.log(
            user=deactivated_by,
            action='COORDINATION_TEAM_DEACTIVATED',
            content_type='CoordinationTeam',
            object_id=str(self.id),
            details={'team_code': self.code},
        )


# ---------------------------------------------------------------------------
# TeamMembership
# ---------------------------------------------------------------------------

class TeamMembership(TimeStampedModel):
    """An agency's membership in a CoordinationTeam."""

    class MemberRole(models.TextChoices):
        LEAD = 'LEAD', 'Lead Agency'
        CO_LEAD = 'CO_LEAD', 'Co-Lead'
        MEMBER = 'MEMBER', 'Member'
        OBSERVER = 'OBSERVER', 'Observer'
        ADVISOR = 'ADVISOR', 'Technical Advisor'
        SUPPORT = 'SUPPORT', 'Support Agency'

    team = models.ForeignKey(
        CoordinationTeam, on_delete=models.CASCADE, related_name='memberships'
    )
    agency = models.ForeignKey(
        Agency, on_delete=models.CASCADE, related_name='team_memberships'
    )
    role = models.CharField(max_length=20, choices=MemberRole.choices, default=MemberRole.MEMBER)

    primary_representative = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='primary_memberships'
    )
    alternate_representative = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='alternate_memberships'
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    commitment_level = models.CharField(max_length=100, blank=True)
    resources_committed = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Team Membership'
        verbose_name_plural = 'Team Memberships'
        unique_together = [['team', 'agency']]
        indexes = [
            models.Index(fields=['team', 'is_active']),
            models.Index(fields=['agency', 'is_active']),
        ]

    def __str__(self):
        return f"{self.agency.acronym} in {self.team.code} ({self.role})"


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(TimeStampedModel):
    """A coordination task assigned to an agency."""

    class Priority(models.TextChoices):
        CRITICAL = 'CRITICAL', 'Critical'
        URGENT = 'URGENT', 'Urgent'
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'

    class Status(models.TextChoices):
        ASSIGNED = 'ASSIGNED', 'Assigned'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    # Choices aliases kept for serializer compatibility
    STATUS_CHOICES = Status.choices

    coordination_team = models.ForeignKey(
        CoordinationTeam, on_delete=models.CASCADE, related_name='tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ASSIGNED)

    assigned_to_agency = models.ForeignKey(
        Agency, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_tasks'
    )
    assigned_to_user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_coordination_tasks'
    )
    assigned_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_coordination_tasks'
    )

    due_date = models.DateTimeField()
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    deliverables = models.JSONField(default=list, blank=True)
    progress_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    progress_notes = models.TextField(blank=True)
    blockers = models.TextField(blank=True)

    parent_task = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sub_tasks'
    )
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='blocking_tasks')

    class Meta:
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        ordering = ['-priority', 'due_date']
        indexes = [
            models.Index(fields=['coordination_team', 'status']),
            models.Index(fields=['assigned_to_agency', 'status']),
            models.Index(fields=['assigned_to_user', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]

    def __str__(self):
        return f"[{self.priority}] {self.title}"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def accept(self, accepted_by: User) -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.status = self.Status.ACCEPTED
        self.save(update_fields=['status', 'updated_at'])
        AuditLog.log(
            user=accepted_by,
            action='TASK_ACCEPTED',
            content_type='Task',
            object_id=str(self.id),
            details={'title': self.title, 'agency': str(self.assigned_to_agency_id)},
        )

    def start(self, started_by: User) -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.status = self.Status.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])
        AuditLog.log(
            user=started_by,
            action='TASK_STARTED',
            content_type='Task',
            object_id=str(self.id),
            details={'title': self.title},
        )

    def complete(self, completed_by: User, notes: str = '') -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.status = self.Status.COMPLETED
        self.progress_percentage = 100
        self.completed_at = timezone.now()
        if notes:
            self.progress_notes = notes
        self.save(update_fields=['status', 'progress_percentage', 'completed_at', 'progress_notes', 'updated_at'])
        AuditLog.log(
            user=completed_by,
            action='TASK_COMPLETED',
            content_type='Task',
            object_id=str(self.id),
            details={'title': self.title, 'duration_hours': self._duration_hours()},
        )

    def cancel(self, cancelled_by: User, reason: str = '') -> None:
        from core.models import AuditLog

        self.status = self.Status.CANCELLED
        if reason:
            self.blockers = reason
        self.save(update_fields=['status', 'blockers', 'updated_at'])
        AuditLog.log(
            user=cancelled_by,
            action='TASK_CANCELLED',
            content_type='Task',
            object_id=str(self.id),
            details={'title': self.title, 'reason': reason},
        )

    def _duration_hours(self) -> float:
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds() / 3600, 2)
        return 0.0


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

class Meeting(TimeStampedModel):
    """A coordination meeting."""

    class MeetingType(models.TextChoices):
        REGULAR = 'REGULAR', 'Regular'
        EMERGENCY = 'EMERGENCY', 'Emergency'
        BRIEFING = 'BRIEFING', 'Briefing'
        WORKING = 'WORKING', 'Working Session'
        REVIEW = 'REVIEW', 'Review'
        DEBRIEF = 'DEBRIEF', 'Debrief'

    class MeetingStatus(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        POSTPONED = 'POSTPONED', 'Postponed'

    coordination_team = models.ForeignKey(
        CoordinationTeam, on_delete=models.CASCADE, related_name='meetings'
    )
    title = models.CharField(max_length=255)
    meeting_type = models.CharField(max_length=15, choices=MeetingType.choices, default=MeetingType.REGULAR)
    status = models.CharField(max_length=15, choices=MeetingStatus.choices, default=MeetingStatus.SCHEDULED)

    chair = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='chaired_meetings'
    )
    secretary = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='secretaried_meetings'
    )

    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    venue = models.CharField(max_length=255, blank=True)
    is_virtual = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True)

    agenda = models.JSONField(default=list, blank=True)
    pre_read_documents = models.JSONField(default=list, blank=True)
    minutes = models.TextField(blank=True)
    decisions_made = models.JSONField(default=list, blank=True)
    action_points = models.JSONField(default=list, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Meeting'
        verbose_name_plural = 'Meetings'
        ordering = ['-scheduled_start']
        indexes = [
            models.Index(fields=['coordination_team', '-scheduled_start']),
            models.Index(fields=['status', '-scheduled_start']),
            models.Index(fields=['meeting_type', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.scheduled_start:%Y-%m-%d})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.scheduled_end and self.scheduled_start and self.scheduled_end <= self.scheduled_start:
            raise ValidationError(
                {'scheduled_end': 'Scheduled end must be after scheduled start.'}
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def commence(self, commenced_by: User) -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.status = self.MeetingStatus.IN_PROGRESS
        self.actual_start = timezone.now()
        self.save(update_fields=['status', 'actual_start', 'updated_at'])
        AuditLog.log(
            user=commenced_by,
            action='MEETING_COMMENCED',
            content_type='Meeting',
            object_id=str(self.id),
            details={'title': self.title},
        )

    def close(self, closed_by: User, minutes: str, decisions: list, action_points: list) -> None:
        from django.utils import timezone
        from core.models import AuditLog

        self.status = self.MeetingStatus.COMPLETED
        self.actual_end = timezone.now()
        self.minutes = minutes
        self.decisions_made = decisions
        self.action_points = action_points
        self.save(update_fields=[
            'status', 'actual_end', 'minutes',
            'decisions_made', 'action_points', 'updated_at'
        ])
        AuditLog.log(
            user=closed_by,
            action='MEETING_CLOSED',
            content_type='Meeting',
            object_id=str(self.id),
            details={
                'title': self.title,
                'decisions_count': len(decisions),
                'action_points_count': len(action_points),
            },
        )

    def cancel(self, cancelled_by: User, reason: str = '') -> None:
        from core.models import AuditLog

        self.status = self.MeetingStatus.CANCELLED
        if reason:
            self.notes = reason
        self.save(update_fields=['status', 'notes', 'updated_at'])
        AuditLog.log(
            user=cancelled_by,
            action='MEETING_CANCELLED',
            content_type='Meeting',
            object_id=str(self.id),
            details={'title': self.title, 'reason': reason},
        )


# ---------------------------------------------------------------------------
# MeetingAttendance
# ---------------------------------------------------------------------------

class MeetingAttendance(TimeStampedModel):
    """Attendance record for a meeting participant."""

    class AttendanceStatus(models.TextChoices):
        INVITED = 'INVITED', 'Invited'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        ATTENDED = 'ATTENDED', 'Attended'
        ABSENT = 'ABSENT', 'Absent'
        APOLOGY = 'APOLOGY', 'Sent Apology'

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendances')
    attendee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_attendances')
    representing_agency = models.ForeignKey(
        Agency, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='meeting_representations'
    )

    status = models.CharField(max_length=15, choices=AttendanceStatus.choices, default=AttendanceStatus.INVITED)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    apology_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Meeting Attendance'
        verbose_name_plural = 'Meeting Attendances'
        unique_together = [['meeting', 'attendee']]
        indexes = [
            models.Index(fields=['meeting', 'status']),
            models.Index(fields=['attendee', 'status']),
        ]

    def __str__(self):
        return f"{self.attendee.username} @ {self.meeting.title} ({self.status})"


# ---------------------------------------------------------------------------
# CommunicationChannel
# ---------------------------------------------------------------------------

class CommunicationChannel(TimeStampedModel):
    """A communication channel used by a coordination team."""

    class ChannelType(models.TextChoices):
        EMAIL = 'EMAIL', 'Email List'
        CHAT = 'CHAT', 'Chat Group'
        FORUM = 'FORUM', 'Discussion Forum'
        PHONE = 'PHONE', 'Phone Tree'
        RADIO = 'RADIO', 'Radio Network'
        VIDEO = 'VIDEO', 'Video Conference'
        PORTAL = 'PORTAL', 'Shared Portal'

    coordination_team = models.ForeignKey(
        CoordinationTeam, on_delete=models.CASCADE, related_name='communication_channels'
    )
    name = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=10, choices=ChannelType.choices)
    description = models.TextField(blank=True)

    contact_address = models.CharField(max_length=255, blank=True)  # email/url/number
    access_credentials = models.JSONField(default=dict, blank=True)  # encrypted in practice

    members = models.ManyToManyField(User, blank=True, related_name='communication_channels')
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Communication Channel'
        verbose_name_plural = 'Communication Channels'
        ordering = ['name']
        indexes = [
            models.Index(fields=['coordination_team', 'is_active']),
            models.Index(fields=['channel_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.channel_type})"


# ---------------------------------------------------------------------------
# InformationProduct
# ---------------------------------------------------------------------------

class InformationProduct(TimeStampedModel):
    """A shared information product (SitRep, map, briefing, etc.)."""

    class ProductType(models.TextChoices):
        SITREP = 'SITREP', 'Situation Report'
        BRIEFING = 'BRIEFING', 'Briefing Note'
        ANALYSIS = 'ANALYSIS', 'Analysis Report'
        MAP = 'MAP', 'Map / Visualisation'
        GUIDELINE = 'GUIDELINE', 'Guideline / SOP'
        PLAN = 'PLAN', 'Plan / Strategy'
        DATA = 'DATA', 'Dataset'
        BULLETIN = 'BULLETIN', 'Bulletin'

    coordination_team = models.ForeignKey(
        CoordinationTeam, on_delete=models.CASCADE, related_name='information_products'
    )
    title = models.CharField(max_length=255)
    product_type = models.CharField(max_length=15, choices=ProductType.choices)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=20, default='1.0')
    effective_date = models.DateField()

    produced_by_agency = models.ForeignKey(
        Agency, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='produced_products'
    )
    author = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='authored_products'
    )

    file_url = models.URLField(blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    content_summary = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Sharing controls
    is_public = models.BooleanField(default=False)
    shared_with_agencies = models.ManyToManyField(Agency, blank=True, related_name='received_products')
    is_current = models.BooleanField(default=True)
    superseded_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='supersedes'
    )

    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Information Product'
        verbose_name_plural = 'Information Products'
        ordering = ['-effective_date', '-created_at']
        indexes = [
            models.Index(fields=['coordination_team', '-effective_date']),
            models.Index(fields=['product_type', 'is_current']),
            models.Index(fields=['is_public', '-effective_date']),
        ]

    def __str__(self):
        return f"{self.title} v{self.version} ({self.product_type})"

    def supersede_with(self, new_product: 'InformationProduct', updated_by: User) -> None:
        from core.models import AuditLog

        self.is_current = False
        self.superseded_by = new_product
        self.save(update_fields=['is_current', 'superseded_by', 'updated_at'])
        AuditLog.log(
            user=updated_by,
            action='INFORMATION_PRODUCT_SUPERSEDED',
            content_type='InformationProduct',
            object_id=str(self.id),
            details={'title': self.title, 'new_product_id': str(new_product.id)},
        )


# ---------------------------------------------------------------------------
# CoordinationDashboard
# ---------------------------------------------------------------------------

class CoordinationDashboard(TimeStampedModel):
    """A shared dashboard configuration for a coordination team."""

    coordination_team = models.OneToOneField(
        CoordinationTeam, on_delete=models.CASCADE, related_name='dashboard'
    )
    title = models.CharField(max_length=255, default='Coordination Dashboard')
    widgets = models.JSONField(default=list, blank=True)
    layout = models.JSONField(default=dict, blank=True)
    shared_with = models.ManyToManyField(
    settings.AUTH_USER_MODEL,
    related_name='coordination_shared_dashboards',
    blank=True,
)
    is_public = models.BooleanField(default=False)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Coordination Dashboard'
        verbose_name_plural = 'Coordination Dashboards'

    def __str__(self):
        return f"Dashboard — {self.coordination_team.name}"