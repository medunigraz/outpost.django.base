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
    search_fields = ("name",)


@admin.register(models.ReplaceableEntity)
class ReplaceableAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(models.MaterializedView)
class MaterializedViewAdmin(admin.ModelAdmin):
    search_fields = ("name", "task")
    list_display = ("name", "updated", "task", "task_state", "interval")
    readonly_fields = ("name", "task", "updated")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
