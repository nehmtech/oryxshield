"""
Push notification service for OryxShield communications.

Provider selection (set in settings / .env):
  PUSH_NOTIFICATION_PROVIDER = 'fcm'   → Firebase Cloud Messaging v1 (production)
  PUSH_NOTIFICATION_PROVIDER = 'local' → Console logger (development, default)

FCM v1 via firebase_admin SDK (already in requirements.txt):
  Required .env vars (once Firebase project is created):
    FCM_SERVICE_ACCOUNT_JSON  — path to service-account.json   OR
    GOOGLE_APPLICATION_CREDENTIALS — standard GCP env var       OR
    FCM_SERVICE_ACCOUNT_DICT  — JSON string of service account (for env-only deploys)
    FCM_PROJECT_ID            — Firebase project ID (e.g. "oryxshield-prod")
"""
import json
import logging
import uuid
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class PushProvider:
    """Base class for push notification providers."""

    def send(self, device_token: str, title: str, body: str, data: Optional[Dict] = None) -> Dict:
        raise NotImplementedError

    def send_multicast(
        self, device_tokens: List[str], title: str, body: str, data: Optional[Dict] = None
    ) -> Dict:
        raise NotImplementedError


# ── Firebase Cloud Messaging v1 (via firebase_admin SDK) ─────────────────────

class FCMProvider(PushProvider):
    """
    Firebase Cloud Messaging using the official firebase_admin SDK (FCM HTTP v1).

    This replaces the deprecated legacy API (fcm.googleapis.com/fcm/send) which
    Google shut down in June 2023. The firebase_admin SDK uses OAuth2 + the
    modern FCM v1 endpoint (fcm.googleapis.com/v1/projects/…/messages:send).

    Configuration (add to .env when Firebase project is ready):
        FCM_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
        FCM_PROJECT_ID=your-firebase-project-id
    """

    _app = None  # shared firebase_admin.App singleton

    def __init__(self):
        self._configured = False
        self._init_firebase()

    def _init_firebase(self) -> None:
        """Initialise firebase_admin app once per process."""
        if FCMProvider._app is not None:
            self._configured = True
            return

        try:
            import firebase_admin
            from firebase_admin import credentials as fb_creds

            # Option 1: path to service-account JSON file
            sa_json_path = getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', '')
            # Option 2: inline JSON string (useful for Railway/Heroku env vars)
            sa_json_dict = getattr(settings, 'FCM_SERVICE_ACCOUNT_DICT', None)

            if sa_json_path:
                cred = fb_creds.Certificate(sa_json_path)
            elif sa_json_dict:
                if isinstance(sa_json_dict, str):
                    sa_json_dict = json.loads(sa_json_dict)
                cred = fb_creds.Certificate(sa_json_dict)
            else:
                # Attempt Application Default Credentials
                # (works on GCP, or when GOOGLE_APPLICATION_CREDENTIALS is set)
                cred = fb_creds.ApplicationDefault()

            project_id = getattr(settings, 'FCM_PROJECT_ID', None)
            options = {'projectId': project_id} if project_id else {}
            FCMProvider._app = firebase_admin.initialize_app(cred, options)
            self._configured = True
            logger.info("FCM firebase_admin initialised (project=%s)", project_id or 'default')

        except Exception as exc:
            logger.warning(
                "FCM not configured — push notifications will use local mock. "
                "Set FCM_SERVICE_ACCOUNT_JSON and FCM_PROJECT_ID in .env to enable. "
                "Error: %s", exc,
            )
            self._configured = False

    def send(
        self, device_token: str, title: str, body: str, data: Optional[Dict] = None
    ) -> Dict:
        if not self._configured:
            return {'success': False, 'message_id': '', 'error': 'FCM not configured'}
        try:
            from firebase_admin import messaging
            msg = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=device_token,
                android=messaging.AndroidConfig(priority='high'),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound='default')
                    )
                ),
                data={str(k): str(v) for k, v in (data or {}).items()},
            )
            message_id = messaging.send(msg, app=FCMProvider._app)
            return {'success': True, 'message_id': message_id, 'error': ''}
        except Exception as exc:
            logger.error("FCM send error: %s", exc)
            return {'success': False, 'message_id': '', 'error': str(exc)}

    def send_multicast(
        self, device_tokens: List[str], title: str, body: str, data: Optional[Dict] = None
    ) -> Dict:
        if not self._configured:
            return {'success_count': 0, 'failure_count': len(device_tokens), 'error': 'FCM not configured'}
        try:
            from firebase_admin import messaging

            # firebase_admin supports up to 500 tokens per multicast call
            success_count = 0
            failure_count = 0
            results = []
            chunk_size = 500

            str_data = {str(k): str(v) for k, v in (data or {}).items()}

            for i in range(0, len(device_tokens), chunk_size):
                chunk = device_tokens[i: i + chunk_size]
                multicast_msg = messaging.MulticastMessage(
                    notification=messaging.Notification(title=title, body=body),
                    tokens=chunk,
                    android=messaging.AndroidConfig(priority='high'),
                    data=str_data,
                )
                response = messaging.send_each_for_multicast(multicast_msg, app=FCMProvider._app)
                success_count += response.success_count
                failure_count += response.failure_count
                results.extend([
                    {'success': r.message_id is not None, 'message_id': r.message_id or '',
                     'error': str(r.exception) if r.exception else ''}
                    for r in response.responses
                ])

            return {'success_count': success_count, 'failure_count': failure_count, 'results': results}
        except Exception as exc:
            logger.error("FCM multicast error: %s", exc)
            return {'success_count': 0, 'failure_count': len(device_tokens), 'error': str(exc)}


