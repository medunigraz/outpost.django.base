import logging
import subprocess

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, ProgrammingError, connection, models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from PIL import Image, ImageColor, ImageOps
from sqlalchemy.exc import DBAPIError

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
        proc = subprocess.run(
            ["ping", "-c1", "-w2", self.hostname],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        online = proc.returncode == 0
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    class Meta:
        verbose_name = _("Notification")


class MaterializedView(models.Model):
    name = models.CharField(max_length=256)
    updated = models.DateTimeField(null=True)

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
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            (index,) = cursor.fetchone()
            logger.debug(f"View {self.name} has {index} unique inidzes")
            return index > 0

    def has_online_sources(self):
        from ..fdw import OutpostFdw

        query = f"""
        SELECT
            cl_d.relname AS name,
            ns.nspname AS schema,
            ft.ftoptions AS options
        FROM pg_rewrite AS r
        JOIN pg_class AS cl_r ON r.ev_class = cl_r.oid
        JOIN pg_depend AS d ON r.oid = d.objid
        JOIN pg_class AS cl_d ON d.refobjid = cl_d.oid
        JOIN pg_namespace AS ns ON cl_d.relnamespace = ns.oid
        JOIN pg_foreign_table AS ft ON ft.ftrelid = cl_d.oid
        JOIN pg_foreign_server AS fs ON fs.oid = ft.ftserver
        WHERE
            cl_d.relkind = 'f' AND
            cl_r.relname = '{self.name}' AND
            fs.srvname = 'sqlalchemy'
        GROUP BY
            cl_d.relname,
            ns.nspname,
            ft.ftoptions
        ORDER BY
            ns.nspname,
            cl_d.relname;
        """
        logger.debug(f"Is materialized view source online: {self.name}")
        with connection.cursor() as cursor:
            cursor.execute(query)
            for (name, schema, options) in cursor:
                if options:
                    args = dict([o.split("=", 1) for o in options])
                    try:
                        OutpostFdw(args, {}).connection.connect()
                    except DBAPIError as e:
                        logger.warn(e)
                        return False
            return True
