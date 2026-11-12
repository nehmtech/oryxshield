"""
Surveillance models for OryxShield.
All models extend core.TimeStampedModel which provides:
  id (UUID PK), created_at, updated_at, is_deleted, deleted_at
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Location

User = get_user_model()


class DataSource(TimeStampedModel):
    """External data sources feeding the surveillance system."""

    SOURCE_TYPES = [
        ("HOSPITAL", "Hospital"),
        ("LABORATORY", "Laboratory"),
        ("CLINIC", "Clinic"),
        ("PHARMACY", "Pharmacy"),
        ("COMMUNITY", "Community Health Centre"),
        ("DHIS2", "DHIS2 System"),
        ("SORMAS", "SORMAS System"),
        ("EMR", "Electronic Medical Record"),
        ("LIS", "Laboratory Information System"),
        ("MANUAL", "Manual Entry"),
        ("API", "External API"),
        ("OTHER", "Other"),
    ]

    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, db_index=True)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="data_sources"
    )
    api_endpoint = models.URLField(blank=True, help_text="API endpoint for automated sync")
    # NOTE: api_key is stored as plaintext for development/synthetic data.
    # In production, replace with django-encrypted-model-fields or move to
    # a secrets vault (AWS Secrets Manager / HashiCorp Vault).
    # The serializer marks this write_only so it is never returned in API responses.
    api_key = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_frequency = models.PositiveIntegerField(
        default=3600, help_text="Sync frequency in seconds"
    )
    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["source_type", "is_active"]),
            models.Index(fields=["location"]),
            models.Index(fields=["is_deleted", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.source_type})"


class HealthData(TimeStampedModel):
    """Raw health / case data from all data sources."""

    DATA_TYPES = [
        ("CASE", "Case Report"),
        ("LAB_RESULT", "Lab Result"),
        ("SYMPTOM", "Symptom Report"),
        ("ADMISSION", "Hospital Admission"),
        ("DEATH", "Death Report"),
        ("VACCINATION", "Vaccination Record"),
        ("PHARMACY", "Pharmacy Sales"),
        ("SYNDROMIC", "Syndromic Surveillance"),
    ]

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("U", "Unknown"),
        ("O", "Other"),
    ]

    SEVERITY_CHOICES = [
        ("MILD", "Mild"),
        ("MODERATE", "Moderate"),
        ("SEVERE", "Severe"),
        ("CRITICAL", "Critical"),
    ]

    OUTCOME_CHOICES = [
        ("RECOVERED", "Recovered"),
        ("HOSPITALISED", "Hospitalised"),
        ("DECEASED", "Deceased"),
        ("UNKNOWN", "Unknown"),
    ]

    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name="health_data"
    )
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="health_data"
    )
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, db_index=True)
    date_recorded = models.DateTimeField(db_index=True)

    # Patient (anonymised)
    patient_id = models.CharField(max_length=100, blank=True, help_text="Anonymised patient ID")
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    # Disease
    disease_code = models.CharField(max_length=50, db_index=True, help_text="ICD-10 or custom code")
    disease_name = models.CharField(max_length=200)
    symptoms = models.JSONField(default=list, blank=True)

    # Clinical
    test_type = models.CharField(max_length=100, blank=True)
    test_result = models.CharField(max_length=50, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, blank=True)
    outcome = models.CharField(max_length=15, choices=OUTCOME_CHOICES, blank=True)

    # Geolocation
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Processing
    raw_data = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    processing_errors = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_recorded"]
        indexes = [
            models.Index(fields=["data_type", "-date_recorded"]),
            models.Index(fields=["disease_code", "-date_recorded"]),
            models.Index(fields=["location", "-date_recorded"]),
            models.Index(fields=["processed", "is_deleted"]),
            models.Index(fields=["data_source", "-date_recorded"]),
            # Composite: multi-column filter (location + disease + date)
            models.Index(fields=["location", "disease_code", "-date_recorded"],
                         name="hd_loc_dis_date_idx"),
            # Composite: unprocessed records query
            models.Index(fields=["processed", "is_deleted", "-date_recorded"],
                         name="hd_proc_del_date_idx"),
        ]
        verbose_name = "Health Data"
        verbose_name_plural = "Health Data"

    def __str__(self):
        return f"{self.disease_name} — {self.date_recorded:%Y-%m-%d}"


class DiseaseProfile(TimeStampedModel):
    """
    Master disease registry — surveillance thresholds, clinical parameters,
    case definitions used by anomaly detection and alert pipelines.
    """

    disease_code = models.CharField(max_length=50, unique=True, db_index=True)
    disease_name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)

    # Notification
    is_notifiable = models.BooleanField(default=False, db_index=True)
    notification_timeframe = models.PositiveIntegerField(
        null=True, blank=True, help_text="Hours within which authorities must be notified"
    )
    requires_laboratory_confirmation = models.BooleanField(default=False)

    # Epidemic thresholds
    alert_threshold = models.PositiveIntegerField(
        default=5, help_text="Cases within period to trigger alert"
    )
    epidemic_threshold = models.PositiveIntegerField(
        default=10, help_text="Cases within period to declare epidemic"
    )

    # Disease characteristics (days)
    incubation_period_min = models.PositiveIntegerField(null=True, blank=True)
    incubation_period_max = models.PositiveIntegerField(null=True, blank=True)
    infectious_period = models.PositiveIntegerField(null=True, blank=True)

    # Clinical
    symptoms = models.JSONField(default=list, blank=True)
    transmission_routes = models.JSONField(default=list, blank=True)
    risk_factors = models.JSONField(default=list, blank=True)
    surveillance_case_definition = models.TextField(blank=True)
    laboratory_tests = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["disease_name"]
        verbose_name = "Disease Profile"
        verbose_name_plural = "Disease Profiles"

    def __str__(self):
        return f"{self.disease_name} ({self.disease_code})"


class AnomalyDetection(TimeStampedModel):
    """
    Detected anomalies produced by the ML / statistical pipeline.
    """

    SEVERITY_LEVELS = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    ANOMALY_TYPES = [
        ("SPIKE", "Case Spike"),
        ("TREND", "Unusual Trend"),
        ("CLUSTER", "Geographic Cluster"),
        ("OUTBREAK", "Potential Outbreak"),
        ("PATTERN", "Pattern Change"),
        ("SEASONAL", "Seasonal Anomaly"),
    ]

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="anomalies"
    )
    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    anomaly_type = models.CharField(max_length=20, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, db_index=True)

    # Detection
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    detection_method = models.CharField(max_length=100)
    confidence_score = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Statistics
    expected_cases = models.PositiveIntegerField(default=0)
    actual_cases = models.PositiveIntegerField(default=0)
    baseline_cases = models.PositiveIntegerField(default=0)
    percentage_increase = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Period
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Verification
    is_verified = models.BooleanField(default=False, db_index=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="verified_anomalies"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    is_false_positive = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True)

    related_health_data = models.ManyToManyField(
        HealthData, related_name="anomalies", blank=True
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["severity", "-detected_at"]),
            models.Index(fields=["location", "-detected_at"]),
            models.Index(fields=["is_verified", "is_false_positive"]),
            models.Index(fields=["is_deleted", "severity"]),
        ]
        verbose_name = "Anomaly Detection"
        verbose_name_plural = "Anomaly Detections"

    def __str__(self):
        return f"{self.anomaly_type} — {self.disease_name} @ {self.location.name}"


class CaseCluster(TimeStampedModel):
    """Geographic cluster of disease cases identified by spatial scan statistics."""

    name = models.CharField(max_length=200)
    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="case_clusters"
    )

    case_count = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    # Geography
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    affected_areas = models.JSONField(default=list, blank=True)

    # Epidemiology
    attack_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    population_at_risk = models.PositiveIntegerField(null=True, blank=True)

    # Detection metadata
    detection_method = models.CharField(max_length=100)
    detection_algorithm = models.CharField(max_length=50, default="SaTScan")
    p_value = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)

    related_cases = models.ManyToManyField(HealthData, related_name="clusters", blank=True)
    related_anomaly = models.ForeignKey(
        AnomalyDetection, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="clusters"
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-start_date", "-case_count"]
        indexes = [
            models.Index(fields=["is_active", "-start_date"]),
            models.Index(fields=["location", "-start_date"]),
            models.Index(fields=["disease_code", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.case_count} cases"


class Hotspot(TimeStampedModel):
    """Geographic disease hotspot identified by Getis-Ord Gi* spatial analysis."""

    RISK_LEVELS = [
        ("LOW", "Low Risk"),
        ("MEDIUM", "Medium Risk"),
        ("HIGH", "High Risk"),
        ("CRITICAL", "Critical Risk"),
    ]

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="hotspots"
    )
    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, db_index=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.DecimalField(max_digits=10, decimal_places=2)

    case_count = models.PositiveIntegerField(default=0)
    incidence_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gi_statistic = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Getis-Ord Gi* statistic"
    )
    z_score = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    p_value = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)

    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    related_cluster = models.ForeignKey(
        CaseCluster, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hotspots"
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-risk_level", "-start_date"]
        indexes = [
            models.Index(fields=["risk_level", "is_active"]),
            models.Index(fields=["location", "-start_date"]),
            models.Index(fields=["disease_code", "is_active"]),
        ]

    def __str__(self):
        return f"Hotspot @ {self.location.name} — {self.risk_level}"


class SurveillanceReport(TimeStampedModel):
    """Periodic or outbreak-specific surveillance report."""

    REPORT_TYPES = [
        ("DAILY", "Daily Report"),
        ("WEEKLY", "Weekly Report"),
        ("MONTHLY", "Monthly Report"),
        ("OUTBREAK", "Outbreak Report"),
        ("SPECIAL", "Special Report"),
    ]

    report_type = models.CharField(max_length=10, choices=REPORT_TYPES, db_index=True)
    title = models.CharField(max_length=300)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="surveillance_reports"
    )

    start_date = models.DateField()
    end_date = models.DateField()

    total_cases = models.PositiveIntegerField(default=0)
    new_cases = models.PositiveIntegerField(default=0)
    active_clusters = models.PositiveIntegerField(default=0)
    active_hotspots = models.PositiveIntegerField(default=0)
    anomalies_detected = models.PositiveIntegerField(default=0)

    summary = models.TextField()
    key_findings = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)

    report_file = models.FileField(upload_to="surveillance_reports/%Y/%m/", null=True, blank=True)

    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="generated_reports"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_surveillance_reports"
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_surveillance_reports"
    )

    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["report_type", "-start_date"]),
            models.Index(fields=["location", "-start_date"]),
            models.Index(fields=["is_published"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_date} → {self.end_date})"


class DataQualityCheck(TimeStampedModel):
    """Automated data quality validation result for a DataSource."""

    CHECK_TYPES = [
        ("COMPLETENESS", "Completeness Check"),
        ("CONSISTENCY", "Consistency Check"),
        ("ACCURACY", "Accuracy Check"),
        ("TIMELINESS", "Timeliness Check"),
        ("DUPLICATION", "Duplication Check"),
    ]

    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("PARTIAL", "Partial"),
    ]

    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name="quality_checks"
    )
    check_type = models.CharField(max_length=15, choices=CHECK_TYPES, db_index=True)
    check_date = models.DateTimeField(auto_now_add=True, db_index=True)

    records_checked = models.PositiveIntegerField(default=0)
    records_passed = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    pass_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    issues = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="COMPLETED")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-check_date"]
        indexes = [
            models.Index(fields=["data_source", "-check_date"]),
            models.Index(fields=["check_type", "status"]),
        ]

    def __str__(self):
        return f"{self.check_type} — {self.data_source.name} — {self.pass_rate}%"