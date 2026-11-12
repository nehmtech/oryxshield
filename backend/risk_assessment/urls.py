"""
URL configuration for risk_assessment app.
Include under the prefix /api/v1/risk/ in the project urls.py.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertViewSet,
    PredictiveModelViewSet,
    RiskDashboardViewSet,
    RiskFactorViewSet,
    RiskScoreViewSet,
    ThresholdViewSet,
    ThreatClassificationViewSet,
)

router = DefaultRouter()
router.register(r"scores", RiskScoreViewSet, basename="riskscore")
router.register(r"threats", ThreatClassificationViewSet, basename="threatclassification")
router.register(r"alerts", AlertViewSet, basename="alert")
router.register(r"thresholds", ThresholdViewSet, basename="threshold")
router.register(r"factors", RiskFactorViewSet, basename="riskfactor")
router.register(r"models", PredictiveModelViewSet, basename="predictivemodel")
router.register(r"dashboard", RiskDashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]