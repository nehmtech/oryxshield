"""URL configuration for OryxShield integrations app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExternalSystemViewSet, DataMappingViewSet, IntegrationJobViewSet,
    WebhookViewSet, WebhookLogViewSet, APIKeyViewSet,
    IntegrationLogViewSet, DataTransferViewSet
)

router = DefaultRouter()
router.register(r'systems', ExternalSystemViewSet, basename='externalsystem')
router.register(r'mappings', DataMappingViewSet, basename='datamapping')
router.register(r'jobs', IntegrationJobViewSet, basename='integrationjob')
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'webhook-logs', WebhookLogViewSet, basename='webhooklog')
router.register(r'api-keys', APIKeyViewSet, basename='apikey')
router.register(r'logs', IntegrationLogViewSet, basename='integrationlog')
router.register(r'transfers', DataTransferViewSet, basename='datatransfer')

urlpatterns = [path('', include(router.urls))]