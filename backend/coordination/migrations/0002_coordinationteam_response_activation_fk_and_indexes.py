import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coordination', '0001_initial'),
        ('response', '0001_initial'),
    ]

    operations = [
        # Replace raw UUIDField with a proper FK to ResponseActivation
        migrations.RemoveField(
            model_name='coordinationteam',
            name='response_activation_id',
        ),
        migrations.AddField(
            model_name='coordinationteam',
            name='response_activation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='coordination_teams',
                to='response.responseactivation',
            ),
        ),

        # ── Agency indexes ────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='agency',
            index=models.Index(fields=['agency_type', 'is_active'], name='coord_agency_type_active_idx'),
        ),
        migrations.AddIndex(
            model_name='agency',
            index=models.Index(fields=['is_active', 'name'], name='coord_agency_active_name_idx'),
        ),

        # ── CoordinationTeam indexes ──────────────────────────────────────────
        migrations.AddIndex(
            model_name='coordinationteam',
            index=models.Index(fields=['is_active', '-activated_at'], name='coord_team_active_at_idx'),
        ),
        migrations.AddIndex(
            model_name='coordinationteam',
            index=models.Index(fields=['team_type', 'is_active'], name='coord_team_type_active_idx'),
        ),
        migrations.AddIndex(
            model_name='coordinationteam',
            index=models.Index(fields=['response_activation'], name='coord_team_activation_idx'),
        ),

        # ── TeamMembership indexes ────────────────────────────────────────────
        migrations.AddIndex(
            model_name='teammembership',
            index=models.Index(fields=['team', 'is_active'], name='coord_membership_team_idx'),
        ),
        migrations.AddIndex(
            model_name='teammembership',
            index=models.Index(fields=['agency', 'is_active'], name='coord_membership_agency_idx'),
        ),

        # ── Task indexes ──────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['coordination_team', 'status'], name='coord_task_team_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['assigned_to_agency', 'status'], name='coord_task_agency_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['assigned_to_user', 'status'], name='coord_task_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['priority', 'status'], name='coord_task_priority_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['due_date', 'status'], name='coord_task_due_status_idx'),
        ),

        # ── Meeting indexes ───────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='meeting',
            index=models.Index(fields=['coordination_team', '-scheduled_start'], name='coord_meeting_team_start_idx'),
        ),
        migrations.AddIndex(
            model_name='meeting',
            index=models.Index(fields=['status', '-scheduled_start'], name='coord_meeting_status_start_idx'),
        ),
        migrations.AddIndex(
            model_name='meeting',
            index=models.Index(fields=['meeting_type', 'status'], name='coord_meeting_type_status_idx'),
        ),

        # ── MeetingAttendance indexes ─────────────────────────────────────────
        migrations.AddIndex(
            model_name='meetingattendance',
            index=models.Index(fields=['meeting', 'status'], name='coord_attendance_meeting_idx'),
        ),
        migrations.AddIndex(
            model_name='meetingattendance',
            index=models.Index(fields=['attendee', 'status'], name='coord_attendance_attendee_idx'),
        ),

        # ── CommunicationChannel indexes ──────────────────────────────────────
        migrations.AddIndex(
            model_name='communicationchannel',
            index=models.Index(fields=['coordination_team', 'is_active'], name='coord_channel_team_active_idx'),
        ),
        migrations.AddIndex(
            model_name='communicationchannel',
            index=models.Index(fields=['channel_type', 'is_active'], name='coord_channel_type_active_idx'),
        ),

        # ── InformationProduct indexes ────────────────────────────────────────
        migrations.AddIndex(
            model_name='informationproduct',
            index=models.Index(fields=['coordination_team', '-effective_date'], name='coord_product_team_date_idx'),
        ),
        migrations.AddIndex(
            model_name='informationproduct',
            index=models.Index(fields=['product_type', 'is_current'], name='coord_product_type_current_idx'),
        ),
        migrations.AddIndex(
            model_name='informationproduct',
            index=models.Index(fields=['is_public', '-effective_date'], name='coord_product_public_date_idx'),
        ),
    ]
