"""
Response models for OryxShield.

Extends TimeStampedModel which provides:
  id (UUID), created_at, updated_at, is_deleted, deleted_at
All querysets filter is_deleted=False.
"""
import uuid
import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from core.models import TimeStampedModel, Location, AuditLog
from risk_assessment.models import RiskScore, Alert

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class ActiveManager(models.Manager):
    """Default manager that excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ---------------------------------------------------------------------------
# ResponseLevel
# ---------------------------------------------------------------------------

class ResponseLevel(TimeStampedModel):
    """
    Tiered response levels 1–5.

    Level 1 – Routine Surveillance   (risk < 4.0)
    Level 2 – Enhanced Surveillance  (risk 4.0–5.9)
    Level 3 – Targeted Response      (risk 6.0–7.4)
    Level 4 – Coordinated Response   (risk 7.5–8.9)
    Level 5 – Emergency Response     (risk ≥ 9.0)
    """

    LEVEL_CHOICES = [
        (1, "Level 1 – Routine Surveillance"),
        (2, "Level 2 – Enhanced Surveillance"),
        (3, "Level 3 – Targeted Response"),
        (4, "Level 4 – Coordinated Response"),
        (5, "Level 5 – Emergency Response"),
    ]

    level = models.IntegerField(
        choices=LEVEL_CHOICES,
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    name = models.CharField(max_length=200)
    description = models.TextField()

    # Activation criteria
    risk_score_threshold = models.DecimalField(max_digits=4, decimal_places=2)
    case_count_threshold = models.IntegerField(null=True, blank=True)

    # Required / optional actions
    required_actions = models.JSONField(default=list, blank=True)
    optional_actions = models.JSONField(default=list, blank=True)

    # Resources & timing
    required_resources = models.JSONField(default=list, blank=True)
    estimated_duration_days = models.IntegerField(null=True, blank=True)

    # Escalation
    auto_escalate_after_days = models.IntegerField(null=True, blank=True)
    escalation_criteria = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return f"Level {self.level} – {self.name}"


# ---------------------------------------------------------------------------
# ResponseProtocol
# ---------------------------------------------------------------------------

class ResponseProtocol(TimeStampedModel):
    """
    Response protocols for specific diseases or scenarios.
    """

    PROTOCOL_TYPES = [
        ("DISEASE", "Disease-Specific"),
        ("SCENARIO", "Scenario-Based"),
        ("GENERAL", "General Protocol"),
    ]

    name = models.CharField(max_length=200)
    protocol_type = models.CharField(max_length=20, choices=PROTOCOL_TYPES)
    code = models.CharField(max_length=50, unique=True, db_index=True)

    # Applicability
    disease_codes = models.JSONField(default=list, blank=True)
    applicable_locations = models.ManyToManyField(
        Location,
        related_name="response_protocols",
        blank=True,
    )

    # Protocol content
    description = models.TextField()
    objectives = models.JSONField(default=list, blank=True)
    procedures = models.JSONField(default=list, blank=True)

    # Decision support
    decision_tree = models.JSONField(default=dict, blank=True)

    # Resource requirements
    required_personnel = models.JSONField(default=list, blank=True)
    required_equipment = models.JSONField(default=list, blank=True)
    required_supplies = models.JSONField(default=list, blank=True)

    # Timing
    response_time_hours = models.IntegerField(
        default=24,
        help_text="Expected response time in hours",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    version = models.CharField(max_length=20, default="1.0")
    last_reviewed = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_protocols",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_protocols",
    )

    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["protocol_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# ResponseActivation
# ---------------------------------------------------------------------------

class ResponseActivation(TimeStampedModel):
    """
    An active response instance tied to a location and disease event.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending Activation"),
        ("ACTIVE", "Active"),
        ("ESCALATED", "Escalated"),
        ("DEESCALATED", "De-escalated"),
        ("COMPLETED", "Completed"),
        ("SUSPENDED", "Suspended"),
        ("CANCELLED", "Cancelled"),
    ]

    activation_code = models.CharField(max_length=50, unique=True, db_index=True)

    response_level = models.ForeignKey(
        ResponseLevel,
        on_delete=models.PROTECT,
        related_name="activations",
    )
    protocol = models.ForeignKey(
        ResponseProtocol,
        on_delete=models.PROTECT,
        related_name="activations",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="response_activations",
    )

    disease_code = models.CharField(max_length=50, blank=True, db_index=True)
    disease_name = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    # Timing
    activated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expected_completion = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Hard expiry — activation auto-closes after this datetime.",
    )

    # Personnel
    incident_commander = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commanded_responses",
    )
    activated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activated_responses",
    )

    # Trigger linkage
    triggered_by_alert = models.ForeignKey(
        Alert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="response_activations",
    )
    triggered_by_risk_score = models.ForeignKey(
        RiskScore,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="response_activations",
    )

    justification = models.TextField()
    objectives = models.JSONField(default=list, blank=True)

    # Resources
    personnel_deployed = models.IntegerField(default=0)
    resources_allocated = models.JSONField(default=dict, blank=True)

    # Progress
    completion_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Escalation history – append-only list of dicts
    escalation_history = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-activated_at"]
        indexes = [
            models.Index(fields=["status", "-activated_at"]),
            models.Index(fields=["location", "status"]),
            models.Index(fields=["disease_code", "status"]),
        ]

    def __str__(self):
        return f"{self.activation_code} – Level {self.response_level.level}"

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    def escalate(self, new_level: ResponseLevel, user, reason: str) -> None:
        """
        Escalate this response to *new_level*.

        Raises ValueError if new_level is not higher than the current level.
        Writes an AuditLog entry and updates status in-place using update_fields.
        """
        if new_level.level <= self.response_level.level:
            raise ValueError(
                f"Cannot escalate to Level {new_level.level}: "
                f"current level is already {self.response_level.level}."
            )

        previous_level = self.response_level.level

        history_entry = {
            "timestamp": timezone.now().isoformat(),
            "from_level": previous_level,
            "to_level": new_level.level,
            "escalated_by": user.username if user else "system",
            "reason": reason,
        }

        self.escalation_history = list(self.escalation_history) + [history_entry]
        self.response_level = new_level
        self.status = "ESCALATED"
        self.save(
            update_fields=[
                "escalation_history",
                "response_level",
                "status",
                "updated_at",
            ]
        )

        AuditLog.log(
            action="RESPONSE_ESCALATED",
            actor=user,
            target_object_id=str(self.id),
            target_content_type="response.ResponseActivation",
            details={
                "activation_code": self.activation_code,
                "from_level": previous_level,
                "to_level": new_level.level,
                "reason": reason,
            },
        )

        logger.info(
            "Response %s escalated from Level %s to Level %s by %s",
            self.activation_code,
            previous_level,
            new_level.level,
            user.username if user else "system",
        )

    def complete(self, user=None) -> None:
        """
        Mark this response as completed.
        Updates status, completion timestamp, and percentage atomically.
        """
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.completion_percentage = 100
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "completion_percentage",
                "updated_at",
            ]
        )

        AuditLog.log(
            action="RESPONSE_COMPLETED",
            actor=user,
            target_object_id=str(self.id),
            target_content_type="response.ResponseActivation",
            details={
                "activation_code": self.activation_code,
                "location": self.location.name,
                "disease_code": self.disease_code,
            },
        )

        logger.info("Response %s marked COMPLETED", self.activation_code)

    def suspend(self, user, reason: str) -> None:
        """Suspend an active response."""
        self.status = "SUSPENDED"
        self.metadata["suspension_reason"] = reason
        self.save(update_fields=["status", "metadata", "updated_at"])

        AuditLog.log(
            action="RESPONSE_SUSPENDED",
            actor=user,
            target_object_id=str(self.id),
            target_content_type="response.ResponseActivation",
            details={"activation_code": self.activation_code, "reason": reason},
        )

    def deescalate(self, new_level: ResponseLevel, user, reason: str) -> None:
        """
        De-escalate this response to a lower level.
        """
        if new_level.level >= self.response_level.level:
            raise ValueError(
                f"Cannot de-escalate to Level {new_level.level}: "
                f"current level is {self.response_level.level}."
            )

        previous_level = self.response_level.level
        history_entry = {
            "timestamp": timezone.now().isoformat(),
            "from_level": previous_level,
            "to_level": new_level.level,
            "deescalated_by": user.username if user else "system",
            "reason": reason,
        }

        self.escalation_history = list(self.escalation_history) + [history_entry]
        self.response_level = new_level
        self.status = "DEESCALATED"
        self.save(
            update_fields=[
                "escalation_history",
                "response_level",
                "status",
                "updated_at",
            ]
        )

        AuditLog.log(
            action="RESPONSE_DEESCALATED",
            actor=user,
            target_object_id=str(self.id),
            target_content_type="response.ResponseActivation",
            details={
                "activation_code": self.activation_code,
                "from_level": previous_level,
                "to_level": new_level.level,
                "reason": reason,
            },
        )


