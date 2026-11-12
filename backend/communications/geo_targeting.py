"""
Geo-targeting service for OryxShield communications.
Location-based recipient resolution without PostGIS dependency.
"""
import logging
from typing import Dict, List, Optional

from django.db.models import Q

logger = logging.getLogger(__name__)


class GeoTargetingService:
    """Resolve message recipients from locations, criteria, and contact lists."""

    # ── Location-based resolution ──────────────────────────────────────────────

    def get_recipients_in_location(
        self,
        location_id: str,
        include_sublocations: bool = True,
    ) -> List[str]:
        """
        Return identifiers (email + phone) for all active users in a location.

        Args:
            location_id: core.Location UUID string
            include_sublocations: recurse into descendant locations

        Returns:
            list of email/phone strings (may contain duplicates across calls)
        """
        from core.models import Location
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            location = Location.objects.get(id=location_id, is_deleted=False)
        except Location.DoesNotExist:
            logger.error("Location %s not found", location_id)
            return []

        if include_sublocations and hasattr(location, 'get_descendants'):
            locations = [location] + list(location.get_descendants())
        else:
            locations = [location]

        location_ids = [str(loc.id) for loc in locations]

        users = User.objects.filter(location_id__in=location_ids, is_active=True).only(
            'email', 'phone_number'
        )
        recipients = self._extract_identifiers(users)
        logger.info("Found %d recipients in location %s", len(recipients), location.name)
        return recipients

    def get_recipients_in_multiple_locations(
        self,
        location_ids: List[str],
        include_sublocations: bool = True,
    ) -> List[str]:
        """Deduplicated recipients across multiple locations."""
        all_ids: set = set()
        for loc_id in location_ids:
            all_ids.update(self.get_recipients_in_location(loc_id, include_sublocations))
        return list(all_ids)

    # ── Criteria filtering ─────────────────────────────────────────────────────

    def filter_recipients_by_criteria(
        self,
        base_recipients: List[str],
        criteria: Dict,
    ) -> List[str]:
        """
        Intersect base_recipients with users matching criteria.

        criteria keys (all optional):
            age_min, age_max, gender, health_status, occupation, risk_level
        """
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        User = get_user_model()

        if not criteria:
            return base_recipients

        filters = Q(is_active=True)

        if 'age_min' in criteria:
            cutoff = timezone.now().date() - timedelta(days=criteria['age_min'] * 365)
            filters &= Q(date_of_birth__lte=cutoff)

        if 'age_max' in criteria:
            cutoff = timezone.now().date() - timedelta(days=criteria['age_max'] * 365)
            filters &= Q(date_of_birth__gte=cutoff)

        if 'gender' in criteria:
            filters &= Q(gender=criteria['gender'])

        if 'occupation' in criteria:
            filters &= Q(occupation__icontains=criteria['occupation'])

        if 'risk_level' in criteria:
            filters &= Q(risk_assessments__risk_level=criteria['risk_level'])

        if 'health_status' in criteria:
            filters &= Q(health_records__status=criteria['health_status'])

        filtered_users = User.objects.filter(filters).distinct().only('email', 'phone_number')
        filtered_ids = set(self._extract_identifiers(filtered_users))
        result = list(set(base_recipients) & filtered_ids)
        logger.info("Criteria filter: %d → %d recipients", len(base_recipients), len(result))
        return result

    # ── Broadcast recipient resolution ─────────────────────────────────────────

    def get_recipients_for_broadcast(
        self,
        target_locations: List[str],
        target_criteria: Dict,
        include_sublocations: bool = True,
    ) -> Dict[str, List[str]]:
        """
        Resolve broadcast recipients segmented by channel.

        Returns:
            {
                'sms':   [phone numbers],
                'email': [email addresses],
                'push':  [device tokens],
                'total': int (unique people),
            }
        """
        all_ids = self.get_recipients_in_multiple_locations(target_locations, include_sublocations)

        if target_criteria:
            all_ids = self.filter_recipients_by_criteria(all_ids, target_criteria)

        sms_recipients = [i for i in all_ids if self._is_phone(i)]
        email_recipients = [i for i in all_ids if self._is_email(i)]
        push_tokens = self._resolve_push_tokens(email_recipients, sms_recipients)

        result = {
            'sms': sms_recipients,
            'email': email_recipients,
            'push': push_tokens,
            'total': len(set(sms_recipients + email_recipients)),
        }
        logger.info(
            "Broadcast recipients: %d SMS, %d email, %d push",
            len(sms_recipients), len(email_recipients), len(push_tokens),
        )
        return result

    def estimate_reach(
        self,
        target_locations: List[str],
        target_criteria: Dict,
        include_sublocations: bool = True,
    ) -> int:
        return self.get_recipients_for_broadcast(
            target_locations, target_criteria, include_sublocations
        )['total']

    # ── Specialised queries ────────────────────────────────────────────────────

    def get_high_risk_recipients(self, location_id: str) -> List[str]:
        """All high-risk recipients in a location."""
        base = self.get_recipients_in_location(location_id)
        return self.filter_recipients_by_criteria(base, {'risk_level': 'HIGH'})

    def get_healthcare_workers(self, location_id: Optional[str] = None) -> List[str]:
        """Healthcare worker identifiers, optionally scoped to a location."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        filters = Q(is_active=True) & (
            Q(role__in=['HEALTHCARE_WORKER', 'DOCTOR', 'NURSE'])
            | Q(occupation__icontains='health')
        )
        if location_id:
            filters &= Q(location_id=location_id)

        users = User.objects.filter(filters).only('email', 'phone_number')
        result = self._extract_identifiers(users)
        logger.info("Found %d healthcare workers", len(result))
        return result

    def get_contact_list_recipients(self, contact_list_id: str) -> Dict[str, List[str]]:
        """Resolve recipients from a saved ContactList."""
        from communications.models import ContactList

        try:
            contact_list = ContactList.objects.get(id=contact_list_id, is_deleted=False)
        except ContactList.DoesNotExist:
            logger.error("ContactList %s not found", contact_list_id)
            return {'sms': [], 'email': []}

        sms = [c['phone'] for c in contact_list.contacts if c.get('phone')]
        email = [c['email'] for c in contact_list.contacts if c.get('email')]
        return {'sms': sms, 'email': email}

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_identifiers(users) -> List[str]:
        result = []
        for user in users:
            if getattr(user, 'email', None):
                result.append(user.email)
            if getattr(user, 'phone_number', None):
                result.append(user.phone_number)
        return result

    @staticmethod
    def _is_email(identifier: str) -> bool:
        return '@' in identifier

    @staticmethod
    def _is_phone(identifier: str) -> bool:
        stripped = identifier.replace('+', '').replace('-', '').replace(' ', '')
        return stripped.isdigit() and len(stripped) >= 7

    def _resolve_push_tokens(
        self, email_recipients: List[str], sms_recipients: List[str]
    ) -> List[str]:
        """Fetch FCM/APNS device tokens for resolved users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = User.objects.filter(
            Q(email__in=email_recipients) | Q(phone_number__in=sms_recipients),
            is_active=True,
        )
        tokens = []
        for user in users:
            if hasattr(user, 'device_tokens'):
                tokens.extend(
                    user.device_tokens.filter(is_active=True).values_list('token', flat=True)
                )
        return tokens


# Singleton instance
geo_targeting = GeoTargetingService()