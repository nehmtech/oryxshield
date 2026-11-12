from django.apps import AppConfig


class ResourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'resources'
    verbose_name = 'Resource Management System'

    def ready(self):
        import resources.signals  # noqa: F401