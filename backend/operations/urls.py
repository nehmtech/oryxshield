"""URL routing for operations app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CaseViewSet, ContactViewSet, ContactMonitoringViewSet,
    TestingCenterViewSet, TestingAppointmentViewSet,
    VaccinationCampaignViewSet, VaccinationRecordViewSet,
    QuarantineFacilityViewSet, QuarantineRecordViewSet,
    OperationsDashboardViewSet,
)

router = DefaultRouter()
router.register(r'cases', CaseViewSet, basename='case')
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'monitoring', ContactMonitoringViewSet, basename='contactmonitoring')
router.register(r'testing-centers', TestingCenterViewSet, basename='testingcenter')
router.register(r'testing-appointments', TestingAppointmentViewSet, basename='testingappointment')
router.register(r'vaccination-campaigns', VaccinationCampaignViewSet, basename='vaccinationcampaign')
router.register(r'vaccination-records', VaccinationRecordViewSet, basename='vaccinationrecord')
router.register(r'quarantine-facilities', QuarantineFacilityViewSet, basename='quarantinefacility')
router.register(r'quarantine-records', QuarantineRecordViewSet, basename='quarantinerecord')
router.register(r'dashboard', OperationsDashboardViewSet, basename='dashboard')

urlpatterns = [path('', include(router.urls))]