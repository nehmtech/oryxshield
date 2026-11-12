"""
Performance indexes for HealthData and related surveillance models.

Adds:
- Compound (is_deleted, date_recorded) for dashboard aggregate counts
- Compound (disease_code, location, date_recorded) for joint filters
- db_index on severity and outcome for filtering
- db_index on patient_id for search
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveillance", "0001_initial"),
    ]

    operations = [
        # ── HealthData ────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="healthdata",
            index=models.Index(
                fields=["is_deleted", "-date_recorded"],
                name="surv_hd_deleted_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="healthdata",
            index=models.Index(
                fields=["disease_code", "location", "-date_recorded"],
                name="surv_hd_disease_loc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="healthdata",
            index=models.Index(
                fields=["severity", "-date_recorded"],
                name="surv_hd_severity_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="healthdata",
            index=models.Index(
                fields=["outcome", "-date_recorded"],
                name="surv_hd_outcome_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="healthdata",
            index=models.Index(
                fields=["patient_id"],
                name="surv_hd_patient_idx",
            ),
        ),
        # ── AnomalyDetection ─────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="anomalydetection",
            index=models.Index(
                fields=["is_deleted", "is_verified", "is_false_positive", "-detected_at"],
                name="surv_anomaly_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="anomalydetection",
            index=models.Index(
                fields=["severity", "-detected_at"],
                name="surv_anomaly_severity_idx",
            ),
        ),
    ]
