import logging
from functools import cached_property

import icmplib
from celery.result import AsyncResult
from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import (
    IntegrityError,
    ProgrammingError,
    connection,
    models,
)
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from PIL import (
    Image,
    ImageColor,
    ImageOps,
)
from sqlalchemy.exc import DBAPIError

from .conf import settings
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
            qs = qs.select_related(*self._select_related)
        if self._prefetch_related:
            qs = qs.prefetch_related(*self._prefetch_related)
        return qs


class NetworkedDeviceMixin(models.Model):
    hostname = models.CharField(max_length=128, blank=False, null=False)
    enabled = models.BooleanField(default=True)
    online = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def update(self):
        logger.debug("{s} starting ping: {s.online}".format(s=self))
        try:
            online = icmplib.ping(
                self.hostname,
                count=settings.BASE_NETWORKED_DEVICE_PING_COUNT,
                interval=settings.BASE_NETWORKED_DEVICE_PING_INTERVAL,
                timeout=settings.BASE_NETWORKED_DEVICE_PING_TIMEOUT,
                privileged=False,
            ).is_alive
        except icmplib.ICMPLibError:
            logger.warn(
                f"Unable to determine online status for {self.hostname}, assuming offline"
            )
            online = False
        if self.online != online:
            self.online = online
            logger.debug("{s} online: {s.online}".format(s=self))
            self.save()


class Icon(models.Model):
    name = models.CharField(max_length=128)
    image = models.FileField(upload_to=Uuid4Upload)

    class Meta:
        verbose_name = _("Icon")

    def __str__(self):
        return self.name

    def colorize(self, color):
        image = Image.open(self.image.path)
        saturation = image.convert("L")
        result = ImageOps.colorize(
            saturation, ImageColor.getrgb("#{0}".format(color)), (255, 255, 255)
        )
        result = result.convert("RGBA")
        result.putalpha(image.split()[3])
        return result


class License(models.Model):
    name = models.CharField(max_length=128)
    text = models.TextField()

    class Meta:
        verbose_name = _("License")

    def __str__(self):
        return self.name


class ReplaceableEntity(models.Model):
    name = models.CharField(max_length=16, primary_key=True)
    character = models.CharField(max_length=1)

    class Meta:
        verbose_name = _("Replaceable entity")

    def __str__(self):
        return self.name


class Notification(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36)
    content_object = GenericForeignKey("content_type", "object_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Notification")


class MaterializedView(models.Model):
    name = models.CharField(max_length=256)
    updated = models.DateTimeField(null=True)
    interval = models.DurationField(
        default=settings.BASE_MATERIALIZED_VIEW_REFRESH_INTERVAL
    )
    task = models.UUIDField(blank=True, null=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def refresh(self):

        query_default = f"""
        REFRESH MATERIALIZED VIEW {self.name};
        """
        query_concurrent = f"""
        REFRESH MATERIALIZED VIEW CONCURRENTLY {self.name};
        """
        try:
            with connection.cursor() as cursor:
                if self.has_unique_indizes():
                    logger.debug(f"Concurrent refresh: {self.name}")
                    cursor.execute(query_concurrent)
                else:
                    logger.debug(f"Refresh: {self.name}")
                    cursor.execute(query_default)
        except (IntegrityError, ProgrammingError) as e:
            logger.error(e)
            return False
        return True

    def has_unique_indizes(self):
        query = f"""
        SELECT
            COUNT(1) AS count
        FROM
            pg_indexes
        WHERE
            tablename = '{self.name}' AND
            indexdef LIKE 'CREATE UNIQUE INDEX %'
        """  #  nosec B608
        with connection.cursor() as cursor:
            cursor.execute(query)
            (index,) = cursor.fetchone()
            logger.debug(f"View {self.name} has {index} unique inidzes")
            return index > 0

    @property
    def task_state(self):
        if not self.task:
            return None
        task = AsyncResult(str(self.task))
        return task.state

    @cached_property
    def model(self):
        models = apps.get_models()
        return next((m for m in models if m._meta.db_table == self.name), None)


class Language(models.Model):
    name = models.CharField(max_length=512)
    part3 = models.CharField(max_length=3)
    part2b = models.CharField(max_length=3, blank=True, null=True)
    part2t = models.CharField(max_length=3, blank=True, null=True)
    part1 = models.CharField(max_length=2, blank=True, null=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["part3"]),
            models.Index(fields=["part2b"]),
            models.Index(fields=["part2t"]),
            models.Index(fields=["part1"]),
        ]

    def __str__(self):
        return str(self.name)
