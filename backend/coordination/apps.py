from django.apps import AppConfig


class CoordinationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coordination'
    verbose_name = 'Coordination Platform'

    def ready(self):
        import coordination.signals  # noqa: F401