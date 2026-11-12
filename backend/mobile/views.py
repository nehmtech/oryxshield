"""
Views for mobile app — OryxShield.

All ViewSets:
- Write AuditLog on create / update / delete.
- Use transaction.atomic() for multi-model writes.
- Use update_fields on targeted saves.
- Soft-delete only (is_deleted=True).
"""
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from core.models import AuditLog
from core.pagination import CustomPagination

from .models import (
    MobileDevice, OfflineData, FieldWorker, FieldActivity, MobileSurvey,
    SurveyResponse, DataCollectionForm, FormSubmission, MobileNotification,
)
from .serializers import (
    MobileDeviceSerializer, MobileDeviceLocationSerializer,
    OfflineDataSerializer, SyncRequestSerializer,
    FieldWorkerSerializer, FieldWorkerLocationSerializer,
    FieldActivitySerializer,
    MobileSurveySerializer,
    SurveyResponseSerializer,
    DataCollectionFormSerializer,
    FormSubmissionSerializer,
    MobileNotificationSerializer, BulkNotificationSerializer,
)


def _audit(request, action, model, object_id, detail=None):
    AuditLog.log(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=model,
        object_id=str(object_id),
        detail=detail or {},
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )


# ---------------------------------------------------------------------------
# MobileDevice
# ---------------------------------------------------------------------------

class MobileDeviceViewSet(viewsets.ModelViewSet):
    """
    CRUD for mobile devices.
    Each user sees only their own devices.
    """
    serializer_class = MobileDeviceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['device_type', 'is_active']
    search_fields = ['device_id', 'device_name']

    def get_queryset(self):
        return MobileDevice.objects.filter(
            user=self.request.user, is_deleted=False
        ).select_related('user')

    def perform_create(self, serializer):
        with transaction.atomic():
            device = serializer.save(user=self.request.user)
            _audit(self.request, 'CREATE', 'MobileDevice', device.pk,
                   {'device_id': device.device_id})

    def perform_update(self, serializer):
        with transaction.atomic():
            device = serializer.save()
            _audit(self.request, 'UPDATE', 'MobileDevice', device.pk,
                   {'device_id': device.device_id})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'MobileDevice', instance.pk,
                   {'device_id': instance.device_id})

    @action(detail=True, methods=['post'], url_path='update-location')
    def update_location(self, request, pk=None):
        """Update the device's last known location."""
        device = self.get_object()
        serializer = MobileDeviceLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device.update_location(
            serializer.validated_data['latitude'],
            serializer.validated_data['longitude'],
        )
        _audit(request, 'UPDATE', 'MobileDevice', device.pk,
               {'action': 'location_update'})
        return Response({'status': 'Location updated.'})

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """Deactivate a device (revokes push notifications)."""
        device = self.get_object()
        with transaction.atomic():
            device.is_active = False
            device.fcm_token = ''
            device.apns_token = ''
            device.save(update_fields=['is_active', 'fcm_token', 'apns_token', 'updated_at'])
            _audit(request, 'UPDATE', 'MobileDevice', device.pk, {'action': 'deactivate'})
        return Response({'status': 'Device deactivated.'})


# ---------------------------------------------------------------------------
# OfflineData
# ---------------------------------------------------------------------------

