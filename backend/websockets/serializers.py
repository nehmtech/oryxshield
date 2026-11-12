"""
REST serializers for the websockets app.
"""
from rest_framework import serializers
from .models import ChannelGroup, WebSocketConnection, BroadcastMessage, RoomPresence


class ChannelGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model  = ChannelGroup
        fields = [
            'id', 'name', 'display_name', 'description',
            'access_policy', 'allowed_roles', 'is_persistent',
            'member_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'member_count']

    def get_member_count(self, obj) -> int:
        return obj.members.count()


class WebSocketConnectionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = WebSocketConnection
        fields = [
            'id', 'username', 'channel_name', 'group',
            'event_type', 'timestamp', 'ip_address', 'close_code',
        ]
        read_only_fields = fields


class BroadcastMessageSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model  = BroadcastMessage
        fields = [
            'id', 'group_name', 'target_user', 'message_type',
            'payload', 'delivery_status', 'sent_at', 'source',
            'recipient_count', 'created_at',
        ]
        read_only_fields = fields


class RoomPresenceSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model  = RoomPresence
        fields = [
            'id', 'group_name', 'username', 'channel_name',
            'connected_at', 'last_seen',
        ]
        read_only_fields = fields