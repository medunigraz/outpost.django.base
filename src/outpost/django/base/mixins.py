from django.contrib.auth import authenticate, login
from rest_framework.utils.mediatypes import media_type_matches, order_by_precedence
from rest_framework.viewsets import ModelViewSet
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from rest_framework_extensions.etag.mixins import ReadOnlyETAGMixin
from reversion.views import RevisionMixin

from . import key_constructors


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
        header = "HTTP_AUTHORIZATION"
        if header in request.META:
            authmeth, auth = request.META.get(header).split(" ", 1)
            if authmeth.lower() == "basic":
                auth = auth.strip().decode("base64")
                username, password = auth.split(":", 1)
                user = authenticate(username=username, password=password)
                if user:
                    login(request, user)
        return super().dispatch(request, *args, **kwargs)


class ReadOnlyETAGCacheMixin(ReadOnlyETAGMixin, CacheResponseMixin):
    object_cache_key_func = key_constructors.DetailKeyConstructor()
    list_cache_key_func = key_constructors.ListKeyConstructor()
    object_etag_func = key_constructors.DetailKeyConstructor()
    list_etag_func = key_constructors.ListKeyConstructor()
