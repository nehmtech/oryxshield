"""
Views for coordination app — OryxShield.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Q
from django.utils import timezone
import logging

from .models import (
    Agency, CoordinationTeam, TeamMembership, Task, Meeting,
    MeetingAttendance, CommunicationChannel, InformationProduct,
    CoordinationDashboard,
)
from .serializers import (
    AgencySerializer, AgencyListSerializer,
    CoordinationTeamSerializer, CoordinationTeamListSerializer,
    TeamMembershipSerializer,
    TaskSerializer, TaskListSerializer, TaskUpdateSerializer,
    MeetingSerializer, MeetingListSerializer, MeetingMinutesSerializer,
    MeetingAttendanceSerializer,
    CommunicationChannelSerializer,
    InformationProductSerializer, InformationProductListSerializer,
    CoordinationDashboardSerializer,
    CoordinationDashboardDataSerializer, CoordinationMetricsSerializer,
)
from core.pagination import CustomPagination
from core.models import AuditLog

logger = logging.getLogger(__name__)

_ACTIVE_TASK_STATUSES = ['ASSIGNED', 'ACCEPTED', 'IN_PROGRESS']


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------

class AgencyViewSet(viewsets.ModelViewSet):
    """CRUD + active-filter for Agency."""

    queryset = Agency.objects.filter(is_deleted=False).select_related('headquarters_location')
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['agency_type', 'is_active']
    search_fields = ['name', 'acronym', 'primary_contact']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        return AgencyListSerializer if self.action == 'list' else AgencySerializer

    def perform_create(self, serializer):
        agency = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='AGENCY_CREATED',
            content_type='Agency',
            object_id=str(agency.id),
            details={'name': agency.name, 'acronym': agency.acronym},
        )

    def perform_update(self, serializer):
        agency = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='AGENCY_UPDATED',
            content_type='Agency',
            object_id=str(agency.id),
            details={'name': agency.name},
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='AGENCY_DELETED',
            content_type='Agency',
            object_id=str(instance.id),
            details={'name': instance.name},
        )

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.queryset.filter(is_active=True)
        page = self.paginate_queryset(qs)
        serializer = AgencyListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# CoordinationTeam
# ---------------------------------------------------------------------------

class CoordinationTeamViewSet(viewsets.ModelViewSet):
    """CRUD + activate/deactivate + members for CoordinationTeam."""

    queryset = (
        CoordinationTeam.objects
        .filter(is_deleted=False)
        .select_related('lead_agency', 'team_leader', 'deputy_leader')
        .prefetch_related('memberships__agency', 'memberships__primary_representative')
    )
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['team_type', 'is_active', 'lead_agency']
    search_fields = ['name', 'code', 'mandate']
    ordering_fields = ['activated_at', 'name']
    ordering = ['-activated_at']

    def get_serializer_class(self):
        return CoordinationTeamListSerializer if self.action == 'list' else CoordinationTeamSerializer

    def perform_create(self, serializer):
        team = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='COORDINATION_TEAM_CREATED',
            content_type='CoordinationTeam',
            object_id=str(team.id),
            details={'name': team.name, 'code': team.code},
        )

    def perform_update(self, serializer):
        team = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='COORDINATION_TEAM_UPDATED',
            content_type='CoordinationTeam',
            object_id=str(team.id),
            details={'name': team.name, 'code': team.code},
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='COORDINATION_TEAM_DELETED',
            content_type='CoordinationTeam',
            object_id=str(instance.id),
            details={'name': instance.name},
        )

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.queryset.filter(is_active=True)
        page = self.paginate_queryset(qs)
        serializer = CoordinationTeamListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        team = self.get_object()
        if team.is_active:
            return Response({'detail': 'Team is already active.'}, status=status.HTTP_400_BAD_REQUEST)
        team.activate(activated_by=request.user)
        return Response(CoordinationTeamSerializer(team).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        team = self.get_object()
        if not team.is_active:
            return Response({'detail': 'Team is already inactive.'}, status=status.HTTP_400_BAD_REQUEST)
        team.deactivate(deactivated_by=request.user)
        return Response(CoordinationTeamSerializer(team).data)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        team = self.get_object()
        memberships = team.memberships.filter(is_active=True).select_related(
            'agency', 'primary_representative', 'alternate_representative'
        )
        serializer = TeamMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='members/add')
    def add_member(self, request, pk=None):
        team = self.get_object()
        serializer = TeamMembershipSerializer(data={**request.data, 'team': team.id})
        serializer.is_valid(raise_exception=True)
        membership = serializer.save(team=team)
        AuditLog.log(
            user=request.user,
            action='TEAM_MEMBER_ADDED',
            content_type='TeamMembership',
            object_id=str(membership.id),
            details={'team': team.code, 'agency': membership.agency.acronym},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# TeamMembership
# ---------------------------------------------------------------------------

class TeamMembershipViewSet(viewsets.ModelViewSet):
    """CRUD for TeamMembership — used by the /coordination/memberships/ endpoint."""

    queryset = TeamMembership.objects.filter(is_deleted=False).select_related(
        'team', 'agency', 'primary_representative', 'alternate_representative'
    )
    serializer_class = TeamMembershipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['team', 'agency', 'is_active']
    search_fields = ['agency__name', 'team__name', 'role']
    ordering_fields = ['created_at', 'team__name']
    ordering = ['-created_at']

    http_method_names = ['get', 'patch', 'delete', 'head', 'options']


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskViewSet(viewsets.ModelViewSet):
    """CRUD + progress update + my_tasks + overdue for Task."""

    queryset = (
        Task.objects
        .filter(is_deleted=False)
        .select_related('coordination_team', 'assigned_to_agency', 'assigned_to_user', 'assigned_by')
    )
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'coordination_team', 'assigned_to_agency']
    search_fields = ['title', 'description']
    ordering_fields = ['due_date', 'priority', 'created_at']
    ordering = ['-priority', 'due_date']

    def get_serializer_class(self):
        return TaskListSerializer if self.action == 'list' else TaskSerializer

    def perform_create(self, serializer):
        task = serializer.save(assigned_by=self.request.user)
        AuditLog.log(
            user=self.request.user,
            action='TASK_CREATED',
            content_type='Task',
            object_id=str(task.id),
            details={
                'title': task.title,
                'priority': task.priority,
                'agency': str(task.assigned_to_agency_id),
                'due_date': str(task.due_date),
            },
        )

    def perform_update(self, serializer):
        task = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='TASK_UPDATED',
            content_type='Task',
            object_id=str(task.id),
            details={'title': task.title, 'status': task.status},
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='TASK_DELETED',
            content_type='Task',
            object_id=str(instance.id),
            details={'title': instance.title},
        )

    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        qs = self.queryset.filter(assigned_to_user=request.user)
        page = self.paginate_queryset(qs)
        serializer = TaskListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        qs = self.queryset.filter(
            status__in=_ACTIVE_TASK_STATUSES,
            due_date__lt=timezone.now()
        )
        page = self.paginate_queryset(qs)
        serializer = TaskListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def critical(self, request):
        qs = self.queryset.filter(priority='CRITICAL', status__in=_ACTIVE_TASK_STATUSES)
        page = self.paginate_queryset(qs)
        serializer = TaskListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_progress(self, request, pk=None):
        task = self.get_object()
        serializer = TaskUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_fields = ['updated_at']
        for field, value in serializer.validated_data.items():
            setattr(task, field, value)
            update_fields.append(field)

        # Status-driven side effects
        if task.status == Task.Status.IN_PROGRESS and not task.started_at:
            task.started_at = timezone.now()
            update_fields.append('started_at')
        if task.status == Task.Status.COMPLETED and not task.completed_at:
            task.progress_percentage = 100
            task.completed_at = timezone.now()
            update_fields.extend(['progress_percentage', 'completed_at'])

        task.save(update_fields=list(set(update_fields)))
        AuditLog.log(
            user=request.user,
            action='TASK_PROGRESS_UPDATED',
            content_type='Task',
            object_id=str(task.id),
            details={
                'title': task.title,
                'status': task.status,
                'progress_percentage': task.progress_percentage,
            },
        )
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.ASSIGNED:
            return Response(
                {'detail': f'Cannot accept a task with status {task.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.accept(accepted_by=request.user)
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        if task.status not in (Task.Status.IN_PROGRESS, Task.Status.ACCEPTED):
            return Response(
                {'detail': f'Cannot complete a task with status {task.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        notes = request.data.get('notes', '')
        task.complete(completed_by=request.user, notes=notes)
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        task = self.get_object()
        if task.status not in (Task.Status.ACCEPTED, Task.Status.ASSIGNED):
            return Response(
                {'detail': f'Cannot start a task with status {task.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.start(started_by=request.user)
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        task = self.get_object()
        if task.status in (Task.Status.COMPLETED, Task.Status.CANCELLED):
            return Response(
                {'detail': f'Cannot cancel a task with status {task.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        reason = request.data.get('reason', '')
        task.cancel(cancelled_by=request.user, reason=reason)
        return Response(TaskSerializer(task).data)


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

class MeetingViewSet(viewsets.ModelViewSet):
    """CRUD + commence/close/cancel + minutes + attendance for Meeting."""

    queryset = (
        Meeting.objects
        .filter(is_deleted=False)
        .select_related('coordination_team', 'chair', 'secretary')
        .prefetch_related('attendances__attendee', 'attendances__representing_agency')
    )
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['meeting_type', 'status', 'coordination_team', 'is_virtual']
    search_fields = ['title']
    ordering_fields = ['scheduled_start']
    ordering = ['-scheduled_start']

    def get_serializer_class(self):
        return MeetingListSerializer if self.action == 'list' else MeetingSerializer

    def perform_create(self, serializer):
        meeting = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='MEETING_CREATED',
            content_type='Meeting',
            object_id=str(meeting.id),
            details={
                'title': meeting.title,
                'type': meeting.meeting_type,
                'scheduled_start': str(meeting.scheduled_start),
            },
        )

    def perform_update(self, serializer):
        meeting = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='MEETING_UPDATED',
            content_type='Meeting',
            object_id=str(meeting.id),
            details={'title': meeting.title},
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='MEETING_DELETED',
            content_type='Meeting',
            object_id=str(instance.id),
            details={'title': instance.title},
        )

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        qs = self.queryset.filter(
            status='SCHEDULED',
            scheduled_start__gte=timezone.now()
        ).order_by('scheduled_start')
        page = self.paginate_queryset(qs)
        serializer = MeetingListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def commence(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status != Meeting.MeetingStatus.SCHEDULED:
            return Response(
                {'detail': f'Cannot commence meeting with status {meeting.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        meeting.commence(commenced_by=request.user)
        return Response(MeetingSerializer(meeting).data)

    @action(detail=True, methods=['post'])
    def add_minutes(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status not in (Meeting.MeetingStatus.IN_PROGRESS, Meeting.MeetingStatus.SCHEDULED):
            return Response(
                {'detail': f'Cannot add minutes to meeting with status {meeting.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = MeetingMinutesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meeting.close(
            closed_by=request.user,
            minutes=serializer.validated_data['minutes'],
            decisions=serializer.validated_data.get('decisions_made', []),
            action_points=serializer.validated_data.get('action_points', []),
        )
        return Response(MeetingSerializer(meeting).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a meeting, optionally recording minutes."""
        meeting = self.get_object()
        if meeting.status == Meeting.MeetingStatus.COMPLETED:
            return Response(
                {'detail': 'Meeting is already completed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        minutes = request.data.get('minutes', '')
        decisions = request.data.get('decisions', [])
        action_points = request.data.get('action_points', [])
        meeting.close(
            closed_by=request.user,
            minutes=minutes,
            decisions=decisions,
            action_points=action_points,
        )
        return Response(MeetingSerializer(meeting).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status in (Meeting.MeetingStatus.COMPLETED, Meeting.MeetingStatus.CANCELLED):
            return Response(
                {'detail': f'Cannot cancel meeting with status {meeting.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        reason = request.data.get('reason', '')
        meeting.cancel(cancelled_by=request.user, reason=reason)
        return Response(MeetingSerializer(meeting).data)

    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        meeting = self.get_object()
        records = meeting.attendances.select_related('attendee', 'representing_agency')
        serializer = MeetingAttendanceSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='attendance/record')
    def record_attendance(self, request, pk=None):
        meeting = self.get_object()
        data = {**request.data, 'meeting': meeting.id}
        serializer = MeetingAttendanceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(meeting=meeting)
        AuditLog.log(
            user=request.user,
            action='MEETING_ATTENDANCE_RECORDED',
            content_type='MeetingAttendance',
            object_id=str(record.id),
            details={
                'meeting': meeting.title,
                'attendee': record.attendee.username,
                'status': record.status,
            },
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# CommunicationChannel
# ---------------------------------------------------------------------------

class CommunicationChannelViewSet(viewsets.ModelViewSet):
    """CRUD for CommunicationChannel."""

    queryset = CommunicationChannel.objects.filter(is_deleted=False).select_related('coordination_team')
    serializer_class = CommunicationChannelSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['channel_type', 'coordination_team', 'is_active', 'is_primary']
    search_fields = ['name']

    def perform_create(self, serializer):
        channel = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='COMM_CHANNEL_CREATED',
            content_type='CommunicationChannel',
            object_id=str(channel.id),
            details={'name': channel.name, 'type': channel.channel_type},
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='COMM_CHANNEL_DELETED',
            content_type='CommunicationChannel',
            object_id=str(instance.id),
            details={'name': instance.name},
        )


# ---------------------------------------------------------------------------
# InformationProduct
# ---------------------------------------------------------------------------

class InformationProductViewSet(viewsets.ModelViewSet):
    """CRUD + current-filter + supersede for InformationProduct."""

    queryset = (
        InformationProduct.objects
        .filter(is_deleted=False)
        .select_related('coordination_team', 'produced_by_agency', 'author')
    )
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product_type', 'is_current', 'coordination_team', 'is_public']
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['effective_date', 'created_at']
    ordering = ['-effective_date']

    def get_serializer_class(self):
        return InformationProductListSerializer if self.action == 'list' else InformationProductSerializer

    def perform_create(self, serializer):
        product = serializer.save(author=self.request.user)
        AuditLog.log(
            user=self.request.user,
            action='INFO_PRODUCT_CREATED',
            content_type='InformationProduct',
            object_id=str(product.id),
            details={
                'title': product.title,
                'type': product.product_type,
                'version': product.version,
            },
        )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        AuditLog.log(
            user=self.request.user,
            action='INFO_PRODUCT_DELETED',
            content_type='InformationProduct',
            object_id=str(instance.id),
            details={'title': instance.title},
        )

    @action(detail=False, methods=['get'])
    def current(self, request):
        qs = self.queryset.filter(is_current=True)
        page = self.paginate_queryset(qs)
        serializer = InformationProductListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def supersede(self, request, pk=None):
        """Mark this product as superseded by a newer product (by id)."""
        old_product = self.get_object()
        new_id = request.data.get('new_product_id')
        if not new_id:
            return Response({'detail': 'new_product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            new_product = InformationProduct.objects.get(id=new_id, is_deleted=False)
        except InformationProduct.DoesNotExist:
            return Response({'detail': 'New product not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_product.supersede_with(new_product=new_product, updated_by=request.user)
        return Response(InformationProductSerializer(old_product).data)

    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Increment download count and return the file URL."""
        product = self.get_object()
        if not product.file_url:
            return Response({'detail': 'No file attached to this product.'}, status=status.HTTP_404_NOT_FOUND)
        product.download_count = F('download_count') + 1
        product.save(update_fields=['download_count'])
        return Response({'file_url': product.file_url, 'title': product.title})


# ---------------------------------------------------------------------------
# CoordinationDashboard
# ---------------------------------------------------------------------------

class CoordinationDashboardViewSet(viewsets.ViewSet):
    """Aggregate coordination metrics and per-team dashboards."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """System-wide coordination overview."""
        active_teams = CoordinationTeam.objects.filter(is_active=True, is_deleted=False).count()
        active_tasks = Task.objects.filter(
            status__in=_ACTIVE_TASK_STATUSES, is_deleted=False
        ).count()
        overdue_tasks = Task.objects.filter(
            status__in=_ACTIVE_TASK_STATUSES,
            due_date__lt=timezone.now(),
            is_deleted=False
        ).count()
        upcoming_meetings = Meeting.objects.filter(
            status='SCHEDULED',
            scheduled_start__gte=timezone.now(),
            is_deleted=False
        ).count()

        tasks_by_priority = dict(
            Task.objects.filter(status__in=_ACTIVE_TASK_STATUSES, is_deleted=False)
            .values('priority')
            .annotate(count=Count('id'))
            .values_list('priority', 'count')
        )

        tasks_by_agency = list(
            Task.objects.filter(status__in=_ACTIVE_TASK_STATUSES, is_deleted=False)
            .values('assigned_to_agency__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        recent_products = list(
            InformationProduct.objects.filter(is_current=True, is_deleted=False)
            .order_by('-effective_date')[:5]
            .values('id', 'title', 'product_type', 'effective_date')
        )

        critical_tasks = list(
            Task.objects.filter(
                priority='CRITICAL',
                status__in=_ACTIVE_TASK_STATUSES,
                is_deleted=False
            ).order_by('due_date')[:10].values(
                'id', 'title', 'due_date', 'assigned_to_agency__name', 'progress_percentage'
            )
        )

        teams_summary = list(
            CoordinationTeam.objects.filter(is_active=True, is_deleted=False)
            .annotate(
                task_count=Count('tasks', filter=Q(tasks__is_deleted=False)),
            )
            .values('id', 'name', 'code', 'team_type', 'task_count')
            .order_by('-task_count')[:10]
        )

        data = {
            'active_teams': active_teams,
            'active_tasks': active_tasks,
            'overdue_tasks': overdue_tasks,
            'upcoming_meetings': upcoming_meetings,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_agency': tasks_by_agency,
            'recent_products': recent_products,
            'critical_tasks': critical_tasks,
            'teams_summary': teams_summary,
        }
        serializer = CoordinationDashboardDataSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Aggregate coordination metrics."""
        total_tasks = Task.objects.filter(is_deleted=False).count()
        completed_tasks = Task.objects.filter(status='COMPLETED', is_deleted=False).count()
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0, 2)

        # Average task duration in hours for completed tasks that have start + end
        avg_duration_result = (
            Task.objects.filter(status='COMPLETED', started_at__isnull=False,
                                completed_at__isnull=False, is_deleted=False)
            .annotate(duration=ExpressionWrapper(
                F('completed_at') - F('started_at'),
                output_field=DurationField()
            ))
            .aggregate(avg_dur=Avg('duration'))
        )
        raw_avg = avg_duration_result.get('avg_dur')
        avg_hours = round(raw_avg.total_seconds() / 3600, 2) if raw_avg else 0.0

        overdue_tasks = Task.objects.filter(
            status__in=_ACTIVE_TASK_STATUSES,
            due_date__lt=timezone.now(),
            is_deleted=False
        ).count()
        critical_overdue = Task.objects.filter(
            priority='CRITICAL',
            status__in=_ACTIVE_TASK_STATUSES,
            due_date__lt=timezone.now(),
            is_deleted=False
        ).count()

        data = {
            'total_teams': CoordinationTeam.objects.filter(is_deleted=False).count(),
            'total_agencies': Agency.objects.filter(is_deleted=False).count(),
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'task_completion_rate': completion_rate,
            'average_task_duration_hours': avg_hours,
            'meetings_held': Meeting.objects.filter(status='COMPLETED', is_deleted=False).count(),
            'information_products_shared': InformationProduct.objects.filter(is_deleted=False).count(),
            'overdue_tasks': overdue_tasks,
            'critical_overdue_tasks': critical_overdue,
        }
        serializer = CoordinationMetricsSerializer(data)
        return Response(serializer.data)