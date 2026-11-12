"""
OryxShield - Analytics Celery Tasks
============================================

6 production-ready Celery tasks.  All use bind=True + max_retries.

Tasks:
    run_epi_model_simulation    – run SIR/SEIR/etc. simulation and persist results
    process_data_export         – generate export file (CSV/Excel/JSON)
    generate_report_from_template – render WHO/IHR/custom report
    calculate_indicators        – daily indicator values for all locations
    run_spatial_analysis        – hotspot / clustering / Moran's I
    clear_expired_caches        – prune stale analytics cache keys

Helper (not a task):
    get_export_data             – fetch and serialise data for export
    calculate_indicator_value   – compute one indicator/location/date
"""

from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import logging
import time

logger = logging.getLogger(__name__)


# =============================================================================
# EPIDEMIOLOGICAL MODEL SIMULATION
# =============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_epi_model_simulation(self, model_id, simulation_days=365, parameters=None):
    """
    Execute an epidemiological model simulation and persist the results.

    Args:
        model_id (str):         UUID of EpidemiologicalModel.
        simulation_days (int):  Horizon in days (1–3650).
        parameters (dict|None): Override model parameters.

    Returns:
        dict: {status, model_id, simulation_days, r0, peak_day, peak_infections, elapsed_time}
    """
    from .models import EpidemiologicalModel
    from .epidemiological_models import run_model

    try:
        try:
            model = EpidemiologicalModel.objects.get(id=model_id, is_deleted=False)
        except EpidemiologicalModel.DoesNotExist:
            logger.error("EpidemiologicalModel %s not found or deleted", model_id)
            return {'status': 'error', 'message': 'Model not found'}

        logger.info("Starting simulation: model=%s type=%s days=%d",
                    model.name, model.model_type, simulation_days)

        # Merge caller parameters on top of stored parameters
        base = model.parameters.copy()
        if parameters:
            base.update(parameters)
        # Always inject initial conditions from the model record
        base.update({
            'initial_susceptible': model.initial_susceptible,
            'initial_infected':    model.initial_infected,
            'initial_recovered':   model.initial_recovered,
        })
        if model.initial_exposed is not None:
            base['initial_exposed'] = model.initial_exposed
        # Expose stored R0 so run_model() can derive beta when it is absent
        if model.basic_reproduction_number is not None:
            base.setdefault('basic_reproduction_number',
                            float(model.basic_reproduction_number))

        start   = time.time()
        results = run_model(model_type=model.model_type, parameters=base, days=simulation_days)
        elapsed = time.time() - start

        model.simulation_results      = results
        model.simulation_completed_at = timezone.now()

        if 'peak_day' in results:
            model.peak_day = results['peak_day']
        if 'peak_infections' in results:
            model.peak_infections = results['peak_infections']
        if 'r0' in results:
            model.basic_reproduction_number = Decimal(str(results['r0']))
        if 'attack_rate' in results:
            model.attack_rate = Decimal(str(results['attack_rate']))

        model.save(update_fields=[
            'simulation_results', 'simulation_completed_at',
            'peak_day', 'peak_infections',
            'basic_reproduction_number', 'attack_rate',
        ])

        # Invalidate cached overview so dashboard sees fresh data
        cache.delete('analytics:dashboard:overview')

        logger.info(
            "Simulation complete: model=%s R0=%s peak_day=%s elapsed=%.2fs",
            model.name, results.get('r0', 'N/A'), results.get('peak_day', 'N/A'), elapsed)

        return {
            'status':          'success',
            'model_id':        str(model.id),
            'simulation_days': simulation_days,
            'r0':              results.get('r0'),
            'peak_day':        results.get('peak_day'),
            'peak_infections': results.get('peak_infections'),
            'elapsed_time':    elapsed,
        }

    except Exception as exc:
        logger.error("Simulation error for model %s: %s", model_id, exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'status': 'error', 'message': str(exc)}


