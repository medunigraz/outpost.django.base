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

# from rest_hooks.models import Hook

from . import (
    models,
    serializers,
)
from .conf import settings


class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContentType.objects.all()
    serializer_class = serializers.ContentTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("app_label", "model")


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = models.Notification.objects.all()
    serializer_class = serializers.NotificationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("object_id", "content_type")

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return super().get_queryset().filter(user=self.request.user)
        return super().get_queryset().none()


class TaskViewSet(
    generics.ListAPIView, generics.RetrieveAPIView, viewsets.GenericViewSet
):
    serializer_class = serializers.TaskSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        return list()

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        if lookup_url_kwarg not in self.kwargs:
            raise Exception(
                f"Expected view {self.__class__.__name__} to be called with a "
                f'URL keyword argument named "{lookup_url_kwarg}". Fix your '
                "URL conf, or set the `.lookup_field` attribute on the view "
                "correctly."
            )

        task = self.kwargs[lookup_url_kwarg]
        return AsyncResult(task)


# class HookViewSet(viewsets.ModelViewSet):
#    """
#    Retrieve, create, update or destroy webhooks.
#    """
#
#    queryset = Hook.objects.all()
#    model = Hook
#    serializer_class = serializers.HookSerializer
#
#    def perform_create(self, serializer):
#        serializer.save(user=self.request.user)


class LanguageViewSet(viewsets.ModelViewSet):
    queryset = models.Language.objects.all()
    serializer_class = serializers.LanguageSerializer
    permission_classes = (permissions.DjangoModelPermissionsOrAnonReadOnly,)
    filterset_fields = ("name", "part3", "part2b", "part2t", "part1")
