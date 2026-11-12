"""
OryxShield - Analytics Views
=====================================

10 ViewSets covering all analytics models with filtering, pagination,
permission enforcement, custom @action endpoints, and structured logging.

All list endpoints respect is_deleted=False through the base queryset.
Custom actions queue Celery tasks and return 202 Accepted.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
import io
import json
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

from .models import (
    EpidemiologicalModel, SpatialAnalysis, TimeSeriesAnalysis,
    StatisticalReport, Dashboard, DataExport, Indicator,
    IndicatorValue, ReportTemplate,
)
from .serializers import (
    EpidemiologicalModelSerializer, EpidemiologicalModelListSerializer,
    SpatialAnalysisSerializer, TimeSeriesAnalysisSerializer,
    StatisticalReportSerializer, StatisticalReportListSerializer,
    DashboardSerializer, DataExportSerializer,
    IndicatorSerializer, IndicatorValueSerializer,
    ReportTemplateSerializer,
    RunModelSerializer, ExportDataSerializer, AnalyticsDashboardSerializer,
)
from core.pagination import CustomPagination

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# EPIDEMIOLOGICAL MODEL
# =============================================================================

class EpidemiologicalModelViewSet(viewsets.ModelViewSet):
    """
    CRUD + simulation execution for epidemiological disease-spread models.

    Custom actions:
        POST /{id}/run_simulation/ – queue a Celery simulation task.
    """

    queryset = EpidemiologicalModel.objects.filter(is_deleted=False).select_related(
        'location', 'created_by')
    permission_classes  = [IsAuthenticated]
    filter_backends     = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields    = ['model_type', 'disease_code', 'location', 'is_validated']
    search_fields       = ['name', 'disease_name', 'disease_code']
    ordering_fields     = ['created_at', 'name', 'basic_reproduction_number']
    ordering            = ['-created_at']
    pagination_class    = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return EpidemiologicalModelListSerializer
        return EpidemiologicalModelSerializer

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        logger.info(
            "User %s created epi model '%s' (id=%s)",
            self.request.user.username, obj.name, obj.id)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
        logger.info("Soft-deleted epi model id=%s", instance.id)

    @action(detail=True, methods=['post'])
    def run_simulation(self, request, pk=None):
        """
        POST /api/v1/analytics/epi-models/{id}/run_simulation/

        Body:  { "simulation_days": 365, "parameters": {"beta": 0.3, "gamma": 0.1} }
        Returns: { "status", "task_id", "model_id", "simulation_days" }
        """
        model = self.get_object()
        serializer = RunModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        days   = serializer.validated_data.get('simulation_days', model.simulation_days)
        params = serializer.validated_data.get('parameters', model.parameters)

        try:
            from .tasks import run_epi_model_simulation
            task = run_epi_model_simulation.delay(str(model.id), days, params)
            logger.info("Queued simulation for model %s (task=%s, days=%d)",
                        model.id, task.id, days)
            return Response({
                'status': 'Simulation started',
                'task_id': task.id,
                'model_id': str(model.id),
                'simulation_days': days,
            }, status=status.HTTP_202_ACCEPTED)

        except ImportError:
            return Response({'error': 'Background task processing not available'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.error("Error queuing simulation for model %s: %s", model.id, exc,
                         exc_info=True)
            return Response({'error': str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

class SpatialAnalysisViewSet(viewsets.ModelViewSet):
    """CRUD for spatial statistical analyses (hotspot, clustering, Moran's I)."""

    queryset = SpatialAnalysis.objects.filter(is_deleted=False).select_related(
        'location', 'performed_by')
    serializer_class   = SpatialAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['analysis_type', 'disease_code', 'location']
    search_fields      = ['name', 'disease_name']
    ordering_fields    = ['created_at', 'start_date', 'end_date']
    ordering           = ['-created_at']
    pagination_class   = CustomPagination

    def perform_create(self, serializer):
        obj = serializer.save(performed_by=self.request.user)
        logger.info("User %s created spatial analysis '%s' (id=%s)",
                    self.request.user.username, obj.name, obj.id)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])


# =============================================================================
# TIME SERIES ANALYSIS
# =============================================================================

