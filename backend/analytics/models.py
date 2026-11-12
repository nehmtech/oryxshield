"""
OryxShield - Analytics Models
======================================

9 production-ready models for epidemiological analytics.

Models:
    1. EpidemiologicalModel  - Mathematical disease spread models (SIR/SEIR/SIRS/SEIRS/SIS)
    2. SpatialAnalysis       - Geographic & hotspot analysis
    3. TimeSeriesAnalysis    - Temporal trends & forecasting
    4. StatisticalReport     - Comprehensive statistical reports with publication workflow
    5. Dashboard             - Custom analytics dashboards with auto-refresh
    6. DataExport            - Multi-format async data exports
    7. Indicator             - Key Performance Indicators (KPIs)
    8. IndicatorValue        - Time-series KPI measurements
    9. ReportTemplate        - Automated report generation templates

All models inherit from core.models.TimeStampedModel providing:
    - UUID primary keys
    - created_at / updated_at timestamps
    - is_deleted soft-delete flag
    - metadata JSON field
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.conf import settings

from core.models import TimeStampedModel, Location


# =============================================================================
# EPIDEMIOLOGICAL MODEL
# =============================================================================

class EpidemiologicalModel(TimeStampedModel):
    """
    Mathematical models for disease spread prediction and analysis.

    Supports SIR, SEIR, SIRS, SEIRS, SIS, and CUSTOM model types.
    Stores initial conditions, parameters, simulation results, and
    validation metrics.  The calculate_r0() and validate_model()
    methods keep computed fields up-to-date.
    """

    MODEL_TYPES = [
        ('SIR',    'SIR  - Susceptible-Infected-Recovered'),
        ('SEIR',   'SEIR - Susceptible-Exposed-Infected-Recovered'),
        ('SIRS',   'SIRS - SIR with Immunity Loss'),
        ('SEIRS',  'SEIRS - SEIR with Immunity Loss'),
        ('SIS',    'SIS  - Susceptible-Infected-Susceptible'),
        ('CUSTOM', 'Custom - User Defined'),
    ]

    # ── identification ──────────────────────────────────────────────────────
    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, db_index=True)
    description = models.TextField(blank=True)

    # ── disease scope ────────────────────────────────────────────────────────
    disease_code = models.CharField(max_length=50, db_index=True,
                                    help_text='ICD-10 or other classification code')
    disease_name = models.CharField(max_length=200)
    location = models.ForeignKey(Location, on_delete=models.CASCADE,
                                 related_name='epi_models')

    # ── model parameters ─────────────────────────────────────────────────────
    parameters = models.JSONField(default=dict,
                                  help_text='beta, gamma, sigma, xi, etc.')

    # ── initial conditions ───────────────────────────────────────────────────
    initial_susceptible = models.IntegerField(validators=[MinValueValidator(0)])
    initial_infected    = models.IntegerField(validators=[MinValueValidator(0)])
    initial_recovered   = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    initial_exposed     = models.IntegerField(null=True, blank=True,
                                              validators=[MinValueValidator(0)],
                                              help_text='SEIR/SEIRS only')

    # ── calculated epidemiological metrics ──────────────────────────────────
    basic_reproduction_number = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='R0 – average secondary infections per case')
    attack_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Percentage of population infected')
    peak_day        = models.IntegerField(null=True, blank=True)
    peak_infections = models.IntegerField(null=True, blank=True)

    # ── simulation ───────────────────────────────────────────────────────────
    simulation_days = models.IntegerField(
        default=365, validators=[MinValueValidator(1), MaxValueValidator(3650)])
    simulation_results      = models.JSONField(default=dict, blank=True)
    simulation_completed_at = models.DateTimeField(null=True, blank=True)

    # ── validation ───────────────────────────────────────────────────────────
    model_fit_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    rmse         = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_validated = models.BooleanField(default=False, db_index=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    # ── authorship ───────────────────────────────────────────────────────────
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='epi_models')
    metadata   = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Epidemiological Model'
        verbose_name_plural = 'Epidemiological Models'
        indexes = [
            models.Index(fields=['disease_code', '-created_at']),
            models.Index(fields=['location', '-created_at']),
            models.Index(fields=['model_type', 'is_validated']),
            models.Index(fields=['-simulation_completed_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"

    def calculate_r0(self):
        """
        Calculate R0 = beta / gamma and persist.

        Returns:
            Decimal | None: The calculated R0, or None if parameters absent.
        """
        if self.model_type in ('SIR', 'SEIR', 'SIRS', 'SEIRS', 'SIS'):
            beta  = self.parameters.get('beta')
            gamma = self.parameters.get('gamma')
            if beta and gamma and gamma > 0:
                r0 = Decimal(str(beta / gamma))
                type(self).objects.filter(pk=self.pk).update(
                    basic_reproduction_number=r0)
                self.basic_reproduction_number = r0
                return r0
        return None

    def get_total_population(self):
        """Return S + E + I + R."""
        total = self.initial_susceptible + self.initial_infected + self.initial_recovered
        if self.initial_exposed:
            total += self.initial_exposed
        return total

    def validate_model(self, observed_data):
        """
        Validate model against observed infection counts.

        Args:
            observed_data (list[int]): Observed case counts matching simulation length.

        Returns:
            dict | None: {rmse, fit_score, validated} or None if no simulation data.
        """
        if not self.simulation_results or 'infected' not in self.simulation_results:
            return None

        import numpy as np

        predicted = self.simulation_results['infected'][:len(observed_data)]
        rmse_val  = float(np.sqrt(np.mean(
            (np.array(observed_data) - np.array(predicted)) ** 2)))
        max_obs   = max(observed_data) if observed_data else 1
        fit_score = max(0.0, 100.0 * (1 - rmse_val / max_obs))

        self.rmse           = Decimal(str(rmse_val))
        self.model_fit_score = Decimal(str(fit_score))
        self.is_validated   = True
        self.validated_at   = timezone.now()
        self.save(update_fields=['rmse', 'model_fit_score', 'is_validated', 'validated_at'])

        return {'rmse': rmse_val, 'fit_score': fit_score, 'validated': True}


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

class SpatialAnalysis(TimeStampedModel):
    """
    Geographic and spatial statistical analysis of disease patterns.

    Analysis types:
        HOTSPOT       – Getis-Ord Gi* hotspot detection
        CLUSTERING    – DBSCAN / K-means spatial clustering
        AUTOCORRELATION – Moran's I spatial autocorrelation
        KERNEL_DENSITY  – Kernel density estimation
        SPATIAL_SCAN    – SaTScan spatial scan statistics
    """

    ANALYSIS_TYPES = [
        ('HOTSPOT',          'Hotspot Analysis – Getis-Ord Gi*'),
        ('CLUSTERING',       'Spatial Clustering'),
        ('AUTOCORRELATION',  "Spatial Autocorrelation – Moran's I"),
        ('KERNEL_DENSITY',   'Kernel Density Estimation'),
        ('SPATIAL_SCAN',     'Spatial Scan Statistics'),
    ]

    name          = models.CharField(max_length=200)
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES, db_index=True)
    description   = models.TextField(blank=True)

    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    location     = models.ForeignKey(Location, on_delete=models.CASCADE,
                                     related_name='spatial_analyses')

    start_date = models.DateField()
    end_date   = models.DateField()

    # ── results ──────────────────────────────────────────────────────────────
    results       = models.JSONField(default=dict, blank=True)
    hotspots      = models.JSONField(default=list, blank=True)
    hotspot_count = models.IntegerField(default=0)
    clusters      = models.JSONField(default=list, blank=True)
    cluster_count = models.IntegerField(default=0)

    # ── statistics ───────────────────────────────────────────────────────────
    morans_i = models.DecimalField(max_digits=5,  decimal_places=3, null=True, blank=True)
    p_value  = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    z_score  = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # ── visualisation ────────────────────────────────────────────────────────
    map_data   = models.JSONField(default=dict, blank=True,
                                  help_text='GeoJSON for map visualisation')
    parameters = models.JSONField(default=dict, blank=True)

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='spatial_analyses')
    metadata     = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Spatial Analysis'
        verbose_name_plural = 'Spatial Analyses'
        indexes = [
            models.Index(fields=['disease_code', '-created_at']),
            models.Index(fields=['location', '-created_at']),
            models.Index(fields=['analysis_type', '-created_at']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.name} – {self.get_analysis_type_display()}"

    def is_significant(self, alpha=0.05):
        """Return True if p_value < alpha."""
        return float(self.p_value) < alpha if self.p_value is not None else False

    def get_duration_days(self):
        """Return analysis period in days."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0


