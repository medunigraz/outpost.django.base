from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from . import models


class NotificationInlineAdmin(GenericTabularInline):
    model = models.Notification


@admin.register(models.Icon)
class IconAdmin(admin.ModelAdmin):
    pass


@admin.register(models.License)
class LicenseAdmin(admin.ModelAdmin):
    search_fields = (
        'name',
    )


@admin.register(models.ReplaceableEntity)
class ReplaceableAdmin(admin.ModelAdmin):
    search_fields = (
        'name',
    )
