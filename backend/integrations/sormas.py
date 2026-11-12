"""
SORMAS integration service for OryxShield.

Handles bidirectional sync with SORMAS
(Surveillance Outbreak Response Management and Analysis System):
- Case synchronisation
- Contact tracing synchronisation
- Sample / laboratory tracking
- Outbreak event linking
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class SORMASClient:
    """
    HTTP client for SORMAS REST API.
    """

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.timeout = system.timeout_seconds
        self.session = requests.Session()
        self._configure_auth()

    def _configure_auth(self):
        creds = self.system.get_credentials()
        auth_type = self.system.auth_type

        if auth_type == 'BASIC':
            self.session.auth = (
                creds.get('username', ''),
                creds.get('password', '')
            )
        elif auth_type in ('TOKEN', 'API_KEY'):
            self.session.headers.update({
                'Authorization': f"Bearer {creds.get('token', '')}",
            })

        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def _url(self, path):
        return f"{self.base_url}/sormas-rest/{path.lstrip('/')}"

    def get(self, path, params=None):
        response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path, payload):
        response = self.session.post(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def put(self, path, payload):
        response = self.session.put(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> dict:
        try:
            data = self.get('info/version')
            return {'healthy': True, 'version': str(data)}
        except requests.exceptions.ConnectionError as e:
            return {'healthy': False, 'error': f"Connection refused: {e}"}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Timeout'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # Cases
    # -------------------------------------------------------------------------

    def get_cases(self, since: Optional[str] = None, page: int = 0, size: int = 50) -> list:
        """
        Fetch cases since a given ISO8601 timestamp.
        Returns list of SORMAS case DTOs.
        """
        params = {'page': page, 'size': size}
        if since:
            params['since'] = since
        return self.get('cases/query', params=params)

    def push_case(self, payload: dict) -> dict:
        """Create or update a case in SORMAS."""
        return self.post('cases/push', [payload])

    def push_cases_bulk(self, cases: list) -> dict:
        return self.post('cases/push', cases)

    def get_case_by_uuid(self, uuid: str) -> dict:
        return self.get(f'cases/query/{uuid}')

    # -------------------------------------------------------------------------
    # Contacts
    # -------------------------------------------------------------------------

    def get_contacts(self, since: Optional[str] = None, page: int = 0, size: int = 50) -> list:
        params = {'page': page, 'size': size}
        if since:
            params['since'] = since
        return self.get('contacts/query', params=params)

    def push_contact(self, payload: dict) -> dict:
        return self.post('contacts/push', [payload])

    def push_contacts_bulk(self, contacts: list) -> dict:
        return self.post('contacts/push', contacts)

    # -------------------------------------------------------------------------
    # Samples / Laboratory
    # -------------------------------------------------------------------------

    def get_samples(self, since: Optional[str] = None, page: int = 0, size: int = 50) -> list:
        params = {'page': page, 'size': size}
        if since:
            params['since'] = since
        return self.get('samples/query', params=params)

    def push_sample(self, payload: dict) -> dict:
        return self.post('samples/push', [payload])

    # -------------------------------------------------------------------------
    # Outbreaks / Events
    # -------------------------------------------------------------------------

    def get_events(self, since: Optional[str] = None, page: int = 0, size: int = 50) -> list:
        params = {'page': page, 'size': size}
        if since:
            params['since'] = since
        return self.get('events/query', params=params)

    def get_event_participants(self, event_uuid: str) -> list:
        return self.get(f'eventparticipants/{event_uuid}')

    # -------------------------------------------------------------------------
    # Infrastructure (Region, District, Facility)
    # -------------------------------------------------------------------------

    def get_regions(self) -> list:
        return self.get('regions/all')

    def get_districts(self, region_uuid: Optional[str] = None) -> list:
        path = f'districts/{region_uuid}' if region_uuid else 'districts/all'
        return self.get(path)

    def get_facilities(self, district_uuid: Optional[str] = None) -> list:
        if district_uuid:
            return self.get(f'facilities/{district_uuid}')
        return self.get('facilities/all')


class SORMASSyncService:
    """
    High-level bidirectional sync service between OryxShield and SORMAS.
    """

    def __init__(self, system):
        self.system = system
        self.client = SORMASClient(system)
        self.config = system.configuration

    def import_cases(self, since: Optional[str] = None) -> dict:
        """Pull cases from SORMAS and upsert into OryxShield."""
        from .models import IntegrationLog

        page = 0
        total = 0
        errors = []

        while True:
            try:
                cases = self.client.get_cases(since=since, page=page, size=50)
                if not cases:
                    break

                for case_dto in cases:
                    try:
                        self._upsert_case(case_dto)
                        total += 1
                    except Exception as e:
                        errors.append({'uuid': case_dto.get('uuid'), 'error': str(e)})
                        logger.error(f"SORMAS case upsert failed: {e}")

                if len(cases) < 50:
                    break
                page += 1

            except Exception as e:
                logger.error(f"SORMAS import page {page} error: {e}")
                break

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO' if not errors else 'WARNING',
            category='SYNC',
            message=f"SORMAS case import: {total} records, {len(errors)} errors",
            operation='import_cases',
        )

        return {'imported': total, 'errors': errors}

    def export_alerts(self) -> dict:
        """Push OryxShield alerts as SORMAS events."""
        from risk_assessment.models import Alert
        from .models import IntegrationLog

        alerts = Alert.objects.filter(
            is_deleted=False,
            metadata__sormas_exported=False
        ).select_related('location')

        success = 0
        errors = []

        for alert in alerts:
            try:
                payload = self._build_event_payload(alert)
                self.client.post('events/push', [payload])
                alert.metadata['sormas_exported'] = True
                alert.save(update_fields=['metadata', 'updated_at'])
                success += 1
            except Exception as e:
                errors.append({'alert_id': str(alert.id), 'error': str(e)})

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"SORMAS alert export: {success} pushed, {len(errors)} failed",
            operation='export_alerts',
        )

        return {'exported': success, 'errors': errors}

    def _upsert_case(self, case_dto: dict):
        """
        Map SORMAS case DTO into OryxShield HealthData.
        Awaiting SORMAS API credentials and schema confirmation from government.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "SORMAS _upsert_case: mapping not yet implemented — "
            "case_uuid=%s disease=%s will not be saved. "
            "Implement when SORMAS API credentials are available.",
            case_dto.get('uuid', 'unknown'),
            case_dto.get('disease', 'unknown'),
        )

    def _build_event_payload(self, alert) -> dict:
        """Build a SORMAS event payload from a OryxShield Alert."""
        return {
            'uuid': alert.metadata.get('sormas_uuid') or str(alert.id).replace('-', '').upper()[:36],
            'eventTitle': alert.title if hasattr(alert, 'title') else str(alert),
            'eventStatus': 'SIGNAL',
            'diseaseTransmissionMode': 'UNKNOWN',
            'reportDateTime': alert.created_at.isoformat(),
        }