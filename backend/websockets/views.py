"""
REST API views for the websockets app.

Endpoints (all require IsAuthenticated):

  GET  /ws-mgmt/groups/                    – list channel groups
  POST /ws-mgmt/groups/                    – create channel group (staff)
  GET  /ws-mgmt/groups/<pk>/               – detail
  PATCH/PUT /ws-mgmt/groups/<pk>/          – update (staff)
  DELETE /ws-mgmt/groups/<pk>/             – soft-delete (staff)
  GET  /ws-mgmt/groups/<pk>/presence/      – current room presence
  POST /ws-mgmt/groups/<pk>/replay/        – replay missed messages to caller

  GET  /ws-mgmt/connections/               – connection log (staff: all; user: own)
  GET  /ws-mgmt/broadcasts/               – broadcast log (staff: all; user: own)
"""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import AuditLog
from core.pagination import CustomPagination

from .models import BroadcastMessage, ChannelGroup, RoomPresence, WebSocketConnection
from .serializers import (
    BroadcastMessageSerializer,
    ChannelGroupSerializer,
    RoomPresenceSerializer,
    WebSocketConnectionSerializer,
)
from .utils import replay_missed_messages


# ---------------------------------------------------------------------------
# ChannelGroupViewSet
# ---------------------------------------------------------------------------

class ChannelGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = ChannelGroupSerializer
    pagination_class   = CustomPagination

    def get_queryset(self):
        return ChannelGroup.objects.filter(is_deleted=False).order_by('name')

    def perform_create(self, serializer):
        group = serializer.save()
        AuditLog.log(
            user=self.request.user,
            action='create',
            model_name='ChannelGroup',
            object_id=str(group.pk),
            details={'name': group.name},
        )

    def perform_update(self, serializer):
        group = serializer.save(update_fields=[
            *serializer.validated_data.keys(),
            'updated_at',
        ])
        AuditLog.log(
            user=self.request.user,
            action='update',
            model_name='ChannelGroup',
            object_id=str(group.pk),
            details={'fields': list(serializer.validated_data.keys())},
        )

    def perform_destroy(self, instance):
        instance.soft_delete()
        AuditLog.log(
            user=self.request.user,
            action='delete',
            model_name='ChannelGroup',
            object_id=str(instance.pk),
            details={'name': instance.name},
        )

    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Staff only.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Staff only.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Staff only.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='presence')
    def presence(self, request, pk=None):
        group = self.get_object()
        entries = RoomPresence.objects.filter(group=group).select_related('user')
        serializer = RoomPresenceSerializer(entries, many=True)
        return Response({
            'group': group.name,
            'online_count': entries.count(),
            'users': serializer.data,
        })

    @action(detail=True, methods=['post'], url_path='replay')
    def replay(self, request, pk=None):
        group    = self.get_object()
        since    = request.data.get('since')  # ISO datetime string
        if not since:
            return Response({'detail': 'since (ISO datetime) required.'}, status=status.HTTP_400_BAD_REQUEST)
        count = replay_missed_messages(request.user.pk, group.name, since)
        return Response({'replayed': count})


# ---------------------------------------------------------------------------
# WebSocketConnectionViewSet  (read-only)
# ---------------------------------------------------------------------------

class WebSocketConnectionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = WebSocketConnectionSerializer
    pagination_class   = CustomPagination

    def get_queryset(self):
        qs = WebSocketConnection.objects.select_related('user', 'group').order_by('-timestamp')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs


# ---------------------------------------------------------------------------
# BroadcastMessageViewSet  (read-only)
# ---------------------------------------------------------------------------

class BroadcastMessageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = BroadcastMessageSerializer
    pagination_class   = CustomPagination

    def get_queryset(self):
        qs = BroadcastMessage.objects.filter(is_deleted=False).select_related(
            'group', 'target_user'
        ).order_by('-created_at')
        if not self.request.user.is_staff:
            qs = qs.filter(target_user=self.request.user)
        return qs