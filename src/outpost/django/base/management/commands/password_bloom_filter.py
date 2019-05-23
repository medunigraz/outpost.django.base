import logging
import os

from django.core.management.base import BaseCommand
from flor import BloomFilter
from tqdm import trange

from ...conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate bloom filter for common passwords'

    def add_arguments(self, parser):
        parser.add_argument('input', type=str)
        parser.add_argument('-n', type=int, default=1000000)
        parser.add_argument('-p', type=float, default=0.00001)

    def handle(self, *args, **options):
        bf = BloomFilter(n=options.get('n') * 2, p=options.get('p'))
        with open(options.get('input'), 'r') as inp:
            for i in trange(options.get('n')):
                line = inp.readline()
                if not line:
                    break
                bf.add(line.strip().upper().encode('ascii'))
        filename = settings.BASE_PASSWORD_STRENGTH_BLOOM_FILE
        tmpfile = f'{filename}.tmp'
        logger.info(f'Writing new password bloom filter: {tmpfile}')
        with open(tmpfile, 'wb') as outp:
            bf.write(outp)
        logger.info(f'Replacing old password bloom filter: {filename}')
        os.rename(tmpfile, filename)