# =============================================================================
# TIME SERIES ANALYSIS
# =============================================================================

class TimeSeriesAnalysis(TimeStampedModel):
    """
    Temporal analysis and forecasting of disease trends.

    Analysis types:
        TREND        – Trend detection
        SEASONALITY  – Seasonal pattern identification
        FORECASTING  – ARIMA / Prophet future prediction
        CHANGE_POINT – Abrupt change detection
        DECOMPOSITION – Component separation
    """

    ANALYSIS_TYPES = [
        ('TREND',         'Trend Analysis'),
        ('SEASONALITY',   'Seasonality Detection'),
        ('FORECASTING',   'Forecasting'),
        ('CHANGE_POINT',  'Change Point Detection'),
        ('DECOMPOSITION', 'Time Series Decomposition'),
    ]

    TREND_DIRECTIONS = [
        ('INCREASING',  'Increasing'),
        ('DECREASING',  'Decreasing'),
        ('STABLE',      'Stable'),
        ('FLUCTUATING', 'Fluctuating'),
    ]

    name          = models.CharField(max_length=200)
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES, db_index=True)
    description   = models.TextField(blank=True)

    disease_code = models.CharField(max_length=50, db_index=True)
    disease_name = models.CharField(max_length=200)
    location     = models.ForeignKey(Location, on_delete=models.CASCADE,
                                     related_name='timeseries_analyses')

    start_date = models.DateField()
    end_date   = models.DateField()

    forecast_days = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)])

    results = models.JSONField(default=dict, blank=True)

    # ── trend ─────────────────────────────────────────────────────────────────
    trend_direction = models.CharField(max_length=20, choices=TREND_DIRECTIONS, blank=True)
    trend_strength  = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)])

    # ── seasonality ──────────────────────────────────────────────────────────
    has_seasonality     = models.BooleanField(default=False)
    seasonal_period     = models.IntegerField(null=True, blank=True,
                                              help_text='Cycle length in days')
    seasonality_strength = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    # ── forecast ─────────────────────────────────────────────────────────────
    forecast_data                = models.JSONField(default=list, blank=True)
    forecast_confidence_intervals = models.JSONField(default=dict, blank=True)
    model_used       = models.CharField(max_length=100, blank=True)
    model_parameters = models.JSONField(default=dict, blank=True)

    # ── performance metrics ──────────────────────────────────────────────────
    mae  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rmse = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    mape = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='timeseries_analyses')
    metadata     = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Time Series Analysis'
        verbose_name_plural = 'Time Series Analyses'
        indexes = [
            models.Index(fields=['disease_code', '-created_at']),
            models.Index(fields=['location', '-created_at']),
            models.Index(fields=['analysis_type', '-created_at']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.name} – {self.get_analysis_type_display()}"


# =============================================================================
# STATISTICAL REPORT
# =============================================================================

class StatisticalReport(TimeStampedModel):
    """
    Comprehensive statistical analysis reports with publication workflow.

    Publication flow: draft → review → publish (is_published=True).
    """

    REPORT_TYPES = [
        ('DESCRIPTIVE',  'Descriptive Statistics'),
        ('INFERENTIAL',  'Inferential Statistics'),
        ('COMPARATIVE',  'Comparative Analysis'),
        ('CORRELATION',  'Correlation Analysis'),
        ('REGRESSION',   'Regression Analysis'),
    ]

    title       = models.CharField(max_length=300)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, db_index=True)
    description = models.TextField(blank=True)

    disease_codes = models.JSONField(default=list, blank=True)
    locations     = models.ManyToManyField(Location, related_name='statistical_reports', blank=True)

    start_date = models.DateField()
    end_date   = models.DateField()

    executive_summary = models.TextField()
    key_findings      = models.JSONField(default=list, blank=True)
    results           = models.JSONField(default=dict, blank=True)
    tables            = models.JSONField(default=list, blank=True)
    charts            = models.JSONField(default=list, blank=True)

    report_file = models.FileField(upload_to='statistical_reports/', null=True, blank=True)

    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    author      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='statistical_reports')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_statistical_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Statistical Report'
        verbose_name_plural = 'Statistical Reports'
        indexes = [
            models.Index(fields=['-created_at', 'is_published']),
            models.Index(fields=['report_type', 'is_published']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()})"

    def publish(self, user=None):
        """
        Publish the report.

        Args:
            user (User | None): Reviewer publishing the report.
        """
        self.is_published = True
        self.published_at = timezone.now()
        if user:
            self.reviewed_by = user
            self.reviewed_at = timezone.now()
        self.save(update_fields=['is_published', 'published_at', 'reviewed_by', 'reviewed_at'])


