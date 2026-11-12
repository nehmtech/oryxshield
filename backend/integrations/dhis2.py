"""
DHIS2 integration service for OryxShield.

Handles data exchange with DHIS2 (District Health Information System):
- Tracked entity instance sync (cases, contacts)
- Aggregate data exchange
- Program event capture
- Organization unit mapping
- Data element mapping
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class DHIS2Client:
    """
    HTTP client for DHIS2 REST API.
    Manages auth, pagination, rate limiting, error handling.
    """

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.api_version = system.api_version or '2.37'
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
        elif auth_type == 'API_KEY':
            self.session.headers.update({
                'Authorization': f"ApiToken {creds.get('token', '')}"
            })
        elif auth_type == 'TOKEN':
            self.session.headers.update({
                'Authorization': f"Bearer {creds.get('token', '')}"
            })

        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def _api_url(self, path):
        return f"{self.base_url}/api/{self.api_version}/{path.lstrip('/')}"

    def get(self, path, params=None):
        url = self._api_url(path)
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path, payload):
        url = self._api_url(path)
        response = self.session.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def put(self, path, payload):
        url = self._api_url(path)
        response = self.session.put(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> dict:
        """Ping system info endpoint to verify connectivity."""
        try:
            data = self.get('system/info')
            return {
                'healthy': True,
                'version': data.get('version', 'unknown'),
                'revision': data.get('revision', ''),
            }
        except requests.exceptions.ConnectionError as e:
            return {'healthy': False, 'error': f"Connection failed: {e}"}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Request timed out'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # Organisation Units
    # -------------------------------------------------------------------------

    def get_org_units(self, page=1, page_size=50) -> dict:
        """Retrieve DHIS2 organisation units with paging."""
        return self.get('organisationUnits', params={
            'fields': 'id,name,code,level,parent[id,name],geometry',
            'paging': 'true',
            'page': page,
            'pageSize': page_size,
        })

    def get_org_unit(self, uid: str) -> dict:
        return self.get(f'organisationUnits/{uid}', params={
            'fields': 'id,name,code,level,parent[id,name],geometry'
        })

    # -------------------------------------------------------------------------
    # Tracked Entity Instances (Cases / Contacts)
    # -------------------------------------------------------------------------

    def get_tracked_entities(
        self,
        program: str,
        org_unit: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        last_updated: Optional[str] = None
    ) -> dict:
        params = {
            'program': program,
            'fields': '*',
            'paging': 'true',
            'page': page,
            'pageSize': page_size,
        }
        if org_unit:
            params['ou'] = org_unit
            params['ouMode'] = 'DESCENDANTS'
        if last_updated:
            params['lastUpdated'] = last_updated
        return self.get('trackedEntityInstances', params=params)

    def create_tracked_entity(self, payload: dict) -> dict:
        """
        POST to trackedEntityInstances.
        payload: {
            trackedEntityType, orgUnit,
            attributes: [{attribute, value}, ...],
            enrollments: [{...}]
        }
        """
        return self.post('trackedEntityInstances', payload)

    def update_tracked_entity(self, tei_uid: str, payload: dict) -> dict:
        return self.put(f'trackedEntityInstances/{tei_uid}', payload)

    # -------------------------------------------------------------------------
    # Events (Program Stage events)
    # -------------------------------------------------------------------------

    def get_events(
        self,
        program: str,
        org_unit: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        params = {
            'program': program,
            'fields': '*',
            'paging': 'true',
            'page': page,
            'pageSize': page_size,
        }
        if org_unit:
            params['orgUnit'] = org_unit
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        return self.get('events', params=params)

    def create_event(self, payload: dict) -> dict:
        return self.post('events', payload)

    def create_events_bulk(self, events: list) -> dict:
        return self.post('events', {'events': events})

    # -------------------------------------------------------------------------
    # Aggregate Data (Aggregate Data Exchange)
    # -------------------------------------------------------------------------

    def get_data_value_sets(
        self,
        data_set: str,
        org_unit: str,
        period: str
    ) -> dict:
        return self.get('dataValueSets', params={
            'dataSet': data_set,
            'orgUnit': org_unit,
            'period': period,
        })

    def push_data_value_set(self, payload: dict) -> dict:
        """
        POST aggregate data values.
        payload: {
            dataSet, period, orgUnit, completeDate,
            dataValues: [{dataElement, value, categoryOptionCombo}, ...]
        }
        """
        return self.post('dataValueSets', payload)

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    def get_data_elements(self, page=1, page_size=100) -> dict:
        return self.get('dataElements', params={
            'fields': 'id,name,code,valueType,domainType',
            'paging': 'true',
            'page': page,
            'pageSize': page_size,
        })

    def get_programs(self) -> dict:
        return self.get('programs', params={
            'fields': 'id,name,programType,trackedEntityType[id,name],programStages[id,name]',
            'paging': 'false',
        })


class DHIS2SyncService:
    """
    High-level service for bidirectional OryxShield ↔ DHIS2 sync.
    Used by Celery tasks.
    """

    def __init__(self, system):
        self.system = system
        self.client = DHIS2Client(system)
        self.config = system.configuration

    def export_cases(self, filters: dict = None) -> dict:
        """Export OryxShield cases to DHIS2 tracked entity instances."""
        from surveillance.models import HealthData
        from .models import DataMapping, IntegrationLog

        filters = filters or {}
        program = self.config.get('case_program_id')
        if not program:
            raise ValueError("DHIS2 case_program_id not configured")

        qs = HealthData.objects.filter(is_deleted=False)
        if filters.get('date_from'):
            qs = qs.filter(report_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(report_date__lte=filters['date_to'])

        mappings = DataMapping.objects.filter(
            external_system=self.system,
            entity_type='Case',
            direction__in=['OUTBOUND', 'BIDIRECTIONAL'],
            is_active=True
        )

        success = 0
        failed = 0
        errors = []

        for case in qs.iterator(chunk_size=50):
            try:
                payload = self._build_tei_payload(case, mappings, program)
                dhis2_uid = case.metadata.get('dhis2_uid')

                if dhis2_uid:
                    self.client.update_tracked_entity(dhis2_uid, payload)
                else:
                    result = self.client.create_tracked_entity(payload)
                    ref = result.get('response', {}).get('importSummaries', [{}])[0].get('reference')
                    if ref:
                        case.metadata['dhis2_uid'] = ref
                        case.save(update_fields=['metadata', 'updated_at'])

                success += 1

            except Exception as e:
                failed += 1
                errors.append({'case_id': str(case.id), 'error': str(e)})
                logger.error(f"DHIS2 export failed for case {case.id}: {e}")

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO' if not errors else 'WARNING',
            category='SYNC',
            message=f"DHIS2 case export: {success} succeeded, {failed} failed",
            operation='export_cases',
            response_data={'success': success, 'failed': failed, 'errors': errors[:10]},
        )

        return {'success': success, 'failed': failed, 'errors': errors}

    def import_events(self, program: str, org_unit: str = None, since: str = None) -> dict:
        """Import DHIS2 program events into OryxShield."""
        from .models import IntegrationLog

        page = 1
        total_imported = 0
        errors = []

        while True:
            try:
                data = self.client.get_events(
                    program=program,
                    org_unit=org_unit,
                    page=page,
                    page_size=50,
                    start_date=since,
                )
                events = data.get('events', [])
                if not events:
                    break

                for event in events:
                    try:
                        self._upsert_event(event)
                        total_imported += 1
                    except Exception as e:
                        errors.append({'event_id': event.get('event'), 'error': str(e)})

                pager = data.get('pager', {})
                if page >= pager.get('pageCount', 1):
                    break
                page += 1

            except Exception as e:
                logger.error(f"DHIS2 import page {page} failed: {e}")
                break

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"DHIS2 event import: {total_imported} records",
            operation='import_events',
        )

        return {'imported': total_imported, 'errors': errors}

    def _build_tei_payload(self, case, mappings, program):
        """Build DHIS2 tracked entity instance payload from a OryxShield case."""
        attributes = []
        for mapping in mappings:
            value = self._get_field_value(case, mapping.source_field)
            if value is None and mapping.default_value:
                value = mapping.default_value
            if value is not None:
                attributes.append({
                    'attribute': mapping.target_field,
                    'value': str(value),
                })

        return {
            'trackedEntityType': self.config.get('tracked_entity_type_id', ''),
            'orgUnit': self._resolve_org_unit(case),
            'program': program,
            'attributes': attributes,
        }

    def _get_field_value(self, obj, field_path: str):
        """Resolve dotted field path on a model instance."""
        parts = field_path.split('.')
        val = obj
        for part in parts:
            if val is None:
                return None
            val = getattr(val, part, None)
        return val

    def _resolve_org_unit(self, case) -> str:
        """Map OryxShield location to DHIS2 org unit UID."""
        if hasattr(case, 'location') and case.location:
            return case.location.metadata.get('dhis2_org_unit_uid', '')
        return self.config.get('default_org_unit', '')

    def _upsert_event(self, event: dict):
        """
        Map a DHIS2 event into OryxShield HealthData.
        Awaiting DHIS2 API credentials and data element mapping from government.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "DHIS2 _upsert_event: mapping not yet implemented — "
            "event_uid=%s program=%s will not be saved. "
            "Implement when DHIS2 API credentials and data element UIDs are available.",
            event.get('event', 'unknown'),
            event.get('program', 'unknown'),
        )