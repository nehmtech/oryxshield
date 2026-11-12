"""
Communications models for OryxShield.
Multi-channel messaging, campaigns, broadcasts, and public communications.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


class BaseModel(models.Model):
    """Abstract base model aligned with core app pattern."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class MessageTemplate(BaseModel):
    """
    Reusable message templates with variable substitution and
    multi-language support.
    """
    TEMPLATE_TYPES = [
        ('SMS', 'SMS Template'),
        ('EMAIL', 'Email Template'),
        ('PUSH', 'Push Notification'),
        ('ALERT', 'Alert Message'),
        ('REMINDER', 'Reminder'),
        ('CONFIRMATION', 'Confirmation'),
        ('BROADCAST', 'Broadcast'),
    ]

    LANGUAGES = [
        ('en',  'English'),
        ('af',  'Afrikaans'),
        ('ng',  'Oshiwambo'),
        ('naq', 'Damara/Nama'),
        ('hz',  'Herero'),
        ('kav', 'Kavango'),
    ]

    name = models.CharField(max_length=200, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    language = models.CharField(max_length=5, choices=LANGUAGES, default='en')
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    variables = models.JSONField(
        default=list,
        help_text="List of variable names used in template, e.g. ['name', 'location']"
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['template_type', 'language']),
            models.Index(fields=['is_active', 'template_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()}) [{self.language}]"

    def render(self, context: dict) -> dict:
        """Render template with context variables using {{variable}} syntax."""
        subject = self.subject
        body = self.body
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        return {'subject': subject, 'body': body}


class Campaign(BaseModel):
    """Communication campaigns for public health initiatives."""

    CAMPAIGN_TYPES = [
        ('AWARENESS', 'Public Awareness'),
        ('VACCINATION', 'Vaccination Drive'),
        ('TESTING', 'Testing Campaign'),
        ('PREVENTION', 'Prevention'),
        ('OUTBREAK', 'Outbreak Response'),
        ('EDUCATION', 'Health Education'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    campaign_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_campaigns',
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    key_messages = models.JSONField(default=list)
    channels = models.JSONField(default=list, help_text="List of channel codes to use")

    target_locations = models.ManyToManyField(
        'core.Location',
        blank=True,
        related_name='targeted_campaigns',
    )

    target_reach = models.PositiveIntegerField(default=0)
    actual_reach = models.PositiveIntegerField(default=0)

    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    spent = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['campaign_type', 'status']),
            models.Index(fields=['status', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_running(self) -> bool:
        """True when status is ACTIVE and within date range."""
        now = timezone.now()
        return self.status == 'ACTIVE' and self.start_date <= now <= self.end_date

    @property
    def reach_percentage(self) -> float:
        if not self.target_reach:
            return 0.0
        return round((self.actual_reach / self.target_reach) * 100, 2)


class Message(BaseModel):
    """Individual messages sent through various channels with full delivery tracking."""

    CHANNELS = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('PUSH', 'Push Notification'),
        ('WHATSAPP', 'WhatsApp'),
        ('VOICE', 'Voice Call'),
        ('SOCIAL', 'Social Media'),
        ('RADIO', 'Radio Broadcast'),
        ('TV', 'Television'),
        ('WEBSITE', 'Website/Portal'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('QUEUED', 'Queued'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read'),
        ('FAILED', 'Failed'),
        ('BOUNCED', 'Bounced'),
    ]

    PRIORITY_LEVELS = [
        ('URGENT', 'Urgent'),
        ('HIGH', 'High'),
        ('NORMAL', 'Normal'),
        ('LOW', 'Low'),
    ]

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='messages',
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='messages',
    )

    channel = models.CharField(max_length=20, choices=CHANNELS)
    recipient_identifier = models.CharField(
        max_length=255,
        help_text="Phone number, email address, device token, or user ID",
    )

    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')

    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)

    provider_message_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', 'status']),
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['recipient_identifier']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} → {self.recipient_identifier} [{self.status}]"

    def can_retry(self) -> bool:
        return self.status == 'FAILED' and self.retry_count < self.max_retries

    def mark_sent(self, provider_id: str = '') -> None:
        self.status = 'SENT'
        self.sent_at = timezone.now()
        if provider_id:
            self.provider_message_id = provider_id
        self.save(update_fields=['status', 'sent_at', 'provider_message_id', 'updated_at'])

    def mark_delivered(self, delivered_at=None) -> None:
        self.status = 'DELIVERED'
        self.delivered_at = delivered_at or timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'updated_at'])

    def mark_failed(self, error: str) -> None:
        self.status = 'FAILED'
        self.error_message = error
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])