# ---------------------------------------------------------------------------
# EscalationTrigger
# ---------------------------------------------------------------------------

class EscalationTrigger(TimeStampedModel):
    """
    Automated escalation triggers evaluated against active responses.
    """

    TRIGGER_TYPES = [
        ("CASE_COUNT", "Case Count Threshold"),
        ("RISK_SCORE", "Risk Score Threshold"),
        ("TIME_ELAPSED", "Time Elapsed"),
        ("CAPACITY", "Capacity Threshold"),
        ("MORTALITY", "Mortality Rate Threshold"),
    ]

    name = models.CharField(max_length=200)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES, db_index=True)
    description = models.TextField(blank=True)

    from_level = models.ForeignKey(
        ResponseLevel,
        on_delete=models.CASCADE,
        related_name="escalation_triggers_from",
    )
    to_level = models.ForeignKey(
        ResponseLevel,
        on_delete=models.CASCADE,
        related_name="escalation_triggers_to",
    )

    threshold_value = models.DecimalField(max_digits=10, decimal_places=2)
    evaluation_period_days = models.IntegerField(default=7)

    disease_codes = models.JSONField(default=list, blank=True)
    locations = models.ManyToManyField(
        Location,
        related_name="escalation_triggers",
        blank=True,
    )

    auto_escalate = models.BooleanField(default=False)
    notification_recipients = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["from_level", "name"]

    def __str__(self):
        return f"{self.name}: Level {self.from_level.level} → {self.to_level.level}"


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------

