from django_filters.rest_framework import DjangoFilterBackend


class SimpleDjangoFilterBackend(DjangoFilterBackend):
    def to_html(self, request, queryset, view):
        return None
