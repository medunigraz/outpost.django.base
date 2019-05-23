import json
import logging
from datetime import (
    datetime,
    timedelta,
)

from celery.task import (
    PeriodicTask,
    Task,
)
from celery_haystack.tasks import (
    CeleryHaystackSignalHandler,
    CeleryHaystackUpdateIndex,
)
from django.apps import apps
from django.core.cache import cache
from django.utils import timezone
from guardian.utils import clean_orphan_obj_perms

from .models import NetworkedDeviceMixin
from .signals import materialized_view_refreshed
from .utils import MaterializedView

logger = logging.getLogger(__name__)


class MaintainanceTaskMixin:
    options = {
        'queue': 'maintainance'
    }
    queue = 'maintainance'


class RefreshMaterializedViewTask(MaintainanceTaskMixin, Task):

    def run(self, name, **kwargs):
        from django.db import (
            transaction
        )
        logger.debug(f'Refresh materialized view: {name}')
        mv = MaterializedView(name)
        models = apps.get_models()
        model = next((m for m in models if m._meta.db_table == name), None)
        interval = None
        if model:
            refresh = getattr(model, 'Refresh', None)
            if refresh:
                interval = getattr(refresh, 'interval', None)
        else:
            logger.warn(f'Could not find model: {name}')
        with transaction.atomic():
            comment = mv.comment
            try:
                md = json.loads(comment)
                last = md.get('last', None)
                if interval and last:
                    due = timezone.now() - timedelta(seconds=interval)
                    now = timezone.now()
                    if due < datetime.fromtimestamp(last, tz=now.tzinfo):
                        logger.debug(f'View is not due for refresh: {name}')
                        return
            except (json.decoder.JSONDecodeError, TypeError) as e:
                logger.warn(f'Failed to parse {name} comment: {e}')
                md = None
            if not mv.refresh():
                return
            if comment is None:
                md = dict()
            if md:
                md['last'] = timezone.now().timestamp()
                mv.comment = json.dumps(md)
            materialized_view_refreshed.send(
                sender=self.__class__,
                name=name,
                model=model
            )
            logger.info(f'Refreshed materialized view: {name}')


class RefreshMaterializedViewDispatcherTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(minutes=10)
    views = '''
    SELECT oid::regclass::text FROM pg_class WHERE relkind = 'm';
    '''

    def run(self, **kwargs):
        from django.db import connection
        logger.debug('Dispatching materialized view refresh tasks.')
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
        with cache.lock('haystack-writer'):
            super().run(action, identifier, **kwargs)


class UpdateHaystackTask(PeriodicTask):
    run_every = timedelta(hours=2)
    options = {
        'queue': 'haystack'
    }
    queue = 'haystack'

    def run(self):
        with cache.lock('haystack-writer'):
            CeleryHaystackUpdateIndex().run(remove=True)


class CleanUpPermsTask(MaintainanceTaskMixin, PeriodicTask):
    run_every = timedelta(hours=1)

    def run(self):
        clean_orphan_obj_perms()
