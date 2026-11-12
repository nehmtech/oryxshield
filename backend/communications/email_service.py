"""
Email service for OryxShield communications.
Handles transactional and campaign email delivery with HTML templates.
"""
import logging
from typing import Dict, List, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """Sends emails through Django's configured email backend."""

    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@oryxshield.gov.na')
        self.reply_to = getattr(settings, 'DEFAULT_REPLY_TO_EMAIL', None)

    # ── Core send methods ─────────────────────────────────────────────────────

    def send_simple_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> bool:
        """
        Send a plain or HTML email.

        attachments: [{'filename': str, 'content': bytes, 'mimetype': str}]
        Returns True on success.
        """
        try:
            if html_body:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=self.from_email,
                    to=[to_email],
                    cc=cc or [],
                    bcc=bcc or [],
                    reply_to=[self.reply_to] if self.reply_to else None,
                )
                msg.attach_alternative(html_body, 'text/html')
                for att in (attachments or []):
                    msg.attach(
                        att['filename'],
                        att['content'],
                        att.get('mimetype', 'application/octet-stream'),
                    )
                msg.send(fail_silently=False)
            else:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=self.from_email,
                    recipient_list=[to_email],
                    fail_silently=False,
                )
            logger.info("Email sent to %s — %s", to_email, subject)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to_email, exc)
            return False

    def send_templated_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: Dict,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Render a Django template from communications/templates/emails/<template_name>.html
        and send as an HTML+plain email.
        """
        try:
            html_message = render_to_string(f'communications/emails/{template_name}.html', context)
            plain_message = strip_tags(html_message)
            return self.send_simple_email(
                to_email=to_email,
                subject=subject,
                body=plain_message,
                html_body=html_message,
                cc=cc,
                bcc=bcc,
            )
        except Exception as exc:
            logger.error("Failed to render/send templated email to %s: %s", to_email, exc)
            return False

    def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Dict[str, int]:
        """Send identical email to multiple recipients. Returns {'sent': n, 'failed': n}."""
        results = {'sent': 0, 'failed': 0}
        for recipient in recipients:
            if self.send_simple_email(recipient, subject, body, html_body):
                results['sent'] += 1
            else:
                results['failed'] += 1
        logger.info("Bulk email: %d sent, %d failed", results['sent'], results['failed'])
        return results

    # ── Domain-specific helpers ───────────────────────────────────────────────

    def send_health_alert(
        self,
        to_email: str,
        alert_title: str,
        alert_message: str,
        location_name: str,
        severity: str = 'MEDIUM',
    ) -> bool:
        """Send a colour-coded health alert email."""
        severity_colour = {
            'CRITICAL': '#dc3545',
            'HIGH': '#fd7e14',
            'MEDIUM': '#ffc107',
            'LOW': '#28a745',
        }.get(severity.upper(), '#6c757d')

        subject = f"Health Alert [{severity}]: {alert_title}"

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;">
          <div style="background-color:{severity_colour};color:#fff;padding:15px;border-radius:5px;">
            <h2 style="margin:0;">&#9888; {alert_title}</h2>
          </div>
          <div style="margin-top:20px;padding:20px;background:#f8f9fa;border-radius:5px;">
            <p><strong>Location:</strong> {location_name}</p>
            <p><strong>Severity:</strong> {severity}</p>
            <hr style="border:1px solid #dee2e6;">
            <div style="margin-top:15px;">{alert_message}</div>
          </div>
          <div style="margin-top:20px;padding:15px;background:#e9ecef;border-radius:5px;">
            <p style="margin:0;font-size:12px;color:#6c757d;">
              Automated message from OryxShield.
              Contact your local health authority for further guidance.
            </p>
          </div>
        </div></body></html>
        """
        plain_body = (
            f"HEALTH ALERT [{severity}]: {alert_title}\n\n"
            f"Location: {location_name}\n\n"
            f"{alert_message}\n\n"
            "---\nOryxShield automated notification."
        )
        return self.send_simple_email(to_email, subject, plain_body, html_body)

    def send_vaccination_reminder(
        self,
        to_email: str,
        recipient_name: str,
        appointment_date: str,
        location: str,
        vaccine_type: str,
    ) -> bool:
        """Send vaccination appointment reminder."""
        subject = f"Vaccination Appointment Reminder — {appointment_date}"
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;">
          <div style="background:#007bff;color:#fff;padding:15px;border-radius:5px;">
            <h2 style="margin:0;">&#128137; Vaccination Appointment Reminder</h2>
          </div>
          <div style="margin-top:20px;padding:20px;background:#f8f9fa;border-radius:5px;">
            <p>Dear {recipient_name},</p>
            <p>This is a reminder about your upcoming vaccination appointment:</p>
            <table style="width:100%;margin:15px 0;border-collapse:collapse;">
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Date &amp; Time:</strong></td>
                  <td style="padding:8px;">{appointment_date}</td></tr>
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Location:</strong></td>
                  <td style="padding:8px;">{location}</td></tr>
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Vaccine:</strong></td>
                  <td style="padding:8px;">{vaccine_type}</td></tr>
            </table>
            <p><strong>Please bring:</strong> National ID or Passport, previous vaccination card (if any), mask.</p>
            <p>Arrive 10 minutes early. To reschedule, contact your health facility.</p>
          </div>
          <div style="margin-top:20px;padding:15px;background:#e9ecef;border-radius:5px;">
            <p style="margin:0;font-size:12px;color:#6c757d;">OryxShield — stay safe and healthy.</p>
          </div>
        </div></body></html>
        """
        plain_body = (
            f"VACCINATION APPOINTMENT REMINDER\n\n"
            f"Dear {recipient_name},\n\n"
            f"Date & Time: {appointment_date}\n"
            f"Location: {location}\n"
            f"Vaccine: {vaccine_type}\n\n"
            "Please bring: National ID, previous vaccination card, mask.\n"
            "Arrive 10 minutes early.\n\n"
            "OryxShield Team"
        )
        return self.send_simple_email(to_email, subject, plain_body, html_body)

    def send_test_result_notification(
        self,
        to_email: str,
        recipient_name: str,
        test_type: str,
        result: str,
        tested_date: str,
        instructions: str,
    ) -> bool:
        """Send test result notification."""
        subject = f"Test Results Available — {test_type}"
        result_colour = '#28a745' if result.upper() == 'NEGATIVE' else '#dc3545'
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;">
          <div style="background:#6c757d;color:#fff;padding:15px;border-radius:5px;">
            <h2 style="margin:0;">&#128300; Test Results Available</h2>
          </div>
          <div style="margin-top:20px;padding:20px;background:#f8f9fa;border-radius:5px;">
            <p>Dear {recipient_name},</p>
            <table style="width:100%;margin:15px 0;border-collapse:collapse;">
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Test Type:</strong></td>
                  <td style="padding:8px;">{test_type}</td></tr>
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Test Date:</strong></td>
                  <td style="padding:8px;">{tested_date}</td></tr>
              <tr><td style="padding:8px;background:#e9ecef;"><strong>Result:</strong></td>
                  <td style="padding:8px;color:{result_colour};font-weight:bold;">{result}</td></tr>
            </table>
            <div style="margin-top:20px;padding:15px;background:#fff;border-left:4px solid #007bff;">
              <p><strong>Next Steps:</strong></p><p>{instructions}</p>
            </div>
          </div>
          <div style="margin-top:20px;padding:15px;background:#fff3cd;border-radius:5px;">
            <p style="margin:0;font-size:12px;">
              <strong>Important:</strong> For medical advice, consult a qualified healthcare professional.
            </p>
          </div>
        </div></body></html>
        """
        plain_body = (
            f"TEST RESULTS AVAILABLE\n\nDear {recipient_name},\n\n"
            f"Test Type: {test_type}\nTest Date: {tested_date}\nResult: {result}\n\n"
            f"Next Steps:\n{instructions}\n\n"
            "For medical advice, consult a qualified healthcare professional."
        )
        return self.send_simple_email(to_email, subject, plain_body, html_body)

    def send_feedback_response(
        self,
        to_email: str,
        sender_name: str,
        original_subject: str,
        response_text: str,
    ) -> bool:
        """Send a response to a feedback submission."""
        subject = f"Re: {original_subject}"
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:20px;">
          <div style="background:#17a2b8;color:#fff;padding:15px;border-radius:5px;">
            <h2 style="margin:0;">Response to Your Feedback</h2>
          </div>
          <div style="margin-top:20px;padding:20px;background:#f8f9fa;border-radius:5px;">
            <p>Dear {sender_name},</p>
            <p>Thank you for reaching out. Here is our response to your inquiry:</p>
            <div style="margin-top:15px;padding:15px;background:#fff;border-left:4px solid #17a2b8;">
              {response_text}
            </div>
          </div>
          <div style="margin-top:20px;padding:15px;background:#e9ecef;border-radius:5px;">
            <p style="margin:0;font-size:12px;color:#6c757d;">OryxShield — Communications Team</p>
          </div>
        </div></body></html>
        """
        plain_body = (
            f"Dear {sender_name},\n\n"
            f"Thank you for reaching out. Our response to your inquiry:\n\n"
            f"{response_text}\n\n"
            "OryxShield — Communications Team"
        )
        return self.send_simple_email(to_email, subject, plain_body, html_body)


# Singleton instance
email_service = EmailService()