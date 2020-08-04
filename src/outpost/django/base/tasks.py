import json
import logging
from datetime import datetime, timedelta
from hashlib import sha256

from billiard import Pipe, Process
from celery import chord
from celery.result import AsyncResult
from celery.states import READY_STATES
from celery.task import PeriodicTask, Task
from celery_haystack.tasks import CeleryHaystackSignalHandler, CeleryHaystackUpdateIndex
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from guardian.utils import clean_orphan_obj_perms

from .conf import settings
from .models import MaterializedView, NetworkedDeviceMixin
from .signals import materialized_view_refreshed
from .utils import WebEngineScreenshot

logger = logging.getLogger(__name__)


class MaintainanceTaskMixin:
    options = {"queue": "maintainance"}
    queue = "maintainance"


class RefreshMaterializedViewTask(MaintainanceTaskMixin, Task):
    def run(self, pk, force=False, **kwargs):
        mv = MaterializedView.objects.get(pk=pk)
        logger.debug(f"Refresh materialized view: {mv}")
        models = apps.get_models()
        model = next((m for m in models if m._meta.db_table == mv.name), None)
        with transaction.atomic():
            if not mv.refresh():
                logger.warn(f"Materialized view {mv} failed to refresh.")
                return None
            mv.updated = timezone.now()
            mv.save()
        materialized_view_refreshed.send(
            sender=self.__class__, name=mv.name, model=model
        )
        logger.info(f"Refreshed materialized view: {mv}")
        return model._meta.label


class RefreshMaterializedViewResultTask(Task):
    options = {"queue": "haystack"}
    queue = "haystack"

    def run(self, results):
        with cache.lock("haystack-writer"):
            CeleryHaystackUpdateIndex().run(filter(bool, results), remove=True)


class RefreshMaterializedViewDispatcherTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(minutes=5)
    views = """
    SELECT oid::regclass::text FROM pg_class WHERE relkind = 'm';
    """

    def run(self, **kwargs):
        from django.db import connection

        models = apps.get_models()
        logger.debug("Dispatching materialized view refresh tasks.")
        with connection.cursor() as relations:
            relations.execute(self.views)
            tasks = list()
            for (rel,) in relations:
                model = next((m for m in models if m._meta.db_table == rel), None)
                if model:
                    refresh = getattr(model, "Refresh", None)
                    if refresh:
                        interval = getattr(refresh, "interval", None)
                else:
                    logger.warn(f"Could not find model for: {rel}")
                    interval = settings.BASE_MATERIALIZED_VIEW_REFRESH_INTERVAL
                mv, created = MaterializedView.objects.get_or_create(
                    name=rel, defaults={"interval": interval,}
                )
                if created:
                    logger.info(f"Created entry for materialized view {rel}")
                else:
                    if mv.updated + mv.interval > timezone.now():
                        logger.debug(f"View is not due for refresh: {rel}")
                        continue
                if mv.task:
                    if AsyncResult(str(mv.task)).state not in READY_STATES:
                        logger.debug(f"Refresh task is already queued: {rel}")
                        continue
                task = RefreshMaterializedViewTask().si(mv.pk)
                mv.task = task.freeze().id
                mv.save()
                tasks.append(task)
            transaction.on_commit(
                lambda: chord(tasks)(RefreshMaterializedViewResultTask().s())
            )
        connection.close()


class RefreshNetworkedDeviceTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(minutes=2)

    def run(self, **kwargs):
        for cls in NetworkedDeviceMixin.__subclasses__():
            for obj in cls.objects.filter(enabled=True):
                obj.update()


class LockedCeleryHaystackSignalHandler(CeleryHaystackSignalHandler):
    def run(self, action, identifier, **kwargs):
        with cache.lock("haystack-writer"):
            super().run(action, identifier, **kwargs)


# class UpdateHaystackTask(PeriodicTask):
#    run_every = timedelta(hours=2)
#    options = {"queue": "haystack"}
#    queue = "haystack"
#
#    def run(self):
#        with cache.lock("haystack-writer"):
#            CeleryHaystackUpdateIndex().run(remove=True)


class CleanUpPermsTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(hours=1)

    def run(self):
        clean_orphan_obj_perms()


class WebpageScreenshotTask(Task):
    options = {"queue": "webpage"}

    def run(
        self,
        url,
        width=settings.BASE_WEBPAGE_PREVIEW_WIDTH,
        height=settings.BASE_WEBPAGE_PREVIEW_HEIGHT,
        lifetime=settings.BASE_WEBPAGE_PREVIEW_LIFETIME,
    ):
        url_id = sha256()
        url_id.update(url.encode("utf-8"))
        url_id.update(bytes(width))
        url_id.update(bytes(height))
        key = url_id.hexdigest()
        logger.info(f"Screenshot for {url} @ {width}x{height}: {key}")
        if key in cache:
            logger.info(f"Found {key} in cache.")
            return key
        logger.info(f"Locking {key}")
        lock = cache.lock(key)
        lock.acquire()
        logger.info("Starting WebEngineScreenshot app")
        parent_conn, child_conn = Pipe()
        p = Process(target=self.worker, args=(url, width, height, child_conn))
        p.start()
        image = parent_conn.recv()
        p.join()
        if not image:
            logger.info("WebEngineScreenshot app returned nothing")
            return None
        logger.info("Writing WebEngineScreenshot app result to cache")
        cache.set(key, image, timeout=lifetime)
        logger.info("Removing WebEngineScreenshot app singleton")
        return key

    @staticmethod
    def worker(url, width, height, conn):
        app = WebEngineScreenshot(url, width, height)
        conn.send(app.run())