# ── Local mock ─────────────────────────────────────────────────────────────────

class LocalPushProvider(PushProvider):
    """Development mock — logs instead of sending real push notifications."""

    def send(
        self, device_token: str, title: str, body: str, data: Optional[Dict] = None
    ) -> Dict:
        logger.info("[LOCAL PUSH] token=%s… title=%s body=%s", device_token[:20], title, body)
        return {'success': True, 'message_id': str(uuid.uuid4()), 'error': ''}

    def send_multicast(
        self, device_tokens: List[str], title: str, body: str, data: Optional[Dict] = None
    ) -> Dict:
        logger.info("[LOCAL PUSH MULTICAST] count=%d title=%s", len(device_tokens), title)
        return {'success_count': len(device_tokens), 'failure_count': 0}


# ── Service ────────────────────────────────────────────────────────────────────

class PushNotificationService:
    """
    Push notification service.

    Production: set PUSH_NOTIFICATION_PROVIDER=fcm in .env and provide FCM credentials.
    Development: defaults to local console mock.
    """

    def __init__(self):
        provider_name = getattr(settings, 'PUSH_NOTIFICATION_PROVIDER', 'local').lower()
        if provider_name == 'fcm':
            candidate = FCMProvider()
            # If FCM init failed (credentials not set), fall back to local
            self.provider: PushProvider = candidate if candidate._configured else LocalPushProvider()
        else:
            self.provider = LocalPushProvider()

    def send_notification(
        self,
        device_token: str,
        title: str,
        message: str,
        data: Optional[Dict] = None,
        notification_type: str = 'general',
    ) -> Dict:
        """Send push notification to a single device."""
        payload = dict(data or {})
        payload['type'] = notification_type
        result = self.provider.send(device_token, title, message, payload)
        if not result['success']:
            logger.error("Push notification failed: %s", result.get('error'))
        return result

    def send_bulk_notifications(
        self,
        device_tokens: List[str],
        title: str,
        message: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        """Send same notification to multiple devices."""
        result = self.provider.send_multicast(device_tokens, title, message, data)
        logger.info(
            "Bulk push: %d sent, %d failed",
            result.get('success_count', 0),
            result.get('failure_count', 0),
        )
        return result

    # ── Domain helpers ─────────────────────────────────────────────────────────

    def send_health_alert(
        self,
        device_token: str,
        alert_title: str,
        alert_message: str,
        severity: str = 'MEDIUM',
        location: str = '',
    ) -> Dict:
        emoji = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': 'ℹ️', 'LOW': '📢'}.get(severity, 'ℹ️')
        return self.send_notification(
            device_token=device_token,
            title=f"{emoji} Health Alert",
            message=f"{alert_title} — {alert_message}",
            data={'alert_title': alert_title, 'severity': severity, 'location': location, 'action': 'open_alert'},
            notification_type='health_alert',
        )

    def send_vaccination_reminder(
        self,
        device_token: str,
        recipient_name: str,
        appointment_date: str,
        location: str,
        vaccine_type: str,
    ) -> Dict:
        return self.send_notification(
            device_token=device_token,
            title="💉 Vaccination Reminder",
            message=f"Hi {recipient_name}, your {vaccine_type} appointment is on {appointment_date}",
            data={
                'appointment_date': appointment_date,
                'location': location,
                'vaccine_type': vaccine_type,
                'action': 'open_appointment',
            },
            notification_type='vaccination_reminder',
        )

    def send_test_result(self, device_token: str, test_type: str, result: str) -> Dict:
        return self.send_notification(
            device_token=device_token,
            title="🔬 Test Results Available",
            message=f"Your {test_type} results are ready to view",
            data={'test_type': test_type, 'result': result, 'action': 'open_results'},
            notification_type='test_result',
        )

    def send_outbreak_alert(
        self,
        device_tokens: List[str],
        disease_name: str,
        location: str,
        case_count: int,
    ) -> Dict:
        return self.send_bulk_notifications(
            device_tokens=device_tokens,
            title=f"🚨 {disease_name} Alert",
            message=f"{case_count} cases reported in {location}. Stay safe and follow guidelines.",
            data={'disease_name': disease_name, 'location': location, 'case_count': case_count, 'action': 'open_outbreak'},
        )

    def send_lockdown_notification(
        self,
        device_tokens: List[str],
        location: str,
        lockdown_level: str,
        start_date: str,
        restrictions: List[str],
    ) -> Dict:
        return self.send_bulk_notifications(
            device_tokens=device_tokens,
            title=f"🔒 Lockdown Notice — {location}",
            message=f"Level {lockdown_level} lockdown starts {start_date}. Check app for details.",
            data={
                'location': location,
                'lockdown_level': lockdown_level,
                'start_date': start_date,
                'restrictions': str(restrictions),
                'action': 'open_lockdown',
            },
        )


# Singleton instance
push_service = PushNotificationService()
