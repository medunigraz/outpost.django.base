import logging
import subprocess

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _
from PIL import (
    Image,
    ImageColor,
    ImageOps,
)

from .utils import Uuid4Upload

logger = logging.getLogger(__name__)


class RelatedManager(models.Manager):

    def __init__(self, select=None, prefetch=None):
        super().__init__()
        self._select_related = select
        self._prefetch_related = prefetch

    def get_queryset(self):
        qs = super().get_queryset()
        if self._select_related:
            qs = qs.select_related(
                *self._select_related
            )
        if self._prefetch_related:
            qs = qs.prefetch_related(
                *self._prefetch_related
            )
        return qs


class NetworkedDeviceMixin(models.Model):
    hostname = models.CharField(max_length=128, blank=False, null=False)
    enabled = models.BooleanField(default=True)
    online = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def update(self):
        logger.debug('{s} starting ping: {s.online}'.format(s=self))
        proc = subprocess.run(
            [
                'ping',
                '-c1',
                '-w2',
                self.hostname
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL

        )
        online = (proc.returncode == 0)
        if self.online != online:
            self.online = online
            logger.debug('{s} online: {s.online}'.format(s=self))
            self.save()


class Icon(models.Model):
    name = models.CharField(
        max_length=128
    )
    image = models.FileField(
        upload_to=Uuid4Upload
    )

    class Meta:
        verbose_name = _('Icon')

    def __str__(self):
        return self.name

    def colorize(self, color):
        image = Image.open(self.image.path)
        saturation = image.convert('L')
        result = ImageOps.colorize(
            saturation,
            ImageColor.getrgb('#{0}'.format(color)),
            (255, 255, 255)
        )
        result = result.convert('RGBA')
        result.putalpha(image.split()[3])
        return result


class License(models.Model):
    name = models.CharField(max_length=128)
    text = models.TextField()

    class Meta:
        verbose_name = _('License')

    def __str__(self):
        return self.name


class ReplaceableEntity(models.Model):
    name = models.CharField(max_length=16, primary_key=True)
    character = models.CharField(max_length=1)

    class Meta:
        verbose_name = _('Replaceable entity')

    def __str__(self):
        return self.name


class Notification(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.CharField(max_length=36)
    content_object = GenericForeignKey(
        'content_type',
        'object_id'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL
    )

    class Meta:
        verbose_name = _('Notification')
