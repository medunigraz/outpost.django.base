# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-17 13:17
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("base", "0007_auto_20171113_1626")]

    operations = [
        migrations.AlterModelOptions(name="icon", options={"verbose_name": "Icon"}),
        migrations.AlterModelOptions(
            name="license", options={"verbose_name": "License"}
        ),
        migrations.AlterModelOptions(
            name="notification", options={"verbose_name": "Notification"}
        ),
        migrations.AlterModelOptions(
            name="replaceableentity", options={"verbose_name": "Replaceable entity"}
        ),
    ]
