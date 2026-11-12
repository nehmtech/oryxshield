"""
OryxShield — Signal Handlers
======================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Signals
-------
post_save User           → create / save UserProfile
pre_delete User          → write deletion AuditLog
social_account_added     → enrich UserProfile via SocialAuthenticationBackend
post_save SystemConfiguration → invalidate config cache
"""

from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UserProfile auto-creation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created: bool, **kwargs) -> None:
    """Auto-create a UserProfile whenever a User record is first saved."""
    if created:
        from .models import UserProfile
        _, was_created = UserProfile.objects.get_or_create(user=instance)
        if was_created:
            logger.info("UserProfile created for user=%s", instance.username)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance: User, **kwargs) -> None:
    """Propagate User saves to the related profile when it exists."""
    if hasattr(instance, "profile"):
        try:
            instance.profile.save()
        except Exception as exc:
            logger.error("Error saving profile for user=%s: %s", instance.username, exc)


# ---------------------------------------------------------------------------
# User deletion audit
# ---------------------------------------------------------------------------

@receiver(pre_delete, sender=User)
def log_user_deletion(sender, instance: User, **kwargs) -> None:
    """Write an AuditLog entry before a User record is hard-deleted."""
    try:
        from .models import AuditLog
        AuditLog.log(
            user=None,
            action=AuditLog.ActionType.DELETE,
            model_name="User",
            object_id=str(instance.pk),
            object_repr=instance.username,
            metadata={
                "username": instance.username,
                "email": instance.email,
                "is_staff": instance.is_staff,
                "deleted_by_system": True,
            },
        )
        logger.info("User deletion logged: username=%s", instance.username)
    except Exception as exc:
        logger.error("Failed to log user deletion: %s", exc)


# ---------------------------------------------------------------------------
# Social auth enrichment
# ---------------------------------------------------------------------------

try:
    from allauth.socialaccount.signals import social_account_added

    @receiver(social_account_added)
    def handle_social_account_added(request, sociallogin, **kwargs) -> None:
        """Enrich UserProfile when a social account is linked."""
        try:
            from .authentication import SocialAuthenticationBackend
            SocialAuthenticationBackend.process_social_login(request, sociallogin)
            logger.info(
                "Social account linked: provider=%s user=%s",
                sociallogin.account.provider,
                sociallogin.user.username,
            )
        except Exception as exc:
            logger.error("Error processing social account: %s", exc)

except ImportError:
    logger.debug("django-allauth not installed; skipping social_account_added signal.")


# ---------------------------------------------------------------------------
# SystemConfiguration cache invalidation
# ---------------------------------------------------------------------------

@receiver(post_save, sender="core.SystemConfiguration")
def invalidate_config_cache(sender, instance, **kwargs) -> None:
    """Clear the cached config value whenever a SystemConfiguration record changes."""
    try:
        from django.core.cache import cache
        cache_key = f"config:{instance.key}"
        cache.delete(cache_key)
        logger.debug("Config cache invalidated: key=%s", instance.key)
    except Exception as exc:
        logger.error("Failed to invalidate config cache: %s", exc)


@receiver(post_delete, sender="core.SystemConfiguration")
def invalidate_config_cache_on_delete(sender, instance, **kwargs) -> None:
    try:
        from django.core.cache import cache
        cache.delete(f"config:{instance.key}")
    except Exception:
        logger.warning("Failed to invalidate config cache on delete for key=%s", instance.key, exc_info=True)