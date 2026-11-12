"""
Views for operations app.
"""
import logging
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from core.pagination import CustomPagination
from core.models import AuditLog

from .models import (
    Case, Contact, ContactMonitoring,
    TestingCenter, TestingAppointment,
    VaccinationCampaign, VaccinationRecord,
    QuarantineFacility, QuarantineRecord,
)
from .serializers import (
    CaseSerializer, CaseListSerializer,
    ContactSerializer, ContactListSerializer,
    ContactMonitoringSerializer,
    TestingCenterSerializer,
    TestingAppointmentSerializer,
    VaccinationCampaignSerializer,
    VaccinationRecordSerializer,
    QuarantineFacilitySerializer,
    QuarantineRecordSerializer,
    OperationsDashboardSerializer,
)

logger = logging.getLogger(__name__)


def _audit(request, action_label: str, content_type: str, obj_id, detail: dict = None):
    """Thin wrapper to write an immutable AuditLog entry."""
    try:
        AuditLog.log(
            user=request.user,
            action=action_label,
            content_type=content_type,
            object_id=str(obj_id),
            ip_address=request.META.get('REMOTE_ADDR', ''),
            detail=detail or {},
        )
    except Exception:
        logger.exception("AuditLog write failed for %s %s", content_type, obj_id)


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------

