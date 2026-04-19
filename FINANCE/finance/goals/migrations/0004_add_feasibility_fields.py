# Generated migration for adding feasibility fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0003_alter_goal_options_alter_goal_priority_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='goal',
            name='duration_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='goal',
            name='original_deadline',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='goal',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterModelOptions(
            name='goal',
            options={'ordering': ['-priority', 'duration_days', 'deadline']},
        ),
    ]