class TimeSeriesAnalysisViewSet(viewsets.ModelViewSet):
    """CRUD for time-series trend, seasonality, and forecasting analyses."""

    queryset = TimeSeriesAnalysis.objects.filter(is_deleted=False).select_related(
        'location', 'performed_by')
    serializer_class   = TimeSeriesAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['analysis_type', 'disease_code', 'location', 'has_seasonality']
    search_fields      = ['name', 'disease_name']
    ordering_fields    = ['created_at', 'start_date', 'end_date']
    ordering           = ['-created_at']
    pagination_class   = CustomPagination

    def perform_create(self, serializer):
        obj = serializer.save(performed_by=self.request.user)
        logger.info("User %s created time-series analysis '%s' (id=%s)",
                    self.request.user.username, obj.name, obj.id)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])


# =============================================================================
# STATISTICAL REPORT
# =============================================================================

class StatisticalReportViewSet(viewsets.ModelViewSet):
    """
    CRUD for statistical reports with publication workflow.

    Custom actions:
        GET /published/ – list only published reports.
    """

    queryset = StatisticalReport.objects.filter(is_deleted=False).select_related(
        'author', 'reviewed_by').prefetch_related('locations')
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['report_type', 'is_published']
    search_fields      = ['title']
    ordering_fields    = ['created_at', 'start_date', 'published_at']
    ordering           = ['-created_at']
    pagination_class   = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return StatisticalReportListSerializer
        return StatisticalReportSerializer

    def perform_create(self, serializer):
        obj = serializer.save(author=self.request.user)
        logger.info("User %s created statistical report '%s' (id=%s)",
                    self.request.user.username, obj.title, obj.id)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=False, methods=['get'])
    def published(self, request):
        """GET /api/v1/analytics/reports/published/ – paginated published reports."""
        qs   = self.filter_queryset(self.get_queryset().filter(is_published=True))
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Serve the uploaded report file, or generate a PDF from report data."""
        report = self.get_object()
        if report.report_file:
            return FileResponse(
                report.report_file.open('rb'),
                as_attachment=True,
                filename=report.report_file.name.split('/')[-1],
            )
        return _generate_report_pdf(report)


def _generate_report_pdf(report):
    """Build a styled PDF for a StatisticalReport using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from xml.sax.saxutils import escape as _esc

    def _p(text):
        """Escape XML entities so ReportLab's XML parser never chokes."""
        return _esc(str(text or '').strip())

    # ── Colour palette (matches OryxShield dark theme) ───────────────────────
    NAVY    = colors.HexColor('#0a0f1e')
    BLUE    = colors.HexColor('#3b82f6')
    LIGHT   = colors.HexColor('#f9fafb')
    MUTED   = colors.HexColor('#6b7280')
    BORDER  = colors.HexColor('#1f2937')
    SUCCESS = colors.HexColor('#10b981')
    DANGER  = colors.HexColor('#ef4444')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=report.title,
        author=report.author.get_full_name() if report.author else 'OryxShield',
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    S = {
        'report_type': style('rt',
            fontName='Helvetica-Bold', fontSize=8, textColor=BLUE,
            spaceAfter=2, letterSpacing=1.5, alignment=TA_LEFT),
        'title': style('title',
            fontName='Helvetica-Bold', fontSize=22, textColor=NAVY,
            spaceAfter=6, leading=26),
        'meta':  style('meta',
            fontName='Helvetica', fontSize=9, textColor=MUTED,
            spaceAfter=2),
        'section': style('section',
            fontName='Helvetica-Bold', fontSize=12, textColor=NAVY,
            spaceBefore=14, spaceAfter=6),
        'body': style('body',
            fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#111827'),
            leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        'bullet': style('bullet',
            fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#111827'),
            leading=14, spaceAfter=3, leftIndent=14, bulletIndent=0),
        'footer': style('footer',
            fontName='Helvetica', fontSize=8, textColor=MUTED,
            alignment=TA_CENTER),
        'kv_key': style('kv_key',
            fontName='Helvetica-Bold', fontSize=9, textColor=MUTED),
        'kv_val': style('kv_val',
            fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#111827')),
    }

    story = []

    # ── Report type badge ────────────────────────────────────────────────────
    story.append(Paragraph(_p(report.get_report_type_display().upper()), S['report_type']))
    story.append(Spacer(1, 4))

    # ── Title ────────────────────────────────────────────────────────────────
    story.append(Paragraph(_p(report.title), S['title']))

    # ── Meta row ─────────────────────────────────────────────────────────────
    author_name  = report.author.get_full_name() if report.author else '—'
    date_range   = f"{report.start_date} → {report.end_date}"
    pub_status   = 'Published' if report.is_published else 'Draft'
    meta_rows = [
        [_p('Author'), _p(author_name), _p('Period'), _p(date_range)],
        [_p('Status'), _p(pub_status),  _p('Generated'), _p(timezone.now().strftime('%d %b %Y %H:%M'))],
    ]
    meta_table = Table(meta_rows, colWidths=[3*cm, 6*cm, 2.5*cm, 5*cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',  (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), MUTED),
        ('TEXTCOLOR', (2, 0), (2, -1), MUTED),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#111827')),
        ('TEXTCOLOR', (3, 0), (3, -1), colors.HexColor('#111827')),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=1, color=BLUE, spaceAfter=10))

    # ── Description ──────────────────────────────────────────────────────────
    if report.description:
        story.append(Paragraph('Description', S['section']))
        story.append(Paragraph(_p(report.description), S['body']))

    # ── Executive Summary ─────────────────────────────────────────────────────
    if report.executive_summary:
        story.append(Paragraph('Executive Summary', S['section']))
        for para in report.executive_summary.split('\n\n'):
            if para.strip():
                story.append(Paragraph(_p(para), S['body']))

    # ── Key Findings ─────────────────────────────────────────────────────────
    findings = report.key_findings or []
    if findings:
        story.append(Paragraph('Key Findings', S['section']))
        for item in findings:
            text = item if isinstance(item, str) else json.dumps(item, default=str)
            story.append(Paragraph(f'• {_p(text)}', S['bullet']))

    # ── Results ───────────────────────────────────────────────────────────────
    results = report.results or {}
    if results:
        story.append(Paragraph('Results', S['section']))
        for key, val in results.items():
            label = key.replace('_', ' ').title()
            value = val if isinstance(val, str) else json.dumps(val, default=str)
            row_data = [[Paragraph(_p(label), S['kv_key']), Paragraph(_p(value), S['kv_val'])]]
            t = Table(row_data, colWidths=[5*cm, 11.3*cm])
            t.setStyle(TableStyle([
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('LINEBELOW',     (0, 0), (-1, -1), 0.25, BORDER),
            ]))
            story.append(t)
        story.append(Spacer(1, 6))

    # ── Tables ────────────────────────────────────────────────────────────────
    tables = report.tables or []
    for idx, tbl in enumerate(tables, 1):
        if not isinstance(tbl, dict):
            continue
        heading = tbl.get('title') or tbl.get('name') or f'Table {idx}'
        rows    = tbl.get('rows') or tbl.get('data') or []
        headers = tbl.get('headers') or tbl.get('columns') or []
        if not rows:
            continue
        story.append(KeepTogether([
            Paragraph(_p(heading), S['section']),
        ]))
        tbl_data = []
        if headers:
            tbl_data.append([Paragraph(_p(h), S['kv_key']) for h in headers])
        for row in rows:
            if isinstance(row, (list, tuple)):
                tbl_data.append([Paragraph(_p(c), S['kv_val']) for c in row])
            elif isinstance(row, dict):
                tbl_data.append([Paragraph(_p(v), S['kv_val']) for v in row.values()])
        if tbl_data:
            col_count = max(len(r) for r in tbl_data)
            col_w = 16.6*cm / max(col_count, 1)
            t = Table(tbl_data, colWidths=[col_w]*col_count, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (-1, 0), BLUE),
                ('TEXTCOLOR',     (0, 0), (-1, 0), LIGHT),
                ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1, -1), 9),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                ('GRID',          (0, 0), (-1, -1), 0.4, BORDER),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    # ── Footer rule ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'OryxShield — AI Health Surveillance System · NEHMTECH INNOVATIONS LIMITED',
        S['footer'],
    ))

    doc.build(story)
    buf.seek(0)

    safe_title = report.title.replace(' ', '_').replace('/', '-')[:80]
    filename   = f"{safe_title}.pdf"
    response   = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# =============================================================================
