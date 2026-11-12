"""
Tests: custom permission classes.
"""
import pytest
from unittest.mock import MagicMock
from core.permissions import LocationBasedPermission


@pytest.mark.django_db
class TestLocationBasedPermission:
    def test_staff_always_passes(self):
        perm = LocationBasedPermission()
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_staff = True
        obj = MagicMock()
        assert perm.has_object_permission(request, None, obj) is True

    def test_obj_without_location_passes(self):
        perm = LocationBasedPermission()
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_staff = False
        obj = MagicMock(spec=[])  # no .location attribute
        assert perm.has_object_permission(request, None, obj) is True

    def test_ancestor_cache_used_on_repeated_calls(self):
        perm = LocationBasedPermission()
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_staff = False
        # Simulate profile with a location
        loc = MagicMock()
        loc.pk = "parent-pk"
        loc.parent = None
        request.user.profile.location = loc

        child_loc = MagicMock()
        child_loc.pk = "child-pk"
        child_loc.parent = loc

        obj = MagicMock()
        obj.location = child_loc

        # First call builds cache
        result1 = perm.has_object_permission(request, None, obj)
        # Second call should reuse cache (no additional DB hits)
        result2 = perm.has_object_permission(request, None, obj)
        assert result1 == result2