# =============================================================================
# DASHBOARD
# =============================================================================

class Dashboard(TimeStampedModel):
    """
    Custom analytics dashboards with real-time data and auto-refresh.

    Widgets are stored as a JSON list. Access is controlled via
    owner / shared_with / is_public.
    """

    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    widgets = models.JSONField(default=list, blank=True,
                               help_text='List of widget configuration objects')
    layout  = models.JSONField(default=dict, blank=True,
                               help_text='Grid layout (positions & sizes)')
    filters = models.JSONField(default=dict, blank=True,
                               help_text='Global filters applied to all widgets')

    auto_refresh              = models.BooleanField(default=False)
    refresh_interval_minutes  = models.IntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(60)])
    last_refreshed_at         = models.DateTimeField(null=True, blank=True)

    is_public   = models.BooleanField(default=False, db_index=True)
    is_active   = models.BooleanField(default=True,  db_index=True)
    owner       = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='dashboards')
    shared_with = models.ManyToManyField(
    settings.AUTH_USER_MODEL,
    related_name='analytics_shared_dashboards',
    blank=True,
)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        indexes = [
            models.Index(fields=['owner', 'is_active']),
            models.Index(fields=['is_public', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def refresh_data(self):
        """Stamp last_refreshed_at without triggering unrelated signals."""
        type(self).objects.filter(pk=self.pk).update(
            last_refreshed_at=timezone.now())
        self.last_refreshed_at = timezone.now()


# =============================================================================
# DATA EXPORT
# =============================================================================

class DataExport(TimeStampedModel):
    """
    Async data export with multi-format support.

    Status flow: PENDING → PROCESSING → COMPLETED | FAILED → EXPIRED.
    Exports are soft-deleted.  File is cleaned up on hard-delete via signals.
    """

    EXPORT_FORMATS = [
        ('CSV',   'CSV – Comma-Separated Values'),
        ('EXCEL', 'Excel – XLSX'),
        ('JSON',  'JSON – JavaScript Object Notation'),
        ('PDF',   'PDF – Portable Document Format'),
        ('STATA', 'Stata – DTA'),
        ('SPSS',  'SPSS – SAV'),
    ]

    STATUS_CHOICES = [
        ('PENDING',    'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED',  'Completed'),
        ('FAILED',     'Failed'),
        ('EXPIRED',    'Expired'),
    ]

    name          = models.CharField(max_length=200)
    export_format = models.CharField(max_length=20, choices=EXPORT_FORMATS, db_index=True)
    data_type     = models.CharField(max_length=100,
                                     help_text='health_data | locations | …')
    filters       = models.JSONField(default=dict, blank=True)
    start_date    = models.DateField(null=True, blank=True)
    end_date      = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='PENDING', db_index=True)

    file       = models.FileField(upload_to='data_exports/', null=True, blank=True)
    file_size  = models.BigIntegerField(null=True, blank=True, help_text='Bytes')
    row_count  = models.IntegerField(null=True, blank=True)

    processing_started_at   = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_time         = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Seconds')
    error_message = models.TextField(blank=True)

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name='data_exports')
    expires_at   = models.DateTimeField(null=True, blank=True)
    metadata     = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Data Export'
        verbose_name_plural = 'Data Exports'
        indexes = [
            models.Index(fields=['requested_by', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['export_format', 'status']),
        ]

    def __str__(self):
        return f"{self.name} – {self.get_export_format_display()}"

    def is_expired(self):
        """Return True if expires_at has passed."""
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def set_default_expiry(self, days=7):
        """Set expiry to *days* from now and persist."""
        self.expires_at = timezone.now() + timedelta(days=days)
        self.save(update_fields=['expires_at'])


# =============================================================================
# INDICATOR
# =============================================================================

class Indicator(TimeStampedModel):
    """
    Key Performance Indicators (KPIs) with target tracking.

    Indicator types: EPIDEMIOLOGICAL, OPERATIONAL, CAPACITY, QUALITY, OUTCOME.
    Target directions: INCREASE, DECREASE, MAINTAIN.
    Reporting frequencies: DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUAL.
    """

    INDICATOR_TYPES = [
        ('EPIDEMIOLOGICAL', 'Epidemiological'),
        ('OPERATIONAL',     'Operational'),
        ('CAPACITY',        'Capacity'),
        ('QUALITY',         'Quality'),
        ('OUTCOME',         'Outcome'),
    ]

    TARGET_DIRECTIONS = [
        ('INCREASE', 'Increase – Higher is better'),
        ('DECREASE', 'Decrease – Lower is better'),
        ('MAINTAIN', 'Maintain – Keep within range'),
    ]

    REPORTING_FREQUENCIES = [
        ('DAILY',     'Daily'),
        ('WEEKLY',    'Weekly'),
        ('MONTHLY',   'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUAL',    'Annual'),
    ]

    name          = models.CharField(max_length=200)
    code          = models.CharField(max_length=50, unique=True, db_index=True)
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPES, db_index=True)
    description   = models.TextField(blank=True)

    definition          = models.TextField()
    calculation_method  = models.TextField()
    data_source         = models.CharField(max_length=200)

    target_value     = models.DecimalField(max_digits=15, decimal_places=2,
                                           null=True, blank=True)
    target_direction = models.CharField(max_length=20, choices=TARGET_DIRECTIONS,
                                        default='INCREASE')

    unit_of_measure      = models.CharField(max_length=50)
    reporting_frequency  = models.CharField(max_length=20, choices=REPORTING_FREQUENCIES)

    is_active = models.BooleanField(default=True, db_index=True)
    metadata  = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Indicator'
        verbose_name_plural = 'Indicators'
        indexes = [
            models.Index(fields=['indicator_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# =============================================================================
# INDICATOR VALUE
# =============================================================================

class IndicatorValue(TimeStampedModel):
    """
    Time-series measurements of an Indicator for a specific Location and period.

    call calculate_variance() after creation to auto-set target_achieved and
    variance_from_target.
    """

    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE,
                                  related_name='values')
    location  = models.ForeignKey(Location, on_delete=models.CASCADE,
                                  related_name='indicator_values')

    value       = models.DecimalField(max_digits=15, decimal_places=2)
    numerator   = models.DecimalField(max_digits=15, decimal_places=2,
                                      null=True, blank=True,
                                      help_text='Numerator for ratio indicators')
    denominator = models.DecimalField(max_digits=15, decimal_places=2,
                                      null=True, blank=True)

    period_start = models.DateField()
    period_end   = models.DateField()

    target_achieved      = models.BooleanField(null=True, blank=True)
    variance_from_target = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)

    data_quality_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)])

    notes       = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='indicator_values')
    metadata    = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-period_end', 'indicator']
        verbose_name = 'Indicator Value'
        verbose_name_plural = 'Indicator Values'
        indexes = [
            models.Index(fields=['indicator', '-period_end']),
            models.Index(fields=['location', '-period_end']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return f"{self.indicator.name}: {self.value} ({self.period_end})"

    def calculate_variance(self):
        """
        Compute variance_from_target and target_achieved, then persist.

        Achievement logic:
            INCREASE – value >= target
            DECREASE – value <= target
            MAINTAIN – |variance| <= 10 % of target
        """
        if not self.indicator.target_value:
            return

        self.variance_from_target = self.value - self.indicator.target_value
        direction = self.indicator.target_direction

        if direction == 'INCREASE':
            self.target_achieved = self.value >= self.indicator.target_value
        elif direction == 'DECREASE':
            self.target_achieved = self.value <= self.indicator.target_value
        else:  # MAINTAIN
            tolerance = abs(float(self.indicator.target_value) * 0.1)
            self.target_achieved = abs(float(self.variance_from_target)) <= tolerance

        self.save(update_fields=['variance_from_target', 'target_achieved'])


# =============================================================================
# REPORT TEMPLATE
# =============================================================================

class ReportTemplate(TimeStampedModel):
    """
    Templates for automated report generation.

    Template types: WHO_SITREP, IHR, AFRICA_CDC, CUSTOM.
    Output formats: PDF, DOCX, HTML, EXCEL.
    """

    TEMPLATE_TYPES = [
        ('WHO_SITREP', 'WHO Situation Report'),
        ('IHR',        'IHR Report'),
        ('AFRICA_CDC', 'Africa CDC Report'),
        ('CUSTOM',     'Custom Report'),
    ]

    OUTPUT_FORMATS = [
        ('PDF',   'PDF'),
        ('DOCX',  'Word Document'),
        ('HTML',  'HTML'),
        ('EXCEL', 'Excel'),
    ]

    name          = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, db_index=True)
    description   = models.TextField(blank=True)

    sections             = models.JSONField(default=list, blank=True,
                                            help_text='Ordered list of section config objects')
    required_indicators  = models.ManyToManyField(Indicator, related_name='report_templates',
                                                   blank=True)
    required_data_fields = models.JSONField(default=list, blank=True)

    output_format = models.CharField(max_length=20, choices=OUTPUT_FORMATS, default='PDF')
    template_file = models.FileField(upload_to='report_templates/', null=True, blank=True)
    is_active     = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='report_templates')
    metadata   = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"