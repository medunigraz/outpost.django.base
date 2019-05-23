import datetime
import logging

from django.core.cache import cache
from django.utils.encoding import force_text
from rest_framework_extensions.key_constructor.bits import KeyBitBase

logger = logging.getLogger(__name__)


class UpdatedAtKeyBit(KeyBitBase):
    key = 'UpdatedAt:{m.app_label}.{m.model_name}'

    def get_data(self, **kwargs):
        if 'view_instance' not in kwargs:
            logger.warning('No view_instance key in kwargs dictionary')
            return None
        model = kwargs['view_instance'].get_queryset().model
        key = self.key.format(m=model._meta)
        value = cache.get(key, None)
        logger.debug(f'Current value for UpdatedAt key {key}: {value}')
        if not value:
            value = datetime.datetime.utcnow()
            logger.debug(f'Setting value for UpdatedAt key {key}: {value}')
            cache.set(key, value=value)
        return force_text(value)

    @classmethod
    def update(cls, instance):
        key = cls.key.format(m=instance._meta)
        value = datetime.datetime.utcnow()
        logger.debug(f'Setting value for UpdatedAt key {key}: {value}')
        cache.set(key, value=value)


class AuthenticatedKeyBit(KeyBitBase):

    def get_data(self, request, **kwargs):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return 'authenticated'
        return 'anonymous'
