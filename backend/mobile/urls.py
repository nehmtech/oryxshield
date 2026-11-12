"""URL configuration for mobile app — OryxShield."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MobileDeviceViewSet,
    OfflineDataViewSet,
    FieldWorkerViewSet,
    FieldActivityViewSet,
    MobileSurveyViewSet,
    SurveyResponseViewSet,
    DataCollectionFormViewSet,
    FormSubmissionViewSet,
    MobileNotificationViewSet,
)
from django.http import JsonResponse
from .public_interface import chw_dashboard, chw_tasks, delta_sync, nearby_workers

def _ping(request):
    return JsonResponse({"status": "ok"})

router = DefaultRouter()
router.register(r'devices', MobileDeviceViewSet, basename='mobiledevice')
router.register(r'offline-data', OfflineDataViewSet, basename='offlinedata')
router.register(r'field-workers', FieldWorkerViewSet, basename='fieldworker')
router.register(r'field-activities', FieldActivityViewSet, basename='fieldactivity')
router.register(r'surveys', MobileSurveyViewSet, basename='mobilesurvey')
router.register(r'survey-responses', SurveyResponseViewSet, basename='surveyresponse')
router.register(r'forms', DataCollectionFormViewSet, basename='datacollectionform')
router.register(r'form-submissions', FormSubmissionViewSet, basename='formsubmission')
router.register(r'notifications', MobileNotificationViewSet, basename='mobilenotification')

urlpatterns = [
    path('', include(router.urls)),

    # CHW convenience endpoints
    path('dashboard/', chw_dashboard, name='chw-dashboard'),
    path('tasks/', chw_tasks, name='chw-tasks'),

    # Sync
    path('delta/', delta_sync, name='delta-sync'),

    # Proximity
    path('nearby-workers/', nearby_workers, name='nearby-workers'),

    # Ping / liveness check
    path('ping/', _ping, name='mobile-ping'),
]