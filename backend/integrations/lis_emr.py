"""
LIS (Laboratory Information System) and EMR (Electronic Medical Record)
integration services for OryxShield.

LIS integration:
- Lab sample / specimen retrieval
- Test result ingestion
- Lab capacity and turnaround time reporting

EMR integration:
- Patient demographic sync
- Clinical encounter import
- Diagnosis and prescription data exchange
- HL7 FHIR R4 support
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# LIS — Laboratory Information System
# =============================================================================

class LISClient:
    """
    HTTP client for generic LIS REST APIs.
    Supports HL7 FHIR R4 and proprietary JSON endpoints.
    """

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.timeout = system.timeout_seconds
        self.fhir_mode = system.configuration.get('fhir_mode', False)
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})
        self._configure_auth()

    def _configure_auth(self):
        creds = self.system.get_credentials()
        auth_type = self.system.auth_type
        if auth_type == 'BASIC':
            self.session.auth = (creds.get('username', ''), creds.get('password', ''))
        elif auth_type in ('TOKEN', 'API_KEY'):
            self.session.headers.update({'Authorization': f"Bearer {creds.get('token', '')}"})

    def _url(self, path):
        base = f"{self.base_url}/fhir/R4" if self.fhir_mode else self.base_url
        return f"{base}/{path.lstrip('/')}"

    def get(self, path, params=None):
        response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path, payload):
        response = self.session.post(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> dict:
        try:
            path = 'metadata' if self.fhir_mode else 'health'
            self.get(path)
            return {'healthy': True, 'fhir_mode': self.fhir_mode}
        except requests.exceptions.ConnectionError as e:
            return {'healthy': False, 'error': str(e)}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Timeout'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # Specimens
    # -------------------------------------------------------------------------

    def get_specimens(
        self,
        since: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            if status:
                params['status'] = status
            return self.get('Specimen', params=params)
        else:
            params = {'page': page, 'pageSize': page_size}
            if since:
                params['since'] = since
            return self.get('specimens', params=params)

    # -------------------------------------------------------------------------
    # Diagnostic Reports / Results
    # -------------------------------------------------------------------------

    def get_diagnostic_reports(
        self,
        since: Optional[str] = None,
        patient_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            if patient_id:
                params['subject'] = f"Patient/{patient_id}"
            return self.get('DiagnosticReport', params=params)
        else:
            params = {'page': page, 'pageSize': page_size}
            if since:
                params['since'] = since
            return self.get('results', params=params)

    def get_observations(
        self,
        since: Optional[str] = None,
        category: str = 'laboratory',
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            return self.get('Observation', params={
                'category': category,
                '_count': page_size,
                '_page': page,
                **(({'_lastUpdated': f"gt{since}"}) if since else {}),
            })
        return self.get('observations', params={'page': page, 'pageSize': page_size})

    # -------------------------------------------------------------------------
    # Orders
    # -------------------------------------------------------------------------

    def get_service_requests(
        self,
        since: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            if status:
                params['status'] = status
            return self.get('ServiceRequest', params=params)
        return self.get('orders', params={'page': page, 'pageSize': page_size})

    def submit_order(self, payload: dict) -> dict:
        """Submit a lab order / service request."""
        if self.fhir_mode:
            return self.post('ServiceRequest', payload)
        return self.post('orders', payload)


class LISSyncService:
    """High-level LIS sync service."""

    def __init__(self, system):
        self.system = system
        self.client = LISClient(system)

    def import_lab_results(self, since: Optional[str] = None) -> dict:
        """Pull diagnostic reports from LIS and store in OryxShield."""
        from .models import IntegrationLog

        page = 1
        total = 0
        errors = []

        while True:
            try:
                data = self.client.get_diagnostic_reports(since=since, page=page, page_size=50)
                entries = self._extract_entries(data)
                if not entries:
                    break

                for entry in entries:
                    try:
                        self._upsert_lab_result(entry)
                        total += 1
                    except Exception as e:
                        errors.append({'id': self._entry_id(entry), 'error': str(e)})

                if self._is_last_page(data, page, 50):
                    break
                page += 1

            except Exception as e:
                logger.error(f"LIS import page {page}: {e}")
                break

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO' if not errors else 'WARNING',
            category='SYNC',
            message=f"LIS result import: {total} records",
            operation='import_lab_results',
        )

        return {'imported': total, 'errors': errors}

    def _extract_entries(self, data) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if 'entry' in data:  # FHIR Bundle
                return [e.get('resource', e) for e in data.get('entry', [])]
            return data.get('items', data.get('results', []))
        return []

    def _is_last_page(self, data, page, page_size) -> bool:
        if isinstance(data, dict):
            total_pages = data.get('totalPages', data.get('pageCount', 1))
            return page >= total_pages
        return len(self._extract_entries(data)) < page_size

    def _entry_id(self, entry) -> str:
        return entry.get('id', entry.get('uuid', ''))

    def _upsert_lab_result(self, report: dict):
        """
        Map LIS diagnostic report to OryxShield HealthData.
        Awaiting LIS API credentials and HL7/FHIR schema confirmation from government.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "LIS _upsert_lab_result: mapping not yet implemented — "
            "report_id=%s will not be saved. "
            "Implement when LIS API credentials and FHIR schema are available.",
            report.get('id', report.get('uuid', 'unknown')),
        )


# =============================================================================
# EMR — Electronic Medical Record
# =============================================================================

