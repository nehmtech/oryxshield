"""
Risk Assessment models for OryxShield.

All models extend TimeStampedModel (provides id, created_at, updated_at,
is_deleted, deleted_at). Soft-delete is the default; hard deletes are
never used in application code.
"""
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import Location, TimeStampedModel
from surveillance.models import AnomalyDetection, CaseCluster


# ---------------------------------------------------------------------------
# RiskScore
# ---------------------------------------------------------------------------

class RiskScore(TimeStampedModel):
    """
    Multi-criteria risk score for a (location, disease) pair.

    Scores are recalculated every 10 minutes by a Celery beat task.
    Each recalculation creates a new row; previous rows are retained for
    trend analysis and are deactivated via is_active=False.
    """

    RISK_LEVELS = [
        ("VERY_LOW", "Very Low"),
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
        ("CRITICAL", "Critical"),
    ]

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="risk_scores",
    )
    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)

    # ── composite score ──────────────────────────────────────────────────────
    overall_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Weighted composite risk score 0–10.",
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVELS,
        db_index=True,
    )

    # ── component scores (each 0–10) ─────────────────────────────────────────
    incidence_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Incidence-rate component (weight 25 %).",
    )
    transmission_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Growth-rate / R₀ component (weight 25 %).",
    )
    severity_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Case severity / CFR component (weight 20 %).",
    )
    vulnerability_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Population vulnerability component (weight 15 %).",
    )
    capacity_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Healthcare capacity component (weight 15 %).",
    )

    # ── epidemiological metrics ───────────────────────────────────────────────
    r_naught = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Basic reproduction number (R₀).",
    )
    case_fatality_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="CFR expressed as a percentage.",
    )
    attack_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Attack rate as a percentage of at-risk population.",
    )
    doubling_time = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Epidemic doubling time in days.",
    )

    # ── population metrics ────────────────────────────────────────────────────
    population_at_risk = models.IntegerField(default=0)
    vulnerable_population = models.IntegerField(default=0)

    # ── temporal ─────────────────────────────────────────────────────────────
    assessment_date = models.DateField(db_index=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    # ── status / quality ──────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, db_index=True)
    calculation_method = models.CharField(
        max_length=100,
        default="Multi-criteria Risk Assessment",
    )
    confidence_level = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Statistical confidence of this assessment (0–100).",
    )

    # ── related surveillance objects ──────────────────────────────────────────
    related_anomaly = models.ForeignKey(
        AnomalyDetection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="risk_scores",
    )
    related_cluster = models.ForeignKey(
        CaseCluster,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="risk_scores",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-assessment_date", "-overall_score"]
        indexes = [
            models.Index(fields=["location", "disease_code", "-assessment_date"]),
            models.Index(fields=["risk_level", "is_active"]),
            models.Index(fields=["is_active", "-assessment_date"]),
        ]
        # One active score per (location, disease, date); historical rows are
        # retained with is_active=False.
        unique_together = [["location", "disease_code", "assessment_date"]]

    def __str__(self):
        return (
            f"{self.disease_name} @ {self.location.name}"
            f" — {self.risk_level} ({self.overall_score})"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def level_for_score(score: float) -> str:
        """Return the risk level string for a given numeric score."""
        if score >= 9.0:
            return "CRITICAL"
        if score >= 7.5:
            return "VERY_HIGH"
        if score >= 6.0:
            return "HIGH"
        if score >= 4.0:
            return "MEDIUM"
        if score >= 2.0:
            return "LOW"
        return "VERY_LOW"


# ---------------------------------------------------------------------------
# ThreatClassification
# ---------------------------------------------------------------------------

class ThreatClassification(TimeStampedModel):
    """
    Structured threat assessment for a (location, disease) pair.

    Created or refreshed daily by the update_threat_classifications task
    whenever the underlying RiskScore is VERY_HIGH or CRITICAL.
    """

    THREAT_LEVELS = [
        ("MINIMAL", "Minimal"),
        ("LOW", "Low"),
        ("MODERATE", "Moderate"),
        ("HIGH", "High"),
        ("SEVERE", "Severe"),
        ("EXTREME", "Extreme"),
    ]

    ECONOMIC_IMPACT_LEVELS = [
        ("NEGLIGIBLE", "Negligible"),
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CATASTROPHIC", "Catastrophic"),
    ]

    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="threat_classifications",
    )

    threat_level = models.CharField(
        max_length=20,
        choices=THREAT_LEVELS,
        db_index=True,
    )
    threat_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )

    # ── threat characteristics ────────────────────────────────────────────────
    pandemic_potential = models.BooleanField(default=False)
    cross_border_risk = models.BooleanField(default=False)
    economic_impact_level = models.CharField(
        max_length=20,
        choices=ECONOMIC_IMPACT_LEVELS,
        default="MEDIUM",
    )

    # ── assessment provenance ─────────────────────────────────────────────────
    assessment_date = models.DateField(db_index=True, auto_now_add=False)
    assessed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="threat_assessments",
    )

    justification = models.TextField()
    key_factors = models.JSONField(default=list, blank=True)

    related_risk_score = models.ForeignKey(
        RiskScore,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="threat_classifications",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-assessment_date", "-threat_score"]
        indexes = [
            models.Index(fields=["threat_level", "-assessment_date"]),
            models.Index(fields=["location", "-assessment_date"]),
            models.Index(fields=["pandemic_potential", "threat_level"]),
        ]

    def __str__(self):
        return f"{self.disease_name} — {self.threat_level}"


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class Alert(TimeStampedModel):
    """
    System-generated alert arising from anomalies, risk scores, or
    threshold breaches.

    Lifecycle: ACTIVE → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED.
    Expired alerts are auto-closed by the auto_acknowledge_expired_alerts task.
    """

    ALERT_TYPES = [
        ("OUTBREAK", "Outbreak"),
        ("EPIDEMIC", "Epidemic"),
        ("PANDEMIC", "Pandemic"),
        ("CAPACITY", "Capacity"),
        ("THRESHOLD", "Threshold Breach"),
        ("ESCALATION", "Risk Escalation"),
        ("SYSTEM", "System"),
    ]

    SEVERITY_LEVELS = [
        ("INFO", "Information"),
        ("WARNING", "Warning"),
        ("ALERT", "Alert"),
        ("CRITICAL", "Critical"),
        ("EMERGENCY", "Emergency"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("ACKNOWLEDGED", "Acknowledged"),
        ("INVESTIGATING", "Investigating"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        db_index=True,
    )

    # ── content ───────────────────────────────────────────────────────────────
    title = models.CharField(max_length=300)
    description = models.TextField()
    recommendation = models.TextField(blank=True)

    # ── scope ─────────────────────────────────────────────────────────────────
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="alerts",
        null=True, blank=True,
    )
    affected_areas = models.JSONField(default=list, blank=True)
    disease_code = models.CharField(max_length=50, blank=True, db_index=True)
    disease_name = models.CharField(max_length=200, blank=True)

    # ── timing ────────────────────────────────────────────────────────────────
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # ── acknowledgment ────────────────────────────────────────────────────────
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="acknowledged_alerts",
    )

    # ── notifications ─────────────────────────────────────────────────────────
    notification_sent = models.BooleanField(default=False)
    notification_channels = models.JSONField(default=list, blank=True)
    recipients = models.JSONField(
        default=list, blank=True,
        help_text='List of {"type": "sms"|"email", "phone"|"email": "..."} dicts.',
    )

    # ── related objects ───────────────────────────────────────────────────────
    related_risk_score = models.ForeignKey(
        RiskScore,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="alerts",
    )
    related_anomaly = models.ForeignKey(
        AnomalyDetection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="alerts",
    )

    actions_taken = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-triggered_at"]
        indexes = [
            models.Index(fields=["status", "-triggered_at"]),
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["location", "-triggered_at"]),
            models.Index(fields=["disease_code", "status"]),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.title}"

    # ------------------------------------------------------------------
    # State-machine helpers
    # ------------------------------------------------------------------

    def acknowledge(self, user: User, notes: str = "") -> None:
        """Transition ACTIVE → ACKNOWLEDGED."""
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        if self.status != "ACTIVE":
            raise ValidationError(
                f"Cannot acknowledge an alert with status '{self.status}'. "
                "Only ACTIVE alerts can be acknowledged."
            )
        self.status = "ACKNOWLEDGED"
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if notes:
            self.metadata["acknowledgment_notes"] = notes
        self.save(update_fields=[
            "status", "acknowledged_by", "acknowledged_at", "metadata",
        ])

    def resolve(self, resolution_notes: str = "", actions: list | None = None) -> None:
        """Transition * → RESOLVED."""
        from django.utils import timezone

        self.status = "RESOLVED"
        self.resolved_at = timezone.now()
        if resolution_notes:
            self.metadata["resolution_notes"] = resolution_notes
        if actions:
            self.actions_taken = actions
        self.save(update_fields=[
            "status", "resolved_at", "metadata", "actions_taken",
        ])

    def close(self, reason: str = "") -> None:
        """Transition * → CLOSED (final state)."""
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        if self.status == "CLOSED":
            raise ValidationError("Alert is already CLOSED.")
        self.status = "CLOSED"
        self.metadata["closed_at"] = timezone.now().isoformat()
        if reason:
            self.metadata["close_reason"] = reason
        self.save(update_fields=["status", "metadata"])


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------

