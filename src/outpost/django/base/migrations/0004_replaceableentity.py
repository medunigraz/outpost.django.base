# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-12 15:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("base", "0003_license")]

    operations = [
        migrations.CreateModel(
            name="ReplaceableEntity",
            fields=[
                (
                    "name",
                    models.CharField(max_length=16, primary_key=True, serialize=False),
                ),
                ("character", models.CharField(max_length=1)),
            ],
        )
    ]
