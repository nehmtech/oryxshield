"""
OryxShield - Analytics Serializers
===========================================

Serializers:
    EpidemiologicalModelSerializer       – full model data
    EpidemiologicalModelListSerializer   – optimised list view
    SpatialAnalysisSerializer            – spatial analysis
    TimeSeriesAnalysisSerializer         – time series
    StatisticalReportSerializer          – full report
    StatisticalReportListSerializer      – optimised list view
    DashboardSerializer                  – dashboard config
    DataExportSerializer                 – export status & files
    IndicatorSerializer                  – KPI definitions
    IndicatorValueSerializer             – KPI measurements
    ReportTemplateSerializer             – report templates
    RunModelSerializer                   – simulation action payload
    ExportDataSerializer                 – export request payload
    AnalyticsDashboardSerializer         – overview payload
"""

from rest_framework import serializers
from decimal import Decimal

from .models import (
    EpidemiologicalModel, SpatialAnalysis, TimeSeriesAnalysis,
    StatisticalReport, Dashboard, DataExport, Indicator,
    IndicatorValue, ReportTemplate,
)


# =============================================================================
# EPIDEMIOLOGICAL MODEL
# =============================================================================

class EpidemiologicalModelSerializer(serializers.ModelSerializer):

    location_name      = serializers.CharField(source='location.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)

    total_population = serializers.SerializerMethodField()
    r0_status        = serializers.SerializerMethodField()

    class Meta:
        model  = EpidemiologicalModel
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'basic_reproduction_number', 'attack_rate',
            'peak_day', 'peak_infections',
            'simulation_completed_at', 'validated_at',
            'model_fit_score', 'rmse',
        ]

    def get_total_population(self, obj):
        return obj.get_total_population()

    def get_r0_status(self, obj):
        if obj.basic_reproduction_number:
            r0 = float(obj.basic_reproduction_number)
            if r0 > 1:
                return 'epidemic'
            if r0 == 1:
                return 'endemic'
            return 'declining'
        return None

    def validate(self, data):
        model_type = data.get('model_type', '')
        parameters = data.get('parameters', {})

        # ── required parameter keys ───────────────────────────────────────────
        required_map = {
            'SIR':  ['beta', 'gamma'],
            'SIRS': ['beta', 'gamma', 'xi'],
            'SIS':  ['beta', 'gamma'],
            'SEIR':  ['beta', 'gamma', 'sigma'],
            'SEIRS': ['beta', 'gamma', 'sigma', 'xi'],
        }
        required = required_map.get(model_type, [])
        missing  = [p for p in required if p not in parameters]
        if missing:
            raise serializers.ValidationError(
                {'parameters': f'{model_type} model requires: {", ".join(missing)}'})

        # ── parameter positivity ──────────────────────────────────────────────
        for key in required:
            val = parameters.get(key)
            if val is not None and val <= 0:
                raise serializers.ValidationError(
                    {'parameters': f'{key} must be positive'})

        # ── initial conditions ────────────────────────────────────────────────
        s = data.get('initial_susceptible', 0)
        i = data.get('initial_infected', 0)
        e = data.get('initial_exposed')

        if i <= 0:
            raise serializers.ValidationError(
                {'initial_infected': 'Must have at least 1 infected individual'})
        if s < i:
            raise serializers.ValidationError(
                {'initial_susceptible': 'Cannot have more infected than susceptible'})
        if model_type in ('SEIR', 'SEIRS') and e is None:
            raise serializers.ValidationError(
                {'initial_exposed': 'SEIR/SEIRS models require initial_exposed'})

        # ── simulation days ───────────────────────────────────────────────────
        sim_days = data.get('simulation_days', 365)
        if not (1 <= sim_days <= 3650):
            raise serializers.ValidationError(
                {'simulation_days': 'Must be 1–3650 days'})

        return data


class EpidemiologicalModelListSerializer(serializers.ModelSerializer):
    location_name      = serializers.CharField(source='location.name', read_only=True)
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)

    class Meta:
        model  = EpidemiologicalModel
        fields = [
            'id', 'name', 'model_type', 'model_type_display',
            'disease_name', 'disease_code', 'location_name',
            'basic_reproduction_number', 'is_validated',
            'simulation_completed_at', 'created_at',
        ]


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