# DASHBOARD
# =============================================================================

class DashboardViewSet(viewsets.ModelViewSet):
    """
    CRUD for custom analytics dashboards.

    Queryset is scoped to dashboards that the requesting user owns,
    is shared on, or that are public.
    """

    queryset = Dashboard.objects.filter(is_deleted=False, is_active=True).select_related(
        'owner').prefetch_related('shared_with')
    serializer_class   = DashboardSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['is_public', 'is_active', 'auto_refresh']
    search_fields      = ['name', 'description']
    ordering_fields    = ['created_at', 'name', 'last_refreshed_at']
    ordering           = ['name']
    pagination_class   = CustomPagination

    def get_queryset(self):
        return self.queryset.filter(
            Q(owner=self.request.user) |
            Q(shared_with=self.request.user) |
            Q(is_public=True)
        ).distinct()

    def perform_create(self, serializer):
        obj = serializer.save(owner=self.request.user)
        logger.info("User %s created dashboard '%s' (id=%s)",
                    self.request.user.username, obj.name, obj.id)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])


# =============================================================================
# DATA EXPORT
# =============================================================================

class DataExportViewSet(viewsets.ModelViewSet):
    """
    CRUD + async export requests for multi-format data exports.

    Queryset is scoped to the requesting user's exports.

    Custom actions:
        POST /request_export/ – create an export record and queue processing.
    """

    queryset = DataExport.objects.filter(is_deleted=False).select_related('requested_by')
    serializer_class   = DataExportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'export_format']
    ordering_fields    = ['created_at', 'status']
    ordering           = ['-created_at']
    pagination_class   = CustomPagination

    def get_queryset(self):
        return self.queryset.filter(requested_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=False, methods=['post'])
    def request_export(self, request):
        """
        POST /api/v1/analytics/exports/request_export/

        Body:   { "data_type", "export_format", "filters", "start_date", "end_date" }
        Returns: { "export_id", "status", "task_id" }
        """
        serializer = ExportDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        export = DataExport.objects.create(
            name=f"Export {timezone.now().strftime('%Y%m%d_%H%M%S')}",
            export_format=vd['export_format'],
            data_type=vd['data_type'],
            filters=vd.get('filters', {}),
            start_date=vd.get('start_date'),
            end_date=vd.get('end_date'),
            requested_by=request.user,
            status='PENDING',
        )
        export.set_default_expiry(days=7)

        try:
            from .tasks import process_data_export
            task = process_data_export.delay(str(export.id))
            logger.info("User %s queued export %s (format=%s, task=%s)",
                        request.user.username, export.id, export.export_format, task.id)
            return Response({
                'export_id': str(export.id),
                'status': 'Export queued',
                'task_id': task.id,
            }, status=status.HTTP_202_ACCEPTED)

        except ImportError:
            export.status = 'FAILED'
            export.error_message = 'Background task processing not available'
            export.save(update_fields=['status', 'error_message'])
            return Response({'error': 'Background task processing not available'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as exc:
            export.status = 'FAILED'
            export.error_message = str(exc)
            export.save(update_fields=['status', 'error_message'])
            logger.error("Error queuing export %s: %s", export.id, exc, exc_info=True)
            return Response({'error': str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# INDICATOR
# =============================================================================

class IndicatorViewSet(viewsets.ModelViewSet):
    """CRUD for KPI indicator definitions."""

    queryset = Indicator.objects.filter(is_deleted=False)
    serializer_class   = IndicatorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['indicator_type', 'is_active', 'reporting_frequency']
    search_fields      = ['name', 'code', 'definition']
    ordering_fields    = ['name', 'code', 'created_at']
    ordering           = ['name']
    pagination_class   = CustomPagination

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])


# =============================================================================
# INDICATOR VALUE
# =============================================================================

class IndicatorValueViewSet(viewsets.ModelViewSet):
    """CRUD for time-series KPI measurements."""

    queryset = IndicatorValue.objects.filter(is_deleted=False).select_related(
        'indicator', 'location', 'recorded_by')
    serializer_class   = IndicatorValueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['indicator', 'location', 'target_achieved']
    ordering_fields    = ['period_end', 'created_at']
    ordering           = ['-period_end']
    pagination_class   = CustomPagination

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])