class OfflineDataViewSet(viewsets.ModelViewSet):
    """Offline data sync queue — filtered to the requesting user's devices."""

    serializer_class = OfflineDataSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sync_status', 'data_type']

    def get_queryset(self):
        return OfflineData.objects.filter(
            device__user=self.request.user, is_deleted=False
        ).select_related('device')

    def perform_create(self, serializer):
        with transaction.atomic():
            item = serializer.save()
            _audit(self.request, 'CREATE', 'OfflineData', item.pk,
                   {'data_type': item.data_type})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'OfflineData', instance.pk, {})

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """
        Accept a batch of offline records, enqueue async processing.
        Returns a Celery task_id for polling.
        """
        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import process_offline_sync
        task = process_offline_sync.delay(
            serializer.validated_data['device_id'],
            [
                {
                    'data_type': item['data_type'],
                    'payload': item['payload'],
                    'created_at': item['created_at'].isoformat(),
                }
                for item in serializer.validated_data['pending_data']
            ],
        )
        _audit(request, 'SYNC', 'OfflineData', 0,
               {'device_id': serializer.validated_data['device_id'], 'task_id': task.id})
        return Response(
            {'status': 'Sync queued.', 'task_id': task.id},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# FieldWorker
# ---------------------------------------------------------------------------

class FieldWorkerViewSet(viewsets.ModelViewSet):
    """CRUD for field workers."""

    serializer_class = FieldWorkerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['worker_type', 'assigned_location', 'is_active']
    search_fields = ['worker_id', 'user__first_name', 'user__last_name', 'phone_number']

    def get_queryset(self):
        return FieldWorker.objects.filter(
            is_deleted=False
        ).select_related('user', 'assigned_location').prefetch_related('coverage_areas')

    def perform_create(self, serializer):
        with transaction.atomic():
            worker = serializer.save()
            _audit(self.request, 'CREATE', 'FieldWorker', worker.pk,
                   {'worker_id': worker.worker_id, 'worker_type': worker.worker_type})

    def perform_update(self, serializer):
        with transaction.atomic():
            worker = serializer.save()
            _audit(self.request, 'UPDATE', 'FieldWorker', worker.pk,
                   {'worker_id': worker.worker_id})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            _audit(self.request, 'DELETE', 'FieldWorker', instance.pk,
                   {'worker_id': instance.worker_id})

    @action(detail=True, methods=['post'], url_path='update-location')
    def update_location(self, request, pk=None):
        """Update field worker's current GPS position."""
        worker = self.get_object()
        serializer = FieldWorkerLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker.update_location(
            serializer.validated_data['latitude'],
            serializer.validated_data['longitude'],
        )
        _audit(request, 'UPDATE', 'FieldWorker', worker.pk,
               {'action': 'location_update', 'worker_id': worker.worker_id})
        return Response({'status': 'Location updated.'})

    @action(detail=True, methods=['get'], url_path='performance')
    def performance(self, request, pk=None):
        """Return performance counters for a field worker."""
        worker = self.get_object()
        return Response({
            'worker_id': worker.worker_id,
            'cases_managed': worker.cases_managed,
            'contacts_traced': worker.contacts_traced,
            'surveys_completed': worker.surveys_completed,
            'activities_logged': worker.activities_logged,
        })


# ---------------------------------------------------------------------------
# FieldActivity
# ---------------------------------------------------------------------------

class FieldActivityViewSet(viewsets.ModelViewSet):
    """Record and list field activities."""

    serializer_class = FieldActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activity_type', 'field_worker', 'location', 'activity_date']
    search_fields = ['activity_id', 'description']
    ordering_fields = ['activity_date', 'people_reached', 'created_at']

    def get_queryset(self):
        return FieldActivity.objects.filter(
            is_deleted=False
        ).select_related('field_worker__user', 'location')

    def perform_create(self, serializer):
        with transaction.atomic():
            activity = serializer.save()
            # Atomically increment field worker counter
            activity.field_worker.increment_counter('activities_logged')
            _audit(self.request, 'CREATE', 'FieldActivity', activity.pk,
                   {'activity_id': activity.activity_id, 'type': activity.activity_type})

    def perform_update(self, serializer):
        with transaction.atomic():
            activity = serializer.save()
            _audit(self.request, 'UPDATE', 'FieldActivity', activity.pk,
                   {'activity_id': activity.activity_id})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'FieldActivity', instance.pk,
                   {'activity_id': instance.activity_id})


# ---------------------------------------------------------------------------
# MobileSurvey
# ---------------------------------------------------------------------------

