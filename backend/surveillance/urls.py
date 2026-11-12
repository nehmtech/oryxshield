"""
URL configuration for surveillance app.
Mounted at: /api/v1/surveillance/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DataSourceViewSet,
    HealthDataViewSet,
    AnomalyDetectionViewSet,
    CaseClusterViewSet,
    HotspotViewSet,
    SurveillanceReportViewSet,
    DiseaseProfileViewSet,
    DataQualityCheckViewSet,
    SurveillanceDashboardViewSet,
)

router = DefaultRouter()
router.register(r"data-sources", DataSourceViewSet, basename="datasource")
router.register(r"health-data", HealthDataViewSet, basename="healthdata")
router.register(r"anomalies", AnomalyDetectionViewSet, basename="anomalydetection")
router.register(r"clusters", CaseClusterViewSet, basename="casecluster")
router.register(r"hotspots", HotspotViewSet, basename="hotspot")
router.register(r"reports", SurveillanceReportViewSet, basename="surveillancereport")
router.register(r"disease-profiles", DiseaseProfileViewSet, basename="diseaseprofile")
router.register(r"quality-checks", DataQualityCheckViewSet, basename="dataqualitycheck")
router.register(r"dashboard", SurveillanceDashboardViewSet, basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
]