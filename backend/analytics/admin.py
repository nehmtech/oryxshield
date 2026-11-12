"""
OryxShield - Analytics Admin Configuration
===================================================

Enhanced admin interfaces for all 9 analytics models with:
- Custom list_display + computed colour-coded badges
- Advanced search, filter, and ordering
- Logical fieldset groupings
- Bulk actions (validate models, publish reports, expire exports)
- Inline IndicatorValue listing on Indicator detail
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count

from .models import (
    EpidemiologicalModel, SpatialAnalysis, TimeSeriesAnalysis,
    StatisticalReport, Dashboard, DataExport, Indicator,
    IndicatorValue, ReportTemplate,
)


# =============================================================================
# EPIDEMIOLOGICAL MODEL
# =============================================================================

@admin.register(EpidemiologicalModel)
class EpidemiologicalModelAdmin(admin.ModelAdmin):
    list_display    = ['name', 'model_type', 'disease_name', 'location',
                       'r0_badge', 'is_validated', 'simulation_status', 'created_at']
    list_filter     = ['model_type', 'is_validated',
                       ('created_at', admin.DateFieldListFilter)]
    search_fields   = ['name', 'disease_name', 'disease_code', 'location__name',
                       'created_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at',
                       'basic_reproduction_number', 'attack_rate',
                       'peak_day', 'peak_infections',
                       'simulation_completed_at', 'validated_at']
    ordering        = ['-created_at']

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'name', 'model_type', 'description'),
        }),
        ('Disease Scope', {
            'fields': ('disease_code', 'disease_name', 'location'),
        }),
        ('Initial Conditions', {
            'fields': ('initial_susceptible', 'initial_infected',
                       'initial_recovered', 'initial_exposed'),
        }),
        ('Parameters & Simulation', {
            'fields': ('parameters', 'simulation_days'),
        }),
        ('Computed Metrics', {
            'classes': ('collapse',),
            'fields': ('basic_reproduction_number', 'attack_rate',
                       'peak_day', 'peak_infections'),
        }),
        ('Validation', {
            'classes': ('collapse',),
            'fields': ('is_validated', 'validated_at', 'model_fit_score', 'rmse'),
        }),
        ('Simulation Results', {
            'classes': ('collapse',),
            'fields': ('simulation_results', 'simulation_completed_at'),
        }),
        ('Audit', {
            'classes': ('collapse',),
            'fields': ('created_by', 'created_at', 'updated_at', 'is_deleted', 'metadata'),
        }),
    )

    actions = ['mark_validated']

    @admin.display(description='R0', ordering='basic_reproduction_number')
    def r0_badge(self, obj):
        if obj.basic_reproduction_number is None:
            return '—'
        r0 = float(obj.basic_reproduction_number)
        colour = '#e74c3c' if r0 > 1 else '#27ae60'
        return format_html('<span style="color:{};font-weight:bold">{:.2f}</span>', colour, r0)

    @admin.display(description='Simulation')
    def simulation_status(self, obj):
        if obj.simulation_completed_at:
            return format_html('<span style="color:#27ae60">✓ Complete</span>')
        return format_html('<span style="color:#e67e22">Pending</span>')

    @admin.action(description='Mark selected models as validated')
    def mark_validated(self, request, queryset):
        updated = queryset.update(is_validated=True, validated_at=timezone.now())
        self.message_user(request, f"{updated} model(s) marked as validated.")


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

@admin.register(SpatialAnalysis)
class SpatialAnalysisAdmin(admin.ModelAdmin):
    list_display    = ['name', 'analysis_type', 'disease_code', 'location',
                       'hotspot_count', 'significance_badge', 'created_at']
    list_filter     = ['analysis_type', ('created_at', admin.DateFieldListFilter)]
    search_fields   = ['name', 'disease_name', 'disease_code', 'location__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'hotspot_count', 'cluster_count',
                       'morans_i', 'p_value', 'z_score']
    ordering        = ['-created_at']

    fieldsets = (
        ('Identification', {'fields': ('id', 'name', 'analysis_type', 'description')}),
        ('Scope', {'fields': ('disease_code', 'disease_name', 'location',
                              'start_date', 'end_date')}),
        ('Statistics', {'classes': ('collapse',),
                        'fields': ('morans_i', 'p_value', 'z_score')}),
        ('Results', {'classes': ('collapse',),
                     'fields': ('results', 'hotspots', 'hotspot_count',
                                'clusters', 'cluster_count', 'map_data')}),
        ('Audit', {'classes': ('collapse',),
                   'fields': ('performed_by', 'parameters', 'metadata',
                              'created_at', 'updated_at', 'is_deleted')}),
    )

    @admin.display(description='Significant')
    def significance_badge(self, obj):
        if obj.p_value is None:
            return '—'
        colour = '#27ae60' if obj.is_significant() else '#95a5a6'
        label  = 'Yes' if obj.is_significant() else 'No'
        return format_html('<span style="color:{}">{}</span>', colour, label)


# =============================================================================
# TIME SERIES ANALYSIS
# =============================================================================

@admin.register(TimeSeriesAnalysis)
class TimeSeriesAnalysisAdmin(admin.ModelAdmin):
    list_display  = ['name', 'analysis_type', 'disease_code', 'location',
                     'trend_direction', 'has_seasonality', 'forecast_badge', 'created_at']
    list_filter   = ['analysis_type', 'trend_direction', 'has_seasonality',
                     ('created_at', admin.DateFieldListFilter)]
    search_fields = ['name', 'disease_name', 'location__name']
    readonly_fields = ['id', 'created_at', 'updated_at',
                       'trend_direction', 'trend_strength',
                       'has_seasonality', 'seasonal_period',
                       'mae', 'rmse', 'mape']
    ordering      = ['-created_at']

    @admin.display(description='Forecast')
    def forecast_badge(self, obj):
        if obj.forecast_data:
            return format_html('<span style="color:#27ae60">✓ {} days</span>',
                               obj.forecast_days or '?')
        return '—'


# =============================================================================
# STATISTICAL REPORT
# =============================================================================

@admin.register(StatisticalReport)
class StatisticalReportAdmin(admin.ModelAdmin):
    list_display  = ['title', 'report_type', 'author', 'published_badge',
                     'start_date', 'end_date', 'created_at']
    list_filter   = ['report_type', 'is_published',
                     ('created_at', admin.DateFieldListFilter)]
    search_fields = ['title', 'author__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'published_at', 'reviewed_at']
    ordering      = ['-created_at']
    actions       = ['publish_reports']

    fieldsets = (
        ('Identification', {'fields': ('id', 'title', 'report_type', 'description')}),
        ('Scope', {'fields': ('disease_codes', 'locations', 'start_date', 'end_date')}),
        ('Content', {'fields': ('executive_summary', 'key_findings',
                                'results', 'tables', 'charts', 'report_file')}),
        ('Publication', {'fields': ('is_published', 'published_at',
                                    'author', 'reviewed_by', 'reviewed_at')}),
        ('Audit', {'classes': ('collapse',),
                   'fields': ('created_at', 'updated_at', 'is_deleted', 'metadata')}),
    )

    @admin.display(description='Published', boolean=False)
    def published_badge(self, obj):
        if obj.is_published:
            return format_html('<span style="color:#27ae60;font-weight:bold">Published</span>')
        return format_html('<span style="color:#95a5a6">Draft</span>')

    @admin.action(description='Publish selected reports')
    def publish_reports(self, request, queryset):
        for report in queryset.filter(is_published=False):
            report.publish(user=request.user)
        self.message_user(request, f"{queryset.count()} report(s) published.")


# =============================================================================
# DASHBOARD
# =============================================================================

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display  = ['name', 'owner', 'is_public', 'is_active', 'auto_refresh',
                     'widget_count', 'last_refreshed_at', 'created_at']
    list_filter   = ['is_public', 'is_active', 'auto_refresh']
    search_fields = ['name', 'owner__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_refreshed_at']
    ordering      = ['name']

    @admin.display(description='Widgets')
    def widget_count(self, obj):
        return len(obj.widgets) if obj.widgets else 0


# =============================================================================
# DATA EXPORT
# =============================================================================

@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display  = ['name', 'requested_by', 'export_format', 'status_badge',
                     'row_count', 'file_size_display', 'created_at']
    list_filter   = ['status', 'export_format',
                     ('created_at', admin.DateFieldListFilter)]
    search_fields = ['name', 'requested_by__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'status',
                       'file', 'file_size', 'row_count',
                       'processing_started_at', 'processing_completed_at',
                       'processing_time', 'error_message']
    ordering      = ['-created_at']
    actions       = ['mark_expired']

    STATUS_COLOURS = {
        'PENDING':    '#e67e22',
        'PROCESSING': '#3498db',
        'COMPLETED':  '#27ae60',
        'FAILED':     '#e74c3c',
        'EXPIRED':    '#95a5a6',
    }

    @admin.display(description='Status')
    def status_badge(self, obj):
        colour = self.STATUS_COLOURS.get(obj.status, '#333')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colour, obj.get_status_display())

    @admin.display(description='File Size')
    def file_size_display(self, obj):
        if not obj.file_size:
            return '—'
        size = float(obj.file_size)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @admin.action(description='Mark selected exports as Expired')
    def mark_expired(self, request, queryset):
        updated = queryset.update(status='EXPIRED')
        self.message_user(request, f"{updated} export(s) marked as expired.")


# =============================================================================
# INDICATOR + INLINE VALUE
# =============================================================================

class IndicatorValueInline(admin.TabularInline):
    model          = IndicatorValue
    extra          = 0
    max_num        = 10
    fields         = ['location', 'value', 'period_start', 'period_end',
                      'target_achieved', 'data_quality_score']
    readonly_fields = ['target_achieved', 'variance_from_target']
    ordering       = ['-period_end']


@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display  = ['name', 'code', 'indicator_type', 'unit_of_measure',
                     'target_value', 'target_direction', 'is_active', 'value_count']
    list_filter   = ['indicator_type', 'is_active', 'reporting_frequency', 'target_direction']
    search_fields = ['name', 'code', 'definition']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering      = ['name']
    inlines       = [IndicatorValueInline]

    fieldsets = (
        ('Identification', {'fields': ('id', 'name', 'code', 'indicator_type', 'description')}),
        ('Definition', {'fields': ('definition', 'calculation_method', 'data_source')}),
        ('Target', {'fields': ('target_value', 'target_direction', 'unit_of_measure')}),
        ('Configuration', {'fields': ('reporting_frequency', 'is_active')}),
        ('Audit', {'classes': ('collapse',),
                   'fields': ('created_at', 'updated_at', 'is_deleted', 'metadata')}),
    )

    @admin.display(description='# Values')
    def value_count(self, obj):
        return obj.values.filter(is_deleted=False).count()


@admin.register(IndicatorValue)
class IndicatorValueAdmin(admin.ModelAdmin):
    list_display  = ['indicator', 'location', 'value', 'period_end',
                     'target_achieved', 'data_quality_score', 'recorded_by']
    list_filter   = ['target_achieved',
                     ('period_end', admin.DateFieldListFilter)]
    search_fields = ['indicator__name', 'indicator__code', 'location__name']
    readonly_fields = ['id', 'created_at', 'updated_at',
                       'target_achieved', 'variance_from_target']
    ordering      = ['-period_end']


# =============================================================================
# REPORT TEMPLATE
# =============================================================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display  = ['name', 'template_type', 'output_format', 'is_active',
                     'required_indicator_count', 'created_at']
    list_filter   = ['template_type', 'is_active', 'output_format']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering      = ['name']

    fieldsets = (
        ('Identification', {'fields': ('id', 'name', 'template_type', 'description')}),
        ('Structure', {'fields': ('sections', 'required_indicators',
                                  'required_data_fields')}),
        ('Output', {'fields': ('output_format', 'template_file', 'is_active')}),
        ('Audit', {'classes': ('collapse',),
                   'fields': ('created_by', 'created_at', 'updated_at', 'is_deleted', 'metadata')}),
    )

    @admin.display(description='Required Indicators')
    def required_indicator_count(self, obj):
        return obj.required_indicators.count()