class CaseViewSet(viewsets.ModelViewSet):
    """CRUD + domain actions for disease cases."""

    queryset = Case.objects.filter(is_deleted=False).select_related(
        'location', 'assigned_to', 'health_data'
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['classification', 'status', 'location', 'disease_code', 'is_isolated']
    search_fields = ['case_id', 'patient_name', 'disease_name']
    ordering_fields = ['created_at', 'symptom_onset_date', 'diagnosis_date']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return CaseListSerializer
        return CaseSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'Case', instance.pk, {'case_id': instance.case_id})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'Case', instance.pk, {'case_id': instance.case_id})

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'Case', instance.pk)

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Active cases."""
        qs = self.queryset.filter(status=Case.STATUS_ACTIVE)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = CaseListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def confirmed(self, request):
        """Confirmed cases."""
        qs = self.queryset.filter(
            classification=Case.CLASSIFICATION_CONFIRMED,
            status=Case.STATUS_ACTIVE,
        )
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = CaseListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Close a case with a terminal outcome."""
        instance = self.get_object()
        outcome = request.data.get('outcome')
        if outcome not in (Case.STATUS_RECOVERED, Case.STATUS_DECEASED, Case.CLASSIFICATION_NOT_A_CASE):
            return Response(
                {'error': 'outcome must be RECOVERED, DECEASED, or NOT_A_CASE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.resolve(outcome)
        _audit(request, 'RESOLVE_CASE', 'Case', instance.pk, {'outcome': outcome})
        return Response({'status': 'resolved', 'outcome': outcome})

    @action(detail=True, methods=['post'])
    def isolate(self, request, pk=None):
        """Start isolation for a case."""
        instance = self.get_object()
        location = request.data.get('isolation_location', '')
        instance.start_isolation(location)
        _audit(request, 'ISOLATE_CASE', 'Case', instance.pk)
        return Response({'status': 'isolated'})

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """All contacts for this case."""
        instance = self.get_object()
        contacts = Contact.objects.filter(
            source_case=instance, is_deleted=False
        )
        page = self.paginate_queryset(contacts)
        serializer = ContactListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class ContactViewSet(viewsets.ModelViewSet):
    """CRUD + domain actions for case contacts."""

    queryset = Contact.objects.filter(is_deleted=False).select_related(
        'source_case', 'location', 'assigned_to', 'became_case'
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'contact_type', 'source_case', 'location', 'is_quarantined']
    search_fields = ['contact_id', 'contact_name', 'contact_phone']
    ordering_fields = ['created_at', 'exposure_date', 'monitoring_end_date']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ContactListSerializer
        return ContactSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'Contact', instance.pk, {'contact_id': instance.contact_id})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'Contact', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'Contact', instance.pk)

    @action(detail=False, methods=['get'])
    def under_monitoring(self, request):
        qs = self.queryset.filter(status=Contact.STATUS_MONITORING)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = ContactListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def symptomatic(self, request):
        qs = self.queryset.filter(status=Contact.STATUS_SYMPTOMATIC)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = ContactListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def start_monitoring(self, request, pk=None):
        instance = self.get_object()
        period = int(request.data.get('period_days', 14))
        if period < 1 or period > 30:
            return Response(
                {'error': 'period_days must be 1–30.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.start_monitoring(period_days=period)
        _audit(request, 'START_MONITORING', 'Contact', instance.pk, {'period_days': period})
        return Response({'status': 'monitoring_started', 'period_days': period})

    @action(detail=True, methods=['post'])
    def convert_to_case(self, request, pk=None):
        """Mark contact as converted to a case."""
        contact = self.get_object()
        case_id = request.data.get('case_id')
        try:
            case = Case.objects.get(case_id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found.'}, status=status.HTTP_404_NOT_FOUND)
        contact.convert_to_case(case)
        _audit(request, 'CONVERT_TO_CASE', 'Contact', contact.pk, {'case_id': case_id})
        return Response({'status': 'converted', 'case_id': case_id})

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        instance = self.get_object()
        instance.clear()
        _audit(request, 'CLEAR_CONTACT', 'Contact', instance.pk)
        return Response({'status': 'cleared'})


# ---------------------------------------------------------------------------
# Contact Monitoring
# ---------------------------------------------------------------------------

class ContactMonitoringViewSet(viewsets.ModelViewSet):
    """Daily monitoring records for contacts."""

    queryset = ContactMonitoring.objects.filter(is_deleted=False).select_related(
        'contact', 'monitored_by'
    )
    serializer_class = ContactMonitoringSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['contact', 'monitoring_date', 'has_symptoms', 'is_compliant']
    ordering_fields = ['monitoring_date']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        instance = serializer.save(monitored_by=self.request.user)
        _audit(self.request, 'CREATE', 'ContactMonitoring', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'ContactMonitoring', instance.pk)

    @action(detail=False, methods=['get'])
    def symptomatic_today(self, request):
        today = timezone.now().date()
        qs = self.queryset.filter(monitoring_date=today, has_symptoms=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Testing Center
# ---------------------------------------------------------------------------

class TestingCenterViewSet(viewsets.ModelViewSet):
    """Testing facility management."""

    queryset = TestingCenter.objects.filter(is_deleted=False).select_related('location')
    serializer_class = TestingCenterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['location', 'is_operational']
    search_fields = ['name', 'code']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'TestingCenter', instance.pk, {'code': instance.code})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'TestingCenter', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'TestingCenter', instance.pk)

    @action(detail=False, methods=['get'])
    def operational(self, request):
        qs = self.queryset.filter(is_operational=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'])
    def capacity_status(self, request, pk=None):
        center = self.get_object()
        return Response({
            'code': center.code,
            'daily_capacity': center.daily_capacity,
            'current_load': center.current_load,
            'available_slots': center.available_slots,
            'is_at_capacity': center.is_at_capacity,
        })


# ---------------------------------------------------------------------------
# Testing Appointment
# ---------------------------------------------------------------------------

class TestingAppointmentViewSet(viewsets.ModelViewSet):
    """Testing appointment scheduling and result tracking."""

    queryset = TestingAppointment.objects.filter(is_deleted=False).select_related(
        'testing_center', 'case', 'contact'
    )
    serializer_class = TestingAppointmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'testing_center', 'appointment_date', 'result']
    search_fields = ['appointment_id', 'patient_name', 'patient_id_number']
    ordering_fields = ['appointment_date', 'appointment_time']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'TestingAppointment', instance.pk,
               {'appointment_id': instance.appointment_id})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'TestingAppointment', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'TestingAppointment', instance.pk)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        qs = self.queryset.filter(appointment_date=today)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def record_result(self, request, pk=None):
        """Record a test result."""
        instance = self.get_object()
        result = request.data.get('result')
        if result not in (
            TestingAppointment.RESULT_POSITIVE,
            TestingAppointment.RESULT_NEGATIVE,
            TestingAppointment.RESULT_INCONCLUSIVE,
        ):
            return Response(
                {'error': 'result must be POSITIVE, NEGATIVE, or INCONCLUSIVE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.record_result(
            result=result,
            lab_ref=request.data.get('lab_reference', ''),
        )
        _audit(request, 'RECORD_RESULT', 'TestingAppointment', instance.pk,
               {'result': result})
        return Response({'status': 'result_recorded', 'result': result})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        instance = self.get_object()
        instance.cancel()
        _audit(request, 'CANCEL', 'TestingAppointment', instance.pk)
        return Response({'status': 'cancelled'})


# ---------------------------------------------------------------------------
# Vaccination Campaign
# ---------------------------------------------------------------------------

class VaccinationCampaignViewSet(viewsets.ModelViewSet):
    """Vaccination campaign management."""

    queryset = VaccinationCampaign.objects.filter(is_deleted=False).prefetch_related(
        'target_locations'
    ).select_related('campaign_manager')
    serializer_class = VaccinationCampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'campaign_code', 'vaccine_name']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'VaccinationCampaign', instance.pk,
               {'campaign_code': instance.campaign_code})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'VaccinationCampaign', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'VaccinationCampaign', instance.pk)

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.queryset.filter(status=VaccinationCampaign.STATUS_ACTIVE)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        instance = self.get_object()
        instance.activate()
        _audit(request, 'ACTIVATE_CAMPAIGN', 'VaccinationCampaign', instance.pk)
        return Response({'status': 'activated'})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        instance = self.get_object()
        instance.pause()
        _audit(request, 'PAUSE_CAMPAIGN', 'VaccinationCampaign', instance.pk)
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        instance = self.get_object()
        instance.complete()
        _audit(request, 'COMPLETE_CAMPAIGN', 'VaccinationCampaign', instance.pk)
        return Response({'status': 'completed'})

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        instance = self.get_object()
        return Response({
            'campaign_code': instance.campaign_code,
            'target_population': instance.target_population,
            'people_vaccinated': instance.people_vaccinated,
            'doses_administered': instance.doses_administered,
            'coverage_rate': instance.coverage_rate,
            'status': instance.status,
        })


