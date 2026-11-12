"""
REST API URL configuration for the websockets management app.
Include in your project urls.py:

    path('api/ws-mgmt/', include('websockets.urls')),
"""
from rest_framework.routers import DefaultRouter
from .views import BroadcastMessageViewSet, ChannelGroupViewSet, WebSocketConnectionViewSet

router = DefaultRouter()
router.register(r'groups',      ChannelGroupViewSet,          basename='channelgroup')
router.register(r'connections', WebSocketConnectionViewSet,   basename='wsconnection')
router.register(r'broadcasts',  BroadcastMessageViewSet,      basename='broadcastmessage')

urlpatterns = router.urls