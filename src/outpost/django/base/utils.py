import logging
import subprocess
from base64 import urlsafe_b64encode
from functools import partial
from pathlib import PurePosixPath
from uuid import uuid4

from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)


class Uuid4Upload(str):

    def __new__(cls, instance, filename):
        f = PurePosixPath(filename)
        u = urlsafe_b64encode(uuid4().bytes).decode('ascii').rstrip('=')
        p = PurePosixPath(instance.__module__, instance._meta.object_name)
        return str.__new__(cls, p.joinpath(u).with_suffix(f.suffix))


def colorscale(hexstr, scalefactor):
    """
    Scales a hex string by ``scalefactor``. Returns scaled hex string.

    To darken the color, use a float value between 0 and 1.
    To brighten the color, use a float value greater than 1.

    >>> colorscale("DF3C3C", .5)
    6F1E1E
    >>> colorscale("52D24F", 1.6)
    83FF7E
    >>> colorscale("4F75D2", 1)
    4F75D2
    """

    def clamp(val, minimum=0, maximum=255):
        if val < minimum:
            return minimum
        if val > maximum:
            return maximum
        return val

    if scalefactor < 0 or len(hexstr) != 6:
        return hexstr

    r, g, b = int(hexstr[:2], 16), int(hexstr[2:4], 16), int(hexstr[4:], 16)

    r = int(clamp(r * scalefactor))
    g = int(clamp(g * scalefactor))
    b = int(clamp(b * scalefactor))

    return "%02x%02x%02x" % (r, g, b)


class Process():

    def __init__(self, *args, stderr=subprocess.STDOUT):
        self.handlers = []
        logger.debug('Preparing: {}'.format(' '.join(args)))
        self.args = args
        self.cmd = partial(
            subprocess.Popen,
            args,
            stdout=subprocess.PIPE,
            stderr=stderr,
            universal_newlines=True
        )

    def handler(self, h):
        if callable(h):
            self.handlers.append(h)

    def run(self):
        logger.debug(f'Executing: {self.args}')
        pipe = self.cmd()

        while True:
            line = pipe.stdout.readline().strip()

            if line == '' and pipe.poll() is not None:
                break

            logger.debug('Process line: {}'.format(line))
            for h in self.handlers:
                h(line)
        retcode = pipe.returncode
        logger.debug(f'Done: {self.args} returns {retcode}')
        return retcode


class MaterializedView:

    def __init__(self, name):
        from django.db import connection
        self.name = name
        self.connection = connection

    def refresh(self):
        from django.db import (
            IntegrityError,
            ProgrammingError,
        )
        query_default = f'''
        REFRESH MATERIALIZED VIEW {self.name};
        '''
        query_concurrent = f'''
        REFRESH MATERIALIZED VIEW CONCURRENTLY {self.name};
        '''
        try:
            with self.connection.cursor() as cursor:
                if self.has_unique_indizes():
                    logger.debug(f'Concurrent refresh: {self.name}')
                    cursor.execute(query_concurrent)
                else:
                    logger.debug(f'Refresh: {self.name}')
                    cursor.execute(query_default)
        except (IntegrityError, ProgrammingError) as e:
            logger.error(e)
            return False
        return True

    def has_unique_indizes(self):
        query = f'''
        SELECT
            COUNT(1) AS count
        FROM
            pg_indexes
        WHERE
            tablename = '{self.name}' AND
            indexdef LIKE 'CREATE UNIQUE INDEX %'
        '''
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            (index,) = cursor.fetchone()
            logger.debug(f'View {self.name} has {index} unique inidzes')
            return index > 0

    def has_online_sources(self):
        from ..fdw import OutpostFdw
        query = f'''
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
        '''
        logger.debug(f'Is materialized view source online: {self.name}')
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            for (name, schema, options) in cursor:
                if options:
                    args = dict([o.split('=', 1) for o in options])
                    try:
                        OutpostFdw(args, {}).connection.connect()
                    except DBAPIError as e:
                        logger.warn(e)
                        return False
            return True

    @property
    def comment(self):
        query = f'''
        SELECT obj_description('{self.name}'::regclass);
        '''
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            (data,) = cursor.fetchone()
            return data

    @comment.setter
    def comment(self, value):
        query = f'''
        COMMENT ON MATERIALIZED VIEW "{self.name}" IS '{value}';
        '''
        with self.connection.cursor() as cursor:
            cursor.execute(query)