class Broadcast(BaseModel):
    """Mass broadcast messages with full approval workflow."""

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='broadcasts',
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='broadcasts',
    )

    title = models.CharField(max_length=200)
    message_content = models.TextField()

    channels = models.JSONField(default=list)

    target_locations = models.ManyToManyField(
        'core.Location',
        blank=True,
        related_name='broadcasts',
    )
    target_criteria = models.JSONField(
        default=dict,
        help_text="Audience criteria: {age_min, age_max, gender, risk_level, ...}",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='broadcasts_created',
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='broadcasts_approved',
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    total_recipients = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    messages_delivered = models.PositiveIntegerField(default=0)
    messages_failed = models.PositiveIntegerField(default=0)

    error_log = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['created_by', 'status']),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"

    @property
    def delivery_rate(self) -> float:
        if not self.messages_sent:
            return 0.0
        return round((self.messages_delivered / self.messages_sent) * 100, 2)

    def approve(self, approver) -> None:
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.status = 'APPROVED'
        self.save(update_fields=['approved_by', 'approved_at', 'status', 'updated_at'])

    def cancel(self) -> None:
        self.status = 'CANCELLED'
        self.save(update_fields=['status', 'updated_at'])


class ContactList(BaseModel):
    """Managed contact lists for targeted messaging."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contact_lists',
    )
    location = models.ForeignKey(
        'core.Location',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contact_lists',
    )

    contacts = models.JSONField(
        default=list,
        help_text="List of {name, email, phone, metadata} dicts",
    )
    tags = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.contact_count} contacts)"

    @property
    def contact_count(self) -> int:
        return len(self.contacts)

    def add_contacts(self, new_contacts: list) -> int:
        """Append contacts and return new total count."""
        self.contacts.extend(new_contacts)
        self.save(update_fields=['contacts', 'updated_at'])
        return self.contact_count

    def remove_contacts(self, identifiers: list) -> int:
        """Remove contacts by email or phone. Returns remaining count."""
        id_set = set(identifiers)
        self.contacts = [
            c for c in self.contacts
            if c.get('email') not in id_set and c.get('phone') not in id_set
        ]
        self.save(update_fields=['contacts', 'updated_at'])
        return self.contact_count


class PublicAnnouncement(BaseModel):
    """
    Public announcements, press releases, and health advisories
    with SEO support and publish/expiry lifecycle.
    """
    ANNOUNCEMENT_TYPES = [
        ('PRESS_RELEASE', 'Press Release'),
        ('PUBLIC_NOTICE', 'Public Notice'),
        ('ADVISORY', 'Health Advisory'),
        ('GUIDELINE', 'Guideline'),
        ('FAQ', 'FAQ'),
        ('UPDATE', 'Status Update'),
        ('EMERGENCY', 'Emergency Notice'),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True, blank=True)

    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES)
    content = models.TextField()
    summary = models.TextField(help_text="Brief summary displayed in listing views")

    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements',
    )

    is_published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    is_featured = models.BooleanField(default=False)
    display_priority = models.PositiveSmallIntegerField(
        default=0,
        help_text="Higher number = shown first",
    )

    target_locations = models.ManyToManyField(
        'core.Location',
        blank=True,
        related_name='announcements',
    )

    attachments = models.JSONField(default=list)
    tags = models.JSONField(default=list)
    view_count = models.PositiveIntegerField(default=0)

    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    seo_keywords = models.JSONField(default=list)

    class Meta:
        ordering = ['-display_priority', '-publish_date']
        indexes = [
            models.Index(fields=['announcement_type', 'is_published']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', 'is_featured']),
            models.Index(fields=['-display_priority', '-publish_date']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while PublicAnnouncement.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_live(self) -> bool:
        """True if published and within publish/expiry window."""
        if not self.is_published:
            return False
        now = timezone.now()
        if self.publish_date and self.publish_date > now:
            return False
        if self.expiry_date and self.expiry_date < now:
            return False
        return True

    def publish(self, publish_now: bool = True) -> None:
        self.is_published = True
        if publish_now and not self.publish_date:
            self.publish_date = timezone.now()
        self.save(update_fields=['is_published', 'publish_date', 'updated_at'])

    def unpublish(self) -> None:
        self.is_published = False
        self.save(update_fields=['is_published', 'updated_at'])

    def increment_view(self) -> int:
        PublicAnnouncement.objects.filter(pk=self.pk).update(
            view_count=models.F('view_count') + 1
        )
        self.refresh_from_db(fields=['view_count'])
        return self.view_count


class SocialMediaPost(BaseModel):
    """Social media posts across multiple platforms with engagement tracking."""

    PLATFORMS = [
        ('TWITTER', 'Twitter/X'),
        ('FACEBOOK', 'Facebook'),
        ('INSTAGRAM', 'Instagram'),
        ('LINKEDIN', 'LinkedIn'),
        ('YOUTUBE', 'YouTube'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('PUBLISHED', 'Published'),
        ('FAILED', 'Failed'),
    ]

    platform = models.CharField(max_length=20, choices=PLATFORMS)
    content = models.TextField()

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='social_posts',
    )

    media_urls = models.JSONField(default=list)
    hashtags = models.JSONField(default=list)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    platform_post_id = models.CharField(max_length=255, blank=True)
    post_url = models.URLField(blank=True)
    error_message = models.TextField(blank=True)

    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='social_posts',
    )

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['platform', 'status']),
            models.Index(fields=['status', 'scheduled_for']),
        ]

    def __str__(self):
        return f"{self.get_platform_display()} — {self.content[:60]}"

    @property
    def engagement_rate(self) -> float:
        if not self.reach:
            return 0.0
        return round(((self.likes + self.shares + self.comments) / self.reach) * 100, 4)

    def mark_published(self, post_id: str, post_url: str) -> None:
        self.status = 'PUBLISHED'
        self.published_at = timezone.now()
        self.platform_post_id = post_id
        self.post_url = post_url
        self.save(update_fields=[
            'status', 'published_at', 'platform_post_id', 'post_url', 'updated_at'
        ])

    def mark_failed(self, error: str) -> None:
        self.status = 'FAILED'
        self.error_message = error
        self.save(update_fields=['status', 'error_message', 'updated_at'])

    def update_metrics(self, metrics: dict) -> None:
        self.likes = metrics.get('likes', self.likes)
        self.shares = metrics.get('shares', self.shares)
        self.comments = metrics.get('comments', self.comments)
        self.reach = metrics.get('reach', self.reach)
        self.impressions = metrics.get('impressions', self.impressions)
        self.save(update_fields=[
            'likes', 'shares', 'comments', 'reach', 'impressions', 'updated_at'
        ])


class FeedbackResponse(BaseModel):
    """Public feedback and complaint management with full assignment workflow."""

    FEEDBACK_TYPES = [
        ('INQUIRY', 'General Inquiry'),
        ('COMPLAINT', 'Complaint'),
        ('SUGGESTION', 'Suggestion'),
        ('REPORT', 'Incident Report'),
        ('REQUEST', 'Information Request'),
        ('APPRECIATION', 'Appreciation'),
    ]

    STATUS_CHOICES = [
        ('RECEIVED', 'Received'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RESPONDED', 'Responded'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('ESCALATED', 'Escalated'),
    ]

    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)

    sender_name = models.CharField(max_length=200)
    sender_email = models.EmailField(blank=True)
    sender_phone = models.CharField(max_length=30, blank=True)

    subject = models.CharField(max_length=300)
    message = models.TextField()

    location = models.ForeignKey(
        'core.Location',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='feedback',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RECEIVED')
    is_urgent = models.BooleanField(default=False)

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_feedback',
    )

    response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    attachments = models.JSONField(default=list)
    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-is_urgent', '-created_at']
        indexes = [
            models.Index(fields=['feedback_type', 'status']),
            models.Index(fields=['is_urgent', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.get_feedback_type_display()} — {self.subject}"

    @property
    def response_time_hours(self) -> float | None:
        if not self.responded_at:
            return None
        delta = self.responded_at - self.created_at
        return round(delta.total_seconds() / 3600, 2)

    def assign(self, user) -> None:
        self.assigned_to = user
        self.status = 'UNDER_REVIEW'
        self.save(update_fields=['assigned_to', 'status', 'updated_at'])

    def respond(self, response_text: str) -> None:
        self.response = response_text
        self.responded_at = timezone.now()
        self.status = 'RESPONDED'
        self.save(update_fields=['response', 'responded_at', 'status', 'updated_at'])

    def resolve(self) -> None:
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at', 'updated_at'])

    def escalate(self, notes: str = '') -> None:
        self.status = 'ESCALATED'
        if notes:
            self.internal_notes = f"{self.internal_notes}\n[ESCALATED] {notes}".strip()
        self.save(update_fields=['status', 'internal_notes', 'updated_at'])