# =============================================================================
# DATA EXPORT
# =============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=180)
def process_data_export(self, export_id):
    """
    Generate an export file and attach it to the DataExport record.

    Args:
        export_id (str): UUID of DataExport.

    Returns:
        dict: {status, export_id, row_count, file_size, elapsed_time}
    """
    from .models import DataExport
    from .export_formats import export_to_csv, export_to_json, export_to_excel
    from django.core.files.base import ContentFile

    export = None
    try:
        try:
            export = DataExport.objects.get(id=export_id, is_deleted=False)
        except DataExport.DoesNotExist:
            logger.error("DataExport %s not found or deleted", export_id)
            return {'status': 'error', 'message': 'Export not found'}

        export.status = 'PROCESSING'
        export.processing_started_at = timezone.now()
        export.save(update_fields=['status', 'processing_started_at'])

        logger.info("Processing export: id=%s format=%s type=%s",
                    export.id, export.export_format, export.data_type)

        start = time.time()
        data  = get_export_data(
            data_type=export.data_type,
            filters=export.filters,
            start_date=export.start_date,
            end_date=export.end_date,
        )

        if not data:
            raise ValueError("No data found matching export criteria")

        fmt = export.export_format
        if fmt == 'CSV':
            raw      = export_to_csv(data)
            filename = f"{export.name}.csv"
            content  = raw.encode('utf-8')

        elif fmt == 'EXCEL':
            content  = export_to_excel(data)
            filename = f"{export.name}.xlsx"

        elif fmt == 'JSON':
            raw      = export_to_json(data)
            filename = f"{export.name}.json"
            content  = raw.encode('utf-8')

        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        elapsed = time.time() - start

        export.file.save(filename, ContentFile(content), save=False)
        export.file_size              = len(content)
        export.row_count              = len(data)
        export.status                 = 'COMPLETED'
        export.processing_completed_at = timezone.now()
        export.processing_time        = Decimal(str(elapsed))
        export.save(update_fields=[
            'file', 'file_size', 'row_count', 'status',
            'processing_completed_at', 'processing_time',
        ])

        logger.info("Export completed: id=%s rows=%d bytes=%d elapsed=%.2fs",
                    export.id, export.row_count, export.file_size, elapsed)

        return {
            'status':       'success',
            'export_id':    str(export.id),
            'row_count':    export.row_count,
            'file_size':    export.file_size,
            'elapsed_time': elapsed,
        }

    except Exception as exc:
        logger.error("Export error for %s: %s", export_id, exc, exc_info=True)
        if export is not None:
            try:
                export.status                 = 'FAILED'
                export.error_message          = str(exc)
                export.processing_completed_at = timezone.now()
                export.save(update_fields=[
                    'status', 'error_message', 'processing_completed_at'])
            except Exception:
                logger.error("Failed to persist export failure status", exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'status': 'error', 'message': str(exc)}


def get_export_data(data_type, filters, start_date=None, end_date=None):
    """
    Fetch and serialise records for export.

    Supported data_type values:
        health_data – HealthData records from the surveillance app
        locations   – Location records from the core app

    Args:
        data_type (str):          Which dataset to export.
        filters (dict):           Field-level filters to apply.
        start_date (date|None):   Lower bound on date_recorded / created_at.
        end_date   (date|None):   Upper bound on date_recorded / created_at.

    Returns:
        list[dict]: Serialisable rows ready for export_to_* functions.
    """
    from surveillance.models import HealthData
    from core.models import Location

    def _stringify_uuids(rows):
        """Convert UUID / datetime values to plain strings in-place."""
        for row in rows:
            for key, val in list(row.items()):
                if hasattr(val, 'hex'):            # UUID
                    row[key] = str(val)
                elif hasattr(val, 'isoformat'):    # date / datetime
                    row[key] = val.isoformat()
        return rows

    try:
        if data_type == 'health_data':
            qs = HealthData.objects.filter(is_deleted=False)
            if start_date:
                qs = qs.filter(date_recorded__gte=start_date)
            if end_date:
                qs = qs.filter(date_recorded__lte=end_date)
            if filters:
                if 'disease_code' in filters:
                    qs = qs.filter(disease_code=filters['disease_code'])
                if 'location' in filters:
                    qs = qs.filter(location_id=filters['location'])
                if 'severity' in filters:
                    qs = qs.filter(severity=filters['severity'])
                if 'case_classification' in filters:
                    qs = qs.filter(case_classification=filters['case_classification'])
                if 'outcome' in filters:
                    qs = qs.filter(outcome=filters['outcome'])
            return _stringify_uuids(list(qs.values()))

        if data_type == 'locations':
            qs = Location.objects.filter(is_deleted=False)
            if filters:
                if 'location_type' in filters:
                    qs = qs.filter(location_type=filters['location_type'])
                if 'parent' in filters:
                    qs = qs.filter(parent_id=filters['parent'])
            return _stringify_uuids(list(qs.values()))

        logger.warning("Unknown export data_type: %s", data_type)
        return []

    except Exception as exc:
        logger.error("get_export_data error: %s", exc, exc_info=True)
        raise


