"""
Serializers for communications app.
"""
import re
from rest_framework import serializers
from .models import (
    MessageTemplate, Campaign, Message, Broadcast, ContactList,
    PublicAnnouncement, SocialMediaPost, FeedbackResponse,
)

_PHONE_RE = re.compile(r'^\+?[\d\s\-()]{7,20}$')


# ── MessageTemplate ────────────────────────────────────────────────────────────

class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class MessageTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ['id', 'name', 'template_type', 'language', 'is_active', 'version']


# ── Campaign ───────────────────────────────────────────────────────────────────

class CampaignSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(
        source='campaign_manager.get_full_name', read_only=True
    )
    is_running = serializers.BooleanField(read_only=True)
    reach_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Campaign
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'actual_reach']


class CampaignListSerializer(serializers.ModelSerializer):
    is_running = serializers.BooleanField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'campaign_type', 'status',
            'start_date', 'end_date', 'actual_reach', 'target_reach',
            'is_running',
        ]


# ── Message ────────────────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'sent_at', 'delivered_at', 'read_at',
            'provider_message_id',
        ]

    def validate_body(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Message body cannot be empty.")
        return value

    def validate_recipient_identifier(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Recipient identifier is required.")
        return value


class MessageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            'id', 'channel', 'status', 'priority',
            'recipient_identifier', 'subject',
            'sent_at', 'delivered_at',
        ]


# ── Broadcast ──────────────────────────────────────────────────────────────────

class BroadcastSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name', read_only=True
    )
    delivery_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = Broadcast
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'approved_by', 'approved_at', 'sent_at',
            'total_recipients', 'messages_sent',
            'messages_delivered', 'messages_failed',
        ]


class BroadcastListSerializer(serializers.ModelSerializer):
    delivery_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = Broadcast
        fields = [
            'id', 'title', 'status', 'channels',
            'total_recipients', 'messages_sent',
            'messages_delivered', 'delivery_rate',
            'scheduled_for', 'created_at',
        ]


# ── ContactList ────────────────────────────────────────────────────────────────

class ContactListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    contact_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ContactList
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── PublicAnnouncement ─────────────────────────────────────────────────────────

class PublicAnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = PublicAnnouncement
        fields = '__all__'
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at', 'view_count']

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Announcement title cannot be empty.")
        return value

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Announcement content cannot be empty.")
        return value


class PublicAnnouncementListSerializer(serializers.ModelSerializer):
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = PublicAnnouncement
        fields = [
            'id', 'title', 'slug', 'announcement_type',
            'summary', 'publish_date', 'is_published',
            'is_featured', 'is_live', 'view_count',
        ]


# ── SocialMediaPost ────────────────────────────────────────────────────────────

class SocialMediaPostSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    engagement_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = SocialMediaPost
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'published_at', 'platform_post_id', 'post_url',
            'likes', 'shares', 'comments', 'reach', 'impressions',
        ]


# ── FeedbackResponse ───────────────────────────────────────────────────────────

class FeedbackResponseSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name', read_only=True
    )
    response_time_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = FeedbackResponse
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'responded_at', 'resolved_at']


class FeedbackResponseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackResponse
        fields = [
            'id', 'feedback_type', 'subject',
            'sender_name', 'status', 'is_urgent',
            'assigned_to', 'created_at',
        ]


# ── Action serializers ─────────────────────────────────────────────────────────

class SendMessageSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=Message.CHANNELS)
    recipient = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=500, required=False, allow_blank=True)
    body = serializers.CharField()
    priority = serializers.ChoiceField(choices=Message.PRIORITY_LEVELS, default='NORMAL')
    campaign_id = serializers.UUIDField(required=False)
    scheduled_for = serializers.DateTimeField(required=False)

    def validate_body(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Message body cannot be empty.")
        return value

    def validate(self, attrs):
        channel = attrs.get('channel', '')
        recipient = attrs.get('recipient', '')
        if channel == 'SMS' and not _PHONE_RE.match(recipient):
            raise serializers.ValidationError(
                {'recipient': 'Invalid phone number format for SMS channel.'}
            )
        if channel == 'EMAIL' and '@' not in recipient:
            raise serializers.ValidationError(
                {'recipient': 'Invalid email address for EMAIL channel.'}
            )
        return attrs


class SendBulkMessageSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=Message.CHANNELS)
    recipients = serializers.ListField(child=serializers.CharField(), min_length=1)
    subject = serializers.CharField(max_length=500, required=False, allow_blank=True)
    body = serializers.CharField()
    priority = serializers.ChoiceField(choices=Message.PRIORITY_LEVELS, default='NORMAL')
    template_id = serializers.UUIDField(required=False)
    context = serializers.DictField(required=False, default=dict)
    campaign_id = serializers.UUIDField(required=False)


class FeedbackRespondSerializer(serializers.Serializer):
    response = serializers.CharField(min_length=5)


class FeedbackAssignSerializer(serializers.Serializer):
    assigned_to = serializers.UUIDField()


class BroadcastEstimateSerializer(serializers.Serializer):
    location_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    criteria = serializers.DictField(required=False, default=dict)
    include_sublocations = serializers.BooleanField(default=True)


# ── Dashboard ──────────────────────────────────────────────────────────────────

class CommunicationDashboardSerializer(serializers.Serializer):
    active_campaigns = serializers.IntegerField()
    messages_sent_today = serializers.IntegerField()
    messages_pending = serializers.IntegerField()
    delivery_rate_7d = serializers.FloatField()
    recent_broadcasts = serializers.ListField()
    channel_usage = serializers.DictField()
    feedback_pending = serializers.IntegerField()
    announcements_live = serializers.IntegerField()