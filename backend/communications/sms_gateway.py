"""
SMS Gateway service for OryxShield communications.
Supports Africa's Talking and Twilio with automatic fallback.
Default country: Namibia (+264).
"""
import logging
import uuid
from typing import Dict, List

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSProvider:
    """Base class for SMS providers."""

    def send(self, phone_number: str, message: str) -> Dict:
        raise NotImplementedError

    def get_delivery_status(self, message_id: str) -> Dict:
        raise NotImplementedError


# ── Africa's Talking ───────────────────────────────────────────────────────────

class AfricasTalkingProvider(SMSProvider):

    def __init__(self):
        self.api_key = getattr(settings, 'AFRICAS_TALKING_API_KEY', '')
        self.username = getattr(settings, 'AFRICAS_TALKING_USERNAME', 'sandbox')
        self.sender_id = getattr(settings, 'AFRICAS_TALKING_SENDER_ID', 'ORYXSHIELD')
        self.base_url = 'https://api.africastalking.com/version1'

    def send(self, phone_number: str, message: str) -> Dict:
        if not self.api_key:
            return {'success': False, 'message_id': '', 'error': 'API key not configured'}
        try:
            response = requests.post(
                f"{self.base_url}/messaging",
                headers={
                    'apiKey': self.api_key,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                },
                data={
                    'username': self.username,
                    'to': phone_number,
                    'message': message,
                    'from': self.sender_id,
                },
                timeout=30,
            )
            response.raise_for_status()
            recipients = response.json().get('SMSMessageData', {}).get('Recipients', [])
            if recipients and recipients[0].get('status') == 'Success':
                return {'success': True, 'message_id': recipients[0].get('messageId', ''), 'error': ''}
            error = recipients[0].get('status', 'Unknown error') if recipients else 'No recipient data'
            return {'success': False, 'message_id': '', 'error': error}
        except Exception as exc:
            logger.error("Africa's Talking error: %s", exc)
            return {'success': False, 'message_id': '', 'error': str(exc)}

    def get_delivery_status(self, message_id: str) -> Dict:
        try:
            response = requests.get(
                f"{self.base_url}/messaging/deliveryreports",
                headers={'apiKey': self.api_key, 'Accept': 'application/json'},
                params={'username': self.username, 'messageId': message_id},
                timeout=30,
            )
            response.raise_for_status()
            reports = response.json().get('SMSMessageData', {}).get('DeliveryReports', [])
            if reports:
                return {'status': reports[0].get('status', 'Unknown'), 'delivered_at': reports[0].get('deliveredAt')}
            return {'status': 'Unknown', 'delivered_at': None}
        except Exception as exc:
            logger.error("AT delivery status error: %s", exc)
            return {'status': 'Error', 'delivered_at': None}


# ── Twilio ─────────────────────────────────────────────────────────────────────