# =============================================================================
# REPORT TEMPLATE
# =============================================================================

class ReportTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for report templates.

    Custom actions:
        POST /{id}/generate/ – queue report generation from template.
    """

    queryset = ReportTemplate.objects.filter(is_deleted=False).select_related(
        'created_by').prefetch_related('required_indicators')
    serializer_class   = ReportTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['template_type', 'is_active', 'output_format']
    search_fields      = ['name']
    ordering_fields    = ['name', 'created_at']
    ordering           = ['name']
    pagination_class   = CustomPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """
        POST /api/v1/analytics/templates/{id}/generate/

        Synchronously creates a StatisticalReport from the template and returns
        the new report's id so the client can navigate or download immediately.

        Returns: { "status", "report_id", "template_id", "title" }
        """
        from .models import StatisticalReport
        from django.utils import timezone as tz

        template = self.get_object()

        try:
            today = tz.now().date()
            title = f"{template.name} — {today.strftime('%d %b %Y')}"

            report = StatisticalReport.objects.create(
                title=title,
                report_type=template.template_type if hasattr(template, 'template_type') else 'DESCRIPTIVE',
                description=template.description if hasattr(template, 'description') else '',
                start_date=today.replace(day=1),
                end_date=today,
                executive_summary=(
                    f"Report generated from template '{template.name}' "
                    f"on {today.strftime('%d %B %Y')} by {request.user.get_full_name() or request.user.username}."
                ),
                key_findings=[
                    f"Generated from template: {template.name}",
                    f"Template type: {template.template_type}",
                    f"Output format: {template.output_format}",
                ],
                results={},
                tables=[],
                charts=[],
                is_published=False,
                author=request.user,
            )

            logger.info("User %s generated report '%s' (id=%s) from template %s",
                        request.user.username, report.title, report.id, template.id)

            return Response({
                'status':      'Report generated',
                'report_id':   str(report.id),
                'template_id': str(template.id),
                'title':       report.title,
            }, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.error("Error generating report from template %s: %s",
                         template.id, exc, exc_info=True)
            return Response({'error': str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# ANALYTICS OVERVIEW (non-model ViewSet)
# =============================================================================

class AnalyticsDashboardViewSet(viewsets.ViewSet):
    """
    Non-model ViewSet for aggregate analytics dashboard data.

    Custom actions:
        GET /overview/ – return summary counts and recent items.
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        GET /api/v1/analytics/overview/overview/

        Returns cached aggregate counts + recent items + key indicators.
        Cache TTL: 5 minutes per user.
        """
        cache_key  = f'analytics:overview:user:{request.user.id}'
        cached     = cache.get(cache_key)
        if cached:
            return Response(cached)

        total_analyses = (
            SpatialAnalysis.objects.filter(is_deleted=False).count() +
            TimeSeriesAnalysis.objects.filter(is_deleted=False).count()
        )
        total_models  = EpidemiologicalModel.objects.filter(is_deleted=False).count()
        total_reports = StatisticalReport.objects.filter(is_deleted=False).count()
        total_exports = DataExport.objects.filter(
            is_deleted=False, requested_by=request.user).count()

        active_dashboards = Dashboard.objects.filter(
            is_deleted=False, is_active=True
        ).filter(
            Q(owner=request.user) |
            Q(shared_with=request.user) |
            Q(is_public=True)
        ).distinct().count()

        recent_models = list(
            EpidemiologicalModel.objects.filter(is_deleted=False)
            .order_by('-created_at')[:5]
            .values('id', 'name', 'model_type', 'disease_name', 'created_at')
        )
        recent_exports = list(
            DataExport.objects.filter(is_deleted=False, requested_by=request.user)
            .order_by('-created_at')[:5]
            .values('id', 'name', 'status', 'export_format', 'created_at')
        )
        key_indicators = list(
            Indicator.objects.filter(is_deleted=False, is_active=True)
            .order_by('name')[:10]
            .values('id', 'name', 'code', 'indicator_type')
        )

        data = {
            'total_analyses':   total_analyses,
            'total_models':     total_models,
            'total_reports':    total_reports,
            'total_exports':    total_exports,
            'active_dashboards': active_dashboards,
            'recent_models':    recent_models,
            'recent_exports':   recent_exports,
            'key_indicators':   key_indicators,
        }

        serializer = AnalyticsDashboardSerializer(data)
        cache.set(cache_key, serializer.data, 300)
        return Response(serializer.data)