# =============================================================================
# REPORT GENERATION
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def generate_report_from_template(self, template_id):
    """
    Generate a statistical report from a ReportTemplate.

    Args:
        template_id (str): UUID of ReportTemplate.

    Returns:
        dict: {status, template_id, elapsed_time, report_data}
    """
    from .models import ReportTemplate
    from .report_generator import generate_who_sitrep, generate_ihr_report, generate_custom_report

    try:
        try:
            template = ReportTemplate.objects.get(id=template_id, is_deleted=False)
        except ReportTemplate.DoesNotExist:
            logger.error("ReportTemplate %s not found or deleted", template_id)
            return {'status': 'error', 'message': 'Template not found'}

        logger.info("Generating report from template: %s (type=%s)",
                    template.name, template.template_type)

        start = time.time()

        dispatch = {
            'WHO_SITREP': generate_who_sitrep,
            'IHR':        generate_ihr_report,
        }
        generator   = dispatch.get(template.template_type, generate_custom_report)
        report_data = generator(template) if template.template_type in dispatch \
            else generator(template, {})

        elapsed = time.time() - start

        logger.info("Report generated: template=%s elapsed=%.2fs", template.name, elapsed)

        return {
            'status':      'success',
            'template_id': str(template.id),
            'elapsed_time': elapsed,
            'report_data': report_data,
        }

    except Exception as exc:
        logger.error("Report generation error for template %s: %s",
                     template_id, exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'status': 'error', 'message': str(exc)}


# =============================================================================
# INDICATOR CALCULATION
# =============================================================================

@shared_task
def calculate_indicators():
    """
    Calculate all active indicators for every Location and persist IndicatorValues.

    Runs daily (schedule configured in CELERY_BEAT_SCHEDULE).

    Returns:
        dict: {status, indicators_calculated, errors, elapsed_time}
    """
    from .models import Indicator, IndicatorValue
    from core.models import Location

    logger.info("Starting daily indicator calculations")
    start       = time.time()
    today       = timezone.now().date()
    indicators  = Indicator.objects.filter(is_active=True, is_deleted=False)
    locations   = Location.objects.filter(is_deleted=False)
    calculated  = 0
    errors      = 0

    for indicator in indicators:
        for location in locations:
            try:
                value = calculate_indicator_value(indicator, location, today)
                if value is not None:
                    iv = IndicatorValue.objects.create(
                        indicator=indicator,
                        location=location,
                        value=value,
                        period_start=today,
                        period_end=today,
                    )
                    iv.calculate_variance()
                    calculated += 1
            except Exception as exc:
                logger.error(
                    "Indicator calc failed: code=%s location=%s error=%s",
                    indicator.code, location.name, exc)
                errors += 1

    elapsed = time.time() - start
    logger.info("Indicator calculation done: calculated=%d errors=%d elapsed=%.2fs",
                calculated, errors, elapsed)

    return {
        'status':                 'completed',
        'indicators_calculated':  calculated,
        'errors':                 errors,
        'elapsed_time':           elapsed,
    }


