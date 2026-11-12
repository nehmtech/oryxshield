from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'websockets'
    verbose_name = 'WebSocket Connections'

    def ready(self):
        import websockets.signals  # noqa: F401