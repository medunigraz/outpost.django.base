import json
import logging
from datetime import datetime, timedelta

from celery.task import PeriodicTask, Task
from celery_haystack.tasks import CeleryHaystackSignalHandler, CeleryHaystackUpdateIndex
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from guardian.utils import clean_orphan_obj_perms

from .models import NetworkedDeviceMixin, MaterializedView
from .signals import materialized_view_refreshed

logger = logging.getLogger(__name__)


class MaintainanceTaskMixin:
    options = {"queue": "maintainance"}
    queue = "maintainance"


class RefreshMaterializedViewTask(MaintainanceTaskMixin, Task):
    def run(self, name, force=False, **kwargs):

        logger.debug(f"Refresh materialized view: {name}")
        models = apps.get_models()
        model = next((m for m in models if m._meta.db_table == name), None)
        interval = None
        if model:
            refresh = getattr(model, "Refresh", None)
            if refresh:
                interval = getattr(refresh, "interval", None)
        else:
            logger.warn(f"Could not find model: {name}")
        with transaction.atomic():
            mv, created = MaterializedView.objects.get_or_create(name=name)
            now = timezone.now()
            if created:
                logger.info(f"Created entry for materialized view {name}")
            else:
                if interval:
                    due = now - timedelta(seconds=interval)
                    if due < mv.updated:
                        if not force:
                            logger.debug(f"View is not due for refresh: {name}")
                            return
                        else:
                            logger.info(f"Force refreshing view: {name}")
            if not mv.refresh():
                logger.warn(f"Materialized view {name} failed to refresh.")
                return
            mv.updated = now
            mv.save()
        materialized_view_refreshed.send(sender=self.__class__, name=name, model=model)
        logger.info(f"Refreshed materialized view: {name}")


class RefreshMaterializedViewDispatcherTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(minutes=10)
    views = """
    SELECT oid::regclass::text FROM pg_class WHERE relkind = 'm';
    """

    def run(self, **kwargs):
        from django.db import connection

        logger.debug("Dispatching materialized view refresh tasks.")
        with connection.cursor() as relations:
            relations.execute(self.views)
            for (rel,) in relations:
                RefreshMaterializedViewTask().delay(rel)
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


class UpdateHaystackTask(PeriodicTask):
    run_every = timedelta(hours=2)
    options = {"queue": "haystack"}
    queue = "haystack"

    def run(self):
        with cache.lock("haystack-writer"):
            CeleryHaystackUpdateIndex().run(remove=True)


class CleanUpPermsTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(hours=1)

    def run(self):
        clean_orphan_obj_perms()
