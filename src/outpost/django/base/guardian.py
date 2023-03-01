from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from guardian.ctypes import get_content_type
from guardian.models import (
    GroupObjectPermission,
    UserObjectPermission,
)
from guardian.shortcuts import (
    assign_perm,
    get_objects_for_user,
)


class GuardedModelAdminFilterMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        permission = f"{qs.model._meta.app_label}.view_{qs.model._meta.model_name}"
        return get_objects_for_user(
            request.user, permission, qs, accept_global_perms=True
        )


class GuardedModelAdminObjectMixin:
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ct = get_content_type(obj)
        if not change:
            for n in ("view", "change", "delete"):
                assign_perm(f"{ct.app_label}.{n}_{ct.model}", request.user, obj)

    def has_view_permission(self, request, obj=None):
        if obj is None:
            if super().has_view_permission(request, obj):
                return True
            ct = get_content_type(self.model)
            for n in ("view", "change"):
                p = Permission.objects.get(content_type=ct, codename=f"{n}_{ct.model}")
                if UserObjectPermission.objects.filter(
                    user=request.user, content_type=ct, permission=p
                ).exists():
                    return True
                if GroupObjectPermission.objects.filter(
                    group__in=request.user.groups.all(), content_type=ct, permission=p
                ).exists():
                    return True
            return False
        ct = get_content_type(obj)
        view = f"{ct.app_label}.view_{ct.model}"
        change = f"{ct.app_label}.change_{ct.model}"
        return request.user.has_perm(view, obj) or request.user.has_perm(change, obj)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        ct = get_content_type(obj)
        permission = f"{ct.app_label}.change_{ct.model}"
        return request.user.has_perm(permission, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        ct = get_content_type(obj)
        permission = f"{ct.app_label}.delete_{ct.model}"
        return request.user.has_perm(permission, obj)
