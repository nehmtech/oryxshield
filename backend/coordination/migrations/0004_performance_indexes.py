"""
Performance indexes for coordination models.

Adds:
- Task.priority index (used in filters, was missing)
- Compound (due_date, status) for overdue-task queries
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coordination", "0003_index_name_sync"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="task",
            index=models.Index(
                fields=["priority", "status"],
                name="coord_task_priority_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(
                fields=["due_date", "status"],
                name="coord_task_due_status_idx",
            ),
        ),
    ]
