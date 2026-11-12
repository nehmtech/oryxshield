"""
Views for response app.
"""
import uuid
import logging
from datetime import timedelta

from django.db import IntegrityError

from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DurationField
from django.utils import timezone

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from core.models import AuditLog
from core.pagination import CustomPagination
from core.permissions import IsAdminOrReadOnly

from .models import (
    ResponseLevel,
    ResponseProtocol,
    ResponseActivation,
    EscalationTrigger,
    ActionItem,
    ResponseReport,
    DecisionLog,
)
from .serializers import (
    ResponseLevelSerializer,
    ResponseProtocolSerializer,
    ResponseProtocolListSerializer,
    ResponseActivationSerializer,
    ResponseActivationListSerializer,
    ActivationCreateSerializer,
    EscalationSerializer,
    DeescalationSerializer,
    SuspendSerializer,
    EscalationTriggerSerializer,
    ActionItemSerializer,
    ActionItemListSerializer,
    ActionCompleteSerializer,
    ActionStartSerializer,
    ResponseReportSerializer,
    ResponseReportListSerializer,
    PublishReportSerializer,
    DecisionLogSerializer,
    ResponseDashboardSerializer,
    ResponseStatisticsSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ResponseLevel
# ---------------------------------------------------------------------------

class ResponseLevelViewSet(viewsets.ModelViewSet):
    """CRUD for ResponseLevel."""

    queryset = ResponseLevel.objects.all()
    serializer_class = ResponseLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = CustomPagination

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Return only active levels ordered by level number."""
        qs = self.get_queryset().filter(is_active=True).order_by("level")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# ResponseProtocol
# ---------------------------------------------------------------------------

class ResponseProtocolViewSet(viewsets.ModelViewSet):
    """CRUD for ResponseProtocol."""

    queryset = ResponseProtocol.objects.prefetch_related("applicable_locations")
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["protocol_type", "is_active"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "created_at", "last_reviewed"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ResponseProtocolListSerializer
        return ResponseProtocolSerializer

    def perform_create(self, serializer):
        protocol = serializer.save(created_by=self.request.user)
        AuditLog.log(
            action="PROTOCOL_CREATED",
            actor=self.request.user,
            target_object_id=str(protocol.id),
            target_content_type="response.ResponseProtocol",
            details={"code": protocol.code, "name": protocol.name},
        )

    def perform_update(self, serializer):
        protocol = serializer.save()
        AuditLog.log(
            action="PROTOCOL_UPDATED",
            actor=self.request.user,
            target_object_id=str(protocol.id),
            target_content_type="response.ResponseProtocol",
            details={"code": protocol.code},
        )

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Return active protocols."""
        qs = self.get_queryset().filter(is_active=True)
        page = self.paginate_queryset(qs)
        serializer = ResponseProtocolListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_disease(self, request):
        """Filter protocols applicable to a specific disease code."""
        disease_code = request.query_params.get("disease_code", "").strip()
        if not disease_code:
            return Response(
                {"error": "disease_code query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = self.get_queryset().filter(
            disease_codes__contains=[disease_code],
            is_active=True,
        )
        page = self.paginate_queryset(qs)
        serializer = ResponseProtocolListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# ResponseActivation
# ---------------------------------------------------------------------------

class ResponseActivationViewSet(viewsets.ModelViewSet):
    """Full lifecycle management for ResponseActivation."""

    queryset = ResponseActivation.objects.select_related(
        "response_level", "protocol", "location",
        "incident_commander", "activated_by",
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "response_level", "location", "disease_code"]
    search_fields = ["activation_code", "disease_name", "justification"]
    ordering_fields = ["activated_at", "status", "completion_percentage"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ResponseActivationListSerializer
        if self.action == "create":
            return ActivationCreateSerializer
        return ResponseActivationSerializer

    def perform_create(self, serializer):
        for _ in range(5):
            activation_code = f"RSP-{uuid.uuid4().hex[:8].upper()}"
            try:
                activation = serializer.save(
                    activation_code=activation_code,
                    activated_by=self.request.user,
                    status="ACTIVE",
                )
                break
            except IntegrityError:
                continue
        else:
            raise IntegrityError("Could not generate a unique activation_code after 5 attempts.")
        AuditLog.log(
            action="RESPONSE_ACTIVATED",
            actor=self.request.user,
            target_object_id=str(activation.id),
            target_content_type="response.ResponseActivation",
            details={
                "activation_code": activation.activation_code,
                "level": activation.response_level.level,
                "location": activation.location.name,
                "disease_code": activation.disease_code,
            },
        )
        logger.info(
            "Response %s activated at Level %s for %s",
            activation.activation_code,
            activation.response_level.level,
            activation.location.name,
        )

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Active responses (status ACTIVE or ESCALATED)."""
        qs = self.get_queryset().filter(status__in=["ACTIVE", "ESCALATED"])
        page = self.paginate_queryset(qs)
        serializer = ResponseActivationListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def level_5(self, request):
        """All Level-5 emergency responses currently active."""
        qs = self.get_queryset().filter(
            response_level__level=5,
            status__in=["ACTIVE", "ESCALATED"],
        )
        page = self.paginate_queryset(qs)
        serializer = ResponseActivationListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        """Escalate a response to a higher level."""
        activation = self.get_object()

        if activation.status in ("COMPLETED", "CANCELLED", "SUSPENDED"):
            return Response(
                {"error": f"Cannot escalate a {activation.status} response."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EscalationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            new_level = ResponseLevel.objects.get(
                id=serializer.validated_data["new_level_id"]
            )
        except ResponseLevel.DoesNotExist:
            return Response(
                {"error": "Response level not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            activation.escalate(
                new_level,
                request.user,
                serializer.validated_data["reason"],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "status": "Response escalated.",
                "new_level": new_level.level,
                "activation_code": activation.activation_code,
            }
        )

    @action(detail=True, methods=["post"])
    def deescalate(self, request, pk=None):
        """De-escalate a response to a lower level."""
        activation = self.get_object()

        if activation.status in ("COMPLETED", "CANCELLED", "SUSPENDED"):
            return Response(
                {"error": f"Cannot de-escalate a {activation.status} response."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DeescalationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            new_level = ResponseLevel.objects.get(
                id=serializer.validated_data["new_level_id"]
            )
        except ResponseLevel.DoesNotExist:
            return Response(
                {"error": "Response level not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            activation.deescalate(
                new_level,
                request.user,
                serializer.validated_data["reason"],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "status": "Response de-escalated.",
                "new_level": new_level.level,
                "activation_code": activation.activation_code,
            }
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark a response as completed."""
        activation = self.get_object()

        if activation.status == "COMPLETED":
            return Response(
                {"error": "Response is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if activation.status == "CANCELLED":
            return Response(
                {"error": "Cannot complete a cancelled response."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activation.complete(user=request.user)
        return Response(
            {
                "status": "Response completed.",
                "activation_code": activation.activation_code,
            }
        )

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend an active response."""
        activation = self.get_object()

        if activation.status not in ("ACTIVE", "ESCALATED"):
            return Response(
                {"error": "Only ACTIVE or ESCALATED responses can be suspended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        activation.suspend(request.user, serializer.validated_data["reason"])
        return Response(
            {
                "status": "Response suspended.",
                "activation_code": activation.activation_code,
            }
        )

    @action(detail=True, methods=["get"])
    def actions(self, request, pk=None):
        """Return all action items for this response."""
        activation = self.get_object()
        items = activation.action_items.filter(is_deleted=False).order_by(
            "priority", "due_date"
        )
        page = self.paginate_queryset(items)
        serializer = ActionItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """Chronological timeline of all significant events for this response."""
        activation = self.get_object()
        events = []

        # Initial activation
        events.append(
            {
                "timestamp": activation.activated_at.isoformat(),
                "event": "Response Activated",
                "details": (
                    f"Level {activation.response_level.level} activated at "
                    f"{activation.location.name}"
                ),
                "actor": activation.activated_by.username if activation.activated_by else "system",
            }
        )

        # Escalation / de-escalation history
        for entry in activation.escalation_history:
            direction = (
                "Escalated"
                if entry.get("to_level", 0) > entry.get("from_level", 0)
                else "De-escalated"
            )
            events.append(
                {
                    "timestamp": entry["timestamp"],
                    "event": f"Response {direction}",
                    "details": (
                        f"Level {entry['from_level']} → Level {entry['to_level']}. "
                        f"Reason: {entry.get('reason', '')}"
                    ),
                    "actor": entry.get("escalated_by") or entry.get("deescalated_by", "system"),
                }
            )

        # Action completions
        completed_actions = activation.action_items.filter(
            status="COMPLETED",
            completed_at__isnull=False,
        ).values("title", "completed_at", "priority")
        for act in completed_actions:
            events.append(
                {
                    "timestamp": act["completed_at"].isoformat(),
                    "event": "Action Completed",
                    "details": f"[{act['priority']}] {act['title']}",
                    "actor": None,
                }
            )

        # Decisions
        decisions = activation.decisions.values("decision_title", "decision_date")
        for dec in decisions:
            events.append(
                {
                    "timestamp": dec["decision_date"].isoformat(),
                    "event": "Decision Logged",
                    "details": dec["decision_title"],
                    "actor": None,
                }
            )

        # Completion
        if activation.completed_at:
            events.append(
                {
                    "timestamp": activation.completed_at.isoformat(),
                    "event": "Response Completed",
                    "details": f"Completion: {activation.completion_percentage}%",
                    "actor": None,
                }
            )

        events.sort(key=lambda e: e["timestamp"])
        return Response(events)

    @action(detail=True, methods=["get"])
    def effectiveness(self, request, pk=None):
        """Calculate and return response effectiveness score."""
        activation = self.get_object()
        from .decision_support import calculate_response_effectiveness

        score = calculate_response_effectiveness(activation)
        return Response(
            {
                "activation_code": activation.activation_code,
                "effectiveness_score": round(score, 2),
                "completion_percentage": activation.completion_percentage,
            }
        )

    @action(detail=True, methods=["get"])
    def escalation_recommendation(self, request, pk=None):
        """Return escalation recommendation for this response."""
        activation = self.get_object()
        from .escalation import recommend_escalation

        recommendation = recommend_escalation(activation)
        return Response(recommendation)

    @action(detail=True, methods=["get"])
    def resource_suggestions(self, request, pk=None):
        """Suggest resource allocation for this response."""
        activation = self.get_object()
        from .decision_support import suggest_resource_allocation

        suggestions = suggest_resource_allocation(activation)
        return Response(suggestions)


# ---------------------------------------------------------------------------
# EscalationTrigger
# ---------------------------------------------------------------------------

class EscalationTriggerViewSet(viewsets.ModelViewSet):
    """CRUD for EscalationTrigger."""

    queryset = EscalationTrigger.objects.select_related("from_level", "to_level")
    serializer_class = EscalationTriggerSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["trigger_type", "is_active", "from_level", "to_level"]
    ordering_fields = ["from_level", "name", "created_at"]
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        trigger = serializer.save()
        AuditLog.log(
            action="ESCALATION_TRIGGER_CREATED",
            actor=self.request.user,
            target_object_id=str(trigger.id),
            target_content_type="response.EscalationTrigger",
            details={
                "name": trigger.name,
                "trigger_type": trigger.trigger_type,
                "from_level": trigger.from_level.level,
                "to_level": trigger.to_level.level,
                "auto_escalate": trigger.auto_escalate,
            },
        )

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Return active triggers."""
        qs = self.get_queryset().filter(is_active=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------

class ActionItemViewSet(viewsets.ModelViewSet):
    """Full lifecycle management for ActionItem."""

    queryset = ActionItem.objects.select_related("response_activation", "assigned_to")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "priority", "assigned_to", "response_activation"]
    search_fields = ["title", "description"]
    ordering_fields = ["priority", "due_date", "created_at"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ActionItemListSerializer
        return ActionItemSerializer

    def perform_create(self, serializer):
        item = serializer.save()
        AuditLog.log(
            action="ACTION_ITEM_CREATED",
            actor=self.request.user,
            target_object_id=str(item.id),
            target_content_type="response.ActionItem",
            details={
                "title": item.title,
                "priority": item.priority,
                "activation_code": item.response_activation.activation_code,
            },
        )

    # ------------------------------------------------------------------
    # Filtered list actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def pending(self, request):
        qs = self.get_queryset().filter(status="PENDING")
        page = self.paginate_queryset(qs)
        serializer = ActionItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        qs = self.get_queryset().filter(
            status__in=["PENDING", "IN_PROGRESS"],
            due_date__lt=timezone.now(),
        )
        page = self.paginate_queryset(qs)
        serializer = ActionItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_actions(self, request):
        qs = self.get_queryset().filter(assigned_to=request.user)
        page = self.paginate_queryset(qs)
        serializer = ActionItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def critical_pending(self, request):
        """Critical priority items that are pending or in progress."""
        qs = self.get_queryset().filter(
            priority="CRITICAL",
            status__in=["PENDING", "IN_PROGRESS"],
        ).order_by("due_date")
        page = self.paginate_queryset(qs)
        serializer = ActionItemListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Mark an action as in-progress."""
        item = self.get_object()

        if item.status != "PENDING":
            return Response(
                {"error": f"Cannot start an action with status {item.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.start(user=request.user)
        return Response({"status": "Action started.", "action_id": str(item.id)})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark an action as completed."""
        item = self.get_object()

        if item.status == "COMPLETED":
            return Response(
                {"error": "Action is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if item.status == "CANCELLED":
            return Response(
                {"error": "Cannot complete a cancelled action."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActionCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item.mark_completed(
            notes=serializer.validated_data.get("completion_notes", ""),
            user=request.user,
        )
        return Response({"status": "Action completed.", "action_id": str(item.id)})

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        """Mark an action as blocked."""
        item = self.get_object()
        if item.status in ("COMPLETED", "CANCELLED"):
            return Response(
                {"error": f"Cannot block an action with status {item.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        blocker = request.data.get("blocker", "").strip()
        if not blocker:
            return Response(
                {"error": "blocker description is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.block(blocker_description=blocker, user=request.user)
        return Response({"status": "Action blocked.", "action_id": str(item.id)})


# ---------------------------------------------------------------------------
# ResponseReport
# ---------------------------------------------------------------------------

class ResponseReportViewSet(viewsets.ModelViewSet):
    """CRUD for ResponseReport."""

    queryset = ResponseReport.objects.select_related(
        "response_activation", "submitted_by", "reviewed_by"
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["report_type", "is_published", "response_activation"]
    search_fields = ["title", "executive_summary"]
    ordering_fields = ["report_date", "created_at"]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == "list":
            return ResponseReportListSerializer
        return ResponseReportSerializer

    def perform_create(self, serializer):
        report = serializer.save(submitted_by=self.request.user)
        AuditLog.log(
            action="REPORT_CREATED",
            actor=self.request.user,
            target_object_id=str(report.id),
            target_content_type="response.ResponseReport",
            details={
                "title": report.title,
                "report_type": report.report_type,
                "activation_code": report.response_activation.activation_code,
            },
        )

    @action(detail=False, methods=["get"])
    def published(self, request):
        qs = self.get_queryset().filter(is_published=True)
        page = self.paginate_queryset(qs)
        serializer = ResponseReportListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish a report (sets is_published=True, records reviewer)."""
        report = self.get_object()

        if report.is_published:
            return Response(
                {"error": "Report is already published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PublishReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report.publish(reviewer=request.user)
        AuditLog.log(
            action="REPORT_PUBLISHED",
            actor=request.user,
            target_object_id=str(report.id),
            target_content_type="response.ResponseReport",
            details={"title": report.title},
        )
        return Response({"status": "Report published.", "report_id": str(report.id)})


# ---------------------------------------------------------------------------
# DecisionLog
# ---------------------------------------------------------------------------

class DecisionLogViewSet(viewsets.ModelViewSet):
    """CRUD for DecisionLog (creation is effectively append-only)."""

    queryset = DecisionLog.objects.select_related("response_activation", "decided_by")
    serializer_class = DecisionLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["response_activation", "reviewed"]
    search_fields = ["decision_title", "decision_description"]
    ordering_fields = ["decision_date"]
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        log = serializer.save(decided_by=self.request.user)
        AuditLog.log(
            action="DECISION_LOGGED",
            actor=self.request.user,
            target_object_id=str(log.id),
            target_content_type="response.DecisionLog",
            details={
                "decision_title": log.decision_title,
                "activation_code": log.response_activation.activation_code,
            },
        )

    @action(detail=True, methods=["post"])
    def mark_reviewed(self, request, pk=None):
        """Mark a decision log entry as reviewed."""
        log = self.get_object()
        review_notes = request.data.get("review_notes", "")
        log.reviewed = True
        log.review_notes = review_notes
        log.save(update_fields=["reviewed", "review_notes", "updated_at"])
        return Response({"status": "Decision marked as reviewed.", "id": str(log.id)})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class ResponseDashboardViewSet(viewsets.ViewSet):
    """Aggregated dashboard metrics for the response app."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """High-level dashboard overview."""
        active_qs = ResponseActivation.objects.filter(
            status__in=["ACTIVE", "ESCALATED"],
            is_deleted=False,
        )

        level_5_responses = active_qs.filter(response_level__level=5).count()
        pending_actions = ActionItem.objects.filter(
            status="PENDING", is_deleted=False
        ).count()
        overdue_actions = ActionItem.objects.filter(
            status__in=["PENDING", "IN_PROGRESS"],
            due_date__lt=timezone.now(),
            is_deleted=False,
        ).count()

        responses_by_level = dict(
            active_qs.values("response_level__level")
            .annotate(count=Count("id"))
            .values_list("response_level__level", "count")
        )

        recent_activations = list(
            active_qs.order_by("-activated_at")[:5].values(
                "id", "activation_code", "response_level__level",
                "location__name", "disease_name", "status", "activated_at",
                "completion_percentage",
            )
        )

        critical_actions = list(
            ActionItem.objects.filter(
                priority="CRITICAL",
                status__in=["PENDING", "IN_PROGRESS"],
                is_deleted=False,
            )
            .order_by("due_date")[:5]
            .values(
                "id", "title", "priority", "status",
                "due_date", "assigned_to__username",
            )
        )

        data = {
            "active_responses": active_qs.count(),
            "level_5_responses": level_5_responses,
            "pending_actions": pending_actions,
            "overdue_actions": overdue_actions,
            "responses_by_level": responses_by_level,
            "recent_activations": recent_activations,
            "critical_actions": critical_actions,
        }
        serializer = ResponseDashboardSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Aggregated statistics for all response activations."""
        base_qs = ResponseActivation.objects.filter(is_deleted=False)
        total = base_qs.count()
        active = base_qs.filter(status="ACTIVE").count()
        completed = base_qs.filter(status="COMPLETED").count()
        escalated = base_qs.filter(status="ESCALATED").count()

        # Average completion time
        completed_qs = base_qs.filter(
            status="COMPLETED",
            completed_at__isnull=False,
        ).annotate(
            duration=ExpressionWrapper(
                F("completed_at") - F("activated_at"),
                output_field=DurationField(),
            )
        )
        avg_duration = completed_qs.aggregate(avg=Avg("duration"))["avg"]
        avg_completion_hours = (
            avg_duration.total_seconds() / 3600 if avg_duration else 0.0
        )

        # Response level distribution
        by_level = dict(
            base_qs.values("response_level__level")
            .annotate(count=Count("id"))
            .values_list("response_level__level", "count")
        )

        # Action stats
        action_base = ActionItem.objects.filter(is_deleted=False)
        action_stats = {
            "total": action_base.count(),
            "completed": action_base.filter(status="COMPLETED").count(),
            "pending": action_base.filter(status="PENDING").count(),
            "overdue": action_base.filter(
                status__in=["PENDING", "IN_PROGRESS"],
                due_date__lt=timezone.now(),
            ).count(),
            "critical_open": action_base.filter(
                priority="CRITICAL",
                status__in=["PENDING", "IN_PROGRESS"],
            ).count(),
        }

        data = {
            "total_activations": total,
            "active_activations": active,
            "completed_activations": completed,
            "escalated_activations": escalated,
            "average_response_time_hours": 24.0,  # Populated by ops telemetry
            "average_completion_time_hours": round(avg_completion_hours, 2),
            "escalation_rate_pct": round((escalated / total * 100) if total else 0.0, 2),
            "completion_rate_pct": round((completed / total * 100) if total else 0.0, 2),
            "by_level": by_level,
            "action_stats": action_stats,
        }
        serializer = ResponseStatisticsSerializer(data)
        return Response(serializer.data)