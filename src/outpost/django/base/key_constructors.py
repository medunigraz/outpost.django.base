import datetime
import logging

from collections.abc import Iterable

from django.core.cache import cache
from django.utils.encoding import force_text
from rest_framework_extensions.key_constructor import bits, constructors

from .models import MaterializedView

logger = logging.getLogger(__name__)


class UpdatedAtKeyBit(bits.KeyBitBase):
    key = "UpdatedAt:{m.app_label}.{m.model_name}"

    def get_data(self, **kwargs):
        if "view_instance" not in kwargs:
            logger.warning("No view_instance key in kwargs dictionary")
            return None
        model = kwargs["view_instance"].get_queryset().model
        key = self.key.format(m=model._meta)
        value = cache.get(key, None)
        logger.debug(f"Current value for UpdatedAt key {key}: {value}")
        if not value:
            value = datetime.datetime.utcnow()
            logger.debug(f"Setting value for UpdatedAt key {key}: {value}")
            cache.set(key, value=value)
        return force_text(value)

    @classmethod
    def update(cls, instance):
        key = cls.key.format(m=instance._meta)
        value = datetime.datetime.utcnow()
        logger.debug(f"Setting value for UpdatedAt key {key}: {value}")
        cache.set(key, value=value)


class MaterializedViewLastUpdateKeyBit(bits.KeyBitBase):
    def get_data(self, **kwargs):
        if "view_instance" not in kwargs:
            logger.warning("No view_instance key in kwargs dictionary")
            return None
        name = kwargs["view_instance"].get_queryset().model._meta.db_table
        try:
            mv = MaterializedView.objects.exclude(updated=None).get(name=name)
            return force_text(mv.updated)
        except MaterializedView.DoesNotExist:
            pass
        return None


class AuthenticatedKeyBit(bits.KeyBitBase):
    def get_data(self, request, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return "authenticated"
        return "anonymous"


class PermissionKeyBit(bits.KeyBitBase):
    def get_data(self, request, params, **kwargs):
        user = getattr(request, "user", None)
        if user:
            if isinstance(params, str):
                if user.has_perm(params):
                    return params
            if isinstance(params, Iterable):
                perms = [p for p in params if user.has_perm(p)]
                if perms:
                    return ";".join(perms)
        return "anonymous"


class BaseKeyConstructor(constructors.DefaultKeyConstructor):
    updated = MaterializedViewLastUpdateKeyBit()
    user = bits.UserKeyBit()
    format = bits.FormatKeyBit()
    language = bits.LanguageKeyBit()
    unique_view_id = bits.UniqueViewIdKeyBit()
    query_params = bits.QueryParamsKeyBit()


class DetailKeyConstructor(BaseKeyConstructor):
    retrieve_sql_query = bits.RetrieveSqlQueryKeyBit()


class ListKeyConstructor(BaseKeyConstructor):
    list_sql_query = bits.ListSqlQueryKeyBit()