class MobileSurveyViewSet(viewsets.ModelViewSet):
    """Manage mobile surveys."""

    serializer_class = MobileSurveySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['survey_type', 'is_active']
    search_fields = ['title', 'survey_code']

    def get_queryset(self):
        return MobileSurvey.objects.filter(
            is_deleted=False
        ).select_related('created_by').prefetch_related('responses', 'target_locations')

    def perform_create(self, serializer):
        with transaction.atomic():
            survey = serializer.save(created_by=self.request.user)
            _audit(self.request, 'CREATE', 'MobileSurvey', survey.pk,
                   {'survey_code': survey.survey_code})

    def perform_update(self, serializer):
        with transaction.atomic():
            survey = serializer.save()
            _audit(self.request, 'UPDATE', 'MobileSurvey', survey.pk,
                   {'survey_code': survey.survey_code})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            _audit(self.request, 'DELETE', 'MobileSurvey', instance.pk,
                   {'survey_code': instance.survey_code})

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """
        Return all responses for a survey as a flat list.
        Intended for data export and analysis.
        """
        survey = self.get_object()
        responses = SurveyResponse.objects.filter(
            survey=survey, is_deleted=False
        ).select_related('field_worker__user', 'location').order_by('-response_date')
        serializer = SurveyResponseSerializer(responses, many=True)
        return Response({
            'survey': survey.survey_code,
            'total': responses.count(),
            'results': serializer.data,
        })


# ---------------------------------------------------------------------------
# SurveyResponse
# ---------------------------------------------------------------------------

class SurveyResponseViewSet(viewsets.ModelViewSet):
    """Submit and retrieve survey responses."""

    serializer_class = SurveyResponseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['survey', 'field_worker', 'location', 'response_date']
    ordering_fields = ['response_date', 'created_at']

    def get_queryset(self):
        return SurveyResponse.objects.filter(
            is_deleted=False
        ).select_related('survey', 'field_worker__user', 'location')

    def perform_create(self, serializer):
        with transaction.atomic():
            response = serializer.save()
            if response.field_worker:
                response.field_worker.increment_counter('surveys_completed')
            if response.created_offline:
                response.synced_at = timezone.now()
                response.save(update_fields=['synced_at'])
            _audit(self.request, 'CREATE', 'SurveyResponse', response.pk,
                   {'response_id': response.response_id, 'survey': response.survey.survey_code})

    def perform_update(self, serializer):
        with transaction.atomic():
            response = serializer.save()
            _audit(self.request, 'UPDATE', 'SurveyResponse', response.pk,
                   {'response_id': response.response_id})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'SurveyResponse', instance.pk,
                   {'response_id': instance.response_id})


# ---------------------------------------------------------------------------
# DataCollectionForm
# ---------------------------------------------------------------------------

class DataCollectionFormViewSet(viewsets.ModelViewSet):
    """Manage data collection forms."""

    serializer_class = DataCollectionFormSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['form_type', 'is_active']
    search_fields = ['title', 'form_code']

    def get_queryset(self):
        return DataCollectionForm.objects.filter(
            is_deleted=False
        ).select_related('created_by')

    def perform_create(self, serializer):
        with transaction.atomic():
            form = serializer.save(created_by=self.request.user)
            _audit(self.request, 'CREATE', 'DataCollectionForm', form.pk,
                   {'form_code': form.form_code})

    def perform_update(self, serializer):
        with transaction.atomic():
            form = serializer.save()
            _audit(self.request, 'UPDATE', 'DataCollectionForm', form.pk,
                   {'form_code': form.form_code})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.is_active = False
            instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            _audit(self.request, 'DELETE', 'DataCollectionForm', instance.pk,
                   {'form_code': instance.form_code})


# ---------------------------------------------------------------------------
# FormSubmission
# ---------------------------------------------------------------------------

