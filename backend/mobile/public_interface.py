"""
Public interface for mobile app — OryxShield.

Exposes:
- CHW dashboard endpoint
- Delta-sync endpoint (pull updates since last_sync)
- Worker proximity search
- Async validation task for form submissions
"""
import logging
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .chw_tools import build_chw_dashboard, get_worker_tasks, workers_near_location
from .sync_engine import SyncEngine, ConflictStrategy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CHW Dashboard
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chw_dashboard(request):
    """
    Return the mobile home-screen dashboard for the authenticated CHW.

    GET /api/v1/mobile/dashboard/
    """
    from .models import FieldWorker

    try:
        worker = FieldWorker.objects.get(user=request.user, is_deleted=False)
    except FieldWorker.DoesNotExist:
        return Response(
            {'detail': 'No FieldWorker profile found for this user.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    data = build_chw_dashboard(worker.pk)
    return Response(data)


# ---------------------------------------------------------------------------
# Worker task list
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chw_tasks(request):
    """
    Return outstanding tasks for the authenticated CHW.

    GET /api/v1/mobile/tasks/
    """
    from .models import FieldWorker

    try:
        worker = FieldWorker.objects.get(user=request.user, is_deleted=False)
    except FieldWorker.DoesNotExist:
        return Response(
            {'detail': 'No FieldWorker profile found for this user.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    tasks = get_worker_tasks(worker.pk)
    return Response({'count': len(tasks), 'tasks': tasks})


# ---------------------------------------------------------------------------
# Delta sync (pull)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def delta_sync(request):
    """
    Return server-side records updated since `last_sync`.

    GET /api/v1/mobile/delta/?device_id=abc123&last_sync=2026-01-01T00:00:00Z
    """
    device_id = request.query_params.get('device_id', '').strip()
    last_sync_str = request.query_params.get('last_sync', '').strip()

    if not device_id:
        return Response(
            {'detail': "'device_id' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not last_sync_str:
        return Response(
            {'detail': "'last_sync' query parameter is required (ISO 8601)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        last_sync = datetime.fromisoformat(last_sync_str.replace('Z', '+00:00'))
    except ValueError:
        return Response(
            {'detail': "'last_sync' must be a valid ISO 8601 datetime."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify device belongs to the requesting user
    from .models import MobileDevice
    if not MobileDevice.objects.filter(
        device_id=device_id, user=request.user, is_deleted=False
    ).exists():
        return Response(
            {'detail': 'Device not found or not registered to this account.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    engine = SyncEngine(device_id=device_id)
    delta = engine.get_delta(last_sync)

    return Response({
        'device_id': device_id,
        'last_sync': last_sync_str,
        'server_time': timezone.now().isoformat(),
        'delta': delta,
    })


# ---------------------------------------------------------------------------
# Proximity search
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nearby_workers(request):
    """
    Return field workers within a radius of the given coordinates.

    GET /api/v1/mobile/nearby-workers/?lat=-1.286&lng=36.817&radius_km=5
    """
    try:
        lat = float(request.query_params.get('lat', ''))
        lng = float(request.query_params.get('lng', ''))
    except (TypeError, ValueError):
        return Response(
            {'detail': "'lat' and 'lng' query parameters are required and must be numeric."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        radius_km = float(request.query_params.get('radius_km', 5.0))
    except ValueError:
        radius_km = 5.0

    if not (-90 <= lat <= 90):
        return Response(
            {'detail': "'lat' must be between -90 and 90."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (-180 <= lng <= 180):
        return Response(
            {'detail': "'lng' must be between -180 and 180."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    workers = workers_near_location(lat, lng, radius_km)
    return Response({
        'centre': {'latitude': lat, 'longitude': lng},
        'radius_km': radius_km,
        'count': len(workers),
        'workers': workers,
    })


# ---------------------------------------------------------------------------
# Async form validation (Celery task)
# ---------------------------------------------------------------------------

from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def validate_form_submission_async(self, submission_pk: int) -> dict:
    """
    Run server-side validation on a FormSubmission asynchronously.
    Called automatically by signals for offline submissions.
    """
    from .models import FormSubmission

    try:
        submission = FormSubmission.objects.select_related('form').get(pk=submission_pk)
    except FormSubmission.DoesNotExist:
        logger.warning("validate_form_submission_async: submission %s not found.", submission_pk)
        return {'status': 'error', 'message': 'Submission not found.'}

    try:
        is_valid, errors = submission.validate_against_form()
        logger.info(
            "validate_form_submission_async: submission %s valid=%s errors=%d",
            submission.submission_id, is_valid, len(errors),
        )
        return {
            'status': 'completed',
            'submission_id': submission.submission_id,
            'is_valid': is_valid,
            'error_count': len(errors),
        }
    except Exception as exc:
        logger.exception(
            "validate_form_submission_async: error for submission %s: %s",
            submission_pk, exc,
        )
        raise self.retry(exc=exc)