class SpatialAnalysisSerializer(serializers.ModelSerializer):

    location_name          = serializers.CharField(source='location.name', read_only=True)
    performed_by_username  = serializers.CharField(source='performed_by.username', read_only=True)
    analysis_type_display  = serializers.CharField(source='get_analysis_type_display', read_only=True)

    is_significant = serializers.SerializerMethodField()
    duration_days  = serializers.SerializerMethodField()

    class Meta:
        model  = SpatialAnalysis
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'hotspot_count', 'cluster_count',
        ]

    def get_is_significant(self, obj):
        return obj.is_significant()

    def get_duration_days(self, obj):
        return obj.get_duration_days()

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end:
            if end < start:
                raise serializers.ValidationError({'end_date': 'Must be after start_date'})
            if (end - start).days < 7:
                raise serializers.ValidationError(
                    {'date_range': 'Analysis period must be at least 7 days'})
        return data


# =============================================================================
# TIME SERIES ANALYSIS
# =============================================================================

class TimeSeriesAnalysisSerializer(serializers.ModelSerializer):

    location_name          = serializers.CharField(source='location.name', read_only=True)
    performed_by_username  = serializers.CharField(source='performed_by.username', read_only=True)
    analysis_type_display  = serializers.CharField(source='get_analysis_type_display', read_only=True)
    trend_direction_display = serializers.CharField(source='get_trend_direction_display', read_only=True)

    has_forecast     = serializers.SerializerMethodField()
    forecast_horizon = serializers.SerializerMethodField()

    class Meta:
        model  = TimeSeriesAnalysis
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'trend_direction', 'trend_strength',
            'has_seasonality', 'seasonal_period',
            'mae', 'rmse', 'mape',
        ]

    def get_has_forecast(self, obj):
        return bool(obj.forecast_data)

    def get_forecast_horizon(self, obj):
        return obj.forecast_days

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'Must be after start_date'})

        forecast_days = data.get('forecast_days')
        if forecast_days is not None and not (1 <= forecast_days <= 365):
            raise serializers.ValidationError(
                {'forecast_days': 'Must be 1–365 days'})

        return data


# =============================================================================
# STATISTICAL REPORT
# =============================================================================

class StatisticalReportSerializer(serializers.ModelSerializer):

    author_name        = serializers.CharField(source='author.username', read_only=True)
    reviewed_by_name   = serializers.CharField(source='reviewed_by.username', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    location_names     = serializers.SerializerMethodField()

    class Meta:
        model  = StatisticalReport
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'published_at', 'reviewed_at',
        ]

    def get_location_names(self, obj):
        return list(obj.locations.values_list('name', flat=True))

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'Must be after start_date'})
        return data


class StatisticalReportListSerializer(serializers.ModelSerializer):
    author_name        = serializers.CharField(source='author.username', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)

    class Meta:
        model  = StatisticalReport
        fields = [
            'id', 'title', 'report_type', 'report_type_display',
            'start_date', 'end_date', 'is_published',
            'author_name', 'created_at',
        ]


# =============================================================================
# DASHBOARD
# =============================================================================

class DashboardSerializer(serializers.ModelSerializer):

    owner_name            = serializers.CharField(source='owner.username', read_only=True)
    shared_with_usernames = serializers.SerializerMethodField()
    widget_count          = serializers.SerializerMethodField()

    class Meta:
        model  = Dashboard
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'last_refreshed_at',
        ]

    def get_shared_with_usernames(self, obj):
        return list(obj.shared_with.values_list('username', flat=True))

    def get_widget_count(self, obj):
        return len(obj.widgets) if obj.widgets else 0

    def validate_refresh_interval_minutes(self, value):
        if not (1 <= value <= 60):
            raise serializers.ValidationError('Must be 1–60 minutes')
        return value


# =============================================================================
# DATA EXPORT
# =============================================================================

class DataExportSerializer(serializers.ModelSerializer):

    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    export_format_display = serializers.CharField(source='get_export_format_display', read_only=True)
    status_display        = serializers.CharField(source='get_status_display', read_only=True)

    is_expired       = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model  = DataExport
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'status', 'file', 'file_size', 'row_count',
            'processing_started_at', 'processing_completed_at',
            'processing_time', 'error_message',
        ]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_file_size_display(self, obj):
        if not obj.file_size:
            return None
        size = float(obj.file_size)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'Must be after start_date'})
        return data


