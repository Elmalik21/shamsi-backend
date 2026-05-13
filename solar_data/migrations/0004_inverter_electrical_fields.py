"""
solar_data/migrations/0004_inverter_electrical_fields.py
Add IEC 62109 electrical parameters to Inverter model.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solar_data', '0003_installationcost_inverter_solarpanel_designproject_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inverter',
            name='max_dc_voltage_v',
            field=models.FloatField(
                blank=True, null=True,
                help_text='Maximum DC input voltage (V) — IEC 62109 Vmax'
            ),
        ),
        migrations.AddField(
            model_name='inverter',
            name='mppt_min_v',
            field=models.FloatField(
                blank=True, null=True,
                help_text='MPPT voltage range minimum (V)'
            ),
        ),
        migrations.AddField(
            model_name='inverter',
            name='mppt_max_v',
            field=models.FloatField(
                blank=True, null=True,
                help_text='MPPT voltage range maximum (V)'
            ),
        ),
        migrations.AddField(
            model_name='inverter',
            name='max_dc_current_a',
            field=models.FloatField(
                blank=True, null=True,
                help_text='Maximum DC input current per MPPT string (A)'
            ),
        ),
        migrations.AddField(
            model_name='inverter',
            name='mppt_channels',
            field=models.IntegerField(
                default=1,
                help_text='Number of independent MPPT channels'
            ),
        ),
        migrations.AddField(
            model_name='inverter',
            name='max_strings',
            field=models.IntegerField(
                default=1,
                help_text='Maximum number of PV strings'
            ),
        ),
    ]
