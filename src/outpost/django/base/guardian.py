from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import (
    Group,
    Permission,
)
from django.contrib.contenttypes.models import ContentType
from guardian.admin import GuardedModelAdminMixin as BaseGuardedModelAdminMixin
from guardian.ctypes import get_content_type
from guardian.models import (
    GroupObjectPermission,
    UserObjectPermission,
)
from guardian.shortcuts import (
    assign_perm,
    get_objects_for_user,
)
from polymorphic.utils import get_base_polymorphic_model


class UserPermissionManageForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.all())


class GroupPermissionManageForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all())


class GuardedModelAdminMixin(BaseGuardedModelAdminMixin):
    def get_obj_perms_user_select_form(self, request):
        return UserPermissionManageForm

    def get_obj_perms_group_select_form(self, request):
        return GroupPermissionManageForm


class GuardedModelAdminFilterMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ct = get_content_type(qs.model)
        permission = f"{ct.app_label}.view_{ct.model}"
        base = get_base_polymorphic_model(qs.model)
        if base:
            base_qs = base.objects.instance_of(self.base_model).non_polymorphic()
            user_qs = get_objects_for_user(
                request.user, permission, base_qs, accept_global_perms=True
            )
            return qs.filter(pk__in=user_qs)
        return get_objects_for_user(
            request.user, permission, qs, accept_global_perms=True
        )


class GuardedModelAdminSaveMixin:

    object_permissions = list()
    related_object_permissions = dict()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ct = get_content_type(obj)
        for n in self.object_permissions:
            perm = f"{ct.app_label}.{n}_{ct.model}"
            if request.user.has_perm(perm, obj):
                continue
            assign_perm(f"{ct.app_label}.{n}_{ct.model}", request.user, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        for fs in formsets:
            ct = get_content_type(fs.model)
            base = get_base_polymorphic_model(fs.model) or fs.model
            for f in fs.forms:
                if not f.instance.pk:
                    continue
                permissions = self.related_object_permissions.get(base)
                if not permissions:
                    continue
                for n in permissions:
                    perm = f"{ct.app_label}.{n}_{ct.model}"
                    if request.user.has_perm(perm, f.instance):
                        continue
                    assign_perm(
                        f"{ct.app_label}.{n}_{ct.model}", request.user, f.instance
                    )


class GuardedModelAdminPermissionMixin:
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
