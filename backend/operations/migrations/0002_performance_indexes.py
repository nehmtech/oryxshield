"""
Performance indexes for operations models.

Adds:
- Contact.is_quarantined index (heavily filtered, was missing)
- Compound (status, exposure_date) for monitoring period queries
- Compound (location, disease_code, status) for regional case queries
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["is_quarantined", "-created_at"],
                name="ops_contact_quarantine_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["status", "exposure_date"],
                name="ops_contact_status_exposure_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="case",
            index=models.Index(
                fields=["location", "disease_code", "status"],
                name="ops_case_loc_disease_status_idx",
            ),
        ),
    ]
