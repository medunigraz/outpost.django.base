import os

from appconf import AppConf
from django.conf import settings


class BaseAppConf(AppConf):
    PASSWORD_STRENGTH_BLOOM_FILE = os.path.join(
        settings.MEDIA_ROOT,
        'passwords.flor'
    )
    PASSWORD_STRENGTH_CACHE_TIMEOUT = 3600
    PASSWORD_STRENGTH_CACHE_SLEEP = 0.1

    class Meta:
        prefix = 'base'
