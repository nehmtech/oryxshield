"""
Sync engine for mobile app — OryxShield.

Handles:
- Conflict detection (server vs client timestamp).
- Merge strategies (server-wins, client-wins, manual).
- Batch processing with atomic writes.
- Delta sync: return only records changed since last_sync.
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConflictStrategy(str, Enum):
    SERVER_WINS = 'server_wins'
    CLIENT_WINS = 'client_wins'
    LATEST_WINS = 'latest_wins'   # compare updated_at timestamps
    MANUAL = 'manual'             # flag for human review


@dataclass
class SyncItem:
    data_type: str
    payload: Dict[str, Any]
    created_at: datetime
    checksum: str = ''

    def __post_init__(self):
        if not self.checksum:
            self.checksum = hashlib.sha256(
                json.dumps(self.payload, sort_keys=True, default=str).encode()
            ).hexdigest()


@dataclass
class SyncResult:
    total: int = 0
    synced: int = 0
    failed: int = 0
    conflicts: int = 0
    skipped: int = 0
    errors: List[Dict] = field(default_factory=list)
    conflict_records: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'total': self.total,
            'synced': self.synced,
            'failed': self.failed,
            'conflicts': self.conflicts,
            'skipped': self.skipped,
            'errors': self.errors,
            'conflict_records': self.conflict_records,
        }


class SyncEngine:
    """
    Stateless sync engine — instantiate per request / task invocation.

    Usage::

        engine = SyncEngine(device_id='abc123')
        result = engine.process_batch(pending_items)
    """

    MAX_ATTEMPTS = 5

    def __init__(
        self,
        device_id: str,
        conflict_strategy: ConflictStrategy = ConflictStrategy.LATEST_WINS,
    ):
        self.device_id = device_id
        self.conflict_strategy = conflict_strategy
        self._device = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_batch(self, raw_items: List[Dict]) -> SyncResult:
        """
        Process a list of raw sync item dicts from the mobile client.
        Each dict must have: data_type, payload, created_at.
        """
        result = SyncResult(total=len(raw_items))
        device = self._get_device()
        if device is None:
            result.errors.append({'error': f'Device {self.device_id} not found.'})
            return result

        items = [self._parse_item(raw) for raw in raw_items]

        for item in items:
            try:
                outcome = self._process_item(device, item)
                if outcome == 'synced':
                    result.synced += 1
                elif outcome == 'skipped':
                    result.skipped += 1
                elif outcome == 'conflict':
                    result.conflicts += 1
                    result.conflict_records.append({
                        'data_type': item.data_type,
                        'checksum': item.checksum,
                    })
            except Exception as exc:
                result.failed += 1
                result.errors.append({
                    'data_type': item.data_type,
                    'checksum': item.checksum,
                    'error': str(exc),
                })
                logger.exception(
                    "SyncEngine: failed item type=%s device=%s: %s",
                    item.data_type, self.device_id, exc,
                )

        return result

    def get_delta(self, last_sync: datetime, data_types: Optional[List[str]] = None) -> Dict:
        """
        Return server-side records updated since last_sync for the device's
        assigned field worker.  Used by the mobile client to pull updates.
        """
        from .models import FieldWorker, FieldActivity, SurveyResponse, FormSubmission

        device = self._get_device()
        if device is None:
            return {'error': f'Device {self.device_id} not found.'}

        delta: Dict[str, List] = {}

        try:
            worker = FieldWorker.objects.get(user=device.user, is_deleted=False)
        except FieldWorker.DoesNotExist:
            return delta

        if data_types is None or 'CASE_VISIT' in data_types:
            activities = FieldActivity.objects.filter(
                field_worker=worker,
                updated_at__gt=last_sync,
                is_deleted=False,
            ).values('activity_id', 'activity_type', 'activity_date', 'updated_at')
            delta['field_activities'] = [
                {**a, 'updated_at': a['updated_at'].isoformat()} for a in activities
            ]

        if data_types is None or 'SURVEY' in data_types:
            responses = SurveyResponse.objects.filter(
                field_worker=worker,
                updated_at__gt=last_sync,
                is_deleted=False,
            ).values('response_id', 'survey__survey_code', 'response_date', 'updated_at')
            delta['survey_responses'] = [
                {**r, 'updated_at': r['updated_at'].isoformat()} for r in responses
            ]

        return delta

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_device(self):
        if self._device is None:
            from .models import MobileDevice
            try:
                self._device = MobileDevice.objects.select_related('user').get(
                    device_id=self.device_id, is_deleted=False
                )
            except MobileDevice.DoesNotExist:
                logger.error("SyncEngine: device %s not found.", self.device_id)
                return None
        return self._device

    @staticmethod
    def _parse_item(raw: Dict) -> SyncItem:
        created_at = raw.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = timezone.now()

        return SyncItem(
            data_type=raw['data_type'],
            payload=raw.get('payload', {}),
            created_at=created_at,
        )

    def _process_item(self, device, item: SyncItem) -> str:
        """
        Process a single sync item.
        Returns 'synced', 'skipped', or 'conflict'.
        """
        from .models import OfflineData

        # Idempotency: already synced?
        if OfflineData.objects.filter(
            device=device,
            checksum=item.checksum,
            sync_status='SYNCED',
        ).exists():
            return 'skipped'

        # Conflict detection
        conflict = self._detect_conflict(device, item)
        if conflict:
            resolved = self._resolve_conflict(item, conflict)
            if resolved == ConflictStrategy.MANUAL:
                self._flag_conflict(device, item)
                return 'conflict'
            # For LATEST_WINS / SERVER_WINS, skip client payload
            if resolved == ConflictStrategy.SERVER_WINS:
                return 'skipped'
            # CLIENT_WINS falls through to normal processing

        with transaction.atomic():
            record = OfflineData.objects.create(
                device=device,
                data_type=item.data_type,
                data_payload=item.payload,
                sync_status='SYNCING',
                created_offline_at=item.created_at,
                checksum=item.checksum,
            )
            try:
                from .tasks import _dispatch_sync_item
                server_id = _dispatch_sync_item(item.data_type, item.payload)
                record.sync_status = 'SYNCED'
                record.synced_at = timezone.now()
                record.server_record_id = str(server_id) if server_id else ''
                record.save(update_fields=[
                    'sync_status', 'synced_at', 'server_record_id',
                ])
            except Exception as exc:
                record.sync_status = 'FAILED'
                record.error_message = str(exc)
                record.save(update_fields=['sync_status', 'error_message'])
                record.increment_attempts()
                raise

        return 'synced'

    def _detect_conflict(self, device, item: SyncItem) -> Optional[Dict]:
        """
        Returns the conflicting server-side record dict if a conflict exists,
        else None.  A conflict is a FAILED record with the same data_type
        submitted by the same device in the same time window (±5 minutes).
        """
        from .models import OfflineData
        from datetime import timedelta

        window_start = item.created_at - timedelta(minutes=5)
        window_end = item.created_at + timedelta(minutes=5)

        existing = OfflineData.objects.filter(
            device=device,
            data_type=item.data_type,
            created_offline_at__range=(window_start, window_end),
            sync_status='SYNCED',
        ).exclude(checksum=item.checksum).first()

        if existing:
            return {'checksum': existing.checksum, 'synced_at': existing.synced_at}
        return None

    def _resolve_conflict(
        self, item: SyncItem, server_record: Dict
    ) -> ConflictStrategy:
        """Apply the configured strategy; return the effective strategy."""
        if self.conflict_strategy == ConflictStrategy.LATEST_WINS:
            server_ts = server_record.get('synced_at') or timezone.now()
            if isinstance(item.created_at, datetime) and item.created_at > server_ts:
                return ConflictStrategy.CLIENT_WINS
            return ConflictStrategy.SERVER_WINS

        return self.conflict_strategy

    def _flag_conflict(self, device, item: SyncItem) -> None:
        """Persist a CONFLICT record for manual review."""
        from .models import OfflineData
        OfflineData.objects.create(
            device=device,
            data_type=item.data_type,
            data_payload=item.payload,
            sync_status='CONFLICT',
            created_offline_at=item.created_at,
            checksum=item.checksum,
            error_message='Conflict flagged for manual resolution.',
        )
        logger.warning(
            "SyncEngine: conflict flagged for device=%s type=%s checksum=%s",
            self.device_id, item.data_type, item.checksum,
        )