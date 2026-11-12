from django.apps import AppConfig


class SurveillanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "surveillance"
    verbose_name = "Surveillance System"

    def ready(self):
        import surveillance.signals  # noqa: F401