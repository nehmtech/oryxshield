"""
Integrations with external disease surveillance systems.

All sync functions return a list of HealthData instances on success, or []
on failure (errors are logged, not re-raised, so tasks can continue).
"""
import logging
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# DHIS2
# ---------------------------------------------------------------------------

def sync_dhis2(data_source) -> list:
    """Pull disease data from a DHIS2 instance and create HealthData records."""
    from .models import HealthData

    base_url = getattr(settings, "DHIS2_BASE_URL", None) or data_source.api_endpoint
    username = getattr(settings, "DHIS2_USERNAME", "")
    password = getattr(settings, "DHIS2_PASSWORD", "")

    if not base_url:
        logger.error("DHIS2: base URL not configured for source %s", data_source.name)
        return []

    params = {
        "dataSet": getattr(settings, "DHIS2_DATASET_ID", "disease_surveillance"),
        "startDate": (timezone.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "endDate": timezone.now().strftime("%Y-%m-%d"),
    }

    try:
        resp = requests.get(
            f"{base_url}/api/dataValueSets",
            params=params,
            auth=(username, password),
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.error("DHIS2 sync error for %s: %s", data_source.name, exc)
        return []

    records = []
    for entry in payload.get("dataValues", []):
        try:
            hd = HealthData(
                data_source=data_source,
                location_id=_resolve_location_id(entry.get("orgUnit")),
                data_type="CASE",
                date_recorded=_parse_dhis2_period(entry.get("period")),
                disease_code=entry.get("dataElement", ""),
                disease_name=entry.get("dataElement", ""),
                raw_data=entry,
            )
            hd.save()
            records.append(hd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DHIS2: skipping malformed entry — %s", exc)

    logger.info("DHIS2 sync complete for %s: %d records", data_source.name, len(records))
    return records


# ---------------------------------------------------------------------------
# SORMAS
# ---------------------------------------------------------------------------

def sync_sormas(data_source) -> list:
    """Pull case data from a SORMAS REST API endpoint."""
    from .models import HealthData

    base_url = data_source.api_endpoint
    api_key = data_source.api_key

    if not base_url:
        logger.error("SORMAS: endpoint not configured for %s", data_source.name)
        return []

    since_ms = int((timezone.now() - timedelta(days=7)).timestamp() * 1_000)

    try:
        resp = requests.get(
            f"{base_url}/api/cases",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={"since": since_ms},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        cases = resp.json()
    except requests.RequestException as exc:
        logger.error("SORMAS sync error for %s: %s", data_source.name, exc)
        return []

    records = []
    for case in cases:
        try:
            hd = HealthData(
                data_source=data_source,
                location_id=_resolve_location_id(case.get("region")),
                data_type="CASE",
                date_recorded=case.get("reportDate"),
                disease_code=case.get("disease", ""),
                disease_name=case.get("disease", ""),
                patient_id=case.get("uuid", ""),
                age=case.get("age"),
                gender=_map_gender(case.get("sex")),
                raw_data=case,
            )
            hd.save()
            records.append(hd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SORMAS: skipping case — %s", exc)

    logger.info("SORMAS sync complete for %s: %d records", data_source.name, len(records))
    return records


# ---------------------------------------------------------------------------
# Generic REST API
# ---------------------------------------------------------------------------

def sync_generic_api(data_source) -> list:
    """Pull records from a generic REST API that returns a JSON list or {records:[]}."""
    from .models import HealthData

    endpoint = data_source.api_endpoint
    if not endpoint:
        logger.error("Generic API: endpoint not set for %s", data_source.name)
        return []

    headers = {}
    if data_source.api_key:
        headers["Authorization"] = f"Bearer {data_source.api_key}"

    try:
        resp = requests.get(endpoint, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.error("Generic API sync error for %s: %s", data_source.name, exc)
        return []

    raw_records = payload if isinstance(payload, list) else payload.get("records", [])

    records = []
    for item in raw_records:
        try:
            hd = HealthData(
                data_source=data_source,
                location_id=item.get("location_id"),
                data_type=item.get("data_type", "CASE"),
                date_recorded=item.get("date_recorded"),
                disease_code=item.get("disease_code", ""),
                disease_name=item.get("disease_name", ""),
                raw_data=item,
            )
            hd.save()
            records.append(hd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Generic API: skipping record — %s", exc)

    logger.info("Generic API sync complete for %s: %d records", data_source.name, len(records))
    return records


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_to_who_eios(report_id) -> dict:
    """Serialise a SurveillanceReport for WHO EIOS submission."""
    from .models import SurveillanceReport

    try:
        report = SurveillanceReport.objects.get(id=report_id, is_deleted=False)
    except SurveillanceReport.DoesNotExist:
        logger.error("WHO EIOS export: report %s not found", report_id)
        return {"status": "error", "message": "Report not found"}

    payload = {
        "title": report.title,
        "location": report.location.name,
        "country_code": getattr(report.location, "country_code", "KE"),
        "start_date": report.start_date.isoformat(),
        "end_date": report.end_date.isoformat(),
        "total_cases": report.total_cases,
        "new_cases": report.new_cases,
        "summary": report.summary,
        "key_findings": report.key_findings,
        "recommendations": report.recommendations,
    }

    logger.info("Exported report %s to WHO EIOS format", report.title)
    return {"status": "success", "data": payload}


def export_to_africa_cdc(anomaly_id) -> dict:
    """Serialise an AnomalyDetection record for Africa CDC submission."""
    from .models import AnomalyDetection

    try:
        anomaly = AnomalyDetection.objects.get(id=anomaly_id, is_deleted=False)
    except AnomalyDetection.DoesNotExist:
        logger.error("Africa CDC export: anomaly %s not found", anomaly_id)
        return {"status": "error", "message": "Anomaly not found"}

    payload = {
        "disease": anomaly.disease_name,
        "disease_code": anomaly.disease_code,
        "location": anomaly.location.name,
        "severity": anomaly.severity,
        "actual_cases": anomaly.actual_cases,
        "expected_cases": anomaly.expected_cases,
        "percentage_increase": float(anomaly.percentage_increase),
        "confidence_score": float(anomaly.confidence_score),
        "detected_at": anomaly.detected_at.isoformat(),
        "is_verified": anomaly.is_verified,
    }

    logger.info("Exported anomaly %s to Africa CDC format", anomaly.id)
    return {"status": "success", "data": payload}


# ---------------------------------------------------------------------------
# Validation utilities
# ---------------------------------------------------------------------------

def validate_icd10_code(code: str) -> bool:
    """Return True if code matches the ICD-10 pattern (e.g. A09, J18.1)."""
    return bool(re.match(r"^[A-Z]\d{2}(\.\d{1,2})?$", code or ""))


def map_disease_code(source_code: str, source_system: str) -> str:
    """
    Map a source-system disease code to the canonical OryxShield code.

    NOTE: Currently uses identity mapping (source code returned unchanged).
    A real mapping table (ICD-10 ↔ DHIS2 ↔ SORMAS codes) should be
    configured in SystemConfiguration or a dedicated MappingTable model
    once the government data dictionary is received. Track in: ORYXSHIELD-INT-001.
    """
    logger.debug(
        "map_disease_code: identity mapping active for source_code=%r source_system=%r — "
        "no cross-system code table configured yet.",
        source_code, source_system,
    )
    return source_code


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_location_id(external_id):
    """
    Look up a Location by its external identifier.
    Falls back to None (which will be caught by save() validation).
    """
    if not external_id:
        return None
    from core.models import Location
    try:
        return Location.objects.get(
            metadata__external_id=external_id
        ).id
    except Location.DoesNotExist:
        return None


def _map_gender(value: str | None) -> str:
    """Map SORMAS/DHIS2 gender values to our single-char choices."""
    mapping = {"MALE": "M", "FEMALE": "F", "UNKNOWN": "U", "OTHER": "O"}
    return mapping.get((value or "").upper(), "U")


def _parse_dhis2_period(period: str | None):
    """Convert DHIS2 period string (e.g. '202501') to a datetime."""
    if not period:
        return timezone.now()
    try:
        from django.utils.dateparse import parse_datetime
        if len(period) == 6:  # YYYYMM
            return timezone.datetime(int(period[:4]), int(period[4:6]), 1,
                                     tzinfo=timezone.get_current_timezone())
        if len(period) == 8:  # YYYYMMDD
            return timezone.datetime(int(period[:4]), int(period[4:6]), int(period[6:8]),
                                     tzinfo=timezone.get_current_timezone())
    except (ValueError, TypeError):
        pass
    return timezone.now()