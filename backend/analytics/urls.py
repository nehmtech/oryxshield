"""
OryxShield - Analytics URL Configuration
=================================================

Base: /api/v1/analytics/

Registered resources:
    epi-models          EpidemiologicalModelViewSet
    spatial             SpatialAnalysisViewSet
    timeseries          TimeSeriesAnalysisViewSet
    reports             StatisticalReportViewSet
    dashboards          DashboardViewSet
    exports             DataExportViewSet
    indicators          IndicatorViewSet
    indicator-values    IndicatorValueViewSet
    templates           ReportTemplateViewSet
    overview            AnalyticsDashboardViewSet

Custom endpoints:
    POST   epi-models/{id}/run_simulation/
    GET    reports/published/
    POST   exports/request_export/
    POST   templates/{id}/generate/
    GET    overview/overview/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EpidemiologicalModelViewSet,
    SpatialAnalysisViewSet,
    TimeSeriesAnalysisViewSet,
    StatisticalReportViewSet,
    DashboardViewSet,
    DataExportViewSet,
    IndicatorViewSet,
    IndicatorValueViewSet,
    ReportTemplateViewSet,
    AnalyticsDashboardViewSet,
)

app_name = 'analytics'

router = DefaultRouter()
router.register(r'epi-models',       EpidemiologicalModelViewSet, basename='epidemiologicalmodel')
router.register(r'spatial',          SpatialAnalysisViewSet,      basename='spatialanalysis')
router.register(r'timeseries',       TimeSeriesAnalysisViewSet,   basename='timeseriesanalysis')
router.register(r'reports',          StatisticalReportViewSet,    basename='statisticalreport')
router.register(r'dashboards',       DashboardViewSet,            basename='dashboard')
router.register(r'exports',          DataExportViewSet,           basename='dataexport')
router.register(r'indicators',       IndicatorViewSet,            basename='indicator')
router.register(r'indicator-values', IndicatorValueViewSet,       basename='indicatorvalue')
router.register(r'templates',        ReportTemplateViewSet,       basename='reporttemplate')
router.register(r'overview',         AnalyticsDashboardViewSet,   basename='overview')

urlpatterns = [
    path('', include(router.urls)),
]