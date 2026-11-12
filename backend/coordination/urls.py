"""
URL configuration for coordination app — OryxShield.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AgencyViewSet,
    CoordinationTeamViewSet,
    TeamMembershipViewSet,
    TaskViewSet,
    MeetingViewSet,
    CommunicationChannelViewSet,
    InformationProductViewSet,
    CoordinationDashboardViewSet,
)

router = DefaultRouter()
router.register(r'agencies', AgencyViewSet, basename='agency')
router.register(r'teams', CoordinationTeamViewSet, basename='coordinationteam')
router.register(r'memberships', TeamMembershipViewSet, basename='teammembership')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'meetings', MeetingViewSet, basename='meeting')
router.register(r'channels', CommunicationChannelViewSet, basename='communicationchannel')
router.register(r'products', InformationProductViewSet, basename='informationproduct')
router.register(r'dashboard', CoordinationDashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]