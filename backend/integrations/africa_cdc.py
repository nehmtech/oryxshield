"""
Africa CDC integration service for OryxShield.

Handles reporting to Africa CDC (African Union's public health agency):
- Continental disease surveillance data reporting
- Emergency event notifications
- Integrated Disease Surveillance and Response (IDSR) data exchange
- Cross-border epidemic alerts
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class AfricaCDCClient:
    """
    HTTP client for Africa CDC data exchange API.
    """

    def __init__(self, system):
        self.system = system
        self.base_url = system.base_url.rstrip('/')
        self.timeout = system.timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
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
        elif auth_type == 'OAUTH2':
            token = self._fetch_oauth_token(creds)
            if token:
                self.session.headers.update({'Authorization': f"Bearer {token}"})

    def _fetch_oauth_token(self, creds: dict) -> Optional[str]:
        try:
            resp = requests.post(
                creds.get('token_url', ''),
                data={
                    'grant_type': 'client_credentials',
                    'client_id': creds.get('client_id', ''),
                    'client_secret': creds.get('client_secret', ''),
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get('access_token')
        except Exception as e:
            logger.error(f"Africa CDC OAuth token fetch failed: {e}")
            return None

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
            return {'healthy': False, 'error': str(e)}
        except requests.exceptions.Timeout:
            return {'healthy': False, 'error': 'Timeout'}
        except requests.exceptions.HTTPError as e:
            return {'healthy': False, 'error': f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {'healthy': False, 'error': str(e)}

    # -------------------------------------------------------------------------
    # IDSR Weekly Reports
    # -------------------------------------------------------------------------

    def submit_weekly_report(self, payload: dict) -> dict:
        """
        Submit an IDSR weekly disease burden report.
        payload: {
            country, week, year,
            diseases: [{diseaseCode, suspected, confirmed, deaths, ...}, ...]
        }
        """
        return self.post('idsr/weekly', payload)

    def get_weekly_reports(
        self,
        country: str,
        year: int,
        week_from: Optional[int] = None,
        week_to: Optional[int] = None,
    ) -> list:
        params = {'country': country, 'year': year}
        if week_from:
            params['weekFrom'] = week_from
        if week_to:
            params['weekTo'] = week_to
        data = self.get('idsr/weekly', params=params)
        return data if isinstance(data, list) else data.get('items', [])

    # -------------------------------------------------------------------------
    # Emergency Event Notifications
    # -------------------------------------------------------------------------

    def notify_emergency(self, payload: dict) -> dict:
        """
        Submit an emergency public health event notification.
        payload: {
            eventType, title, description, countryCode,
            latitude, longitude, startDate,
            diseaseCodes: [...], riskLevel
        }
        """
        return self.post('events/emergency', payload)

    def get_cross_border_alerts(
        self,
        country: str,
        since: Optional[str] = None,
    ) -> list:
        params = {'country': country}
        if since:
            params['since'] = since
        data = self.get('alerts/crossborder', params=params)
        return data if isinstance(data, list) else data.get('items', [])

    # -------------------------------------------------------------------------
    # Continental Surveillance Data
    # -------------------------------------------------------------------------

    def get_continental_trends(
        self,
        disease_code: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        return self.get('surveillance/trends', params={
            'disease': disease_code,
            'startDate': start_date,
            'endDate': end_date,
        })

    def submit_case_report(self, payload: dict) -> dict:
        """Submit an individual or aggregate case report."""
        return self.post('cases/report', payload)


class AfricaCDCSyncService:
    """
    High-level service for Africa CDC data reporting.
    """

    def __init__(self, system):
        self.system = system
        self.client = AfricaCDCClient(system)
        self.config = system.configuration

    def submit_weekly_idsr(self, year: int, week: int) -> dict:
        """
        Build and submit a weekly IDSR report from OryxShield data.
        """
        from surveillance.models import HealthData, DiseaseProfile
        from .models import IntegrationLog
        import datetime

        country = self.config.get('country_code', 'KE')

        # Calculate week date range
        jan4 = datetime.date(year, 1, 4)
        week_start = jan4 + datetime.timedelta(weeks=week - 1, days=-jan4.weekday())
        week_end = week_start + datetime.timedelta(days=6)

        diseases = DiseaseProfile.objects.filter(is_deleted=False, is_active=True)
        disease_rows = []

        for disease in diseases:
            qs = HealthData.objects.filter(
                is_deleted=False,
                disease_code=disease.code,
                report_date__range=(week_start, week_end)
            )
            suspected = qs.filter(case_status='SUSPECTED').count()
            confirmed = qs.filter(case_status='CONFIRMED').count()
            deaths = qs.filter(outcome='DIED').count()

            if suspected + confirmed + deaths > 0:
                disease_rows.append({
                    'diseaseCode': disease.code,
                    'diseaseName': disease.name,
                    'suspected': suspected,
                    'confirmed': confirmed,
                    'deaths': deaths,
                    'total': suspected + confirmed,
                })

        if not disease_rows:
            return {'status': 'skipped', 'reason': 'No reportable data'}

        payload = {
            'country': country,
            'year': year,
            'week': week,
            'weekStart': week_start.isoformat(),
            'weekEnd': week_end.isoformat(),
            'diseases': disease_rows,
        }

        result = self.client.submit_weekly_report(payload)

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"Africa CDC IDSR week {week}/{year}: {len(disease_rows)} diseases reported",
            operation='submit_weekly_idsr',
            response_data=result,
        )

        return result

    def report_outbreak_to_cdc(self, alert_id: str) -> dict:
        """
        Submit a OryxShield high-severity alert as an Africa CDC emergency notification.
        """
        from risk_assessment.models import Alert
        from .models import IntegrationLog

        try:
            alert = Alert.objects.select_related('location').get(id=alert_id)
        except Exception:
            raise ValueError(f"Alert {alert_id} not found")

        payload = {
            'eventType': 'OUTBREAK',
            'title': str(alert),
            'countryCode': self.config.get('country_code', 'KE'),
            'startDate': alert.created_at.date().isoformat(),
            'riskLevel': alert.severity if hasattr(alert, 'severity') else 'HIGH',
        }

        if hasattr(alert, 'location') and alert.location:
            payload['latitude'] = float(getattr(alert.location, 'latitude', 0) or 0)
            payload['longitude'] = float(getattr(alert.location, 'longitude', 0) or 0)

        result = self.client.notify_emergency(payload)

        alert.metadata['africa_cdc_notified'] = True
        alert.metadata['africa_cdc_response'] = result
        alert.save(update_fields=['metadata', 'updated_at'])

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"Africa CDC emergency notification sent for alert {alert_id}",
            operation='report_outbreak',
            entity_type='Alert',
            entity_id=str(alert_id),
            response_data=result,
        )

        return result

    def ingest_cross_border_alerts(self) -> dict:
        """
        Pull cross-border alerts from Africa CDC and create OryxShield risk alerts.
        """
        from .models import IntegrationLog

        country = self.config.get('country_code', 'KE')
        last_sync = self.system.last_sync
        since = last_sync.isoformat() if last_sync else None

        alerts = self.client.get_cross_border_alerts(country=country, since=since)
        imported = 0
        errors = []

        for alert_dto in alerts:
            try:
                self._create_risk_alert(alert_dto)
                imported += 1
            except Exception as e:
                errors.append({'id': alert_dto.get('id'), 'error': str(e)})

        IntegrationLog.objects.create(
            external_system=self.system,
            log_level='INFO',
            category='SYNC',
            message=f"Africa CDC cross-border alerts: {imported} imported",
            operation='ingest_cross_border_alerts',
        )

        return {'imported': imported, 'errors': errors}

    def _create_risk_alert(self, alert_dto: dict):
        """
        Map Africa CDC cross-border alert to OryxShield risk assessment.
        Awaiting Africa CDC API credentials and alert schema confirmation.
        This method will be completed once credentials are received.
        """
        import logging as _log
        _log.getLogger(__name__).warning(
            "Africa CDC _create_risk_alert: mapping not yet implemented — "
            "alert_id=%s disease=%s will not be saved. "
            "Implement when Africa CDC API credentials are available.",
            alert_dto.get('id', alert_dto.get('alertId', 'unknown')),
            alert_dto.get('disease', alert_dto.get('pathogen', 'unknown')),
        )