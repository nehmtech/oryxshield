"""
Views for OryxShield integrations app.

All ViewSets:
- IsAuthenticated on every endpoint
- AuditLog on create / update / destroy
- transaction.atomic() on multi-model writes
- update_fields on targeted saves
- CustomPagination
"""
import uuid
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    ExternalSystem, DataMapping, IntegrationJob, Webhook, WebhookLog,
    APIKey, IntegrationLog, DataTransfer
)
from .serializers import (
    ExternalSystemSerializer, DataMappingSerializer, IntegrationJobSerializer,
    TriggerJobSerializer, WebhookSerializer, WebhookLogSerializer, APIKeySerializer,
    APIKeyRevokeSerializer, IntegrationLogSerializer, DataTransferSerializer
)
from core.pagination import CustomPagination

logger = logging.getLogger(__name__)


class ExternalSystemViewSet(viewsets.ModelViewSet):
    queryset = ExternalSystem.objects.filter(is_deleted=False)
    serializer_class = ExternalSystemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['system_type', 'is_active', 'health_status']
    search_fields = ['name', 'system_code', 'description']
    ordering_fields = ['name', 'created_at', 'last_sync']
    ordering = ['name']

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('CREATE_EXTERNAL_SYSTEM', instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('UPDATE_EXTERNAL_SYSTEM', instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            self._audit('DELETE_EXTERNAL_SYSTEM', instance)

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Queue a health check for this external system."""
        system = self.get_object()
        from .tasks import test_system_connection
        task = test_system_connection.delay(str(system.id))
        self._audit('TEST_CONNECTION', system, request)
        return Response({'status': 'queued', 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'])
    def trigger_sync(self, request, pk=None):
        """Immediately queue a sync job for this system."""
        system = self.get_object()
        from .tasks import _dispatch_scheduled_sync
        _dispatch_scheduled_sync(system)
        self._audit('TRIGGER_SYNC', system, request)
        return Response({'status': 'queued', 'system': system.name})

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Return sync statistics for this system."""
        system = self.get_object()
        return Response({
            'total_sync_count': system.total_sync_count,
            'successful_sync_count': system.successful_sync_count,
            'failed_sync_count': system.failed_sync_count,
            'last_sync': system.last_sync,
            'health_status': system.health_status,
            'health_message': system.health_message,
            'consecutive_failures': system.consecutive_failures,
        })

    def _audit(self, action_name, instance, request=None):
        try:
            from core.models import AuditLog
            req = request or self.request
            AuditLog.log(
                action=action_name,
                actor=req.user,
                target_object_id=str(instance.id),
                target_content_type=instance.__class__.__name__,
                detail={'name': instance.name, 'system_type': instance.system_type},
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )


class DataMappingViewSet(viewsets.ModelViewSet):
    queryset = DataMapping.objects.filter(is_deleted=False)
    serializer_class = DataMappingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['external_system', 'entity_type', 'direction', 'transform_type', 'is_active']
    search_fields = ['source_field', 'target_field', 'entity_type']
    ordering_fields = ['entity_type', 'priority', 'created_at']
    ordering = ['entity_type', 'priority']

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('CREATE_DATA_MAPPING', instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('UPDATE_DATA_MAPPING', instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            self._audit('DELETE_DATA_MAPPING', instance)

    def _audit(self, action_name, instance):
        try:
            from core.models import AuditLog
            AuditLog.log(
                action=action_name,
                actor=self.request.user,
                target_object_id=str(instance.id),
                target_content_type='DataMapping',
                detail={
                    'entity_type': instance.entity_type,
                    'source_field': instance.source_field,
                    'target_field': instance.target_field,
                },
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )


class IntegrationJobViewSet(viewsets.ModelViewSet):
    queryset = IntegrationJob.objects.filter(is_deleted=False).select_related('external_system', 'triggered_by')
    serializer_class = IntegrationJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['external_system', 'job_type', 'status', 'entity_type', 'priority']
    search_fields = ['job_id', 'entity_type']
    ordering_fields = ['created_at', 'started_at', 'priority', 'status']
    ordering = ['-created_at']

    @action(detail=False, methods=['post'])
    def trigger(self, request):
        """Create and immediately queue an integration job."""
        serializer = TriggerJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        try:
            system = ExternalSystem.objects.get(
                id=d['external_system_id'], is_deleted=False
            )
        except ExternalSystem.DoesNotExist:
            return Response({'error': 'External system not found'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            job = IntegrationJob.objects.create(
                job_id=f"JOB-{uuid.uuid4().hex[:8].upper()}",
                external_system=system,
                job_type=d['job_type'],
                entity_type=d['entity_type'],
                priority=d['priority'],
                filters=d['filters'],
                job_config=d['job_config'],
                scheduled_for=d.get('scheduled_for'),
                triggered_by=request.user,
            )
            self._audit('TRIGGER_JOB', job)

        from .tasks import process_integration_job
        task = process_integration_job.apply_async(
            args=[str(job.id)],
            countdown=0 if not job.scheduled_for else max(0, (job.scheduled_for - timezone.now()).total_seconds()),
        )

        job.celery_task_id = task.id
        job.status = 'QUEUED'
        job.save(update_fields=['celery_task_id', 'status', 'updated_at'])

        return Response(
            IntegrationJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending or running job."""
        job = self.get_object()
        if job.status in ('COMPLETED', 'FAILED', 'CANCELLED'):
            return Response(
                {'error': f"Cannot cancel job in status {job.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            job.cancel()
            self._audit('CANCEL_JOB', job)
        return Response(IntegrationJobSerializer(job).data)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Re-queue a failed or cancelled job."""
        job = self.get_object()
        if job.status not in ('FAILED', 'CANCELLED'):
            return Response(
                {'error': f"Only FAILED or CANCELLED jobs can be retried (current: {job.status})"},
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            job.status = 'QUEUED'
            job.error_log = ''
            job.retry_count += 1
            job.started_at = None
            job.completed_at = None
            job.save(update_fields=['status', 'error_log', 'retry_count', 'started_at', 'completed_at', 'updated_at'])
            self._audit('RETRY_JOB', job)

        from .tasks import process_integration_job
        task = process_integration_job.apply_async(args=[str(job.id)], countdown=0)
        job.celery_task_id = task.id
        job.save(update_fields=['celery_task_id'])
        return Response(IntegrationJobSerializer(job).data)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            self._audit('DELETE_JOB', instance)

    def _audit(self, action_name, instance):
        try:
            from core.models import AuditLog
            AuditLog.log(
                action=action_name,
                actor=self.request.user,
                target_object_id=str(instance.id),
                target_content_type='IntegrationJob',
                detail={'job_id': instance.job_id, 'job_type': instance.job_type},
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )


class WebhookViewSet(viewsets.ModelViewSet):
    queryset = Webhook.objects.filter(is_deleted=False)
    serializer_class = WebhookSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event_type', 'is_active', 'external_system']
    search_fields = ['name', 'webhook_url', 'description']
    ordering_fields = ['name', 'total_calls', 'last_triggered', 'created_at']
    ordering = ['name']

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(created_by=self.request.user)
            self._audit('CREATE_WEBHOOK', instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('UPDATE_WEBHOOK', instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            self._audit('DELETE_WEBHOOK', instance)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Send a test payload to this webhook."""
        webhook = self.get_object()
        from .tasks import trigger_webhook
        payload = {
            'event': 'test',
            'webhook_id': str(webhook.id),
            'timestamp': timezone.now().isoformat(),
            'message': 'OryxShield webhook test',
        }
        task = trigger_webhook.delay(str(webhook.id), payload)
        self._audit('TEST_WEBHOOK', webhook)
        return Response({'status': 'queued', 'task_id': task.id})

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle webhook active/inactive."""
        webhook = self.get_object()
        with transaction.atomic():
            webhook.is_active = not webhook.is_active
            webhook.save(update_fields=['is_active', 'updated_at'])
            self._audit('TOGGLE_WEBHOOK', webhook)
        return Response({'is_active': webhook.is_active})

    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """Return webhook delivery logs for this webhook."""
        webhook = self.get_object()
        qs = WebhookLog.objects.filter(webhook=webhook).order_by('-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(WebhookLogSerializer(page, many=True).data)
        return Response(WebhookLogSerializer(qs, many=True).data)

    def _audit(self, action_name, instance):
        try:
            from core.models import AuditLog
            AuditLog.log(
                action=action_name,
                actor=self.request.user,
                target_object_id=str(instance.id),
                target_content_type='Webhook',
                detail={'name': instance.name, 'event_type': instance.event_type},
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )


class WebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WebhookLog.objects.filter(is_deleted=False).select_related('webhook')
    serializer_class = WebhookLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['webhook', 'is_successful', 'event_type']
    ordering_fields = ['created_at', 'response_time_ms', 'attempt_number']
    ordering = ['-created_at']


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = APIKey.objects.filter(is_deleted=False)
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'scope', 'external_system']
    search_fields = ['name', 'description', 'key_prefix']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(owner=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(owner=self.request.user)
            self._audit('CREATE_API_KEY', instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('UPDATE_API_KEY', instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            self._audit('DELETE_API_KEY', instance)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke an API key immediately."""
        api_key = self.get_object()
        if api_key.revoked_at:
            return Response({'error': 'Key already revoked'}, status=status.HTTP_400_BAD_REQUEST)

        s = APIKeyRevokeSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        with transaction.atomic():
            api_key.is_active = False
            api_key.revoked_at = timezone.now()
            api_key.revoked_by = request.user
            api_key.revocation_reason = s.validated_data.get('reason', '')
            api_key.save(update_fields=[
                'is_active', 'revoked_at', 'revoked_by',
                'revocation_reason', 'updated_at'
            ])
            self._audit('REVOKE_API_KEY', api_key)

        return Response({'status': 'revoked', 'revoked_at': api_key.revoked_at})

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Rotate an API key — revokes current and issues a new one."""
        old_key = self.get_object()

        with transaction.atomic():
            # Revoke old
            old_key.is_active = False
            old_key.revoked_at = timezone.now()
            old_key.revoked_by = request.user
            old_key.revocation_reason = 'Rotated'
            old_key.save(update_fields=[
                'is_active', 'revoked_at', 'revoked_by', 'revocation_reason', 'updated_at'
            ])

            # Issue new
            raw, prefix, key_hash = APIKey.generate_key()
            new_key = APIKey.objects.create(
                key_prefix=prefix,
                key_hash=key_hash,
                name=f"{old_key.name} (rotated)",
                owner=old_key.owner,
                scope=old_key.scope,
                permissions=old_key.permissions,
                ip_whitelist=old_key.ip_whitelist,
                rate_limit=old_key.rate_limit,
                burst_limit=old_key.burst_limit,
                external_system=old_key.external_system,
            )
            new_key._raw_key = raw
            self._audit('ROTATE_API_KEY', new_key)

        return Response(APIKeySerializer(new_key).data, status=status.HTTP_201_CREATED)

    def _audit(self, action_name, instance):
        try:
            from core.models import AuditLog
            AuditLog.log(
                action=action_name,
                actor=self.request.user,
                target_object_id=str(instance.id),
                target_content_type='APIKey',
                detail={'name': instance.name, 'scope': instance.scope, 'prefix': instance.key_prefix},
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )


class IntegrationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IntegrationLog.objects.filter(is_deleted=False).select_related(
        'external_system', 'integration_job', 'triggered_by'
    )
    serializer_class = IntegrationLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['log_level', 'category', 'external_system', 'integration_job', 'entity_type']
    search_fields = ['message', 'operation', 'error_code']
    ordering_fields = ['created_at', 'log_level']
    ordering = ['-created_at']


class DataTransferViewSet(viewsets.ModelViewSet):
    queryset = DataTransfer.objects.filter(is_deleted=False).select_related(
        'source_system', 'target_system', 'integration_job', 'initiated_by'
    )
    serializer_class = DataTransferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'transfer_type', 'source_system', 'target_system', 'entity_type']
    search_fields = ['transfer_id', 'entity_type']
    ordering_fields = ['created_at', 'started_at', 'record_count']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        with transaction.atomic():
            transfer_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"
            instance = serializer.save(
                transfer_id=transfer_id,
                initiated_by=self.request.user
            )
            self._audit('CREATE_TRANSFER', instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            self._audit('UPDATE_TRANSFER', instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            self._audit('DELETE_TRANSFER', instance)

    def _audit(self, action_name, instance):
        try:
            from core.models import AuditLog
            AuditLog.log(
                action=action_name,
                actor=self.request.user,
                target_object_id=str(instance.id),
                target_content_type='DataTransfer',
                detail={
                    'transfer_id': instance.transfer_id,
                    'source': str(instance.source_system_id),
                    'target': str(instance.target_system_id),
                    'status': instance.status,
                },
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "integrations audit log failed for action=%s — audit entry not written",
                action_name, exc_info=True,
            )