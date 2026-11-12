"""
WHO EIOS (Epidemic Intelligence from Open Sources) integration.

Provides:
- Inbound signal fetch (open-source intelligence signals)
- Signal classification and deduplication
- Outbound event reporting to WHO IHR notification system
- Article / signal triage and forwarding
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class WHOEIOSClient:
    """
    HTTP client for the WHO EIOS REST API.
    """

    BASE_HEADERS = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.timeout = system.timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(self.BASE_HEADERS)
        self._configure_auth()

    def _configure_auth(self):
        creds = self.system.get_credentials()
        auth_type = self.system.auth_type

        if auth_type == 'API_KEY':
            self.session.headers.update({'X-API-Key': creds.get('api_key', '')})
        elif auth_type == 'TOKEN':
            self.session.headers.update({'Authorization': f"Bearer {creds.get('token', '')}"})
        elif auth_type == 'BASIC':
            self.session.auth = (creds.get('username', ''), creds.get('password', ''))

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

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
            self.get('health')
            return {'healthy': True}
        except requests.exceptions.ConnectionError as e:
            return {'healthy': False, 'error': f"Cannot connect: {e}"}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Timeout reaching WHO EIOS'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # Signals / Articles
    # -------------------------------------------------------------------------

    def get_signals(
        self,
        page: int = 1,
        page_size: int = 50,
        since: Optional[str] = None,
        disease_filter: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> dict:
        """
        Retrieve open-source signals from EIOS.
        Returns paged list of signal objects.
        """
        params = {
            'page': page,
            'pageSize': page_size,
        }
        if since:
            params['publishedAfter'] = since
        if disease_filter:
            params['disease'] = disease_filter
        if country_code:
            params['country'] = country_code
        return self.get('signals', params=params)

    def get_signal(self, signal_id: str) -> dict:
        return self.get(f'signals/{signal_id}')

    def get_articles(
        self,
        page: int = 1,
        page_size: int = 50,
        since: Optional[str] = None,
        keywords: Optional[list] = None,
    ) -> dict:
        params = {'page': page, 'pageSize': page_size}
        if since:
            params['publishedAfter'] = since
        if keywords:
            params['keywords'] = ','.join(keywords)
        return self.get('articles', params=params)

    # -------------------------------------------------------------------------
    # IHR Notifications (outbound)
    # -------------------------------------------------------------------------

    def submit_event_notification(self, payload: dict) -> dict:
        """
        Submit an IHR event notification to WHO.
        payload: {
            eventId, title, description, diseaseCode,
            location: {country, adminLevel1}, reportDate,
            cases: {suspected, confirmed, deaths},
            riskAssessment
        }
        """
        return self.post('notifications/ihr', payload)

    def submit_situation_report(self, payload: dict) -> dict:
        return self.post('reports/situation', payload)


class WHOEIOSSyncService:
    """
    High-level service for WHO EIOS signal ingestion and reporting.
    """

    def __init__(self, system):
        self.system = system
        self.client = WHOEIOSClient(system)
        self.config = system.configuration

    def ingest_signals(self, since: Optional[str] = None) -> dict:
        """
        Pull signals from EIOS and create/update OryxShield surveillance records.
        """
        from .models import IntegrationLog

        page = 1
        total = 0
        errors = []

        country_filter = self.config.get('country_filter')
        disease_filter = self.config.get('disease_filter')

        while True:
            try:
                data = self.client.get_signals(
                    page=page,
                    page_size=50,
                    since=since,
                    disease_filter=disease_filter,
                    country_code=country_filter,
                )
                signals = data.get('items', data) if isinstance(data, dict) else data
                if not signals:
                    break

                for signal in signals:
                    try:
                        self._process_signal(signal)
                        total += 1
                    except Exception as e:
                        errors.append({'signal_id': signal.get('id'), 'error': str(e)})
                        logger.warning(f"EIOS signal processing error: {e}")

                # Handle pagination — adapt to API structure
                if isinstance(data, dict):
                    total_pages = data.get('totalPages', 1)
                    if page >= total_pages:
                        break
                else:
                    if len(signals) < 50:
                        break
                page += 1

            except Exception as e:
                logger.error(f"WHO EIOS ingestion page {page} error: {e}")
                break

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO' if not errors else 'WARNING',
            category='SYNC',
            message=f"WHO EIOS signal ingest: {total} processed, {len(errors)} errors",
            operation='ingest_signals',
        )

        return {'processed': total, 'errors': errors}

    def report_outbreak(self, outbreak_id: str) -> dict:
        """
        Submit a OryxShield-detected outbreak as an IHR notification.
        """
        from surveillance.models import SurveillanceReport
        from .models import IntegrationLog

        try:
            report = SurveillanceReport.objects.get(id=outbreak_id)
        except Exception:
            raise ValueError(f"SurveillanceReport {outbreak_id} not found")

        payload = self._build_ihr_payload(report)
        result = self.client.submit_event_notification(payload)

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"IHR notification submitted for outbreak {outbreak_id}",
            operation='report_outbreak',
            entity_type='SurveillanceReport',
            entity_id=str(outbreak_id),
            response_data=result,
        )

        return result

    def _process_signal(self, signal: dict):
        """
        Map a WHO EIOS signal to a OryxShield surveillance data record.
        Awaiting WHO EIOS API credentials and signal schema confirmation.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "WHO EIOS _process_signal: mapping not yet implemented — "
            "signal_id=%s disease=%s will not be saved. "
            "Implement when WHO EIOS API credentials are available.",
            signal.get('id', 'unknown'),
            signal.get('disease', signal.get('diseaseVariant', 'unknown')),
        )

    def _build_ihr_payload(self, report) -> dict:
        return {
            'eventId': str(report.id),
            'title': getattr(report, 'title', str(report)),
            'description': getattr(report, 'summary', ''),
            'diseaseCode': getattr(report, 'disease_code', ''),
            'reportDate': report.created_at.isoformat(),
            'location': {
                'country': self.config.get('country_code', 'KE'),
            },
        }