class ActionItem(TimeStampedModel):
    """
    A discrete action item within a response activation.
    """

    PRIORITY_LEVELS = [
        ("LOW", "Low Priority"),
        ("MEDIUM", "Medium Priority"),
        ("HIGH", "High Priority"),
        ("CRITICAL", "Critical Priority"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("BLOCKED", "Blocked"),
        ("CANCELLED", "Cancelled"),
    ]

    PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    response_activation = models.ForeignKey(
        ResponseActivation,
        on_delete=models.CASCADE,
        related_name="action_items",
    )

    title = models.CharField(max_length=300)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default="MEDIUM")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_actions",
    )
    assigned_team = models.CharField(max_length=100, blank=True)

    due_date = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    completion_notes = models.TextField(blank=True)
    blockers = models.TextField(blank=True)

    depends_on = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="dependent_actions",
        blank=True,
    )

    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["priority", "due_date"]
        indexes = [
            models.Index(fields=["response_activation", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["priority", "status"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.priority}]"

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    def start(self, user=None) -> None:
        """Mark this action as in-progress."""
        self.status = "IN_PROGRESS"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self, notes: str = "", user=None) -> None:
        """
        Mark this action as completed.
        Triggers response progress recalculation via signal.
        """
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        if notes:
            self.completion_notes = notes
        self.save(
            update_fields=["status", "completed_at", "completion_notes", "updated_at"]
        )

        AuditLog.log(
            action="ACTION_COMPLETED",
            actor=user,
            target_object_id=str(self.id),
            target_content_type="response.ActionItem",
            details={
                "title": self.title,
                "activation_code": self.response_activation.activation_code,
                "priority": self.priority,
            },
        )

    def block(self, blocker_description: str, user=None) -> None:
        """Mark this action as blocked."""
        self.status = "BLOCKED"
        self.blockers = blocker_description
        self.save(update_fields=["status", "blockers", "updated_at"])

    @property
    def is_overdue(self) -> bool:
        if self.due_date and self.status in ("PENDING", "IN_PROGRESS"):
            return timezone.now() > self.due_date
        return False


# ---------------------------------------------------------------------------
# ResponseReport
# ---------------------------------------------------------------------------

class ResponseReport(TimeStampedModel):
    """
    Situation reports, progress updates, and after-action reviews.
    """

    REPORT_TYPES = [
        ("SITUATION", "Situation Report"),
        ("PROGRESS", "Progress Report"),
        ("AFTER_ACTION", "After Action Review"),
        ("DAILY", "Daily Summary"),
    ]

    response_activation = models.ForeignKey(
        ResponseActivation,
        on_delete=models.CASCADE,
        related_name="reports",
    )

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, db_index=True)
    title = models.CharField(max_length=300)

    report_date = models.DateField(db_index=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    executive_summary = models.TextField()
    situation_overview = models.TextField(blank=True)
    actions_taken = models.JSONField(default=list, blank=True)
    challenges = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)

    cases_managed = models.IntegerField(default=0)
    personnel_deployed = models.IntegerField(default=0)
    resources_consumed = models.JSONField(default=dict, blank=True)

    report_file = models.FileField(upload_to="response_reports/", null=True, blank=True)

    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_reports",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_response_reports",
    )

    is_published = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-report_date"]
        indexes = [
            models.Index(fields=["response_activation", "-report_date"]),
            models.Index(fields=["report_type", "is_published"]),
        ]

    def __str__(self):
        return f"{self.title} – {self.report_date}"

    def publish(self, reviewer) -> None:
        """Publish this report."""
        self.is_published = True
        self.reviewed_by = reviewer
        self.save(update_fields=["is_published", "reviewed_by", "updated_at"])


# ---------------------------------------------------------------------------
# DecisionLog
# ---------------------------------------------------------------------------

class DecisionLog(TimeStampedModel):
    """
    Immutable log of key decisions made during a response activation.
    """

    response_activation = models.ForeignKey(
        ResponseActivation,
        on_delete=models.CASCADE,
        related_name="decisions",
    )

    decision_title = models.CharField(max_length=300)
    decision_description = models.TextField()

    situation = models.TextField(help_text="Situation that required the decision.")
    options_considered = models.JSONField(default=list, blank=True)

    decision_made = models.TextField()
    rationale = models.TextField()

    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="made_decisions",
    )
    decision_date = models.DateTimeField(auto_now_add=True, db_index=True)

    expected_outcome = models.TextField(blank=True)
    actual_outcome = models.TextField(blank=True)

    reviewed = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-decision_date"]

    def __str__(self):
        return f"{self.decision_title} – {self.decision_date.date()}"