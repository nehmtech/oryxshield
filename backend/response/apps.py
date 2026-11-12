from django.apps import AppConfig


class ResponseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "response"
    verbose_name = "Response Management System"

    def ready(self):
        import response.signals  # noqa: F401