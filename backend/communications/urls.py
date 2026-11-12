"""
URL configuration for communications app.
Mounted at: /api/v1/communications/
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BroadcastViewSet, CampaignViewSet, CommunicationDashboardViewSet,
    ContactListViewSet, FeedbackResponseViewSet, MessageTemplateViewSet,
    MessageViewSet, PublicAnnouncementViewSet, SocialMediaPostViewSet,
)

router = DefaultRouter()
router.register(r'templates', MessageTemplateViewSet, basename='messagetemplate')
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'broadcasts', BroadcastViewSet, basename='broadcast')
router.register(r'contacts', ContactListViewSet, basename='contactlist')
router.register(r'announcements', PublicAnnouncementViewSet, basename='publicannouncement')
router.register(r'social', SocialMediaPostViewSet, basename='socialmediapost')
router.register(r'feedback', FeedbackResponseViewSet, basename='feedbackresponse')
router.register(r'dashboard', CommunicationDashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]