class Threshold(TimeStampedModel):
    """
    Configurable numeric thresholds that trigger automatic Alert creation.

    Three severity tiers: WARNING < ALERT < CRITICAL.
    """

    THRESHOLD_TYPES = [
        ("CASE_COUNT", "Case Count"),
        ("INCIDENCE_RATE", "Incidence Rate per 100 k"),
        ("MORTALITY_RATE", "Mortality Rate (%)"),
        ("R_NAUGHT", "R₀"),
        ("RISK_SCORE", "Overall Risk Score"),
        ("CAPACITY", "Healthcare Capacity (%)"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    threshold_type = models.CharField(max_length=20, choices=THRESHOLD_TYPES)

    # ── tier values ───────────────────────────────────────────────────────────
    warning_value = models.DecimalField(max_digits=10, decimal_places=2)
    alert_value = models.DecimalField(max_digits=10, decimal_places=2)
    critical_value = models.DecimalField(max_digits=10, decimal_places=2)

    # ── scope (null = all) ────────────────────────────────────────────────────
    disease_code = models.CharField(
        max_length=50, blank=True,
        help_text="Leave blank to apply to all diseases.",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="thresholds",
        help_text="Leave blank to apply to all locations.",
    )

    # ── configuration ─────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, db_index=True)
    evaluation_period = models.PositiveIntegerField(
        default=7,
        help_text="Rolling window in days used to compute the current value.",
    )
    auto_generate_alert = models.BooleanField(
        default=True,
        help_text="Automatically create an Alert when a tier is breached.",
    )
    notification_recipients = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["threshold_type", "is_active"]),
            models.Index(fields=["location", "disease_code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.threshold_type})"

    def evaluate(self, current_value) -> str:
        """
        Evaluate current_value against the configured tiers.

        Returns one of: 'NORMAL', 'WARNING', 'ALERT', 'CRITICAL'.
        """
        from decimal import Decimal

        v = Decimal(str(current_value))
        if v >= self.critical_value:
            return "CRITICAL"
        if v >= self.alert_value:
            return "ALERT"
        if v >= self.warning_value:
            return "WARNING"
        return "NORMAL"


# ---------------------------------------------------------------------------
# RiskFactor
# ---------------------------------------------------------------------------

class RiskFactor(TimeStampedModel):
    """
    A configurable factor that modulates risk calculation weights.

    Factors are categorised (demographic, environmental, etc.) and
    can be scoped to a specific location and/or set of disease codes.
    """

    FACTOR_CATEGORIES = [
        ("DEMOGRAPHIC", "Demographic"),
        ("ENVIRONMENTAL", "Environmental"),
        ("BEHAVIORAL", "Behavioral"),
        ("HEALTHCARE", "Healthcare System"),
        ("SOCIOECONOMIC", "Socioeconomic"),
        ("GEOGRAPHIC", "Geographic"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=FACTOR_CATEGORIES, db_index=True)
    description = models.TextField()

    weight = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Multiplicative weight applied during risk calculation.",
    )

    disease_codes = models.JSONField(
        default=list, blank=True,
        help_text="Applicable disease codes. Empty list = all diseases.",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="risk_factors",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    data_source = models.CharField(max_length=200, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"


# ---------------------------------------------------------------------------
# PredictiveModel
# ---------------------------------------------------------------------------

class PredictiveModel(TimeStampedModel):
    """
    Registry entry for a trained ML model used in outbreak forecasting.

    The model binary is stored in MEDIA_ROOT/ml_models/. Predictions are
    executed via the predict_outbreak Celery task.
    """

    MODEL_TYPES = [
        ("REGRESSION", "Regression"),
        ("CLASSIFICATION", "Classification"),
        ("TIME_SERIES", "Time Series"),
        ("ENSEMBLE", "Ensemble"),
    ]

    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    description = models.TextField()
    algorithm = models.CharField(max_length=100)
    version = models.CharField(max_length=50)

    # ── performance ───────────────────────────────────────────────────────────
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    precision = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    model_file = models.FileField(upload_to="ml_models/", null=True, blank=True)

    # ── training provenance ───────────────────────────────────────────────────
    trained_at = models.DateTimeField(null=True, blank=True)
    training_data_size = models.PositiveIntegerField(default=0)

    # ── status ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=False, db_index=True)
    is_deployed = models.BooleanField(default=False, db_index=True)

    # ── usage stats ───────────────────────────────────────────────────────────
    prediction_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-trained_at", "-created_at"]

    def __str__(self):
        return f"{self.name} v{self.version}"