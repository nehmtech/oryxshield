from django.apps import AppConfig


class RiskAssessmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "risk_assessment"
    verbose_name = "Risk Assessment System"

    def ready(self):
        import risk_assessment.signals  # noqa: F401