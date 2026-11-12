"""
OryxShield - Analytics App Configuration
=================================================
"""

from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
import logging
import sys

logger = logging.getLogger(__name__)


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'Analytics & Reporting System'

    def ready(self):
        try:
            from . import signals  # noqa: F401
            logger.info(f"{self.verbose_name}: Signal handlers registered")
        except ImportError as e:
            logger.warning(f"{self.verbose_name}: Failed to import signals - {e}")
        except Exception as e:
            logger.error(f"{self.verbose_name}: Error registering signals - {e}", exc_info=True)

        self._initialize_cache()
        self._register_celery_tasks()
        self._register_system_checks()

        if settings.DEBUG:
            logger.info(
                f"{self.verbose_name} initialized | "
                "Models: 9 | Endpoints: 50+ | Tasks: 6 | "
                "Formats: CSV/Excel/JSON/PDF/Stata/SPSS"
            )

    def _initialize_cache(self):
        try:
            defaults = {
                'analytics:dashboard:overview': {},
                'analytics:indicators:summary': {},
                'analytics:models:active_count': 0,
                'analytics:reports:published_count': 0,
                'analytics:exports:pending_count': 0,
            }
            for key, value in defaults.items():
                if cache.get(key) is None:
                    cache.set(key, value, 3600)
            logger.debug(f"{self.verbose_name}: Cache initialised ({len(defaults)} keys)")
        except Exception as e:
            logger.warning(f"{self.verbose_name}: Cache init failed - {e}")

    def _register_celery_tasks(self):
        try:
            if 'celery' not in sys.modules:
                return
            from . import tasks  # noqa: F401
            logger.debug(f"{self.verbose_name}: Celery tasks registered")
        except ImportError:
            logger.debug(f"{self.verbose_name}: Celery not configured")
        except Exception as e:
            logger.warning(f"{self.verbose_name}: Task registration error - {e}")

    def _register_system_checks(self):
        try:
            from django.core.checks import register, Tags, Warning, Error

            @register(Tags.compatibility)
            def check_analytics_dependencies(app_configs, **kwargs):
                errors = []
                warnings = []

                for pkg, eid, hint in [
                    ('numpy', 'analytics.E001', 'pip install numpy'),
                    ('scipy', 'analytics.E002', 'pip install scipy'),
                ]:
                    try:
                        __import__(pkg)
                    except ImportError:
                        errors.append(Error(f'{pkg} is required', hint=hint, id=eid))

                for pkg, wid, hint in [
                    ('pandas', 'analytics.W001', 'pip install pandas'),
                    ('statsmodels', 'analytics.W002', 'pip install statsmodels'),
                    ('sklearn', 'analytics.W003', 'pip install scikit-learn'),
                ]:
                    try:
                        __import__(pkg)
                    except ImportError:
                        warnings.append(Warning(f'{pkg} recommended', hint=hint, id=wid))

                return errors + warnings

        except Exception as e:
            logger.warning(f"{self.verbose_name}: System check registration failed - {e}")