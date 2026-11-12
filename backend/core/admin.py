"""
OryxShield — Django Admin
====================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Admin classes
-------------
UserAdmin               — extended with inline profile + bulk actions
UserProfileAdmin        — profile management with 2FA & security info
LocationAdmin           — hierarchical locations with coordinate display
AuditLogAdmin           — read-only immutable audit trail
SystemConfigurationAdmin — key-value config with masked sensitive values
NotificationAdmin       — notification centre with bulk read/unread
APIKeyAdmin             — API keys with masked display + regenerate/revoke actions
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    APIKey,
    AuditLog,
    Location,
    Notification,
    SystemConfiguration,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _("Profile")
    fk_name = "user"
    fields = (
        "phone_number", "organization", "department", "job_title",
        "location", "two_factor_enabled", "two_factor_method",
        "language", "timezone", "email_verified", "phone_verified",
        "failed_login_attempts", "account_locked_until", "last_login_ip",
    )
    readonly_fields = (
        "failed_login_attempts", "account_locked_until", "last_login_ip",
    )


# ---------------------------------------------------------------------------
# UserAdmin
# ---------------------------------------------------------------------------

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = [
        "username", "email", "full_name", "is_active_badge",
        "is_staff", "date_joined", "last_login",
    ]
    list_filter = ["is_active", "is_staff", "is_superuser", "date_joined"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    actions = ["activate_users", "deactivate_users", "unlock_accounts"]

    @admin.display(description=_("Full Name"))
    def full_name(self, obj: User) -> str:
        return obj.get_full_name() or "—"

    @admin.display(description=_("Active"), boolean=False)
    def is_active_badge(self, obj: User) -> str:
        if obj.is_active:
            return format_html('<span style="color:green;font-weight:bold;">✓ Active</span>')
        return format_html('<span style="color:red;">✗ Inactive</span>')

    @admin.action(description=_("Activate selected users"))
    def activate_users(self, request, queryset) -> None:
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} users activated.")

    @admin.action(description=_("Deactivate selected users"))
    def deactivate_users(self, request, queryset) -> None:
        count = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{count} users deactivated.")

    @admin.action(description=_("Unlock selected user accounts"))
    def unlock_accounts(self, request, queryset) -> None:
        count = 0
        for user in queryset:
            if hasattr(user, "profile"):
                user.profile.unlock_account()
                count += 1
        self.message_user(request, f"{count} accounts unlocked.")


# ---------------------------------------------------------------------------
# UserProfileAdmin
# ---------------------------------------------------------------------------

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user", "organization", "department", "location",
        "two_factor_display", "email_verified", "phone_verified",
        "is_locked_display", "created_at",
    ]
    list_filter = [
        "two_factor_enabled", "email_verified", "phone_verified",
        "language", "organization",
    ]
    search_fields = [
        "user__username", "user__email", "organization",
        "department", "phone_number",
    ]
    readonly_fields = [
        "user", "failed_login_attempts", "account_locked_until",
        "last_login_ip", "last_login_location", "has_social_auth",
        "social_providers", "created_at", "updated_at",
    ]
    fieldsets = (
        (_("User"), {"fields": ("user",)}),
        (_("Personal"), {"fields": ("phone_number", "avatar", "bio", "date_of_birth")}),
        (_("Organisation"), {"fields": ("organization", "department", "job_title", "employee_id")}),
        (_("Location & Preferences"), {"fields": ("location", "language", "timezone")}),
        (_("2FA"), {"fields": ("two_factor_enabled", "two_factor_method")}),
        (_("Security"), {
            "fields": (
                "failed_login_attempts", "account_locked_until",
                "last_login_ip", "last_login_location",
            ),
            "classes": ("collapse",),
        }),
        (_("Social Auth"), {
            "fields": ("has_social_auth", "social_providers"),
            "classes": ("collapse",),
        }),
        (_("Verification"), {"fields": ("email_verified", "phone_verified", "terms_accepted_at")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description=_("2FA"), boolean=True)
    def two_factor_display(self, obj: UserProfile) -> bool:
        return obj.two_factor_enabled

    @admin.display(description=_("Locked?"))
    def is_locked_display(self, obj: UserProfile) -> str:
        if obj.is_account_locked():
            return format_html('<span style="color:red;font-weight:bold;">🔒 Locked</span>')
        return format_html('<span style="color:green;">Unlocked</span>')


# ---------------------------------------------------------------------------
# LocationAdmin
# ---------------------------------------------------------------------------

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = [
        "name", "code", "location_type", "parent_link",
        "has_coordinates", "population", "is_deleted", "created_at",
    ]
    list_filter = ["location_type", "is_deleted"]
    search_fields = ["name", "code"]
    readonly_fields = ["created_at", "updated_at", "deleted_at", "full_path", "depth"]
    raw_id_fields = ["parent"]
    actions = ["soft_delete_selected", "restore_selected"]
    fieldsets = (
        (None, {"fields": ("name", "code", "location_type", "parent")}),
        (_("Hierarchy"), {"fields": ("full_path", "depth"), "classes": ("collapse",)}),
        (_("Geospatial"), {"fields": ("latitude", "longitude", "boundary", "elevation_meters")}),
        (_("Demographics"), {"fields": ("population", "area_sq_km")}),
        (_("Metadata"), {"fields": ("metadata",), "classes": ("collapse",)}),
        (_("Soft delete"), {"fields": ("is_deleted", "deleted_at"), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description=_("Parent"))
    def parent_link(self, obj: Location) -> str:
        if obj.parent:
            return format_html(
                '<a href="/admin/core/location/{}/change/">{}</a>',
                obj.parent.pk, obj.parent.name,
            )
        return "—"

    @admin.display(description=_("Coords?"), boolean=True)
    def has_coordinates(self, obj: Location) -> bool:
        return obj.latitude is not None and obj.longitude is not None

    @admin.action(description=_("Soft-delete selected locations"))
    def soft_delete_selected(self, request, queryset) -> None:
        count = 0
        for loc in queryset:
            loc.soft_delete()
            count += 1
        self.message_user(request, f"{count} locations soft-deleted.")

    @admin.action(description=_("Restore selected locations"))
    def restore_selected(self, request, queryset) -> None:
        count = 0
        for loc in queryset:
            loc.restore()
            count += 1
        self.message_user(request, f"{count} locations restored.")


# ---------------------------------------------------------------------------
# AuditLogAdmin — read-only
# ---------------------------------------------------------------------------

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp", "user_link", "action", "model_name",
        "object_id", "ip_address", "success_badge",
    ]
    list_filter = ["action", "model_name", "success"]
    search_fields = ["user__username", "model_name", "object_id", "ip_address"]
    date_hierarchy = "timestamp"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description=_("User"))
    def user_link(self, obj: AuditLog) -> str:
        if obj.user:
            return format_html(
                '<a href="/admin/auth/user/{}/change/">{}</a>',
                obj.user.pk, obj.user.username,
            )
        return "Anonymous"

    @admin.display(description=_("Success"))
    def success_badge(self, obj: AuditLog) -> str:
        if obj.success:
            return format_html('<span style="color:green;">✓</span>')
        return format_html('<span style="color:red;">✗</span>')


# ---------------------------------------------------------------------------
# SystemConfigurationAdmin
# ---------------------------------------------------------------------------

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        "key", "category", "masked_value", "is_active", "is_sensitive", "updated_at",
    ]
    list_filter = ["category", "is_active", "is_sensitive"]
    search_fields = ["key", "description"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["activate_configs", "deactivate_configs"]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # on edit, key is immutable
            return list(self.readonly_fields) + ["key"]
        return self.readonly_fields

    @admin.display(description=_("Value"))
    def masked_value(self, obj: SystemConfiguration) -> str:
        if obj.is_sensitive:
            return "***SENSITIVE***"
        val = str(obj.value)
        return val[:80] + "…" if len(val) > 80 else val

    @admin.action(description=_("Activate selected configurations"))
    def activate_configs(self, request, queryset) -> None:
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} configurations activated.")

    @admin.action(description=_("Deactivate selected configurations"))
    def deactivate_configs(self, request, queryset) -> None:
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} configurations deactivated.")


# ---------------------------------------------------------------------------
# NotificationAdmin
# ---------------------------------------------------------------------------

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "title", "user", "notification_type", "priority",
        "is_read", "is_expired", "created_at",
    ]
    list_filter = ["notification_type", "priority", "is_read"]
    search_fields = ["user__username", "title"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at", "read_at"]
    raw_id_fields = ["user"]
    actions = ["mark_read", "mark_unread"]

    @admin.display(description=_("Expired?"), boolean=True)
    def is_expired(self, obj: Notification) -> bool:
        return obj.is_expired

    @admin.action(description=_("Mark selected as read"))
    def mark_read(self, request, queryset) -> None:
        count = queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"{count} notifications marked as read.")

    @admin.action(description=_("Mark selected as unread"))
    def mark_unread(self, request, queryset) -> None:
        count = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f"{count} notifications marked as unread.")


# ---------------------------------------------------------------------------
# APIKeyAdmin
# ---------------------------------------------------------------------------

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name", "user", "masked_key", "is_active",
        "expires_at", "usage_count", "last_used_at", "created_at",
    ]
    list_filter = ["is_active", "is_deleted"]
    search_fields = ["name", "user__username"]
    readonly_fields = [
        "key", "usage_count", "last_used_at", "last_used_ip",
        "created_at", "updated_at",
    ]
    raw_id_fields = ["user"]
    actions = ["revoke_keys"]

    @admin.display(description=_("Key"))
    def masked_key(self, obj: APIKey) -> str:
        return f"{obj.key[:8]}{'*' * 16}"

    @admin.action(description=_("Revoke selected API keys"))
    def revoke_keys(self, request, queryset) -> None:
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"{count} API keys revoked.")


