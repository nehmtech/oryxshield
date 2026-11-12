from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('response', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='responseactivation',
            name='expires_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Hard expiry — activation auto-closes after this datetime.',
            ),
        ),
    ]
