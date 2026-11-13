"""
Views for the surveillance app.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.utils import timezone
from datetime import timedelta

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsAdminOrReadOnly
from core.pagination import CustomPagination, TimeBasedPagination

from .models import (
    DataSource, HealthData, AnomalyDetection, CaseCluster,
    Hotspot, SurveillanceReport, DiseaseProfile, DataQualityCheck,
)
from .serializers import (
    DataSourceSerializer, DataSourceListSerializer,
    HealthDataSerializer, HealthDataListSerializer, HealthDataCreateSerializer,
    AnomalyDetectionSerializer, AnomalyDetectionListSerializer,
    CaseClusterSerializer, CaseClusterListSerializer,
    HotspotSerializer, HotspotListSerializer,
    SurveillanceReportSerializer, SurveillanceReportListSerializer,
    DiseaseProfileSerializer, DiseaseProfileListSerializer,
    DataQualityCheckSerializer,
    SurveillanceDashboardSerializer, SurveillanceStatisticsSerializer,
    AnomalyVerificationSerializer, DataSourceSyncSerializer, BulkDataUploadSerializer,
)


# ---------------------------------------------------------------------------
# DataSource
# ---------------------------------------------------------------------------

class DataSourceViewSet(viewsets.ModelViewSet):
    """CRUD + sync operations for external data sources."""

    queryset = (
        DataSource.objects.filter(is_deleted=False)
        .select_related("location")
        .order_by("name")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["source_type", "is_active", "location"]
    search_fields = ["name", "contact_person", "contact_email"]
    ordering_fields = ["name", "created_at", "last_sync"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return DataSourceListSerializer if self.action == "list" else DataSourceSerializer

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Enqueue an async sync for this data source."""
        data_source = self.get_object()
        serializer = DataSourceSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import sync_data_source
        task = sync_data_source.delay(
            str(data_source.id),
            serializer.validated_data["force_sync"],
        )
        return Response(
            {"status": "sync_queued", "task_id": task.id, "data_source": data_source.name},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def active_sources(self, request):
        """List all active data sources (unpaginated for dropdowns)."""
        sources = self.queryset.filter(is_active=True)
        serializer = DataSourceListSerializer(sources, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def quality_report(self, request, pk=None):
        """Return the 10 most recent quality checks for this source."""
        data_source = self.get_object()
        checks = (
            DataQualityCheck.objects.filter(data_source=data_source)
            .order_by("-check_date")[:10]
        )
        serializer = DataQualityCheckSerializer(checks, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# HealthData
# ---------------------------------------------------------------------------

class HealthDataViewSet(viewsets.ModelViewSet):
    """Health data ingestion and retrieval."""

    queryset = (
        HealthData.objects.filter(is_deleted=False)
        .select_related("data_source", "location")
        .defer("raw_data", "processing_errors", "symptoms")
        .order_by("-date_recorded")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["data_type", "disease_code", "location", "processed", "data_source", "severity"]
    search_fields = ["disease_name", "patient_id", "disease_code"]
    pagination_class = TimeBasedPagination

    def get_serializer_class(self):
        if self.action == "list":
            return HealthDataListSerializer
        if self.action == "create":
            return HealthDataCreateSerializer
        return HealthDataSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if start := params.get("start_date"):
            qs = qs.filter(date_recorded__gte=start)
        if end := params.get("end_date"):
            qs = qs.filter(date_recorded__lte=end)
        return qs

    @action(detail=False, methods=["post"])
    def bulk_upload(self, request):
        """Accept a CSV/Excel file and queue async processing."""
        serializer = BulkDataUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import process_bulk_upload
        task = process_bulk_upload.delay(
            request.FILES["file"].read(),
            str(serializer.validated_data["data_source_id"]),
            serializer.validated_data["data_type"],
        )
        return Response(
            {"status": "processing_queued", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def unprocessed(self, request):
        """Return unprocessed health records, paginated."""
        qs = self.queryset.filter(processed=False)
        page = self.paginate_queryset(qs)
        serializer = HealthDataListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_disease(self, request):
        """Return records filtered by disease_code."""
        code = request.query_params.get("disease_code")
        if not code:
            return Response(
                {"error": "disease_code query param is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = self.queryset.filter(disease_code=code)
        page = self.paginate_queryset(qs)
        serializer = HealthDataListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# AnomalyDetection
# ---------------------------------------------------------------------------

class AnomalyDetectionViewSet(viewsets.ModelViewSet):
    """Anomaly records produced by the detection pipeline."""

    queryset = (
        AnomalyDetection.objects.filter(is_deleted=False)
        .select_related("location", "verified_by")
        .prefetch_related("related_health_data")
        .order_by("-detected_at")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "anomaly_type", "severity", "is_verified", "is_false_positive",
        "location", "disease_code",
    ]
    search_fields = ["disease_name", "disease_code", "detection_method"]
    ordering_fields = ["detected_at", "severity", "confidence_score"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return AnomalyDetectionListSerializer if self.action == "list" else AnomalyDetectionSerializer

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Epidemiologist verifies or dismisses an anomaly."""
        anomaly = self.get_object()
        serializer = AnomalyVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        anomaly.is_verified = d["is_verified"]
        anomaly.is_false_positive = d["is_false_positive"]
        anomaly.notes = d["notes"]
        anomaly.verified_by = request.user
        anomaly.verified_at = timezone.now()
        anomaly.save(update_fields=[
            "is_verified", "is_false_positive", "notes",
            "verified_by", "verified_at", "updated_at",
        ])
        return Response(AnomalyDetectionSerializer(anomaly).data)

    @action(detail=False, methods=["get"])
    def unverified(self, request):
        qs = self.queryset.filter(is_verified=False, is_false_positive=False)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(AnomalyDetectionListSerializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def critical(self, request):
        qs = self.queryset.filter(severity="CRITICAL")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(AnomalyDetectionListSerializer(page, many=True).data)

    @action(detail=False, methods=["post"])
    def run_detection(self, request):
        """Manually trigger the anomaly detection Celery task."""
        from .tasks import run_anomaly_detection
        task = run_anomaly_detection.delay()
        return Response(
            {"status": "queued", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# CaseCluster
# ---------------------------------------------------------------------------

class CaseClusterViewSet(viewsets.ModelViewSet):
    """Case clusters identified by spatial scan statistics."""

    queryset = (
        CaseCluster.objects.filter(is_deleted=False)
        .select_related("location", "related_anomaly")
        .order_by("-start_date")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active", "location", "disease_code"]
    search_fields = ["name", "disease_name"]
    ordering_fields = ["start_date", "case_count"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return CaseClusterListSerializer if self.action == "list" else CaseClusterSerializer

    @action(detail=False, methods=["get"])
    def active(self, request):
        qs = self.queryset.filter(is_active=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CaseClusterListSerializer(page, many=True).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Mark a cluster as resolved."""
        cluster = self.get_object()
        if not cluster.is_active:
            return Response(
                {"error": "Cluster is already closed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cluster.is_active = False
        cluster.end_date = timezone.now()
        cluster.save(update_fields=["is_active", "end_date", "updated_at"])
        return Response(CaseClusterSerializer(cluster).data)

    @action(detail=False, methods=["get"])
    def map_data(self, request):
        """GeoJSON-ready payload for active clusters."""
        clusters = self.queryset.filter(
            is_active=True,
            center_latitude__isnull=False,
            center_longitude__isnull=False,
        )
        features = [
            {
                "id": str(c.id),
                "name": c.name,
                "disease": c.disease_name,
                "latitude": float(c.center_latitude),
                "longitude": float(c.center_longitude),
                "radius_km": float(c.radius_km or 0),
                "case_count": c.case_count,
                "location": c.location.name,
                "p_value": float(c.p_value) if c.p_value else None,
            }
            for c in clusters
        ]
        return Response(features)


# ---------------------------------------------------------------------------
# Hotspot
# ---------------------------------------------------------------------------

class HotspotViewSet(viewsets.ModelViewSet):
    """Geographic disease hotspots."""

    queryset = (
        Hotspot.objects.filter(is_deleted=False)
        .select_related("location", "related_cluster")
        .order_by("-start_date")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["risk_level", "is_active", "location", "disease_code"]
    search_fields = ["disease_name", "disease_code"]
    ordering_fields = ["start_date", "risk_level", "case_count"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return HotspotListSerializer if self.action == "list" else HotspotSerializer

    @action(detail=False, methods=["get"])
    def active(self, request):
        qs = self.queryset.filter(is_active=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(HotspotListSerializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def high_risk(self, request):
        qs = self.queryset.filter(risk_level__in=["HIGH", "CRITICAL"], is_active=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(HotspotListSerializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def map_data(self, request):
        """GeoJSON-ready payload for active hotspots."""
        hotspots = self.queryset.filter(is_active=True)
        features = [
            {
                "id": str(h.id),
                "disease": h.disease_name,
                "latitude": float(h.latitude),
                "longitude": float(h.longitude),
                "radius_km": float(h.radius_km),
                "risk_level": h.risk_level,
                "case_count": h.case_count,
                "z_score": float(h.z_score) if h.z_score else None,
                "location": h.location.name,
            }
            for h in hotspots
        ]
        return Response(features)


# ---------------------------------------------------------------------------
# SurveillanceReport
# ---------------------------------------------------------------------------

class SurveillanceReportViewSet(viewsets.ModelViewSet):
    """Surveillance report management."""

    queryset = (
        SurveillanceReport.objects.filter(is_deleted=False)
        .select_related("location", "generated_by", "reviewed_by", "approved_by")
        .order_by("-start_date")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["report_type", "is_published", "location"]
    search_fields = ["title"]
    ordering_fields = ["start_date", "created_at"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return SurveillanceReportListSerializer if self.action == "list" else SurveillanceReportSerializer

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish a report, making it publicly visible."""
        report = self.get_object()
        if report.is_published:
            return Response(
                {"error": "Report is already published"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.is_published = True
        report.published_at = timezone.now()
        report.save(update_fields=["is_published", "published_at", "updated_at"])
        return Response(SurveillanceReportSerializer(report).data)

    @action(detail=False, methods=["get"])
    def published(self, request):
        qs = self.queryset.filter(is_published=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(SurveillanceReportListSerializer(page, many=True).data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Serve the report file as a download."""
        report = self.get_object()
        if not report.report_file:
            return Response(
                {"error": "No file attached to this report."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            report.report_file.open("rb"),
            as_attachment=True,
            filename=report.report_file.name.split("/")[-1],
        )


# ---------------------------------------------------------------------------
# DiseaseProfile
# ---------------------------------------------------------------------------

class DiseaseProfileViewSet(viewsets.ModelViewSet):
    """Disease master registry (admin write, authenticated read)."""

    queryset = DiseaseProfile.objects.filter(is_deleted=False).order_by("disease_name")
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "is_notifiable", "is_active"]
    search_fields = ["disease_name", "disease_code"]
    ordering_fields = ["disease_name", "created_at"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return DiseaseProfileListSerializer if self.action == "list" else DiseaseProfileSerializer

    @action(detail=False, methods=["get"])
    def notifiable(self, request):
        """Return all notifiable diseases (no pagination, used by forms)."""
        qs = self.queryset.filter(is_notifiable=True, is_active=True)
        return Response(DiseaseProfileListSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# DataQualityCheck (read-only)
# ---------------------------------------------------------------------------

class DataQualityCheckViewSet(viewsets.ReadOnlyModelViewSet):
    """Quality check results — read only, created by background tasks."""

    queryset = (
        DataQualityCheck.objects.filter(is_deleted=False)
        .select_related("data_source")
        .order_by("-check_date")
    )
    serializer_class = DataQualityCheckSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["check_type", "data_source", "status"]
    ordering_fields = ["check_date", "pass_rate"]
    pagination_class = CustomPagination


# ---------------------------------------------------------------------------
# Dashboard (aggregated, no DB model)
# ---------------------------------------------------------------------------

class SurveillanceDashboardViewSet(viewsets.ViewSet):
    """Real-time dashboard statistics."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="early-warning")
    def early_warning(self, request):
        """
        Statistical early-warning analysis for one disease (optionally one location).

        Query params: disease_code (required), location (id), days (14-365, default 60).
        Runs EARS C1-C3, CUSUM, Poisson exceedance and Rt estimation.
        """
        from .early_warning import analyze, fill_daily_series

        disease_code = (request.query_params.get("disease_code") or "").strip()
        if not disease_code:
            return Response({"detail": "disease_code is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            days = int(request.query_params.get("days", 60))
        except ValueError:
            return Response({"detail": "days must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if not 14 <= days <= 365:
            return Response({"detail": "days must be between 14 and 365."}, status=status.HTTP_400_BAD_REQUEST)

        end = timezone.now().date()
        start = end - timedelta(days=days - 1)
        qs = HealthData.objects.filter(
            is_deleted=False, disease_code=disease_code, date_recorded__date__gte=start,
        )
        location = request.query_params.get("location")
        if location:
            try:
                qs = qs.filter(location_id=location)
            except (ValueError, TypeError, DjangoValidationError):
                return Response({"detail": "invalid location."}, status=status.HTTP_400_BAD_REQUEST)
        counts = {
            row["date_recorded__date"]: row["n"]
            for row in qs.values("date_recorded__date").annotate(n=Count("id"))
        }
        series = fill_daily_series(counts, start, end)
        result = analyze(series).to_dict()
        result.update({"disease_code": disease_code, "location": location,
                       "start": start.isoformat(), "end": end.isoformat(), "series": series})
        return Response(result)

    @action(detail=False, methods=["get"], url_path="early-warning-overview")
    def early_warning_overview(self, request):
        """Worst-first early-warning status per location/disease, with 30-day sparkline series."""
        from .early_warning_service import overview

        try:
            limit = max(1, min(int(request.query_params.get("limit", 12)), 50))
        except ValueError:
            return Response({"detail": "limit must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"results": overview(limit=limit)})

    @action(detail=False, methods=["get"])
    def overview(self, request):
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Single aggregate query instead of 3 sequential COUNT(*) table scans
        hd_counts = HealthData.objects.filter(is_deleted=False).aggregate(
            total_cases_today=Count('id', filter=Q(date_recorded__date=today)),
            total_cases_week=Count('id', filter=Q(date_recorded__date__gte=week_ago)),
            total_cases_month=Count('id', filter=Q(date_recorded__date__gte=month_ago)),
        )
        total_cases_today  = hd_counts['total_cases_today']
        total_cases_week   = hd_counts['total_cases_week']
        total_cases_month  = hd_counts['total_cases_month']

        # Single aggregate for anomaly/cluster/hotspot counts
        active_anomalies = AnomalyDetection.objects.filter(
            is_deleted=False, is_verified=False, is_false_positive=False
        ).count()
        active_clusters = CaseCluster.objects.filter(is_deleted=False, is_active=True).count()
        active_hotspots = Hotspot.objects.filter(is_deleted=False, is_active=True).count()

        high_risk_locations = list(
            Hotspot.objects.filter(
                is_deleted=False, risk_level__in=["HIGH", "CRITICAL"], is_active=True
            )
            .values_list("location__name", flat=True)
            .distinct()[:5]
        )

        trending_diseases = list(
            HealthData.objects.filter(is_deleted=False, date_recorded__date__gte=week_ago)
            .values("disease_name")
            .annotate(count=Count("id"))
            .order_by("-count")
            .values("disease_name", "count")[:5]
        )

        recent_alerts = list(
            AnomalyDetection.objects.filter(
                is_deleted=False, severity__in=["HIGH", "CRITICAL"]
            )
            .order_by("-detected_at")
            .values("id", "disease_name", "severity", "detected_at", "location__name")[:5]
        )

        data = {
            "total_cases_today": total_cases_today,
            "total_cases_week": total_cases_week,
            "total_cases_month": total_cases_month,
            "active_anomalies": active_anomalies,
            "active_clusters": active_clusters,
            "active_hotspots": active_hotspots,
            "high_risk_locations": high_risk_locations,
            "trending_diseases": trending_diseases,
            "recent_alerts": recent_alerts,
        }
        return Response(SurveillanceDashboardSerializer(data).data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        period = request.query_params.get("period", "month")
        days_map = {"week": 7, "month": 30, "year": 365}
        days = days_map.get(period, 30)
        start_date = timezone.now() - timedelta(days=days)

        qs = HealthData.objects.filter(is_deleted=False, date_recorded__gte=start_date)
        total = qs.count()
        unique_diseases = qs.values("disease_code").distinct().count()
        affected_locations = qs.values("location").distinct().count()
        average_per_day = round(total / days, 2) if days else 0

        mid = start_date + timedelta(days=days // 2)
        first_half = qs.filter(date_recorded__lt=mid).count()
        second_half = qs.filter(date_recorded__gte=mid).count()
        if second_half > first_half:
            trend = "increasing"
        elif second_half < first_half:
            trend = "decreasing"
        else:
            trend = "stable"

        top_diseases = list(
            qs.values("disease_name")
            .annotate(count=Count("id"))
            .order_by("-count")
            .values("disease_name", "count")[:10]
        )
        geo_dist = dict(
            qs.values("location__name")
            .annotate(count=Count("id"))
            .values_list("location__name", "count")
        )

        data = {
            "period": period,
            "total_data_points": total,
            "unique_diseases": unique_diseases,
            "affected_locations": affected_locations,
            "average_cases_per_day": average_per_day,
            "case_trend": trend,
            "top_diseases": top_diseases,
            "geographic_distribution": geo_dist,
        }
        return Response(SurveillanceStatisticsSerializer(data).data)