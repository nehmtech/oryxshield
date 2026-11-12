"""
Celery tasks for the surveillance app.

Beat schedule (add to CELERY_BEAT_SCHEDULE in settings):
    run_anomaly_detection   — every 5 minutes
    identify_case_clusters  — every 10 minutes
    detect_hotspots         — every 15 minutes
    cleanup_old_health_data — weekly (Sunday 02:00)
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scheduled: anomaly detection pipeline
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_anomaly_detection(self):
    """
    Detect anomalies in unprocessed HealthData from the last 24 hours.
    Marks records as processed after a successful run.
    Skips if a detection run completed within the last 5 minutes (idempotency guard).
    """
    from django.core.cache import cache
    from .models import HealthData, AnomalyDetection
    from .anomaly_detection import detect_anomalies

    LOCK_KEY = 'run_anomaly_detection:lock'
    LOCK_TTL = 300  # 5 minutes

    if not cache.add(LOCK_KEY, '1', LOCK_TTL):
        logger.info("run_anomaly_detection: skipped — another run completed within 5 min")
        return {"status": "skipped", "reason": "lock_active"}

    logger.info("run_anomaly_detection: starting")

    yesterday = timezone.now() - timedelta(days=1)
    unprocessed = HealthData.objects.filter(
        is_deleted=False,
        processed=False,
        date_recorded__gte=yesterday,
    )

    count = unprocessed.count()
    if count == 0:
        logger.info("run_anomaly_detection: no unprocessed data")
        return {"status": "no_data"}

    try:
        anomalies = detect_anomalies(unprocessed)
    except Exception as exc:
        logger.exception("run_anomaly_detection: detection failed")
        raise self.retry(exc=exc)

    created = 0
    for anomaly_data in anomalies:
        try:
            AnomalyDetection.objects.create(**anomaly_data)
            created += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("run_anomaly_detection: failed to save anomaly — %s", exc)

    unprocessed.update(processed=True)

    if created:
        _emit("anomaly_detected", {"count": created, "timestamp": timezone.now().isoformat()})

    logger.info("run_anomaly_detection: %d anomalies created from %d records", created, count)
    return {"status": "completed", "anomalies_created": created, "data_processed": count}


# ---------------------------------------------------------------------------
# Scheduled: cluster identification
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def identify_case_clusters(self):
    """Identify geographic disease clusters from the past 7 days."""
    from .models import HealthData, CaseCluster
    from .clustering import identify_clusters

    logger.info("identify_case_clusters: starting")

    week_ago = timezone.now() - timedelta(days=7)
    recent = HealthData.objects.filter(
        is_deleted=False,
        date_recorded__gte=week_ago,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    if recent.count() < 10:
        logger.info("identify_case_clusters: insufficient data")
        return {"status": "insufficient_data"}

    try:
        clusters = identify_clusters(recent)
    except Exception as exc:
        logger.exception("identify_case_clusters: failed")
        raise self.retry(exc=exc)

    created = 0
    for data in clusters:
        _, was_created = CaseCluster.objects.update_or_create(
            name=data["name"],
            defaults={k: v for k, v in data.items() if k != "name"},
        )
        if was_created:
            created += 1

    if created:
        _emit("clusters_identified", {"count": created, "timestamp": timezone.now().isoformat()})

    logger.info("identify_case_clusters: %d new clusters", created)
    return {"status": "completed", "clusters_created": created}


# ---------------------------------------------------------------------------
# Scheduled: hotspot detection
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def detect_hotspots(self):
    """Detect geographic hotspots from the past 7 days."""
    from .models import HealthData, Hotspot
    from .clustering import detect_geographic_hotspots

    logger.info("detect_hotspots: starting")

    week_ago = timezone.now() - timedelta(days=7)
    recent = HealthData.objects.filter(
        is_deleted=False,
        date_recorded__gte=week_ago,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    if recent.count() < 10:
        logger.info("detect_hotspots: insufficient data")
        return {"status": "insufficient_data"}

    try:
        hotspots = detect_geographic_hotspots(recent)
    except Exception as exc:
        logger.exception("detect_hotspots: failed")
        raise self.retry(exc=exc)

    created = 0
    for data in hotspots:
        _, was_created = Hotspot.objects.update_or_create(
            location=data["location"],
            disease_code=data["disease_code"],
            defaults={k: v for k, v in data.items() if k not in ("location", "disease_code")},
        )
        if was_created:
            created += 1

    if created:
        _emit("hotspots_detected", {"count": created, "timestamp": timezone.now().isoformat()})

    logger.info("detect_hotspots: %d new hotspots", created)
    return {"status": "completed", "hotspots_created": created}


# ---------------------------------------------------------------------------
# On-demand: external data source sync
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def sync_data_source(self, data_source_id: str, force_sync: bool = False):
    """
    Pull fresh data from an external source (DHIS2, SORMAS, generic REST).
    Skips if the source was synced within its configured sync_frequency window,
    unless force_sync=True.
    """
    from .models import DataSource
    from .integrations import sync_dhis2, sync_sormas, sync_generic_api

    try:
        source = DataSource.objects.get(id=data_source_id, is_deleted=False)
    except DataSource.DoesNotExist:
        logger.error("sync_data_source: source %s not found", data_source_id)
        return {"status": "error", "message": "DataSource not found"}

    if not force_sync and source.last_sync:
        elapsed = (timezone.now() - source.last_sync).total_seconds()
        if elapsed < source.sync_frequency:
            logger.info("sync_data_source: %s recently synced — skipping", source.name)
            return {"status": "skipped", "message": "Recently synced"}

    try:
        if source.source_type == "DHIS2":
            synced = sync_dhis2(source)
        elif source.source_type == "SORMAS":
            synced = sync_sormas(source)
        elif source.api_endpoint:
            synced = sync_generic_api(source)
        else:
            return {"status": "error", "message": "No sync method configured"}
    except Exception as exc:
        logger.exception("sync_data_source: error syncing %s", source.name)
        raise self.retry(exc=exc)

    source.last_sync = timezone.now()
    source.save(update_fields=["last_sync", "updated_at"])

    logger.info("sync_data_source: %s — %d records synced", source.name, len(synced))
    return {"status": "completed", "data_source": source.name, "records_synced": len(synced)}


# ---------------------------------------------------------------------------
# On-demand: bulk CSV upload
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_bulk_upload(self, file_content: bytes, data_source_id: str, data_type: str):
    """Parse a CSV file and create HealthData records in bulk."""
    from io import BytesIO

    import pandas as pd

    from .models import DataSource, HealthData

    try:
        source = DataSource.objects.get(id=data_source_id, is_deleted=False)
    except DataSource.DoesNotExist:
        logger.error("process_bulk_upload: source %s not found", data_source_id)
        return {"status": "error", "message": "DataSource not found"}

    try:
        df = pd.read_csv(BytesIO(file_content))
    except Exception as exc:
        logger.error("process_bulk_upload: cannot parse CSV — %s", exc)
        return {"status": "error", "message": "Invalid CSV file"}

    created, errors = 0, 0
    records_to_create = []

    for _, row in df.iterrows():
        try:
            records_to_create.append(
                HealthData(
                    data_source=source,
                    location_id=row.get("location_id"),
                    data_type=data_type,
                    date_recorded=row.get("date_recorded"),
                    disease_code=str(row.get("disease_code", "")),
                    disease_name=str(row.get("disease_name", "")),
                    age=int(row["age"]) if pd.notna(row.get("age")) else None,
                    gender=str(row.get("gender", ""))[:1].upper() or "U",
                    raw_data=row.where(pd.notna(row), other=None).to_dict(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("process_bulk_upload: row error — %s", exc)
            errors += 1

    try:
        HealthData.objects.bulk_create(records_to_create, batch_size=500)
        created = len(records_to_create)
    except Exception as exc:
        logger.error("process_bulk_upload: bulk_create failed — %s", exc)
        raise self.retry(exc=exc)

    logger.info("process_bulk_upload: %d created, %d errors", created, errors)
    return {"status": "completed", "records_created": created, "errors": errors}


# ---------------------------------------------------------------------------
# On-demand: report generation
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_surveillance_report(self, location_id: str, report_type: str = "DAILY"):
    """Generate a SurveillanceReport for a given location and period."""
    from .models import Location, SurveillanceReport, HealthData, AnomalyDetection, CaseCluster, Hotspot

    try:
        location = Location.objects.get(id=location_id)
    except Location.DoesNotExist:
        logger.error("generate_surveillance_report: location %s not found", location_id)
        return {"status": "error", "message": "Location not found"}

    end_date = timezone.now().date()
    days_map = {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30}
    start_date = end_date - timedelta(days=days_map.get(report_type, 1))

    total_cases = HealthData.objects.filter(
        is_deleted=False, location=location,
        date_recorded__date__gte=start_date, date_recorded__date__lte=end_date,
    ).count()

    new_cases = HealthData.objects.filter(
        is_deleted=False, location=location, date_recorded__date=end_date,
    ).count()

    report = SurveillanceReport.objects.create(
        report_type=report_type,
        title=f"{report_type.title()} Surveillance Report — {location.name}",
        location=location,
        start_date=start_date,
        end_date=end_date,
        total_cases=total_cases,
        new_cases=new_cases,
        active_clusters=CaseCluster.objects.filter(is_deleted=False, location=location, is_active=True).count(),
        active_hotspots=Hotspot.objects.filter(is_deleted=False, location=location, is_active=True).count(),
        anomalies_detected=AnomalyDetection.objects.filter(
            is_deleted=False, location=location, detected_at__date__gte=start_date
        ).count(),
        summary=(
            f"Automated {report_type.lower()} report for {location.name} "
            f"covering {start_date} to {end_date}. "
            f"Total cases: {total_cases}."
        ),
    )

    logger.info("generate_surveillance_report: created %s", report.title)
    return {"status": "completed", "report_id": str(report.id), "report_title": report.title}


# ---------------------------------------------------------------------------
# Scheduled: data archival
# ---------------------------------------------------------------------------

@shared_task
def cleanup_old_health_data():
    """Soft-delete HealthData older than 2 years.  Run weekly."""
    from .models import HealthData

    cutoff = timezone.now() - timedelta(days=730)
    qs = HealthData.objects.filter(is_deleted=False, date_recorded__lt=cutoff)
    count = qs.count()
    qs.update(is_deleted=True, deleted_at=timezone.now())

    logger.info("cleanup_old_health_data: archived %d records", count)
    return {"status": "completed", "records_archived": count}


# ---------------------------------------------------------------------------
# On-demand: data quality checks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2)
def run_data_quality_checks(self, data_source_id: str):
    """Run completeness and duplication checks for a DataSource."""
    from .models import DataSource, HealthData, DataQualityCheck

    try:
        source = DataSource.objects.get(id=data_source_id, is_deleted=False)
    except DataSource.DoesNotExist:
        logger.error("run_data_quality_checks: source %s not found", data_source_id)
        return {"status": "error", "message": "DataSource not found"}

    week_ago = timezone.now() - timedelta(days=7)
    recent = HealthData.objects.filter(
        is_deleted=False, data_source=source, date_recorded__gte=week_ago
    )

    total = recent.count()
    if total == 0:
        return {"status": "no_data"}

    # Completeness: all mandatory fields present
    complete = recent.exclude(
        Q(disease_code="") | Q(disease_name="") | Q(date_recorded__isnull=True)
    ).count()
    completeness_rate = round((complete / total) * 100, 2)

    issues = []
    if completeness_rate < 90:
        issues.append({
            "type": "completeness",
            "message": f"{total - complete} records missing required fields",
        })

    # Duplication: same patient_id + disease_code + date
    duplicates = (
        recent.exclude(patient_id="")
        .values("patient_id", "disease_code", "date_recorded__date")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .count()
    )
    if duplicates:
        issues.append({"type": "duplication", "count": duplicates})

    DataQualityCheck.objects.create(
        data_source=source,
        check_type="COMPLETENESS",
        records_checked=total,
        records_passed=complete,
        records_failed=total - complete,
        pass_rate=completeness_rate,
        issues=issues,
        status="COMPLETED",
    )

    logger.info(
        "run_data_quality_checks: %s — pass rate %.1f%%", source.name, completeness_rate
    )
    return {"status": "completed", "pass_rate": completeness_rate, "records_checked": total}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _emit(event_type: str, payload: dict) -> None:
    """Fire-and-forget WebSocket notification — fails silently."""
    try:
        from websockets.utils import send_surveillance_update  # type: ignore
        send_surveillance_update({"type": event_type, **payload})
    except Exception:  # noqa: BLE001
        logger.debug("WebSocket emit skipped (%s)", event_type)