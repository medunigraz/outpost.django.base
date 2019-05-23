import time
from hashlib import sha1

from celery.result import AsyncResult
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils.translation import gettext as _
from flor import BloomFilter
from rest_framework import (
    generics,
    permissions,
    viewsets,
)
from rest_framework.response import Response
from rest_hooks.models import Hook
from zxcvbn import zxcvbn

from . import (
    models,
    serializers,
)
from .conf import settings


class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContentType.objects.all()
    serializer_class = serializers.ContentTypeSerializer
    permission_classes = (
        permissions.IsAuthenticated,
    )
    filter_fields = (
        'app_label',
        'model',
    )


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = models.Notification.objects.all()
    serializer_class = serializers.NotificationSerializer
    permission_classes = (
        permissions.IsAuthenticated,
    )
    filter_fields = (
        'object_id',
        'content_type',
    )

    def get_queryset(self):
        if (self.request.user.is_authenticated()):
            return super().get_queryset().filter(user=self.request.user)
        return super().get_queryset().none()


class TaskViewSet(generics.ListAPIView, generics.RetrieveAPIView, viewsets.GenericViewSet):
    serializer_class = serializers.TaskSerializer
    permission_classes = (
        permissions.IsAuthenticatedOrReadOnly,
    )

    def get_queryset(self):
        return list()

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )

        task = self.kwargs[lookup_url_kwarg]
        return AsyncResult(task)


class HookViewSet(viewsets.ModelViewSet):
    '''
    Retrieve, create, update or destroy webhooks.
    '''
    queryset = Hook.objects.all()
    model = Hook
    serializer_class = serializers.HookSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PasswordStrengthViewSet(viewsets.ViewSet):
    '''
    Test passwords against a wide range of criterias to prevent them being
    easily guessable.
    '''
    permission_classes = (
        permissions.AllowAny,
    )

    def create(self, request):
        '''
        Test password in request:

            {
                "password":"easy_to_guess"
            }

        Test password and use additional words to be blacklisted (e.g.
        username, first or family name, ...):

            {
                "password":"easy_to_guess",
                "blacklist": [
                    "john",
                    "doe",
                    "j.doe"
                ]
            }
        '''
        raw = request.data.get('password', None)
        if not raw:
            return Response()
        hashed = sha1(raw.encode('utf-8')).hexdigest().upper().encode('ascii')
        key = f'base-password-strength-{hashed}'
        cached = cache.get(key, None)
        if cached:
            time.sleep(settings.BASE_PASSWORD_STRENGTH_CACHE_SLEEP)
            return Response(cached)
        bf = BloomFilter()
        with open(settings.BASE_PASSWORD_STRENGTH_BLOOM_FILE, 'rb') as inp:
            bf.read(inp)
        checked = zxcvbn(raw)
        suggestions = [_(msg) for msg in checked['feedback']['suggestions']]
        result = {
            'leaked': hashed in bf,
            'score': checked['score'],
            'guesses': checked['guesses'],
            'crack_time': checked['crack_times_display']['offline_slow_hashing_1e4_per_second'],
            'feedback': {
                'warning': _(checked['feedback']['warning']),
                'suggestions': suggestions,
            }
        }
        cache.set(
            key,
            result,
            timeout=settings.BASE_PASSWORD_STRENGTH_CACHE_TIMEOUT
        )
        return Response(result)
