import os
from datetime import timedelta

from appconf import AppConf
from django.conf import settings


class BaseAppConf(AppConf):
    NCONVERT = "/usr/local/bin/nconvert"
    MATERIALIZED_VIEW_REFRESH_INTERVAL = timedelta(hours=1)
    MATERIALIZED_VIEW_TASK_DEADLINE = timedelta(minutes=30)
    WEBPAGE_PREVIEW_LIFETIME = 86400
    WEBPAGE_PREVIEW_WIDTH = 1920
    WEBPAGE_PREVIEW_HEIGHT = 1080
    AWS_ACCESS_KEY = None
    AWS_SECRET_ACCESS_KEY = None
    AWS_REGION_NAME = None
    NAVIGATION_ORDER = []

    class Meta:
        prefix = "base"
