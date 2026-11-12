"""
Admin configuration for communications app.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Broadcast, Campaign, ContactList, FeedbackResponse,
    Message, MessageTemplate, PublicAnnouncement,
    SocialMediaPost,
)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'language', 'version', 'is_active']
    list_filter = ['template_type', 'language', 'is_active']
    search_fields = ['name', 'subject', 'body']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'status', 'start_date', 'end_date', 'actual_reach', 'target_reach']
    list_filter = ['campaign_type', 'status']
    search_fields = ['name', 'description']
    filter_horizontal = ['target_locations']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['recipient_identifier', 'channel', 'status', 'priority', 'sent_at', 'delivered_at']
    list_filter = ['channel', 'status', 'priority']
    search_fields = ['recipient_identifier', 'subject']
    readonly_fields = ['id', 'sent_at', 'delivered_at', 'read_at', 'provider_message_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'total_recipients', 'messages_sent', 'delivery_rate', 'created_at']
    list_filter = ['status']
    filter_horizontal = ['target_locations']
    readonly_fields = [
        'id', 'approved_by', 'approved_at', 'sent_at',
        'total_recipients', 'messages_sent', 'messages_delivered', 'messages_failed',
        'created_at', 'updated_at',
    ]

    @admin.display(description='Delivery %')
    def delivery_rate(self, obj):
        return f"{obj.delivery_rate:.1f}%"


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'location', 'contact_count', 'is_active']
    list_filter = ['is_active', 'location']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']

    @admin.display(description='Contacts')
    def contact_count(self, obj):
        return obj.contact_count


@admin.register(PublicAnnouncement)
class PublicAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'announcement_type', 'is_published', 'is_featured', 'publish_date', 'view_count']
    list_filter = ['announcement_type', 'is_published', 'is_featured']
    search_fields = ['title', 'content', 'summary']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['target_locations']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at']
    date_hierarchy = 'publish_date'
    actions = ['publish_selected', 'unpublish_selected']

    @admin.action(description='Publish selected announcements')
    def publish_selected(self, request, queryset):
        for ann in queryset:
            ann.publish()

    @admin.action(description='Unpublish selected announcements')
    def unpublish_selected(self, request, queryset):
        for ann in queryset:
            ann.unpublish()


@admin.register(SocialMediaPost)
class SocialMediaPostAdmin(admin.ModelAdmin):
    list_display = ['platform', 'status', 'published_at', 'reach', 'engagement_rate_display']
    list_filter = ['platform', 'status']
    readonly_fields = ['id', 'published_at', 'platform_post_id', 'post_url', 'created_at', 'updated_at']

    @admin.display(description='Engagement %')
    def engagement_rate_display(self, obj):
        return f"{obj.engagement_rate:.2f}%"


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(admin.ModelAdmin):
    list_display = ['feedback_type', 'sender_name', 'subject', 'status', 'is_urgent', 'assigned_to', 'created_at']
    list_filter = ['feedback_type', 'status', 'is_urgent']
    search_fields = ['sender_name', 'subject', 'message']
    readonly_fields = ['id', 'responded_at', 'resolved_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['mark_urgent', 'mark_resolved']

    @admin.action(description='Mark selected as urgent')
    def mark_urgent(self, request, queryset):
        queryset.update(is_urgent=True)

    @admin.action(description='Mark selected as resolved')
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='RESOLVED', resolved_at=timezone.now())