# ---------------------------------------------------------------------------
# Vaccination Record
# ---------------------------------------------------------------------------

class VaccinationRecordViewSet(viewsets.ModelViewSet):
    """Individual vaccination dose records."""

    queryset = VaccinationRecord.objects.filter(is_deleted=False).select_related(
        'campaign', 'location', 'administered_by'
    )
    serializer_class = VaccinationRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign', 'vaccination_date', 'dose_number', 'location']
    search_fields = ['record_id', 'patient_name', 'patient_id_number']
    ordering_fields = ['vaccination_date']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(administered_by=self.request.user)
            # Update campaign counters
            campaign = instance.campaign
            campaign.doses_administered += 1
            if instance.dose_number == 1:
                campaign.people_vaccinated += 1
            campaign.save(update_fields=[
                'doses_administered', 'people_vaccinated', 'updated_at'
            ])
        _audit(self.request, 'CREATE', 'VaccinationRecord', instance.pk,
               {'record_id': instance.record_id})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'VaccinationRecord', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'VaccinationRecord', instance.pk)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        qs = self.queryset.filter(vaccination_date=today)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def adverse_events(self, request):
        qs = self.queryset.filter(adverse_event_reported=True)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def report_adverse_event(self, request, pk=None):
        instance = self.get_object()
        details = request.data.get('details', '')
        severity = request.data.get('severity', 'MILD')
        if not details:
            return Response(
                {'error': 'details is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.report_adverse_event(details=details, severity=severity)
        _audit(request, 'ADVERSE_EVENT', 'VaccinationRecord', instance.pk,
               {'severity': severity})
        return Response({'status': 'adverse_event_recorded'})


# ---------------------------------------------------------------------------
# Quarantine Facility
# ---------------------------------------------------------------------------

class QuarantineFacilityViewSet(viewsets.ModelViewSet):
    """Quarantine facility management."""

    queryset = QuarantineFacility.objects.filter(is_deleted=False).select_related('location')
    serializer_class = QuarantineFacilitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['facility_type', 'location', 'is_operational']
    search_fields = ['name', 'code']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'CREATE', 'QuarantineFacility', instance.pk,
               {'code': instance.code})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'QuarantineFacility', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'QuarantineFacility', instance.pk)

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Facilities with available beds."""
        qs = [f for f in self.queryset.filter(is_operational=True) if not f.is_full]
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def occupancy(self, request, pk=None):
        facility = self.get_object()
        return Response({
            'code': facility.code,
            'total_capacity': facility.total_capacity,
            'current_occupancy': facility.current_occupancy,
            'available_beds': facility.available_beds,
            'occupancy_rate': facility.occupancy_rate,
            'is_full': facility.is_full,
        })


# ---------------------------------------------------------------------------
# Quarantine Record
# ---------------------------------------------------------------------------

class QuarantineRecordViewSet(viewsets.ModelViewSet):
    """Individual quarantine record management."""

    queryset = QuarantineRecord.objects.filter(is_deleted=False).select_related(
        'facility', 'case', 'contact'
    )
    serializer_class = QuarantineRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['facility', 'status']
    search_fields = ['record_id', 'individual_name', 'individual_id_number']
    ordering_fields = ['admission_date', 'expected_release_date']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            instance.facility.increment_occupancy()
        _audit(self.request, 'CREATE', 'QuarantineRecord', instance.pk,
               {'record_id': instance.record_id})

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit(self.request, 'UPDATE', 'QuarantineRecord', instance.pk)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        _audit(self.request, 'DELETE', 'QuarantineRecord', instance.pk)

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.queryset.filter(status=QuarantineRecord.STATUS_IN_QUARANTINE)
        page = self.paginate_queryset(self.filter_queryset(qs))
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def releasing_today(self, request):
        today = timezone.now().date()
        qs = self.queryset.filter(
            expected_release_date=today,
            status=QuarantineRecord.STATUS_IN_QUARANTINE,
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def start_quarantine(self, request, pk=None):
        instance = self.get_object()
        instance.start_quarantine()
        _audit(request, 'START_QUARANTINE', 'QuarantineRecord', instance.pk)
        return Response({'status': 'in_quarantine'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        instance = self.get_object()
        instance.complete_quarantine()
        _audit(request, 'COMPLETE_QUARANTINE', 'QuarantineRecord', instance.pk)
        return Response({'status': 'completed'})

    @action(detail=True, methods=['post'])
    def release_early(self, request, pk=None):
        instance = self.get_object()
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'reason is required for early release.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.release_early(reason=reason)
        _audit(request, 'RELEASE_EARLY', 'QuarantineRecord', instance.pk, {'reason': reason})
        return Response({'status': 'released_early'})

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        instance = self.get_object()
        new_facility_id = request.data.get('facility_id')
        try:
            new_facility = QuarantineFacility.objects.get(
                pk=new_facility_id, is_operational=True, is_deleted=False
            )
        except QuarantineFacility.DoesNotExist:
            return Response(
                {'error': 'Target facility not found or not operational.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if new_facility.is_full:
            return Response(
                {'error': f'{new_facility.name} is at capacity.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            new_record = instance.transfer(
                new_facility=new_facility,
                reason=request.data.get('reason', ''),
            )
        _audit(request, 'TRANSFER_QUARANTINE', 'QuarantineRecord', instance.pk,
               {'new_facility': str(new_facility_id), 'new_record': new_record.record_id})
        return Response({
            'status': 'transferred',
            'new_record_id': new_record.record_id,
        })


# ---------------------------------------------------------------------------
# Operations Dashboard
# ---------------------------------------------------------------------------

class OperationsDashboardViewSet(viewsets.ViewSet):
    """Read-only dashboard aggregations for operations."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        today = timezone.now().date()

        active_cases = Case.objects.filter(
            status=Case.STATUS_ACTIVE, is_deleted=False
        ).count()
        confirmed_cases = Case.objects.filter(
            classification=Case.CLASSIFICATION_CONFIRMED,
            status=Case.STATUS_ACTIVE,
            is_deleted=False,
        ).count()
        contacts_monitoring = Contact.objects.filter(
            status=Contact.STATUS_MONITORING, is_deleted=False
        ).count()
        symptomatic = Contact.objects.filter(
            status=Contact.STATUS_SYMPTOMATIC, is_deleted=False
        ).count()
        quarantined = Contact.objects.filter(
            is_quarantined=True, is_deleted=False
        ).count()
        tests_today = TestingAppointment.objects.filter(
            appointment_date=today, is_deleted=False
        ).count()
        positive_today = TestingAppointment.objects.filter(
            appointment_date=today,
            result=TestingAppointment.RESULT_POSITIVE,
            is_deleted=False,
        ).count()
        vaccinations_today = VaccinationRecord.objects.filter(
            vaccination_date=today, is_deleted=False
        ).count()
        completions_today = QuarantineRecord.objects.filter(
            expected_release_date=today,
            status=QuarantineRecord.STATUS_IN_QUARANTINE,
            is_deleted=False,
        ).count()
        at_capacity = sum(
            1 for f in QuarantineFacility.objects.filter(
                is_operational=True, is_deleted=False
            )
            if f.is_full
        )

        data = {
            'active_cases': active_cases,
            'confirmed_cases': confirmed_cases,
            'contacts_under_monitoring': contacts_monitoring,
            'symptomatic_contacts': symptomatic,
            'quarantined_individuals': quarantined,
            'tests_today': tests_today,
            'positive_tests_today': positive_today,
            'vaccinations_today': vaccinations_today,
            'quarantine_completions_today': completions_today,
            'facilities_at_capacity': at_capacity,
        }
        serializer = OperationsDashboardSerializer(data)
        return Response(serializer.data)