class EMRClient:
    """
    HTTP client for generic EMR REST APIs (HL7 FHIR R4 or proprietary).
    """

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.timeout = system.timeout_seconds
        self.fhir_mode = system.configuration.get('fhir_mode', True)
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})
        self._configure_auth()

    def _configure_auth(self):
        creds = self.system.get_credentials()
        auth_type = self.system.auth_type
        if auth_type == 'BASIC':
            self.session.auth = (creds.get('username', ''), creds.get('password', ''))
        elif auth_type == 'OAUTH2':
            self._acquire_oauth_token(creds)
        elif auth_type in ('TOKEN', 'API_KEY'):
            self.session.headers.update({'Authorization': f"Bearer {creds.get('token', '')}"})

    def _acquire_oauth_token(self, creds):
        try:
            resp = requests.post(
                creds.get('token_url', ''),
                data={
                    'grant_type': 'client_credentials',
                    'client_id': creds.get('client_id', ''),
                    'client_secret': creds.get('client_secret', ''),
                    'scope': creds.get('scope', 'system/*.read'),
                },
                timeout=30,
            )
            resp.raise_for_status()
            token = resp.json().get('access_token', '')
            self.session.headers.update({'Authorization': f"Bearer {token}"})
        except Exception as e:
            logger.error(f"EMR OAuth token failed: {e}")

    def _url(self, path):
        base = f"{self.base_url}/fhir/R4" if self.fhir_mode else self.base_url
        return f"{base}/{path.lstrip('/')}"

    def get(self, path, params=None):
        response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path, payload):
        response = self.session.post(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> dict:
        try:
            path = 'metadata' if self.fhir_mode else 'health'
            self.get(path)
            return {'healthy': True}
        except requests.exceptions.ConnectionError as e:
            return {'healthy': False, 'error': str(e)}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Timeout'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # Patients
    # -------------------------------------------------------------------------

    def get_patients(self, since: Optional[str] = None, page: int = 1, page_size: int = 50) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            return self.get('Patient', params=params)
        return self.get('patients', params={'page': page, 'pageSize': page_size, 'since': since})

    def get_patient(self, patient_id: str) -> dict:
        if self.fhir_mode:
            return self.get(f'Patient/{patient_id}')
        return self.get(f'patients/{patient_id}')

    # -------------------------------------------------------------------------
    # Encounters / Visits
    # -------------------------------------------------------------------------

    def get_encounters(
        self,
        since: Optional[str] = None,
        patient_id: Optional[str] = None,
        encounter_class: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            if patient_id:
                params['subject'] = f"Patient/{patient_id}"
            if encounter_class:
                params['class'] = encounter_class
            return self.get('Encounter', params=params)
        return self.get('encounters', params={'page': page, 'pageSize': page_size})

    # -------------------------------------------------------------------------
    # Conditions / Diagnoses
    # -------------------------------------------------------------------------

    def get_conditions(
        self,
        since: Optional[str] = None,
        icd_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            if icd_code:
                params['code'] = icd_code
            return self.get('Condition', params=params)
        return self.get('diagnoses', params={'page': page, 'pageSize': page_size})

    # -------------------------------------------------------------------------
    # Immunizations
    # -------------------------------------------------------------------------

    def get_immunizations(self, since: Optional[str] = None, page: int = 1, page_size: int = 50) -> dict:
        if self.fhir_mode:
            params = {'_count': page_size, '_page': page}
            if since:
                params['_lastUpdated'] = f"gt{since}"
            return self.get('Immunization', params=params)
        return self.get('immunizations', params={'page': page, 'pageSize': page_size})


class EMRSyncService:
    """High-level EMR sync service."""

    def __init__(self, system):
        self.system = system
        self.client = EMRClient(system)

    def import_clinical_data(self, since: Optional[str] = None) -> dict:
        """Pull encounters and conditions from EMR into OryxShield."""
        from .models import IntegrationLog

        imported = 0
        errors = []
        page = 1

        while True:
            try:
                data = self.client.get_encounters(since=since, page=page, page_size=50)
                entries = self._extract_fhir_entries(data)
                if not entries:
                    break

                for encounter in entries:
                    try:
                        self._upsert_encounter(encounter)
                        imported += 1
                    except Exception as e:
                        errors.append({'id': encounter.get('id', ''), 'error': str(e)})

                if self._is_last_page(data, page, 50):
                    break
                page += 1

            except Exception as e:
                logger.error(f"EMR import page {page}: {e}")
                break

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO' if not errors else 'WARNING',
            category='SYNC',
            message=f"EMR encounter import: {imported} records",
            operation='import_clinical_data',
        )

        return {'imported': imported, 'errors': errors}

    def _extract_fhir_entries(self, data) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if 'entry' in data:
                return [e.get('resource', {}) for e in data.get('entry', [])]
            return data.get('items', [])
        return []

    def _is_last_page(self, data, page, page_size) -> bool:
        entries = self._extract_fhir_entries(data)
        if isinstance(data, dict):
            total = data.get('total', data.get('totalPages', None))
            if total is not None:
                if 'total' in data:  # FHIR bundle total = total records
                    return page * page_size >= total
                return page >= total
        return len(entries) < page_size

    def _upsert_encounter(self, encounter: dict):
        """
        Map FHIR Encounter to OryxShield HealthData.
        Awaiting EMR API credentials and FHIR profile confirmation from government.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "EMR _upsert_encounter: mapping not yet implemented — "
            "encounter_id=%s will not be saved. "
            "Implement when EMR API credentials and FHIR R4 profile are available.",
            encounter.get('id', 'unknown'),
        )