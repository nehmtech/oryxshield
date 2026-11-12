"""
OryxShield — Core Serializers
========================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Serializers
-----------
UserSerializer           — read-only user summary
UserDetailSerializer     — full user with profile
UserCreateSerializer     — registration
ChangePasswordSerializer — password change
UserProfileSerializer    — profile read
UserProfileUpdateSerializer — profile write
LocationSerializer       — tree-safe location
LocationDetailSerializer — with coordinates and full_path
AuditLogSerializer       — read-only log
SystemConfigurationSerializer — CRUD with sensitive-masking
NotificationSerializer   — read
NotificationCreateSerializer — write
APIKeySerializer         — read with masked key
APIKeyCreateSerializer   — write / returns full key once
"""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import (
    APIKey,
    AuditLog,
    Location,
    Notification,
    SystemConfiguration,
    UserProfile,
)
from .validators import validate_password_strength, validate_phone_number


# ---------------------------------------------------------------------------
# User serializers
# ---------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "is_active", "is_staff", "is_superuser", "date_joined", "groups"]
        read_only_fields = fields

    def get_groups(self, obj: User) -> list:
        return list(obj.groups.values_list("name", flat=True))


class UserDetailSerializer(serializers.ModelSerializer):
    """Full user record with nested profile (read)."""

    profile = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "full_name", "is_active", "is_staff", "is_superuser",
            "date_joined", "last_login", "groups", "profile",
        ]
        read_only_fields = fields

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.username

    def get_groups(self, obj: User) -> list:
        return list(obj.groups.values_list("name", flat=True))

    def get_profile(self, obj: User) -> dict | None:
        if hasattr(obj, "profile"):
            return UserProfileSerializer(obj.profile, context=self.context).data
        return None


class UserCreateSerializer(serializers.ModelSerializer):
    """User registration — returns basic user info (no password in response)."""

    password = serializers.CharField(write_only=True, min_length=10)
    password_confirm = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            "username", "email", "password", "password_confirm",
            "first_name", "last_name",
        ]

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password_strength(attrs["password"])
        try:
            validate_password(attrs["password"])
        except Exception as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=10)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        validate_password_strength(attrs["new_password"])
        return attrs

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


# ---------------------------------------------------------------------------
# UserProfile serializers
# ---------------------------------------------------------------------------

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    location_display = serializers.CharField(source="location.full_path", read_only=True)
    is_locked = serializers.SerializerMethodField()
    last_login_ip = serializers.CharField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = UserProfile
        exclude = ["metadata", "notification_preferences"]
        read_only_fields = [
            "user", "failed_login_attempts", "account_locked_until",
            "last_login_ip", "last_login_location", "social_providers",
            "has_social_auth", "email_verified", "phone_verified",
            "created_at", "updated_at",
        ]

    def get_is_locked(self, obj: UserProfile) -> bool:
        return obj.is_account_locked()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=False, validators=[validate_phone_number])

    class Meta:
        model = UserProfile
        fields = [
            "phone_number", "bio", "date_of_birth",
            "organization", "department", "job_title", "employee_id",
            "language", "timezone", "location",
        ]


# ---------------------------------------------------------------------------
# Location serializers
# ---------------------------------------------------------------------------

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "id", "name", "code", "location_type", "parent",
            "latitude", "longitude", "population", "area_sq_km",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LocationDetailSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)
    coordinates = serializers.SerializerMethodField()
    population_density = serializers.SerializerMethodField()
    depth = serializers.IntegerField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Location
        exclude = ["is_deleted", "deleted_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_coordinates(self, obj: Location) -> dict | None:
        return obj.coordinates

    def get_population_density(self, obj: Location) -> float | None:
        d = obj.population_density
        return float(d) if d is not None else None

    def get_children_count(self, obj: Location) -> int:
        return obj.children.filter(is_deleted=False).count()


class LocationTreeSerializer(LocationSerializer):
    """Recursive serializer for hierarchical tree output."""
    children = serializers.SerializerMethodField()

    class Meta(LocationSerializer.Meta):
        fields = LocationSerializer.Meta.fields + ["children"]  # type: ignore[operator]

    def get_children(self, obj: Location) -> list:
        children = obj.children.filter(is_deleted=False)
        return LocationTreeSerializer(children, many=True, context=self.context).data


# ---------------------------------------------------------------------------
# AuditLog serializers
# ---------------------------------------------------------------------------

class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, default="Anonymous")
    ip_address = serializers.CharField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = [f.name for f in AuditLog._meta.fields]


# ---------------------------------------------------------------------------
# SystemConfiguration serializers
# ---------------------------------------------------------------------------

class SystemConfigurationSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = SystemConfiguration
        fields = [
            "id", "key", "value", "description", "category",
            "is_active", "is_sensitive", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_value(self, obj: SystemConfiguration):
        if obj.is_sensitive:
            return "***SENSITIVE***"
        return obj.value


class SystemConfigurationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfiguration
        fields = ["key", "value", "description", "category", "is_active", "is_sensitive", "default_value"]

    def validate_key(self, value: str) -> str:
        if not value.isupper():
            raise serializers.ValidationError("Key must be UPPER_CASE.")
        return value


# ---------------------------------------------------------------------------
# Notification serializers
# ---------------------------------------------------------------------------

class NotificationSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "is_expired"]


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "user", "title", "message", "notification_type", "priority",
            "action_url", "action_text", "expires_at",
            "related_model", "related_object_id",
        ]

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry must be in the future.")
        return value


# ---------------------------------------------------------------------------
# APIKey serializers
# ---------------------------------------------------------------------------

class APIKeySerializer(serializers.ModelSerializer):
    key = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    owner = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id", "name", "key", "owner", "is_active", "expires_at",
            "allowed_ips", "rate_limit", "permissions",
            "last_used_at", "usage_count", "is_valid",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "key", "usage_count", "last_used_at", "created_at", "updated_at"]

    def get_key(self, obj: APIKey) -> str:
        return f"{obj.key[:8]}{'*' * 20}"

    def get_is_valid(self, obj: APIKey) -> bool:
        return obj.is_valid()


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Returns the full key once on creation — clients must store it securely."""

    class Meta:
        model = APIKey
        fields = [
            "name", "expires_at", "allowed_ips",
            "rate_limit", "rate_limit_window", "permissions",
        ]

    def create(self, validated_data: dict) -> APIKey:
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def to_representation(self, instance: APIKey) -> dict:
        data = super().to_representation(instance)
        data["id"] = str(instance.pk)
        data["key"] = instance.key  # full key — returned once only
        data["warning"] = "Store this key securely. It will not be shown again."
        return data


# ---------------------------------------------------------------------------
# Auth response serializers
# ---------------------------------------------------------------------------

class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserDetailSerializer()


class MessageSerializer(serializers.Serializer):
    """Generic success message response."""
    message = serializers.CharField()
    status = serializers.CharField(default="success")