def calculate_indicator_value(indicator, location, date):
    """
    Compute a single indicator value for one location on a given date.

    Supports standard codes: CFR, IR, HR, CASES, DEATHS, RR, TPR, AVG_AGE.

    Args:
        indicator (Indicator): The KPI definition.
        location  (Location):  The geographic scope.
        date      (date):      Reference date.

    Returns:
        Decimal | None: Computed value, or None if no data / unknown code.
    """
    from surveillance.models import HealthData
    from django.db.models import Avg
    from datetime import timedelta

    try:
        freq = indicator.reporting_frequency
        if freq == 'DAILY':
            start_date, end_date = date, date
        elif freq == 'WEEKLY':
            start_date = date - timedelta(days=6)
            end_date   = date
        elif freq == 'MONTHLY':
            start_date = date.replace(day=1)
            end_date   = date
        else:
            start_date = date - timedelta(days=6)
            end_date   = date

        hd = HealthData.objects.filter(
            location=location,
            date_recorded__gte=start_date,
            date_recorded__lte=end_date,
            is_deleted=False,
        )

        code = indicator.code

        if code == 'CFR':
            total = hd.filter(case_classification__in=['CONFIRMED', 'PROBABLE']).count()
            if total > 0:
                deaths = hd.filter(outcome='DEATH').count()
                return Decimal(str(round(deaths / total * 100, 2)))

        elif code == 'IR':
            new_cases  = hd.filter(case_classification='CONFIRMED').count()
            population = location.metadata.get('population', 100000)
            if population > 0:
                return Decimal(str(round(new_cases / population * 100_000, 2)))

        elif code == 'HR':
            total = hd.filter(case_classification__in=['CONFIRMED', 'PROBABLE']).count()
            if total > 0:
                hosp = hd.filter(hospitalization_status='HOSPITALIZED').count()
                return Decimal(str(round(hosp / total * 100, 2)))

        elif code == 'CASES':
            return Decimal(str(hd.filter(case_classification='CONFIRMED').count()))

        elif code == 'DEATHS':
            return Decimal(str(hd.filter(outcome='DEATH').count()))

        elif code == 'RR':
            total = hd.filter(case_classification__in=['CONFIRMED', 'PROBABLE']).count()
            if total > 0:
                recovered = hd.filter(outcome='RECOVERED').count()
                return Decimal(str(round(recovered / total * 100, 2)))

        elif code == 'TPR':
            total_tested = hd.filter(test_result__in=['POSITIVE', 'NEGATIVE']).count()
            if total_tested > 0:
                positive = hd.filter(test_result='POSITIVE').count()
                return Decimal(str(round(positive / total_tested * 100, 2)))

        elif code == 'AVG_AGE':
            avg = hd.filter(age__isnull=False).aggregate(avg=Avg('age'))['avg']
            if avg is not None:
                return Decimal(str(round(avg, 1)))

        logger.debug("No calculation logic for indicator code: %s", code)
        return None

    except Exception as exc:
        logger.error("calculate_indicator_value error: code=%s location=%s error=%s",
                     indicator.code, location.name, exc, exc_info=True)
        return None


