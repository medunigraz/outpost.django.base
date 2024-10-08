import logging
from base64 import b64decode

from django.contrib.auth import (
    authenticate,
    login,
)
from rest_framework.utils.mediatypes import (
    media_type_matches,
    order_by_precedence,
)
from rest_framework.viewsets import ModelViewSet
from rest_framework_extensions.cache.mixins import (
    CacheResponseMixin as BaseCacheResponseMixin,
)
from rest_framework_extensions.etag.mixins import ReadOnlyETAGMixin
from reversion.views import RevisionMixin

from . import key_constructors

logger = logging.getLogger(__name__)


class MediatypeNegotiationMixin(object):
    def get_serializer_class(self):
        classes = getattr(self, "mediatype_serializer_classes", None)
        serializer = None
        if isinstance(classes, dict):
            if self.request.method.lower() not in ("GET", "HEAD", "OPTIONS"):
                serializer = classes.get(self.request.content_type, None)
            else:
                header = self.request.META.get("HTTP_ACCEPT", "*/*")
                tokens = [token.strip() for token in header.split(",")]
                for a in order_by_precedence(tokens):
                    serializer = next(
                        (c for (k, c) in classes if media_type_matches(k, a)), None
                    )
        if serializer:
            return serializer
        return super(MediatypeNegotiationMixin, self).get_serializer_class()


class GeoModelViewSet(MediatypeNegotiationMixin, RevisionMixin, ModelViewSet):
    pass


class HttpBasicAuthMixin(object):
    """
    View mixin which tries to handle HTTP basic authentication.
    NOTE:
        This does not reply with a HTTP 401 error if no Authentication header
        is present in the request.
    """

    def dispatch(self, request, *args, **kwargs):
        header = request.META.get("HTTP_AUTHORIZATION")
        if header:
            try:
                authmeth, auth = header.split(" ", 1)
            except ValueError:
                logger.warning(
                    f"Unable to unpack HTTP basic authentication header: {header}"
                )
            else:
                if authmeth.lower() == "basic":
                    auth = b64decode(auth.strip()).decode("utf-8")
                    username, password = auth.split(":", 1)
                    user = authenticate(username=username, password=password)
                    if user:
                        login(request, user)
        return super().dispatch(request, *args, **kwargs)


class CacheResponseMixin(BaseCacheResponseMixin):
    object_cache_key_func = key_constructors.DetailKeyConstructor()
    list_cache_key_func = key_constructors.ListKeyConstructor()


class ReadOnlyETAGCacheMixin(ReadOnlyETAGMixin, CacheResponseMixin):
    object_etag_func = key_constructors.DetailKeyConstructor()
    list_etag_func = key_constructors.ListKeyConstructor()


class ContextMixin(object):
    extra_context = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.extra_context:
            context.update(self.extra_context)
        return context
