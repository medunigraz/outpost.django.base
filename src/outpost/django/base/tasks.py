import json
import logging
from datetime import (
    datetime,
    timedelta,
)
from hashlib import sha256

from billiard import (
    Pipe,
    Process,
)
from celery import (
    chord,
    shared_task,
)
from celery.result import AsyncResult
from celery.states import (
    PENDING,
    READY_STATES,
)

# from celery_haystack.tasks import CeleryHaystackSignalHandler, CeleryHaystackUpdateIndex
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from guardian.utils import clean_orphan_obj_perms

from .conf import settings
from .models import (
    MaterializedView,
    NetworkedDeviceMixin,
)
from .signals import materialized_view_refreshed
from .utils import WebEngineScreenshot

logger = logging.getLogger(__name__)


class MaintainanceTaskMixin:
    options = {"queue": "maintainance"}
    queue = "maintainance"


class MaterializedViewTasks:

    view_query = """
    SELECT oid::regclass::text FROM pg_class WHERE relkind = 'm';
    """

    @shared_task(
        bind=True, ignore_result=True, name=f"{__name__}.MaterializedView:dispatch"
    )
    def dispatch(task, force=False):
        from django.db import connection

        queue = task.request.delivery_info.get("routing_key")

        models = apps.get_models()
        now = timezone.now()
        deadline = settings.BASE_MATERIALIZED_VIEW_TASK_DEADLINE
        logger.debug("Dispatching materialized view refresh tasks.")
        with connection.cursor() as relations:
            relations.execute(MaterializedViewTasks.view_query)
            tasks = list()
            for (rel,) in relations:
                model = next((m for m in models if m._meta.db_table == rel), None)
                interval = settings.BASE_MATERIALIZED_VIEW_REFRESH_INTERVAL
                if model:
                    refresh = getattr(model, "Refresh", None)
                    if refresh:
                        interval = getattr(refresh, "interval", None)
                else:
                    logger.warn(f"Could not find model for: {rel}")
                if not isinstance(interval, timedelta):
                    interval = timedelta(seconds=interval)
                mv, created = MaterializedView.objects.get_or_create(
                    name=rel, defaults={"interval": interval}
                )
                if created:
                    logger.info(f"Created entry for materialized view {rel}")
                if not force:
                    if mv.updated:
                        due = mv.updated + mv.interval
                        if due > now:
                            logger.debug(f"View is not due for refresh: {rel}")
                            continue

                        if mv.task:
                            # There is a task registered, check what state it
                            # is in.
                            state = AsyncResult(str(mv.task)).state
                            if state == PENDING and due + deadline > timezone.now():
                                # Task is still waiting for execution is is not
                                # beyond it's deadline extension.
                                logger.debug(f"Refresh task is still pending: {rel}")
                                continue
                task = MaterializedViewTasks.refresh.signature(
                    (mv.pk,), immutable=True, queue=queue
                )
                mv.task = task.freeze().id
                mv.save()
                tasks.append(task)
            transaction.on_commit(
                lambda: chord(tasks)(MaterializedViewTasks.result.s())
            )
        connection.close()

    @shared_task(
        bind=True, ignore_result=False, name=f"{__name__}.MaterializedView:refresh"
    )
    def refresh(task, pk):
        mv = MaterializedView.objects.get(pk=pk)
        logger.debug(f"Refresh materialized view: {mv}")
        with transaction.atomic():
            if not mv.refresh():
                logger.warn(f"Materialized view {mv} failed to refresh.")
                return None
            mv.updated = timezone.now()
            mv.save()
        models = apps.get_models()
        model = next((m for m in models if m._meta.db_table == mv.name), None)
        if not model:
            return None
        materialized_view_refreshed.send(
            sender=MaterializedViewTasks.refresh, name=mv.name, model=model
        )
        logger.info(f"Refreshed materialized view: {mv}")
        return model._meta.label

    @shared_task(
        bind=True, ignore_result=True, name=f"{__name__}.MaterializedView:result"
    )
    def result(task, results):
        with cache.lock("haystack-writer"):
            # CeleryHaystackUpdateIndex().run(filter(bool, results), remove=True)
            pass



class NetworkedDeviceTasks:
    @shared_task(
        bind=True, ignore_result=True, name=f"{__name__}.NetworkedDevice:refresh"
    )
    def refresh(task):
        for cls in NetworkedDeviceMixin.__subclasses__():
            for obj in cls.objects.filter(enabled=True):
                obj.update()


# class LockedCeleryHaystackSignalHandler(CeleryHaystackSignalHandler):
#    def run(self, action, identifier, **kwargs):
#        with cache.lock("haystack-writer"):
#            super().run(action, identifier, **kwargs)


# class UpdateHaystackTask(Task):
#    run_every = timedelta(hours=2)
#    options = {"queue": "haystack"}
#    queue = "haystack"
#
#    def run(self):
#        with cache.lock("haystack-writer"):
#            CeleryHaystackUpdateIndex().run(remove=True)


class GuardianTasks:
    @shared_task(bind=True, ignore_result=True, name=f"{__name__}.Guardian:cleanup")
    def cleanup(task):
        clean_orphan_obj_perms()


class WebpageTasks:
    @shared_task(bind=True, ignore_result=True, name=f"{__name__}.Webpage:sceenshot")
    def screenshot(
        task,
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
        p = Process(target=WebpageTasks.worker, args=(url, width, height, child_conn))
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
