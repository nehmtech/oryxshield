"""
URL configuration for resources app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResourceCategoryViewSet,
    ResourceItemViewSet,
    FacilityViewSet,
    InventoryViewSet,
    StockMovementViewSet,
    ProcurementRequestViewSet,
    FacilityCapacityViewSet,
    SupplierViewSet,
    DemandForecastViewSet,
    ResourceDashboardViewSet,
)

router = DefaultRouter()
router.register(r'categories', ResourceCategoryViewSet, basename='resourcecategory')
router.register(r'items', ResourceItemViewSet, basename='resourceitem')
router.register(r'facilities', FacilityViewSet, basename='facility')
router.register(r'inventory', InventoryViewSet, basename='inventory')
router.register(r'movements', StockMovementViewSet, basename='stockmovement')
router.register(r'procurement', ProcurementRequestViewSet, basename='procurementrequest')
router.register(r'capacity', FacilityCapacityViewSet, basename='facilitycapacity')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'forecasts', DemandForecastViewSet, basename='demandforecast')
router.register(r'dashboard', ResourceDashboardViewSet, basename='resourcedashboard')

urlpatterns = [
    path('', include(router.urls)),
]