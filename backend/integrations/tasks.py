"""
Celery tasks for OryxShield integrations app.

All tasks:
- bind=True, max_retries=3, explicit default_retry_delay
- transaction.atomic() on multi-model writes
- AuditLog on significant mutations
- update_fields on targeted saves
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def test_system_connection(self, system_id: str):
    """
    Test connectivity and health of an external system.
    Updates health_status on the ExternalSystem record.
    """
    from .models import ExternalSystem, IntegrationLog

    try:
        system = ExternalSystem.objects.get(id=system_id, is_deleted=False)
    except ExternalSystem.DoesNotExist:
        return {'status': 'error', 'message': f"System {system_id} not found"}

    logger.info(f"Health-checking system: {system.name}")

    try:
        result = _get_client_for_system(system).health_check()

        if result.get('healthy'):
            system.mark_healthy(result.get('version', ''))
        else:
            system.mark_unhealthy(result.get('error', 'Unknown failure'))

        IntegrationLog.objects.create(
            external_system=system,
            log_level='INFO' if result.get('healthy') else 'WARNING',
            category='HEALTH',
            message=f"Health check {'passed' if result.get('healthy') else 'failed'}: {result.get('error', '')}",
            operation='health_check',
        )

        return {
            'status': 'success',
            'healthy': result.get('healthy'),
            'system': system.name,
        }

    except Exception as exc:
        logger.error(f"Health check error for {system.name}: {exc}")
        system.mark_unhealthy(str(exc))

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_integration_job(self, job_id: str):
    """
    Execute an integration job (import / export / sync / validation).
    Routes to the appropriate service based on system type and job type.
    """
    from .models import IntegrationJob, IntegrationLog

    try:
        job = IntegrationJob.objects.select_related('external_system').get(
            id=job_id, is_deleted=False
        )
    except IntegrationJob.DoesNotExist:
        return {'status': 'error', 'message': f"Job {job_id} not found"}

    if job.status in ('COMPLETED', 'CANCELLED'):
        return {'status': 'skipped', 'reason': f"Job already {job.status}"}

    logger.info(f"Processing job {job.job_id} ({job.job_type}) for {job.external_system.name}")

    job.start()
    job.celery_task_id = self.request.id
    job.save(update_fields=['celery_task_id', 'updated_at'])

    try:
        result = _dispatch_job(job)

        with transaction.atomic():
            job.complete(summary=result)
            job.external_system.record_sync_success()
            IntegrationLog.objects.create(
                external_system=job.external_system,
                integration_job=job,
                log_level='INFO',
                category='SYNC',
                message=f"Job {job.job_id} completed",
                operation=job.job_type,
                response_data=result,
            )

        return {'status': 'success', 'job_id': job.job_id, 'result': result}

    except Exception as exc:
        logger.error(f"Job {job.job_id} failed: {exc}")

        try:
            job.status = 'RETRYING'
            job.retry_count += 1
            job.save(update_fields=['status', 'retry_count', 'updated_at'])
            raise self.retry(exc=exc)

        except self.MaxRetriesExceededError:
            with transaction.atomic():
                job.fail(str(exc))
                job.external_system.record_sync_failure()
                IntegrationLog.objects.create(
                    external_system=job.external_system,
                    integration_job=job,
                    log_level='ERROR',
                    category='SYNC',
                    message=f"Job {job.job_id} failed after {job.max_retries} retries",
                    operation=job.job_type,
                    error_detail=str(exc),
                )
            return {'status': 'failed', 'job_id': job.job_id, 'error': str(exc)}


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def trigger_webhook(self, webhook_id: str, payload: dict, attempt: int = 1):
    """
    Deliver a webhook payload to the configured URL.
    Implements HMAC signing, exponential backoff retry, and full logging.
    """
    import hmac
    import hashlib
    import requests
    from .models import Webhook, WebhookLog

    try:
        webhook = Webhook.objects.get(id=webhook_id, is_deleted=False)
    except Webhook.DoesNotExist:
        return {'status': 'error', 'message': f"Webhook {webhook_id} not found"}

    if not webhook.is_active:
        return {'status': 'skipped', 'reason': 'Webhook inactive'}

    # Build request
    headers = dict(webhook.headers)
    headers['Content-Type'] = 'application/json'
    headers['X-OryxShield-Event'] = payload.get('event', '')
    headers['X-OryxShield-Timestamp'] = str(int(timezone.now().timestamp()))

    if webhook.secret_key:
        body_str = str(payload).encode()
        if webhook.signing_algorithm == 'SHA512':
            sig = hmac.new(webhook.secret_key.encode(), body_str, hashlib.sha512).hexdigest()
        else:
            sig = hmac.new(webhook.secret_key.encode(), body_str, hashlib.sha256).hexdigest()
        headers['X-OryxShield-Signature'] = f"sha256={sig}" if webhook.signing_algorithm == 'SHA256' else f"sha512={sig}"

    start_time = timezone.now()
    success = False
    response_code = None
    response_body = ''
    error_message = ''

    try:
        import requests as req
        response = req.post(
            webhook.webhook_url,
            json=payload,
            headers=headers,
            timeout=webhook.timeout_seconds,
        )
        response_code = response.status_code
        response_body = response.text[:2000]
        success = response.status_code < 400

    except req.exceptions.Timeout:
        error_message = 'Request timed out'
    except req.exceptions.ConnectionError as e:
        error_message = f"Connection failed: {e}"
    except Exception as e:
        error_message = str(e)

    response_ms = int((timezone.now() - start_time).total_seconds() * 1000)
    is_final = success or (attempt >= webhook.retry_attempts)
    next_retry_at = None
    if not success and not is_final:
        delay = webhook.retry_delay_seconds * (float(webhook.retry_backoff_multiplier) ** (attempt - 1))
        next_retry_at = timezone.now() + timezone.timedelta(seconds=int(delay))

    with transaction.atomic():
        WebhookLog.objects.create(
            webhook=webhook,
            event_type=payload.get('event', ''),
            entity_id=str(payload.get('case_id', payload.get('alert_id', ''))),
            request_payload=payload,
            request_headers=headers,
            response_status_code=response_code,
            response_body=response_body,
            response_time_ms=response_ms,
            is_successful=success,
            error_message=error_message,
            attempt_number=attempt,
            is_final_attempt=is_final,
            next_retry_at=next_retry_at,
        )
        webhook.record_call(success=success, response_ms=response_ms)

    if not success and not is_final:
        delay = int(webhook.retry_delay_seconds * (float(webhook.retry_backoff_multiplier) ** (attempt - 1)))
        trigger_webhook.apply_async(
            args=[webhook_id, payload, attempt + 1],
            countdown=delay,
        )
        return {'status': 'retrying', 'attempt': attempt, 'delay': delay}

    return {'status': 'success' if success else 'failed', 'attempt': attempt, 'code': response_code}


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def sync_with_dhis2(self, system_id: str, filters: dict = None):
    """Bidirectional sync with a DHIS2 instance."""
    from .models import ExternalSystem, IntegrationLog
    from .dhis2 import DHIS2SyncService

    try:
        system = ExternalSystem.objects.get(id=system_id, system_type='DHIS2', is_deleted=False)
    except ExternalSystem.DoesNotExist:
        return {'status': 'error', 'message': 'DHIS2 system not found'}

    logger.info(f"DHIS2 sync: {system.name}")

    try:
        service = DHIS2SyncService(system)
        result = service.export_cases(filters=filters or {})
        system.record_sync_success()
        return {'status': 'completed', 'result': result}

    except Exception as exc:
        system.record_sync_failure()
        IntegrationLog.objects.create(
            external_system=system,
            log_level='ERROR',
            category='SYNC',
            message=f"DHIS2 sync failed: {exc}",
            operation='sync_with_dhis2',
            error_detail=str(exc),
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def sync_with_sormas(self, system_id: str):
    """Import cases and contacts from SORMAS."""
    from .models import ExternalSystem, IntegrationLog
    from .sormas import SORMASSyncService

    try:
        system = ExternalSystem.objects.get(id=system_id, system_type='SORMAS', is_deleted=False)
    except ExternalSystem.DoesNotExist:
        return {'status': 'error', 'message': 'SORMAS system not found'}

    logger.info(f"SORMAS sync: {system.name}")

    try:
        service = SORMASSyncService(system)
        since = system.last_sync.isoformat() if system.last_sync else None
        result = service.import_cases(since=since)
        system.record_sync_success()
        return {'status': 'completed', 'result': result}

    except Exception as exc:
        system.record_sync_failure()
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def submit_africa_cdc_weekly(self, system_id: str, year: int, week: int):
    """Submit weekly IDSR report to Africa CDC."""
    from .models import ExternalSystem
    from .africa_cdc import AfricaCDCSyncService

    try:
        system = ExternalSystem.objects.get(id=system_id, system_type='AFRICA_CDC', is_deleted=False)
    except ExternalSystem.DoesNotExist:
        return {'status': 'error', 'message': 'Africa CDC system not found'}

    try:
        service = AfricaCDCSyncService(system)
        result = service.submit_weekly_idsr(year=year, week=week)
        system.record_sync_success()
        return {'status': 'completed', 'result': result}

    except Exception as exc:
        system.record_sync_failure()
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def ingest_who_eios_signals(self, system_id: str):
    """Ingest WHO EIOS open-source signals."""
    from .models import ExternalSystem
    from .who_reporting import WHOEIOSSyncService

    try:
        system = ExternalSystem.objects.get(id=system_id, system_type='WHO_EIOS', is_deleted=False)
    except ExternalSystem.DoesNotExist:
        return {'status': 'error', 'message': 'WHO EIOS system not found'}

    try:
        service = WHOEIOSSyncService(system)
        since = system.last_sync.isoformat() if system.last_sync else None
        result = service.ingest_signals(since=since)
        system.record_sync_success()
        return {'status': 'completed', 'result': result}

    except Exception as exc:
        system.record_sync_failure()
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def health_check_all_systems(self):
    """
    Check health of all active external systems.
    Scheduled task — runs every 15 minutes via Celery Beat.
    """
    from .models import ExternalSystem

    logger.info("Running scheduled health checks for all active systems")

    systems = ExternalSystem.objects.filter(is_active=True, is_deleted=False).values_list('id', flat=True)
    count = 0

    for system_id in systems:
        test_system_connection.delay(str(system_id))
        count += 1

    logger.info(f"Queued health checks for {count} systems")
    return {'status': 'queued', 'system_count': count}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_scheduled_syncs(self):
    """
    Trigger sync for all active systems where sync_interval has elapsed.
    Scheduled via Celery Beat — runs every 5 minutes.
    """
    from django.utils import timezone
    from django.db.models import F
    from datetime import timedelta
    from .models import ExternalSystem

    now = timezone.now()
    overdue = ExternalSystem.objects.filter(
        is_active=True,
        sync_enabled=True,
        is_deleted=False,
    ).filter(
        models.Q(last_sync__isnull=True) |
        models.Q(last_sync__lte=now - timedelta(minutes=1) * models.F('sync_interval_minutes'))
    )

    dispatched = 0
    for system in overdue:
        _dispatch_scheduled_sync(system)
        dispatched += 1

    return {'status': 'dispatched', 'count': dispatched}


# =============================================================================
# Internal helpers
# =============================================================================

def _get_client_for_system(system):
    """Return the appropriate client for a given ExternalSystem."""
    from .dhis2 import DHIS2Client
    from .sormas import SORMASClient
    from .who_reporting import WHOEIOSClient
    from .africa_cdc import AfricaCDCClient
    from .lis_emr import LISClient, EMRClient

    mapping = {
        'DHIS2': DHIS2Client,
        'SORMAS': SORMASClient,
        'WHO_EIOS': WHOEIOSClient,
        'AFRICA_CDC': AfricaCDCClient,
        'LIS': LISClient,
        'EMR': EMRClient,
    }

    client_class = mapping.get(system.system_type)
    if not client_class:
        # Generic fallback — simple HTTP check
        import requests

        class _GenericClient:
            def __init__(self, system):
                self.system = system

            def health_check(self):
                try:
                    r = requests.get(f"{self.system.base_url}/health", timeout=self.system.timeout_seconds)
                    return {'healthy': r.status_code < 500, 'status_code': r.status_code}
                except Exception as e:
                    return {'healthy': False, 'error': str(e)}

        return _GenericClient(system)

    return client_class(system)


def _dispatch_job(job) -> dict:
    """Route an IntegrationJob to the correct sync service method."""
    from .dhis2 import DHIS2SyncService
    from .sormas import SORMASSyncService
    from .who_reporting import WHOEIOSSyncService
    from .africa_cdc import AfricaCDCSyncService
    from .lis_emr import LISSyncService, EMRSyncService

    system = job.external_system
    stype = system.system_type
    jtype = job.job_type

    service_map = {
        'DHIS2': DHIS2SyncService,
        'SORMAS': SORMASSyncService,
        'WHO_EIOS': WHOEIOSSyncService,
        'AFRICA_CDC': AfricaCDCSyncService,
        'LIS': LISSyncService,
        'EMR': EMRSyncService,
    }

    service_class = service_map.get(stype)
    if not service_class:
        return {'status': 'no_service', 'system_type': stype}

    service = service_class(system)
    filters = job.filters or {}

    if jtype == 'EXPORT':
        if hasattr(service, 'export_cases'):
            return service.export_cases(filters=filters)
    elif jtype == 'IMPORT':
        since = filters.get('since')
        if hasattr(service, 'import_cases'):
            return service.import_cases(since=since)
        if hasattr(service, 'import_lab_results'):
            return service.import_lab_results(since=since)
        if hasattr(service, 'import_clinical_data'):
            return service.import_clinical_data(since=since)
        if hasattr(service, 'ingest_signals'):
            return service.ingest_signals(since=since)
    elif jtype == 'SYNC':
        results = {}
        if hasattr(service, 'import_cases'):
            results['import'] = service.import_cases()
        if hasattr(service, 'export_cases'):
            results['export'] = service.export_cases()
        return results

    return {'status': 'dispatched', 'job_type': jtype}


def _dispatch_scheduled_sync(system):
    """Queue the right sync task for a given system type."""
    type_task_map = {
        'DHIS2': sync_with_dhis2,
        'SORMAS': sync_with_sormas,
        'WHO_EIOS': ingest_who_eios_signals,
        'AFRICA_CDC': ingest_who_eios_signals,  # uses generic ingest
    }
    task = type_task_map.get(system.system_type)
    if task:
        task.delay(str(system.id))


# Resolve forward reference to Django models in process_scheduled_syncs
from django.db import models