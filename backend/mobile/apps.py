from django.apps import AppConfig


class MobileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mobile'
    verbose_name = 'Mobile & Field Operations'

    def ready(self):
        import mobile.signals  # noqa: F401