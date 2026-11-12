"""
ViewSets for the risk_assessment app.

URL prefix: /api/v1/risk/
"""
from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from core.pagination import CustomPagination
from core.permissions import IsAdminOrReadOnly

from .models import Alert, PredictiveModel, RiskFactor, RiskScore, Threshold, ThreatClassification
from .serializers import (
    AlertAcknowledgeSerializer,
    AlertCreateSerializer,
    AlertListSerializer,
    AlertResolveSerializer,
    AlertSerializer,
    ComparativeRiskSerializer,
    OutbreakPredictionSerializer,
    PredictiveModelListSerializer,
    PredictiveModelSerializer,
    RiskAssessmentRequestSerializer,
    RiskDashboardSerializer,
    RiskFactorListSerializer,
    RiskFactorSerializer,
    RiskScoreCreateSerializer,
    RiskScoreListSerializer,
    RiskScoreSerializer,
    RiskTrendSerializer,
    ThresholdCheckSerializer,
    ThresholdListSerializer,
    ThresholdSerializer,
    ThreatClassificationListSerializer,
    ThreatClassificationSerializer,
)


# ---------------------------------------------------------------------------
# RiskScore
# ---------------------------------------------------------------------------

class RiskScoreViewSet(viewsets.ModelViewSet):
    """CRUD + actions for RiskScore."""

    queryset = (
        RiskScore.objects.filter(is_deleted=False)
        .select_related("location", "related_anomaly", "related_cluster")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["risk_level", "is_active", "location", "disease_code"]
    search_fields = ["disease_name", "disease_code"]
    ordering_fields = ["assessment_date", "overall_score", "risk_level"]
    ordering = ["-assessment_date"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return RiskScoreListSerializer
        if self.action == "create":
            return RiskScoreCreateSerializer
        return RiskScoreSerializer

    # ── extra actions ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Currently active risk scores."""
        qs = self.filter_queryset(self.get_queryset().filter(is_active=True))
        page = self.paginate_queryset(qs)
        serializer = RiskScoreListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def critical(self, request):
        """CRITICAL and VERY_HIGH active risk scores."""
        qs = self.filter_queryset(
            self.get_queryset().filter(
                risk_level__in=["CRITICAL", "VERY_HIGH"],
                is_active=True,
            )
        )
        page = self.paginate_queryset(qs)
        serializer = RiskScoreListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["post"])
    def calculate(self, request):
        """Enqueue a risk-score calculation task."""
        serializer = RiskAssessmentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import calculate_risk_score

        task = calculate_risk_score.delay(
            str(serializer.validated_data["location_id"]),
            serializer.validated_data["disease_code"],
            serializer.validated_data["force_recalculation"],
        )
        return Response(
            {"status": "calculation_enqueued", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def by_location(self, request):
        """Active risk scores for a specific location."""
        location_id = request.query_params.get("location_id")
        if not location_id:
            return Response(
                {"detail": "location_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.filter_queryset(
            self.get_queryset().filter(location_id=location_id, is_active=True)
        )
        page = self.paginate_queryset(qs)
        serializer = RiskScoreListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """Daily average / max risk score and alert count for the last N days."""
        try:
            days = max(1, min(int(request.query_params.get("days", 30)), 365))
        except (TypeError, ValueError):
            days = 30

        start_date = timezone.now() - timedelta(days=days)
        qs = (
            self.get_queryset()
            .filter(assessment_date__gte=start_date.date())
            .annotate(date=TruncDate("assessment_date"))
            .values("date")
            .annotate(
                average_score=Avg("overall_score"),
                max_score=Max("overall_score"),
                alert_count=Count("alerts"),
            )
            .order_by("date")
        )
        serializer = RiskTrendSerializer(qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# ThreatClassification
# ---------------------------------------------------------------------------

class ThreatClassificationViewSet(viewsets.ModelViewSet):
    """CRUD + actions for ThreatClassification."""

    queryset = (
        ThreatClassification.objects.filter(is_deleted=False)
        .select_related("location", "assessed_by", "related_risk_score")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["threat_level", "pandemic_potential", "cross_border_risk", "location", "disease_code"]
    search_fields = ["disease_name", "disease_code"]
    ordering_fields = ["assessment_date", "threat_score"]
    ordering = ["-assessment_date"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ThreatClassificationListSerializer
        return ThreatClassificationSerializer

    def perform_create(self, serializer):
        from django.utils import timezone

        serializer.save(
            assessed_by=self.request.user,
            assessment_date=timezone.now().date(),
        )

    @action(detail=False, methods=["get"])
    def pandemic_threats(self, request):
        """Threats flagged with pandemic potential."""
        qs = self.filter_queryset(self.get_queryset().filter(pandemic_potential=True))
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def severe(self, request):
        """SEVERE and EXTREME threats."""
        qs = self.filter_queryset(
            self.get_queryset().filter(threat_level__in=["SEVERE", "EXTREME"])
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertViewSet(viewsets.ModelViewSet):
    """CRUD + lifecycle actions for Alert."""

    queryset = (
        Alert.objects.filter(is_deleted=False)
        .select_related("location", "acknowledged_by", "related_risk_score", "related_anomaly")
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["alert_type", "severity", "status", "location", "disease_code"]
    search_fields = ["title", "description"]
    ordering_fields = ["triggered_at", "severity"]
    ordering = ["-triggered_at"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return AlertListSerializer
        if self.action == "create":
            return AlertCreateSerializer
        return AlertSerializer

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Alerts with status ACTIVE or ACKNOWLEDGED."""
        qs = self.filter_queryset(
            self.get_queryset().filter(status__in=["ACTIVE", "ACKNOWLEDGED"])
        )
        page = self.paginate_queryset(qs)
        serializer = AlertListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def unacknowledged(self, request):
        """ACTIVE alerts that have not been acknowledged."""
        qs = self.filter_queryset(
            self.get_queryset().filter(status="ACTIVE", acknowledged_at__isnull=True)
        )
        page = self.paginate_queryset(qs)
        serializer = AlertListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def critical(self, request):
        """CRITICAL and EMERGENCY active alerts."""
        qs = self.filter_queryset(
            self.get_queryset().filter(
                severity__in=["CRITICAL", "EMERGENCY"],
                status__in=["ACTIVE", "ACKNOWLEDGED"],
            )
        )
        page = self.paginate_queryset(qs)
        serializer = AlertListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_location(self, request):
        """Alerts for a specific location."""
        location_id = request.query_params.get("location_id")
        if not location_id:
            return Response(
                {"detail": "location_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = self.filter_queryset(
            self.get_queryset().filter(location_id=location_id)
        )
        page = self.paginate_queryset(qs)
        serializer = AlertListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert."""
        alert = self.get_object()
        if alert.status not in ("ACTIVE",):
            return Response(
                {"detail": f"Cannot acknowledge an alert with status '{alert.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AlertAcknowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert.acknowledge(request.user, notes=serializer.validated_data.get("notes", ""))

        from core.models import AuditLog
        AuditLog.log(
            user=request.user,
            action="ALERT_ACKNOWLEDGED",
            resource_type="Alert",
            resource_id=str(alert.id),
            details={"alert_title": alert.title, "severity": alert.severity},
        )

        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Resolve an alert."""
        alert = self.get_object()
        if alert.status in ("RESOLVED", "CLOSED"):
            return Response(
                {"detail": f"Alert is already '{alert.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AlertResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert.resolve(
            resolution_notes=serializer.validated_data.get("resolution_notes", ""),
            actions=serializer.validated_data.get("actions_taken", []),
        )

        from core.models import AuditLog
        AuditLog.log(
            user=request.user,
            action="ALERT_RESOLVED",
            resource_type="Alert",
            resource_id=str(alert.id),
            details={"alert_title": alert.title},
        )

        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Close an alert (final state — cannot be re-opened)."""
        alert = self.get_object()
        if alert.status == "CLOSED":
            return Response(
                {"detail": "Alert is already CLOSED."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get("reason", "")
        alert.close(reason=reason)

        from core.models import AuditLog
        AuditLog.log(
            user=request.user,
            action="ALERT_CLOSED",
            resource_type="Alert",
            resource_id=str(alert.id),
            details={"alert_title": alert.title, "reason": reason},
        )
        return Response(AlertSerializer(alert).data)

    @action(detail=False, methods=["post"])
    def bulk_acknowledge(self, request):
        """Acknowledge multiple ACTIVE alerts at once."""
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response(
                {"detail": "ids must be a non-empty list of alert UUIDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notes = request.data.get("notes", "")
        acknowledged = 0
        errors = []
        for alert_id in ids:
            try:
                alert = Alert.objects.get(id=alert_id, is_deleted=False)
                if alert.status == "ACTIVE":
                    alert.acknowledge(request.user, notes=notes)
                    acknowledged += 1
            except Alert.DoesNotExist:
                errors.append({"id": str(alert_id), "error": "Not found"})
            except Exception as exc:
                errors.append({"id": str(alert_id), "error": str(exc)})

        return Response({
            "acknowledged": acknowledged,
            "errors": errors,
        })


# ---------------------------------------------------------------------------
# Threshold
# ---------------------------------------------------------------------------

class ThresholdViewSet(viewsets.ModelViewSet):
    """CRUD + check action for Threshold."""

    queryset = Threshold.objects.filter(is_deleted=False).select_related("location")
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["threshold_type", "is_active", "location", "disease_code"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "threshold_type"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ThresholdListSerializer
        return ThresholdSerializer

    @action(detail=False, methods=["get"])
    def active(self, request):
        """All active thresholds (unpaginated — typically a small set)."""
        qs = self.filter_queryset(self.get_queryset().filter(is_active=True))
        serializer = ThresholdListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        """Evaluate a value against this threshold's tiers."""
        threshold = self.get_object()
        serializer = ThresholdCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_value = serializer.validated_data["current_value"]
        result = threshold.evaluate(current_value)

        return Response(
            {
                "threshold": threshold.name,
                "threshold_type": threshold.threshold_type,
                "current_value": float(current_value),
                "result": result,
                "warning_value": float(threshold.warning_value),
                "alert_value": float(threshold.alert_value),
                "critical_value": float(threshold.critical_value),
            }
        )


# ---------------------------------------------------------------------------
# RiskFactor
# ---------------------------------------------------------------------------

class RiskFactorViewSet(viewsets.ModelViewSet):
    """CRUD + category filter for RiskFactor."""

    queryset = RiskFactor.objects.filter(is_deleted=False).select_related("location")
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "is_active", "location"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "weight", "category"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return RiskFactorListSerializer
        return RiskFactorSerializer

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Active risk factors for a specific category."""
        category = request.query_params.get("category")
        if not category:
            return Response(
                {"detail": "category query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = self.filter_queryset(
            self.get_queryset().filter(category=category, is_active=True)
        )
        serializer = RiskFactorSerializer(qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# PredictiveModel
# ---------------------------------------------------------------------------

class PredictiveModelViewSet(viewsets.ModelViewSet):
    """CRUD + predict action for PredictiveModel."""

    queryset = PredictiveModel.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["model_type", "is_active", "is_deployed"]
    search_fields = ["name", "algorithm", "description"]
    ordering_fields = ["name", "accuracy", "trained_at", "prediction_count"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return PredictiveModelListSerializer
        return PredictiveModelSerializer

    @action(detail=False, methods=["get"])
    def deployed(self, request):
        """Active deployed models (suitable for prediction requests)."""
        qs = self.filter_queryset(
            self.get_queryset().filter(is_deployed=True, is_active=True)
        )
        serializer = PredictiveModelListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def predict(self, request, pk=None):
        """Enqueue an outbreak prediction task."""
        model = self.get_object()
        if not model.is_deployed or not model.is_active:
            return Response(
                {"detail": "Model is not deployed or inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OutbreakPredictionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import predict_outbreak

        task = predict_outbreak.delay(
            str(model.id),
            str(serializer.validated_data["location_id"]),
            serializer.validated_data["disease_code"],
            serializer.validated_data["prediction_horizon"],
        )
        return Response(
            {"status": "prediction_enqueued", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class RiskDashboardViewSet(viewsets.ViewSet):
    """Aggregate dashboard endpoints."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """High-level risk snapshot for the dashboard home."""
        # Collapse 2 RiskScore count queries + avg into one aggregate pass
        risk_agg = RiskScore.objects.filter(is_deleted=False, is_active=True).aggregate(
            critical_risks=Count('id', filter=Q(risk_level='CRITICAL')),
            high_risks=Count('id', filter=Q(risk_level__in=['VERY_HIGH', 'HIGH'])),
            avg_score=Avg('overall_score'),
        )
        critical_risks      = risk_agg['critical_risks']
        high_risks          = risk_agg['high_risks']
        avg_score           = risk_agg['avg_score'] or 0.0

        # Collapse 2 Alert count queries into one aggregate pass
        alert_agg = Alert.objects.filter(is_deleted=False).aggregate(
            active_alerts=Count('id', filter=Q(status__in=['ACTIVE', 'ACKNOWLEDGED'])),
            unacknowledged_alerts=Count('id', filter=Q(status='ACTIVE', acknowledged_at__isnull=True)),
        )
        active_alerts          = alert_agg['active_alerts']
        unacknowledged_alerts  = alert_agg['unacknowledged_alerts']

        trending_threats = list(
            ThreatClassification.objects.filter(
                is_deleted=False,
                threat_level__in=["HIGH", "SEVERE", "EXTREME"],
            )
            .order_by("-assessment_date")[:5]
            .values("disease_name", "threat_level", "threat_score")
        )

        high_risk_locations = list(
            RiskScore.objects.filter(
                is_deleted=False,
                risk_level__in=["CRITICAL", "VERY_HIGH"],
                is_active=True,
            )
            .values("location__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
            .values_list("location__name", flat=True)
        )

        recent_alerts = list(
            Alert.objects.filter(
                is_deleted=False,
                status__in=["ACTIVE", "ACKNOWLEDGED"],
            )
            .order_by("-triggered_at")[:5]
            .values("id", "title", "severity", "status", "triggered_at")
        )

        # Convert UUID/datetime to JSON-safe types
        for a in recent_alerts:
            a["id"] = str(a["id"])
            if a["triggered_at"]:
                a["triggered_at"] = a["triggered_at"].isoformat()

        data = {
            "critical_risks": critical_risks,
            "high_risks": high_risks,
            "active_alerts": active_alerts,
            "unacknowledged_alerts": unacknowledged_alerts,
            "average_risk_score": round(float(avg_score), 2),
            "trending_threats": trending_threats,
            "high_risk_locations": list(high_risk_locations),
            "recent_alerts": recent_alerts,
            "generated_at": timezone.now(),
        }

        serializer = RiskDashboardSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def comparative(self, request):
        """Top-10 locations ranked by average active risk score."""
        location_risks = (
            RiskScore.objects.filter(is_deleted=False, is_active=True)
            .values("location__name")
            .annotate(
                risk_score=Avg("overall_score"),
                disease_count=Count("disease_code", distinct=True),
                alert_count=Count("alerts"),
            )
            .order_by("-risk_score")[:10]
        )

        results = []
        for item in location_risks:
            score = float(item["risk_score"] or 0)
            results.append(
                {
                    "location_name": item["location__name"],
                    "risk_score": round(score, 2),
                    "risk_level": RiskScore.level_for_score(score),
                    "disease_count": item["disease_count"],
                    "alert_count": item["alert_count"],
                }
            )

        serializer = ComparativeRiskSerializer(results, many=True)
        return Response(serializer.data)