# =============================================================================
# INDICATOR
# =============================================================================

class IndicatorSerializer(serializers.ModelSerializer):

    indicator_type_display      = serializers.CharField(source='get_indicator_type_display', read_only=True)
    target_direction_display    = serializers.CharField(source='get_target_direction_display', read_only=True)
    reporting_frequency_display = serializers.CharField(source='get_reporting_frequency_display', read_only=True)
    value_count                 = serializers.SerializerMethodField()

    class Meta:
        model  = Indicator
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

    def get_value_count(self, obj):
        return obj.values.filter(is_deleted=False).count()

    def validate_code(self, value):
        return value.upper()

    def validate_target_value(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Target value cannot be negative')
        return value


# =============================================================================
# INDICATOR VALUE
# =============================================================================

class IndicatorValueSerializer(serializers.ModelSerializer):

    indicator_name     = serializers.CharField(source='indicator.name', read_only=True)
    indicator_code     = serializers.CharField(source='indicator.code', read_only=True)
    location_name      = serializers.CharField(source='location.name',  read_only=True)
    recorded_by_username = serializers.CharField(source='recorded_by.username', read_only=True)

    class Meta:
        model  = IndicatorValue
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_deleted',
            'target_achieved', 'variance_from_target',
        ]

    def validate(self, data):
        start = data.get('period_start')
        end   = data.get('period_end')
        if start and end and end < start:
            raise serializers.ValidationError({'period_end': 'Must be after period_start'})

        denominator = data.get('denominator')
        if denominator is not None and denominator == 0:
            raise serializers.ValidationError({'denominator': 'Cannot be zero'})

        quality = data.get('data_quality_score')
        if quality is not None and not (0 <= quality <= 100):
            raise serializers.ValidationError({'data_quality_score': 'Must be 0–100'})

        return data


# =============================================================================
# REPORT TEMPLATE
# =============================================================================

class ReportTemplateSerializer(serializers.ModelSerializer):

    created_by_username     = serializers.CharField(source='created_by.username', read_only=True)
    template_type_display   = serializers.CharField(source='get_template_type_display', read_only=True)
    output_format_display   = serializers.CharField(source='get_output_format_display', read_only=True)
    required_indicator_names = serializers.SerializerMethodField()

    class Meta:
        model  = ReportTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

    def get_required_indicator_names(self, obj):
        return list(obj.required_indicators.values_list('name', flat=True))


# =============================================================================
# ACTION SERIALIZERS
# =============================================================================

class RunModelSerializer(serializers.Serializer):
    """Payload for EpidemiologicalModelViewSet.run_simulation."""

    simulation_days = serializers.IntegerField(
        default=365, min_value=1, max_value=3650)
    parameters = serializers.DictField(required=False)

    def validate_parameters(self, value):
        if value:
            for key, val in value.items():
                if not isinstance(val, (int, float)):
                    raise serializers.ValidationError(
                        f"Parameter '{key}' must be numeric")
                if val < 0:
                    raise serializers.ValidationError(
                        f"Parameter '{key}' cannot be negative")
        return value


class ExportDataSerializer(serializers.Serializer):
    """Payload for DataExportViewSet.request_export."""

    data_type     = serializers.CharField()
    export_format = serializers.ChoiceField(choices=DataExport.EXPORT_FORMATS)
    filters       = serializers.DictField(required=False, default=dict)
    start_date    = serializers.DateField(required=False)
    end_date      = serializers.DateField(required=False)

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'Must be after start_date'})
        return data


class AnalyticsDashboardSerializer(serializers.Serializer):
    """Payload for AnalyticsDashboardViewSet.overview."""

    total_analyses  = serializers.IntegerField()
    total_models    = serializers.IntegerField()
    total_reports   = serializers.IntegerField()
    total_exports   = serializers.IntegerField()
    active_dashboards = serializers.IntegerField()
    recent_models   = serializers.ListField()
    recent_exports  = serializers.ListField()
    key_indicators  = serializers.ListField()