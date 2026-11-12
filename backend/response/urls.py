"""
URL configuration for response app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ResponseLevelViewSet,
    ResponseProtocolViewSet,
    ResponseActivationViewSet,
    EscalationTriggerViewSet,
    ActionItemViewSet,
    ResponseReportViewSet,
    DecisionLogViewSet,
    ResponseDashboardViewSet,
)

router = DefaultRouter()
router.register(r"levels", ResponseLevelViewSet, basename="responselevel")
router.register(r"protocols", ResponseProtocolViewSet, basename="responseprotocol")
router.register(r"activations", ResponseActivationViewSet, basename="responseactivation")
router.register(r"triggers", EscalationTriggerViewSet, basename="escalationtrigger")
router.register(r"actions", ActionItemViewSet, basename="actionitem")
router.register(r"reports", ResponseReportViewSet, basename="responsereport")
router.register(r"decisions", DecisionLogViewSet, basename="decisionlog")
router.register(r"dashboard", ResponseDashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]