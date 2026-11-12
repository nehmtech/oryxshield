"""
Performance indexes for communications models.

Adds:
- Compound (channel, -created_at) for channel-specific reporting
- Compound (recipient_identifier, status) for failed-message lookups
- Compound (announcement_type, is_published, -publish_date) for feed queries
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["channel", "-created_at"],
                name="comms_msg_channel_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["recipient_identifier", "status"],
                name="comms_msg_recipient_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="publicannouncement",
            index=models.Index(
                fields=["announcement_type", "is_published", "-publish_date"],
                name="comms_ann_type_published_idx",
            ),
        ),
    ]