class TwilioProvider(SMSProvider):

    def __init__(self):
        self.account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        self.auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        self.from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '')
        self.base_url = f'https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}'

    def send(self, phone_number: str, message: str) -> Dict:
        if not self.account_sid or not self.auth_token:
            return {'success': False, 'message_id': '', 'error': 'Twilio credentials not configured'}
        try:
            response = requests.post(
                f"{self.base_url}/Messages.json",
                data={'To': phone_number, 'From': self.from_number, 'Body': message},
                auth=(self.account_sid, self.auth_token),
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            return {'success': True, 'message_id': result.get('sid', ''), 'error': ''}
        except Exception as exc:
            logger.error("Twilio error: %s", exc)
            return {'success': False, 'message_id': '', 'error': str(exc)}

    def get_delivery_status(self, message_id: str) -> Dict:
        try:
            response = requests.get(
                f"{self.base_url}/Messages/{message_id}.json",
                auth=(self.account_sid, self.auth_token),
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            return {'status': result.get('status', 'Unknown'), 'delivered_at': result.get('date_sent')}
        except Exception as exc:
            logger.error("Twilio delivery status error: %s", exc)
            return {'status': 'Error', 'delivered_at': None}


# ── Local/mock ─────────────────────────────────────────────────────────────────

class LocalSMSProvider(SMSProvider):
    """Mock provider for development/testing — logs rather than sends."""

    def send(self, phone_number: str, message: str) -> Dict:
        mock_id = str(uuid.uuid4())
        logger.info("[LOCAL SMS] To=%s Message=%s", phone_number, message)
        return {'success': True, 'message_id': mock_id, 'error': ''}

    def get_delivery_status(self, message_id: str) -> Dict:
        from django.utils import timezone
        return {'status': 'delivered', 'delivered_at': timezone.now()}


# ── Gateway ────────────────────────────────────────────────────────────────────

class SMSGateway:
    """
    Multi-provider SMS gateway with automatic fallback.
    Configure PRIMARY_SMS_PROVIDER and FALLBACK_SMS_PROVIDER in settings.
    Accepted values: 'africas_talking', 'twilio', 'local' (default).
    """

    PROVIDER_MAP = {
        'africas_talking': AfricasTalkingProvider,
        'twilio': TwilioProvider,
        'local': LocalSMSProvider,
    }

    def __init__(self):
        self.primary = self._build_provider('PRIMARY_SMS_PROVIDER')
        self.fallback = self._build_provider('FALLBACK_SMS_PROVIDER')

    def _build_provider(self, setting_key: str) -> SMSProvider:
        name = getattr(settings, setting_key, 'local').lower()
        cls = self.PROVIDER_MAP.get(name, LocalSMSProvider)
        return cls()

    # ── Public API ─────────────────────────────────────────────────────────────

    def send_sms(
        self,
        phone_number: str,
        message: str,
        use_fallback: bool = True,
    ) -> Dict:
        """
        Send SMS with optional fallback.
        Returns {'success', 'message_id', 'error', 'provider'}.
        """
        phone_number = self._normalize_phone(phone_number)
        if len(message) > 1600:
            logger.warning("SMS message truncated from %d chars", len(message))
            message = message[:1600]

        result = self.primary.send(phone_number, message)
        result['provider'] = 'primary'

        if not result['success'] and use_fallback:
            logger.warning("Primary SMS provider failed; trying fallback")
            result = self.fallback.send(phone_number, message)
            result['provider'] = 'fallback'

        return result

    def send_bulk_sms(self, phone_numbers: List[str], message: str) -> Dict[str, int]:
        """Send same message to multiple numbers. Returns {'sent', 'failed'}."""
        counts = {'sent': 0, 'failed': 0}
        for number in phone_numbers:
            if self.send_sms(number, message)['success']:
                counts['sent'] += 1
            else:
                counts['failed'] += 1
        logger.info("Bulk SMS: %d sent, %d failed", counts['sent'], counts['failed'])
        return counts

    def get_delivery_status(self, message_id: str, provider: str = 'primary') -> Dict:
        src = self.fallback if provider == 'fallback' else self.primary
        return src.get_delivery_status(message_id)

    # ── Domain helpers ─────────────────────────────────────────────────────────

    def send_health_alert_sms(
        self,
        phone_number: str,
        alert_title: str,
        location: str,
        severity: str = 'MEDIUM',
    ) -> Dict:
        prefix = {'CRITICAL': '🚨 URGENT', 'HIGH': '⚠️ ALERT', 'MEDIUM': 'ℹ️ NOTICE', 'LOW': 'INFO'}.get(
            severity.upper(), 'ALERT'
        )
        message = f"{prefix}: {alert_title} in {location}. See portal or call 999."
        return self.send_sms(phone_number, message)

    def send_vaccination_reminder_sms(
        self,
        phone_number: str,
        recipient_name: str,
        appointment_date: str,
        location: str,
    ) -> Dict:
        message = (
            f"Reminder: {recipient_name}, your vaccination appointment is on "
            f"{appointment_date} at {location}. Bring ID and mask."
        )
        return self.send_sms(phone_number, message)

    def send_test_result_sms(
        self,
        phone_number: str,
        result: str,
        instructions: str,
    ) -> Dict:
        message = f"Your test result: {result}. {instructions}. See portal for full details."
        return self.send_sms(phone_number, message)

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalize_phone(phone_number: str) -> str:
        """Normalise to E.164 format, defaulting to Namibia (+264)."""
        digits = ''.join(filter(str.isdigit, phone_number))
        if digits.startswith('0') and len(digits) <= 10:
            digits = '254' + digits[1:]
        return '+' + digits


# Singleton instance
sms_gateway = SMSGateway()