class FormSubmissionViewSet(viewsets.ModelViewSet):
    """Submit and retrieve data collection form submissions."""

    serializer_class = FormSubmissionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['form', 'field_worker', 'is_validated', 'submission_date']
    ordering_fields = ['submission_date', 'created_at']

    def get_queryset(self):
        return FormSubmission.objects.filter(
            is_deleted=False
        ).select_related('form', 'field_worker__user', 'location')

    def perform_create(self, serializer):
        with transaction.atomic():
            submission = serializer.save()
            is_valid, errors = submission.validate_against_form()
            if submission.created_offline:
                submission.synced_at = timezone.now()
                submission.save(update_fields=['synced_at'])
            _audit(self.request, 'CREATE', 'FormSubmission', submission.pk, {
                'submission_id': submission.submission_id,
                'form': submission.form.form_code,
                'is_validated': is_valid,
            })

    def perform_update(self, serializer):
        with transaction.atomic():
            submission = serializer.save()
            submission.validate_against_form()
            _audit(self.request, 'UPDATE', 'FormSubmission', submission.pk,
                   {'submission_id': submission.submission_id})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'FormSubmission', instance.pk,
                   {'submission_id': instance.submission_id})

    @action(detail=True, methods=['post'], url_path='validate')
    def validate(self, request, pk=None):
        """Re-run server-side validation on an existing submission."""
        submission = self.get_object()
        is_valid, errors = submission.validate_against_form()
        _audit(request, 'VALIDATE', 'FormSubmission', submission.pk,
               {'is_valid': is_valid, 'error_count': len(errors)})
        return Response({
            'submission_id': submission.submission_id,
            'is_validated': is_valid,
            'validation_errors': errors,
        })


# ---------------------------------------------------------------------------
# MobileNotification
# ---------------------------------------------------------------------------

class MobileNotificationViewSet(viewsets.ModelViewSet):
    """Push notifications — users see only their own."""

    serializer_class = MobileNotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'is_sent', 'is_read']
    ordering_fields = ['created_at', 'priority']

    def get_queryset(self):
        return MobileNotification.objects.filter(
            user=self.request.user, is_deleted=False
        ).select_related('device')

    def perform_create(self, serializer):
        with transaction.atomic():
            notification = serializer.save(user=self.request.user)
            _audit(self.request, 'CREATE', 'MobileNotification', notification.pk,
                   {'notification_id': notification.notification_id,
                    'type': notification.notification_type})

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
            _audit(self.request, 'DELETE', 'MobileNotification', instance.pk,
                   {'notification_id': instance.notification_id})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at', 'updated_at'])
        return Response({'status': 'Marked as read.'})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all unread notifications for the current user as read."""
        now = timezone.now()
        updated = MobileNotification.objects.filter(
            user=request.user, is_read=False, is_deleted=False
        ).update(is_read=True, read_at=now)
        return Response({'status': f'{updated} notifications marked as read.'})

    @action(detail=False, methods=['post'], url_path='bulk-send',
            permission_classes=[IsAuthenticated])
    def bulk_send(self, request):
        """
        Create a notification for multiple users at once.
        Admin / staff only.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff may send bulk notifications.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.contrib.auth.models import User as DjangoUser
        import uuid

        users = DjangoUser.objects.filter(pk__in=data['user_ids'], is_active=True)
        if not users.exists():
            return Response(
                {'detail': 'No active users found for the given IDs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notifications = []
        for user in users:
            notifications.append(MobileNotification(
                notification_id=f"NOTIF-{uuid.uuid4().hex[:12].upper()}",
                user=user,
                notification_type=data['notification_type'],
                priority=data['priority'],
                title=data['title'],
                body=data['body'],
                action_url=data['action_url'],
                action_data=data['action_data'],
                expires_at=data['expires_at'],
            ))

        with transaction.atomic():
            MobileNotification.objects.bulk_create(notifications)
            _audit(request, 'BULK_CREATE', 'MobileNotification', 0, {
                'count': len(notifications),
                'type': data['notification_type'],
            })

        from .tasks import send_push_notifications
        send_push_notifications.delay()

        return Response(
            {'status': f'{len(notifications)} notifications created.'},
            status=status.HTTP_201_CREATED,
        )