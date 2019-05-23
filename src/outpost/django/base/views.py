import hashlib
import io
import os
import subprocess
from tempfile import mkstemp

from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    TemplateView,
    View,
)
from PIL import Image as PILImage
from pudb import set_trace
from wand.image import Image

from . import models


class IndexView(TemplateView):
    template_name = 'outpost/index.html'


class ColorizedIconView(View):

    def get(self, request, pk, color):
        icon = get_object_or_404(models.Icon, pk=pk)
        response = HttpResponse(content_type='image/png')
        image = icon.colorize(color)
        image.save(response, 'PNG')
        return response


class TaskView(View):

    def get(self, request, task):
        result = AsyncResult(task)
        return JsonResponse(
            {
                'state': result.state,
                'info': result.info
            }
        )


@method_decorator(csrf_exempt, name='dispatch')
class ImageConvertView(TemplateView):
    template_name = 'outpost/image-convert.html'

    def post(self, request, format):
        if not format:
            format = 'PDF'
        digest = hashlib.sha1()
        digest.update(request.body)
        ckey = f'base-image-convert-{digest.hexdigest()}-{format}'
        response = cache.get(ckey, None)
        if response:
            return response
        response = HttpResponse()
        filein = io.BytesIO(request.body)
        img = PILImage.open(filein)
        # Ugly kludge because OpenText fucks up TIFF/JPEG inlines.
        if img.format == 'TIFF':
            nconvert = settings.OUTPOST.get('nconvert')
            if os.path.isfile(nconvert) and os.access(nconvert, os.X_OK):
                inp_fd, inp = mkstemp()
                outp_fd, outp = mkstemp()
                # We do not need the filehandle for the resulting new TIFF file at
                # this point
                os.close(outp_fd)
                filein.seek(0)
                os.write(inp_fd, request.read())
                os.close(inp_fd)
                args = [
                    nconvert,
                    '-quiet',
                    '-multi',
                    '-o',
                    outp,
                    '-out',
                    'tiff',
                    '-in',
                    'tiff',
                    '-c',
                    '8',
                    '-no_auto_ext',
                    '-overwrite',
                    inp
                ]
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL
                )
                proc.wait()
                with open(outp, 'rb') as outp_fh:
                    filein = io.BytesIO(outp_fh.read())
                os.remove(inp)
                os.remove(outp)

        filein.seek(0)
        with Image(file=filein) as img:
            img.format = format.upper()
            img.save(response)
            response['Content-Type'] = img.mimetype
        cache.set(ckey, response, 86400)
        return response


class ErrorView(TemplateView):

    def get_template_names(self):
        code = self.kwargs.get('code', 500)
        return [f'outpost/error/{code}.html', 'outpost/error.html']


class DebuggerView(View):

    def dispatch(self, request, *args, **kwargs):
        if settings.DEBUG:
            set_trace()
        return HttpResponse()
