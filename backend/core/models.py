"""
OryxShield — Core Models
=================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah
Version : 1.0.0

Models
------
TimeStampedModel    — Abstract UUID + soft-delete base
Location            — Hierarchical geographic locations (Google Maps API coords)
UserProfile         — Extended profile: org, 2FA, security, social auth
AuditLog            — Immutable comprehensive audit trail
SystemConfiguration — Key-value config store with category grouping
Notification        — In-app notification system with priority & expiry
APIKey              — Scoped API keys with rate limits and IP restrictions
"""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class TimeStampedModel(models.Model):
    """
    Abstract base providing UUID PK, created/updated timestamps, and soft delete.
    All application models inherit from this.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
        help_text=_("Unique identifier (UUID)"),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
        get_latest_by = "created_at"

    def soft_delete(self, *, commit: bool = True) -> "TimeStampedModel":
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if commit:
            self.save(update_fields=["is_deleted", "deleted_at"])
        return self

    def restore(self, *, commit: bool = True) -> "TimeStampedModel":
        self.is_deleted = False
        self.deleted_at = None
        if commit:
            self.save(update_fields=["is_deleted", "deleted_at"])
        return self


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class Location(TimeStampedModel):
    """
    Hierarchical geographic location — Country > Region > Constituency > Ward > Village.
    Geospatial data uses lat/lng decimals (Google Maps API compatible).
    Boundary polygons are stored as GeoJSON in a JSONField (no PostGIS required).
    """

    class LocationType(models.TextChoices):
        COUNTRY = "COUNTRY", _("Country")
        REGION = "REGION", _("Region")
        CONSTITUENCY = "CONSTITUENCY", _("Constituency")
        WARD = "WARD", _("Ward")
        VILLAGE = "VILLAGE", _("Village")
        HEALTH_FACILITY = "HEALTH_FACILITY", _("Health Facility")
        CHECKPOINT = "CHECKPOINT", _("Checkpoint")
        OTHER = "OTHER", _("Other")

    name = models.CharField(max_length=200, db_index=True)
    code = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text=_("Unique location code (ISO or administrative)"),
    )
    location_type = models.CharField(
        max_length=20, choices=LocationType.choices, db_index=True,
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE,
        null=True, blank=True, related_name="children",
    )

    # Geospatial — Google Maps API compatible
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    boundary = models.JSONField(
        null=True, blank=True,
        help_text=_("GeoJSON polygon boundary (Google Maps compatible)"),
    )

    # Demographics
    population = models.PositiveIntegerField(null=True, blank=True)
    area_sq_km = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    elevation_meters = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        ordering = ["location_type", "name"]
        indexes = [
            models.Index(fields=["location_type", "name"]),
            models.Index(fields=["parent", "is_deleted"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_deleted=False),
                name="unique_active_location_code",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_location_type_display()})"

    def clean(self) -> None:
        super().clean()
        if self.parent_id:
            visited: set = set()
            current = self.parent
            while current:
                if current.pk == self.pk or current.pk in visited:
                    raise ValidationError(_("Circular parent reference detected."))
                visited.add(current.pk)
                current = current.parent

    @property
    def full_path(self) -> str:
        parts = [self.name]
        node = self.parent
        while node and not node.is_deleted:
            parts.insert(0, node.name)
            node = node.parent
        return " > ".join(parts)

    @property
    def coordinates(self) -> dict | None:
        if self.latitude is not None and self.longitude is not None:
            return {"lat": float(self.latitude), "lng": float(self.longitude)}
        return None

    @property
    def depth(self) -> int:
        level, node = 0, self.parent
        while node:
            level += 1
            node = node.parent
        return level

    @property
    def population_density(self) -> Decimal | None:
        if self.population and self.area_sq_km and self.area_sq_km > 0:
            return Decimal(self.population) / self.area_sq_km
        return None

    def get_ancestors(self, *, include_self: bool = False) -> list:
        ancestors: list = [self] if include_self else []
        node = self.parent
        while node:
            ancestors.append(node)
            node = node.parent
        return ancestors

    def get_descendants(self, *, include_self: bool = False) -> models.QuerySet:
        ids: list = [self.pk] if include_self else []

        def _collect(loc: Location) -> None:
            for child in loc.children.filter(is_deleted=False).iterator():
                ids.append(child.pk)
                _collect(child)

        _collect(self)
        return Location.objects.filter(pk__in=ids)


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------


class UserProfile(TimeStampedModel):
    """
    Extended user profile for OryxShield surveillance system.
    Covers organisation context, 2FA, account lockout, social-auth tracking,
    notification preferences, and language/timezone.
    """

    class TwoFactorMethod(models.TextChoices):
        TOTP = "TOTP", _("Authenticator App (TOTP)")
        SMS = "SMS", _("SMS Code")
        EMAIL = "EMAIL", _("Email Code")

    class Language(models.TextChoices):
        EN  = "en",  _("English")
        AF  = "af",  _("Afrikaans")
        NG  = "ng",  _("Oshiwambo")
        NAQ = "naq", _("Damara/Nama")
        HZ  = "hz",  _("Herero")
        KAV = "kav", _("Kavango")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Personal
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    date_of_birth = models.DateField(null=True, blank=True)

    # Organisation
    organization = models.CharField(max_length=200, blank=True, db_index=True)
    department = models.CharField(max_length=100, blank=True, db_index=True)
    job_title = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=50, blank=True)

    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_users",
    )

    # 2FA
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_method = models.CharField(
        max_length=20, choices=TwoFactorMethod.choices, default=TwoFactorMethod.TOTP,
    )

    # Login/security tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_location = models.CharField(max_length=200, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)

    # Preferences
    notification_preferences = models.JSONField(default=dict, blank=True)
    language = models.CharField(
        max_length=10, choices=Language.choices, default=Language.EN,
    )
    timezone = models.CharField(max_length=50, default="Africa/Windhoek")

    # Social auth
    has_social_auth = models.BooleanField(default=False)
    social_providers = models.JSONField(default=list, blank=True)

    # Verification & consent
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")
        indexes = [
            models.Index(fields=["organization", "department"]),
            models.Index(fields=["location"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self) -> str:
        return f"Profile: {self.user.username}"

    # Account lockout helpers

    def is_account_locked(self) -> bool:
        if self.account_locked_until:
            if timezone.now() < self.account_locked_until:
                return True
            self.account_locked_until = None
            self.failed_login_attempts = 0
            self.save(update_fields=["account_locked_until", "failed_login_attempts"])
        return False

    def lock_account(self, duration_minutes: int = 60) -> None:
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)
        self.save(update_fields=["account_locked_until"])

    def unlock_account(self) -> None:
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=["account_locked_until", "failed_login_attempts"])

    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 60) -> bool:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.lock_account(duration_minutes=lockout_minutes)
            self.save(update_fields=["failed_login_attempts", "account_locked_until"])
            return True
        self.save(update_fields=["failed_login_attempts"])
        return False

    def record_successful_login(self, ip_address: str | None = None, location: str | None = None) -> None:
        fields = ["failed_login_attempts", "account_locked_until"]
        self.failed_login_attempts = 0
        self.account_locked_until = None
        if ip_address:
            self.last_login_ip = ip_address
            fields.append("last_login_ip")
        if location:
            self.last_login_location = location
            fields.append("last_login_location")
        self.save(update_fields=fields)

    # Permission helpers

    def get_permissions(self) -> list:
        return self.notification_preferences.get("permissions", [])

    def has_permission(self, permission: str) -> bool:
        return permission in self.get_permissions() or self.user.is_staff


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(TimeStampedModel):
    """
    Immutable audit trail. Records are write-once; updates and deletes raise ValidationError.
    """

    class ActionType(models.TextChoices):
        CREATE = "CREATE", _("Create")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")
        VIEW = "VIEW", _("View")
        EXPORT = "EXPORT", _("Export")
        IMPORT = "IMPORT", _("Import")
        LOGIN = "LOGIN", _("Login")
        LOGOUT = "LOGOUT", _("Logout")
        LOGIN_FAILED = "LOGIN_FAILED", _("Login Failed")
        PASSWORD_CHANGE = "PASSWORD_CHANGE", _("Password Change")
        PASSWORD_RESET = "PASSWORD_RESET", _("Password Reset")
        ESCALATE = "ESCALATE", _("Escalate")
        ALERT = "ALERT", _("Alert")
        APPROVE = "APPROVE", _("Approve")
        REJECT = "REJECT", _("Reject")
        ACTIVATE = "ACTIVATE", _("Activate")
        DEACTIVATE = "DEACTIVATE", _("Deactivate")
        DOWNLOAD = "DOWNLOAD", _("Download")
        UPLOAD = "UPLOAD", _("Upload")
        CONFIGURE = "CONFIGURE", _("Configure")
        INTEGRATE = "INTEGRATE", _("Integrate")

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audit_logs",
    )
    action = models.CharField(max_length=20, choices=ActionType.choices, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, blank=True, db_index=True)
    object_repr = models.CharField(max_length=200, blank=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True)

    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        get_latest_by = "timestamp"
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["model_name", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["ip_address", "-timestamp"]),
            models.Index(fields=["success", "-timestamp"]),
        ]

    def __str__(self) -> str:
        name = self.user.username if self.user else "Anonymous"
        return f"{name} — {self.action} — {self.model_name} @ {self.timestamp}"

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise ValidationError(_("Audit logs are immutable and cannot be modified."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Audit logs cannot be deleted."))

    @classmethod
    def log(cls, **kwargs):
        """
        Tolerant audit-log writer that normalises legacy field-name variants and
        maps arbitrary action strings to the nearest ActionType value.
        Never raises — swallows all exceptions so audit failures never break
        business logic.
        """
        import logging as _logging
        _logger = _logging.getLogger(__name__)
        try:
            # Remap legacy user field
            if "actor" in kwargs:
                kwargs.setdefault("user", kwargs.pop("actor"))
            else:
                kwargs.pop("actor", None)

            # Remap legacy object_id fields
            for _key in ("target_object_id", "resource_id"):
                if _key in kwargs:
                    kwargs.setdefault("object_id", kwargs.pop(_key))
                else:
                    kwargs.pop(_key, None)

            # Remap legacy model_name fields
            for _key in ("target_content_type", "resource_type", "content_type"):
                if _key in kwargs:
                    _val = str(kwargs.pop(_key))
                    # Strip app-label prefix: "response.ResponseActivation" → "ResponseActivation"
                    kwargs.setdefault("model_name", _val.rsplit(".", 1)[-1])
                else:
                    kwargs.pop(_key, None)

            # Remap legacy metadata fields
            for _key in ("details", "detail"):
                if _key in kwargs:
                    kwargs.setdefault("metadata", kwargs.pop(_key))
                else:
                    kwargs.pop(_key, None)

            # Normalise action value to a valid ActionType choice
            _action = str(kwargs.get("action", "")).upper()
            _valid = {c.value for c in cls.ActionType}
            if _action not in _valid:
                _map = [
                    ("DEESCALAT", "UPDATE"), ("DE_ESCALAT", "UPDATE"),
                    ("ESCALAT", "ESCALATE"),
                    ("SUSPEND", "DEACTIVATE"), ("DEACTIVAT", "DEACTIVATE"),
                    ("ACTIVAT", "ACTIVATE"),
                    ("COMPLET", "UPDATE"), ("RESOLV", "UPDATE"),
                    ("ACKNOWLEDG", "UPDATE"), ("CLOSE", "UPDATE"),
                    ("APPROV", "APPROVE"), ("REJECT", "REJECT"),
                    ("CANCEL", "UPDATE"), ("RETRY", "UPDATE"),
                    ("CREAT", "CREATE"), ("INSERT", "CREATE"),
                    ("DELET", "DELETE"), ("REMOV", "DELETE"),
                    ("EXPORT", "EXPORT"), ("DOWNLOAD", "DOWNLOAD"),
                    ("IMPORT", "IMPORT"), ("UPLOAD", "UPLOAD"),
                    ("LOGIN_FAILED", "LOGIN_FAILED"), ("LOGIN", "LOGIN"),
                    ("LOGOUT", "LOGOUT"),
                    ("PASSWORD_CHANGE", "PASSWORD_CHANGE"),
                    ("PASSWORD_RESET", "PASSWORD_RESET"),
                    ("INTEGRAT", "INTEGRATE"), ("CONFIGUR", "CONFIGURE"),
                    ("VIEW", "VIEW"), ("READ", "VIEW"),
                    ("ALERT", "ALERT"),
                ]
                kwargs["action"] = next((v for k, v in _map if k in _action), "UPDATE")

            # Ensure required model_name is not empty
            if not kwargs.get("model_name"):
                kwargs["model_name"] = "Unknown"

            # Drop any remaining unrecognised fields
            _known = {
                "user", "action", "model_name", "object_id", "object_repr",
                "ip_address", "user_agent", "request_method", "request_path",
                "changes", "metadata", "success", "error_message",
            }
            for _k in list(kwargs.keys()):
                if _k not in _known:
                    del kwargs[_k]

            cls.objects.create(**kwargs)
        except Exception:
            _logger.exception("AuditLog.log() failed — audit entry not written")


# ---------------------------------------------------------------------------
# SystemConfiguration
# ---------------------------------------------------------------------------


class SystemConfiguration(TimeStampedModel):
    """System-wide key-value config store. Keys must be UPPER_CASE."""

    class Category(models.TextChoices):
        GENERAL = "general", _("General")
        SECURITY = "security", _("Security")
        NOTIFICATIONS = "notifications", _("Notifications")
        INTEGRATIONS = "integrations", _("Integrations")
        SURVEILLANCE = "surveillance", _("Surveillance")
        RESPONSE = "response", _("Response")
        ML = "ml", _("Machine Learning")
        PERFORMANCE = "performance", _("Performance")
        FEATURES = "features", _("Features")
        COMPLIANCE = "compliance", _("Compliance")

    key = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text=_("Configuration key in UPPER_CASE"),
    )
    value = models.JSONField(help_text=_("Configuration value (any JSON type)"))
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=50, choices=Category.choices,
        default=Category.GENERAL, db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_sensitive = models.BooleanField(
        default=False,
        help_text=_("If True, value is masked in API responses"),
    )
    default_value = models.JSONField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("System Configuration")
        verbose_name_plural = _("System Configurations")
        ordering = ["category", "key"]
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self) -> str:
        return f"{self.key}: {self.value}"

    def clean(self) -> None:
        super().clean()
        if self.key and not self.key.isupper():
            raise ValidationError({"key": _("Configuration key must be UPPER_CASE.")})


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


class Notification(TimeStampedModel):
    """In-app notification with type, priority, action URL, and optional expiry."""

    class NotificationType(models.TextChoices):
        INFO = "INFO", _("Information")
        WARNING = "WARNING", _("Warning")
        ALERT = "ALERT", _("Alert")
        SUCCESS = "SUCCESS", _("Success")
        ERROR = "ERROR", _("Error")
        SYSTEM = "SYSTEM", _("System")
        REMINDER = "REMINDER", _("Reminder")
        UPDATE = "UPDATE", _("Update")

    class Priority(models.TextChoices):
        LOW = "LOW", _("Low")
        NORMAL = "NORMAL", _("Normal")
        HIGH = "HIGH", _("High")
        URGENT = "URGENT", _("Urgent")

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="notifications", db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices,
        default=NotificationType.INFO, db_index=True,
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices,
        default=Priority.NORMAL, db_index=True,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.URLField(blank=True, max_length=500)
    action_text = models.CharField(max_length=100, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    related_model = models.CharField(max_length=100, blank=True)
    related_object_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["notification_type", "-created_at"]),
            models.Index(fields=["priority", "is_read"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} → {self.user.username}"

    def mark_as_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def mark_as_unread(self) -> None:
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=["is_read", "read_at"])

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)


# ---------------------------------------------------------------------------
# APIKey
# ---------------------------------------------------------------------------


class APIKey(TimeStampedModel):
    """
    Scoped API key for external system integration.
    related_name=core_api_keys avoids clash with integrations.APIKey.
    """

    name = models.CharField(max_length=200)
    key = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="core_api_keys")

    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Security
    allowed_ips = models.JSONField(default=list, blank=True)
    allowed_domains = models.JSONField(default=list, blank=True)

    # Rate limiting
    rate_limit = models.PositiveIntegerField(default=1000, help_text=_("Max requests per hour"))
    rate_limit_window = models.PositiveIntegerField(default=3600, help_text=_("Window in seconds"))

    # Scopes
    permissions = models.JSONField(default=list, blank=True)

    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.BigIntegerField(default=0)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.key[:8]}***"

    def save(self, *args, **kwargs) -> None:
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key() -> str:
        return secrets.token_urlsafe(48)

    def is_valid(self) -> bool:
        if not self.is_active or self.is_deleted:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def is_ip_allowed(self, ip_address: str) -> bool:
        return not self.allowed_ips or ip_address in self.allowed_ips

    def record_usage(self, ip_address: str | None = None) -> None:
        self.last_used_at = timezone.now()
        self.usage_count += 1
        if ip_address:
            self.last_used_ip = ip_address
        self.save(update_fields=["last_used_at", "usage_count", "last_used_ip"])

    def revoke(self) -> None:
        self.is_active = False
        self.save(update_fields=["is_active"])

    def regenerate(self) -> str:
        self.key = self.generate_key()
        self.usage_count = 0
        self.last_used_at = None
        self.last_used_ip = None
        self.save()
        return self.key