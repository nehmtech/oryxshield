"""
Django admin for the websockets app.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import BroadcastMessage, ChannelGroup, RoomPresence, WebSocketConnection


@admin.register(ChannelGroup)
class ChannelGroupAdmin(admin.ModelAdmin):
    list_display  = ('name', 'display_name', 'access_policy', 'is_persistent', 'member_count', 'is_deleted')
    list_filter   = ('access_policy', 'is_persistent', 'is_deleted')
    search_fields = ('name', 'display_name', 'description')
    filter_horizontal = ('members',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_deleted=False)

    actions = ['soft_delete_selected']

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, f'{queryset.count()} group(s) soft-deleted.')
    soft_delete_selected.short_description = 'Soft-delete selected groups'


@admin.register(WebSocketConnection)
class WebSocketConnectionAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'event_type', 'user', 'group', 'ip_address', 'close_code')
    list_filter   = ('event_type',)
    search_fields = ('user__username', 'channel_name', 'ip_address')
    readonly_fields = [f.name for f in WebSocketConnection._meta.get_fields()]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display   = ('created_at', 'message_type', 'group', 'target_user', 'delivery_status', 'recipient_count')
    list_filter    = ('delivery_status', 'message_type')
    search_fields  = ('group__name', 'target_user__username', 'source')
    readonly_fields = ('id', 'created_at', 'updated_at', 'sent_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RoomPresence)
class RoomPresenceAdmin(admin.ModelAdmin):
    list_display  = ('group', 'user', 'connected_at', 'last_seen', 'channel_name')
    list_filter   = ('group',)
    search_fields = ('user__username', 'group__name', 'channel_name')
    readonly_fields = ('id', 'connected_at', 'last_seen')

    def has_add_permission(self, request):
        return False