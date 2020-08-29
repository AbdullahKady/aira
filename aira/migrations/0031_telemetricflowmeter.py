# Generated by Django 2.2.12 on 2020-08-29 01:15

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aira', '0030_applied_irrigation_types'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelemetricFlowmeter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_type', models.CharField(choices=[('LoRA_ARTA', 'LoRA_ARTA')], default='LoRA_ARTA', max_length=30)),
                ('device_id', models.CharField(blank=True, max_length=100, null=True)),
                ('water_percentage', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ('agrifield', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aira.Agrifield')),
            ],
        ),
    ]