# =============================================================================
# SPATIAL ANALYSIS
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_spatial_analysis(self, analysis_id):
    """
    Execute a spatial analysis (hotspot / clustering / autocorrelation).

    Args:
        analysis_id (str): UUID of SpatialAnalysis.

    Returns:
        dict: {status, analysis_id, elapsed_time, results_summary}
    """
    from .models import SpatialAnalysis
    from .spatial_analysis import hotspot_analysis, calculate_morans_i, spatial_clustering
    from surveillance.models import HealthData
    import numpy as np

    try:
        try:
            analysis = SpatialAnalysis.objects.get(id=analysis_id, is_deleted=False)
        except SpatialAnalysis.DoesNotExist:
            logger.error("SpatialAnalysis %s not found or deleted", analysis_id)
            return {'status': 'error', 'message': 'Analysis not found'}

        logger.info("Running spatial analysis: %s (type=%s)",
                    analysis.name, analysis.analysis_type)

        start = time.time()

        health_data = HealthData.objects.filter(
            location__parent=analysis.location,
            disease_code=analysis.disease_code,
            date_recorded__gte=analysis.start_date,
            date_recorded__lte=analysis.end_date,
            is_deleted=False,
            latitude__isnull=False,
            longitude__isnull=False,
        )

        if not health_data.exists():
            logger.warning("No data for spatial analysis %s", analysis.name)
            analysis.results = {'message': 'No data available for analysis period'}
            analysis.save(update_fields=['results'])
            return {'status': 'success', 'message': 'No data available'}

        # Aggregate case counts per coordinate point
        location_data = {}
        for record in health_data:
            key = (float(record.latitude), float(record.longitude))
            location_data[key] = location_data.get(key, 0) + 1

        coordinates = np.array(list(location_data.keys()))
        values      = np.array(list(location_data.values()))

        logger.info("Analysing %d locations (%d total cases)",
                    len(coordinates), int(values.sum()))

        update_fields = ['results']

        if analysis.analysis_type == 'HOTSPOT':
            results = hotspot_analysis(values, coordinates, threshold=1.96)
            analysis.hotspots      = results.get('hotspots', [])
            analysis.hotspot_count = len(analysis.hotspots)
            update_fields += ['hotspots', 'hotspot_count']

        elif analysis.analysis_type == 'AUTOCORRELATION':
            results = calculate_morans_i(values, coordinates)
            analysis.morans_i = Decimal(str(results['morans_i']))
            analysis.p_value  = Decimal(str(results['p_value']))
            analysis.z_score  = Decimal(str(results['z_score']))
            update_fields += ['morans_i', 'p_value', 'z_score']

        elif analysis.analysis_type == 'CLUSTERING':
            results = spatial_clustering(coordinates, values=values,
                                         method='dbscan', eps=0.1, min_samples=5)
            analysis.clusters      = results.get('clusters', [])
            analysis.cluster_count = results.get('n_clusters', 0)
            update_fields += ['clusters', 'cluster_count']

        else:
            results = {'message': f'{analysis.analysis_type} run completed'}

        analysis.results = results
        analysis.save(update_fields=update_fields)

        elapsed = time.time() - start
        logger.info("Spatial analysis done: %s elapsed=%.2fs", analysis.name, elapsed)

        return {
            'status':      'success',
            'analysis_id': str(analysis.id),
            'elapsed_time': elapsed,
            'results_summary': {
                'hotspot_count': analysis.hotspot_count,
                'cluster_count': analysis.cluster_count,
                'morans_i':      float(analysis.morans_i) if analysis.morans_i else None,
            },
        }

    except Exception as exc:
        logger.error("Spatial analysis error for %s: %s", analysis_id, exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {'status': 'error', 'message': str(exc)}


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

@shared_task
def clear_expired_caches():
    """
    Prune stale analytics cache keys.

    Uses Redis KEYS pattern scan when the backend is Redis;
    falls back to clearing a static known-key list otherwise.

    Returns:
        dict: {status, cleared_count}
    """
    logger.info("Clearing expired analytics caches")
    cleared = 0

    try:
        from django.core.cache.backends.redis import RedisCache

        if isinstance(cache, RedisCache):
            client   = cache.client.get_client()
            patterns = [
                'analytics:overview:*',
                'analytics:dashboard:*',
                'analytics:model:*',
                'analytics:spatial:*',
            ]
            for pattern in patterns:
                keys = client.keys(pattern)
                for key in keys:
                    ttl = client.ttl(key)
                    # -1 means no expiry; -2 means gone; skip both
                    if ttl in (-1, -2):
                        continue
                    if ttl < 3600:
                        client.delete(key)
                        cleared += 1

            logger.info("Cleared %d Redis cache keys", cleared)
            return {'status': 'completed', 'cleared_count': cleared}

    except ImportError:
        pass

    # Fallback: delete well-known keys
    for key in (
        'analytics:dashboard:overview',
        'analytics:indicators:summary',
        'analytics:models:active_count',
        'analytics:reports:published_count',
        'analytics:exports:pending_count',
    ):
        cache.delete(key)
        cleared += 1

    logger.info("Cleared %d fallback cache keys", cleared)
    return {'status': 'completed', 'cleared_count': cleared}