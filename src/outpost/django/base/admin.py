from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.translation import gettext_lazy as _

from . import models


admin.site.site_header = _("MUG API Administration")
admin.site.index_title = _("Welcome to MUG API Administration")
admin.site.site_title = _("MUG API Administration")


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
    actions = ['reset_tasks']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def reset_tasks(self, request, queryset):
        rows_updated = queryset.update(task=None)
        if rows_updated == 1:
            message_bit = _("1 task was")
        else:
            message_bit = _("%s stories were") % rows_updated
        self.message_user(request, _("%s successfully marked as published.") % message_bit)
        for mv in queryset:
            mv.task = None

    reset_tasks.short_description = _("Reset tasks for selected materialized views")
