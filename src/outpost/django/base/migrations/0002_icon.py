# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-07 10:07
from __future__ import unicode_literals

from django.db import migrations, models
from ..utils import Uuid4Upload


class Migration(migrations.Migration):

    initial = True

    dependencies = [("base", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Icon",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("image", models.FileField(upload_to=Uuid4Upload)),
            ],
        )
    ]
