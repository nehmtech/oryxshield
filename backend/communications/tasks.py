"""
Celery tasks for communications app.
All mutation tasks use update_fields; scheduled tasks are idempotent.
"""
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Single-message delivery ────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_notification(self, phone_number: str, title: str, message: str, message_id: str = None):
    """
    Send an SMS notification.

    If message_id is provided the existing Message record is updated in-place;
    otherwise a new record is created so the task is safe to use standalone.
    """
    from communications.models import Message
    from communications.sms_gateway import sms_gateway

    logger.info("Sending SMS to %s", phone_number)

    if message_id:
        msg = Message.objects.get(id=message_id)
    else:
        msg = Message.objects.create(
            channel='SMS',
            recipient_identifier=phone_number,
            subject=title,
            body=message,
            status='QUEUED',
        )

    try:
        result = sms_gateway.send_sms(phone_number, message)
        if result['success']:
            msg.mark_sent(provider_id=result.get('message_id', ''))
            logger.info("SMS sent to %s (provider_id=%s)", phone_number, result.get('message_id'))
            return {'status': 'success', 'message_id': str(msg.id), 'provider_id': result.get('message_id')}
        raise RuntimeError(result.get('error', 'SMS provider returned failure'))
    except Exception as exc:
        msg.mark_failed(str(exc))
        logger.error("SMS to %s failed: %s", phone_number, exc)
        if msg.can_retry():
            raise self.retry(exc=exc)
        return {'status': 'failed', 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(
    self,
    email: str,
    subject: str,
    body: str,
    html_body: str = None,
    message_id: str = None,
):
    """Send an email notification. Creates or updates a Message record."""
    from communications.models import Message
    from communications.email_service import email_service

    logger.info("Sending email to %s — %s", email, subject)

    if message_id:
        msg = Message.objects.get(id=message_id)
    else:
        msg = Message.objects.create(
            channel='EMAIL',
            recipient_identifier=email,
            subject=subject,
            body=body,
            status='QUEUED',
        )

    try:
        success = email_service.send_simple_email(
            to_email=email, subject=subject, body=body, html_body=html_body
        )
        if success:
            msg.mark_sent()
            logger.info("Email sent to %s", email)
            return {'status': 'success', 'message_id': str(msg.id)}
        raise RuntimeError("Email service returned failure")
    except Exception as exc:
        msg.mark_failed(str(exc))
        logger.error("Email to %s failed: %s", email, exc)
        if msg.can_retry():
            raise self.retry(exc=exc)
        return {'status': 'failed', 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification(
    self,
    device_token: str,
    title: str,
    message: str,
    data: dict = None,
    message_id: str = None,
):
    """Send a push notification. Creates or updates a Message record."""
    from communications.models import Message
    from communications.push_notifications import push_service

    logger.info("Sending push to %s…", device_token[:20])

    if message_id:
        msg = Message.objects.get(id=message_id)
    else:
        msg = Message.objects.create(
            channel='PUSH',
            recipient_identifier=device_token,
            subject=title,
            body=message,
            status='QUEUED',
            metadata=data or {},
        )

    try:
        result = push_service.send_notification(
            device_token=device_token, title=title, message=message, data=data
        )
        if result['success']:
            msg.mark_sent(provider_id=result.get('message_id', ''))
            logger.info("Push sent (provider_id=%s)", result.get('message_id'))
            return {'status': 'success', 'message_id': str(msg.id)}
        raise RuntimeError(result.get('error', 'Push provider returned failure'))
    except Exception as exc:
        msg.mark_failed(str(exc))
        logger.error("Push notification failed: %s", exc)
        if msg.can_retry():
            raise self.retry(exc=exc)
        return {'status': 'failed', 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_message(
    self,
    channel: str,
    recipient: str,
    subject: str,
    body: str,
    priority: str = 'NORMAL',
    campaign_id: str = None,
):
    """
    Channel-agnostic message dispatcher.
    Creates a Message record then routes to the appropriate channel task.
    """
    from communications.models import Message

    logger.info("Dispatching %s message to %s", channel, recipient)

    msg = Message.objects.create(
        channel=channel,
        recipient_identifier=recipient,
        subject=subject,
        body=body,
        priority=priority,
        status='QUEUED',
        campaign_id=campaign_id,
    )

    try:
        if channel == 'SMS':
            return send_sms_notification.delay(recipient, subject, body, str(msg.id)).get()
        elif channel == 'EMAIL':
            return send_email_notification.delay(recipient, subject, body, message_id=str(msg.id)).get()
        elif channel == 'PUSH':
            return send_push_notification.delay(recipient, subject, body, message_id=str(msg.id)).get()
        elif channel == 'WHATSAPP':
            # WhatsApp shares the SMS path; swap provider in settings for production
            return send_sms_notification.delay(recipient, subject, body, str(msg.id)).get()
        else:
            msg.mark_failed(f'Unsupported channel: {channel}')
            return {'status': 'failed', 'error': f'Unsupported channel: {channel}'}
    except Exception as exc:
        msg.mark_failed(str(exc))
        logger.error("send_message failed for %s/%s: %s", channel, recipient, exc)
        raise self.retry(exc=exc)


# ── Bulk messaging ─────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_bulk_messages(self, data: dict):
    """
    Queue individual send tasks for every recipient in data['recipients'].
    Uses template rendering if template_id is provided.

    data keys: channel, recipients, subject, body, priority, template_id,
               context, campaign_id
    """
    from communications.models import Message, MessageTemplate

    channel = data['channel']
    recipients = data['recipients']
    subject = data.get('subject', '')
    body = data['body']
    priority = data.get('priority', 'NORMAL')
    campaign_id = data.get('campaign_id')

    # Optionally render a template
    if 'template_id' in data:
        try:
            template = MessageTemplate.objects.get(id=data['template_id'], is_deleted=False)
            rendered = template.render(data.get('context', {}))
            subject = rendered['subject'] or subject
            body = rendered['body'] or body
        except MessageTemplate.DoesNotExist:
            logger.error("Template %s not found for bulk send", data['template_id'])

    # Bulk-create message records first
    records = Message.objects.bulk_create([
        Message(
            channel=channel,
            recipient_identifier=r,
            subject=subject,
            body=body,
            priority=priority,
            status='QUEUED',
            campaign_id=campaign_id,
        )
        for r in recipients
    ])

    # Enqueue one delivery task per message
    for msg in records:
        send_message.delay(channel, msg.recipient_identifier, subject, body, priority, campaign_id)

    logger.info("Bulk: queued %d %s messages", len(records), channel)
    return {'status': 'success', 'messages_queued': len(records)}


# ── Broadcast processing ───────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_broadcast(self, broadcast_id: str):
    """
    Resolve recipients for a broadcast and enqueue per-channel messages.
    Marks broadcast SENDING → SENT (or FAILED on unrecoverable error).
    """
    from communications.models import Broadcast, Message
    from communications.geo_targeting import geo_targeting

    try:
        broadcast = Broadcast.objects.get(id=broadcast_id, is_deleted=False)
    except Broadcast.DoesNotExist:
        logger.error("Broadcast %s not found", broadcast_id)
        return {'status': 'error', 'message': 'Broadcast not found'}

    logger.info("Processing broadcast: %s", broadcast.title)

    broadcast.status = 'SENDING'
    broadcast.save(update_fields=['status', 'updated_at'])

    try:
        location_ids = list(
            broadcast.target_locations.values_list('id', flat=True)
        )
        recipients_data = geo_targeting.get_recipients_for_broadcast(
            target_locations=[str(lid) for lid in location_ids],
            target_criteria=broadcast.target_criteria,
        )

        broadcast.total_recipients = recipients_data['total']
        broadcast.save(update_fields=['total_recipients', 'updated_at'])

        messages_to_create = []
        channel_map = {
            'SMS': recipients_data['sms'],
            'EMAIL': recipients_data['email'],
            'PUSH': recipients_data['push'],
        }

        for channel in broadcast.channels:
            for recipient in channel_map.get(channel, []):
                messages_to_create.append(
                    Message(
                        campaign=broadcast.campaign,
                        channel=channel,
                        recipient_identifier=recipient,
                        subject=broadcast.title,
                        body=broadcast.message_content,
                        status='QUEUED',
                        priority='NORMAL',
                    )
                )

        with transaction.atomic():
            created = Message.objects.bulk_create(messages_to_create)
            broadcast.messages_sent = len(created)
            broadcast.status = 'SENT'
            broadcast.sent_at = timezone.now()
            broadcast.save(update_fields=['messages_sent', 'status', 'sent_at', 'updated_at'])

        # Enqueue delivery tasks
        for msg in created:
            send_message.delay(
                msg.channel,
                msg.recipient_identifier,
                msg.subject,
                msg.body,
                campaign_id=str(broadcast.campaign_id) if broadcast.campaign_id else None,
            )

        logger.info(
            "Broadcast '%s' sent: %d messages across %d channels",
            broadcast.title, len(created), len(broadcast.channels),
        )
        return {
            'status': 'success',
            'broadcast_id': str(broadcast.id),
            'messages_sent': len(created),
        }

    except Exception as exc:
        broadcast.status = 'FAILED'
        broadcast.error_log = str(exc)
        broadcast.save(update_fields=['status', 'error_log', 'updated_at'])
        logger.error("Broadcast %s failed: %s", broadcast_id, exc)
        raise self.retry(exc=exc)


# ── Scheduled / periodic tasks ─────────────────────────────────────────────────

@shared_task
def process_scheduled_messages():
    """
    Dispatch all PENDING messages whose scheduled_for has passed.
    Runs every minute via Celery Beat.
    """
    from communications.models import Message

    now = timezone.now()
    scheduled = Message.objects.filter(
        status='PENDING',
        scheduled_for__lte=now,
        is_deleted=False,
    ).select_related('campaign')

    count = scheduled.count()
    if not count:
        return {'status': 'completed', 'messages_processed': 0}

    ids = list(scheduled.values_list('id', flat=True))
    Message.objects.filter(id__in=ids).update(status='QUEUED', updated_at=now)

    for msg in scheduled:
        send_message.delay(
            msg.channel,
            msg.recipient_identifier,
            msg.subject,
            msg.body,
            msg.priority,
            str(msg.campaign_id) if msg.campaign_id else None,
        )

    logger.info("Scheduled messages dispatched: %d", count)
    return {'status': 'completed', 'messages_processed': count}


@shared_task
def update_message_delivery_status():
    """
    Poll SMS provider for delivery status on SENT messages.
    EMAIL/PUSH are assumed delivered after their respective grace periods.
    Runs every 5 minutes via Celery Beat.
    """
    from communications.models import Message
    from communications.sms_gateway import sms_gateway

    now = timezone.now()
    sent_messages = Message.objects.filter(
        status='SENT',
        is_deleted=False,
        sent_at__isnull=False,
    ).select_related('campaign')

    updated = 0
    for msg in sent_messages:
        seconds_since_sent = (now - msg.sent_at).total_seconds()
        try:
            if msg.channel == 'SMS' and msg.provider_message_id:
                if seconds_since_sent >= 60:
                    status_info = sms_gateway.get_delivery_status(msg.provider_message_id)
                    if status_info.get('status', '').lower() == 'delivered':
                        msg.mark_delivered(status_info.get('delivered_at'))
                        updated += 1

            elif msg.channel == 'EMAIL' and seconds_since_sent >= 300:
                msg.mark_delivered()
                updated += 1

            elif msg.channel == 'PUSH' and seconds_since_sent >= 60:
                msg.mark_delivered()
                updated += 1

        except Exception as exc:
            logger.error("Delivery status update failed for msg %s: %s", msg.id, exc)

    logger.info("Delivery status updated for %d messages", updated)
    return {'status': 'completed', 'messages_updated': updated}


@shared_task
def retry_failed_messages():
    """
    Re-enqueue FAILED messages that have not exceeded their retry limit.
    Runs every hour via Celery Beat.
    """
    from communications.models import Message

    failed = Message.objects.filter(status='FAILED', is_deleted=False)
    retried = 0

    for msg in failed:
        if msg.can_retry():
            msg.status = 'QUEUED'
            msg.retry_count += 1
            msg.save(update_fields=['status', 'retry_count', 'updated_at'])
            send_message.delay(
                msg.channel,
                msg.recipient_identifier,
                msg.subject,
                msg.body,
                msg.priority,
                str(msg.campaign_id) if msg.campaign_id else None,
            )
            retried += 1

    logger.info("Retried %d failed messages", retried)
    return {'status': 'completed', 'messages_retried': retried}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def publish_scheduled_social_post(self, post_id: str):
    """
    Publish a SocialMediaPost that has reached its scheduled_for time.
    Enqueued by SocialMediaService.schedule_post() with eta=scheduled_time.
    """
    from communications.models import SocialMediaPost
    from communications.social_media import social_media_service

    try:
        post = SocialMediaPost.objects.get(id=post_id, is_deleted=False)
    except SocialMediaPost.DoesNotExist:
        logger.error("SocialMediaPost %s not found", post_id)
        return {'status': 'error', 'message': 'Post not found'}

    logger.info("Publishing scheduled %s post %s", post.platform, post_id)

    try:
        result = social_media_service.post_to_platform(
            platform=post.platform,
            content=post.content,
            media_urls=post.media_urls,
            hashtags=post.hashtags,
        )
        if result['success']:
            post.mark_published(result['post_id'], result['post_url'])
            logger.info("Social post published: %s", result['post_url'])
            return {'status': 'success', 'post_url': result['post_url']}
        post.mark_failed(result.get('error', 'Unknown error'))
        raise RuntimeError(result.get('error', 'Provider returned failure'))
    except Exception as exc:
        post.mark_failed(str(exc))
        logger.error("Social post %s failed: %s", post_id, exc)
        raise self.retry(exc=exc)


@shared_task
def update_social_media_metrics():
    """
    Refresh engagement metrics for published posts from the last 7 days.
    Runs every 6 hours via Celery Beat.
    """
    from datetime import timedelta
    from communications.models import SocialMediaPost
    from communications.social_media import social_media_service

    cutoff = timezone.now() - timedelta(days=7)
    posts = SocialMediaPost.objects.filter(
        status='PUBLISHED',
        published_at__gte=cutoff,
        is_deleted=False,
    ).exclude(platform_post_id='')

    updated = 0
    for post in posts:
        try:
            metrics = social_media_service.update_post_metrics(post.platform_post_id, post.platform)
            if metrics:
                post.update_metrics(metrics)
                updated += 1
        except Exception as exc:
            logger.error("Metrics update failed for post %s: %s", post.id, exc)

    logger.info("Social media metrics updated for %d posts", updated)
    return {'status': 'completed', 'posts_updated': updated}


@shared_task
def cleanup_old_messages():
    """
    Soft-delete delivered/failed/bounced messages older than 90 days.
    Runs daily via Celery Beat.
    """
    from datetime import timedelta
    from communications.models import Message

    cutoff = timezone.now() - timedelta(days=90)
    count = Message.objects.filter(
        created_at__lt=cutoff,
        status__in=['DELIVERED', 'FAILED', 'BOUNCED'],
        is_deleted=False,
    ).update(is_deleted=True, updated_at=timezone.now())

    logger.info("Cleaned up %d old messages", count)
    return {'status': 'completed', 'messages_cleaned': count}