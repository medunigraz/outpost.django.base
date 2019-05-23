from django.conf import settings
from django.conf.urls import url

from . import views

urlpatterns = [
    url(
        r'^image/convert(?:\/(?P<format>[\w\d]+))?$',
        views.ImageConvertView.as_view(),
        name='image-convert'
    ),
    url(
        r'^icon/(?P<pk>[0-9]+)/(?P<color>[0-9a-f]{6})$',
        views.ColorizedIconView.as_view(),
        name='icon'
    ),
    url(
        r'^task/(?P<task>(:?[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}|#))/$',
        views.TaskView.as_view(),
        name='task'
    ),
    url(
        r'^error/(?P<code>\d+)?$',
        views.ErrorView.as_view(),
        name='error'
    ),
    url(
        r'^error/(?P<code>\d+)?$',
        views.ErrorView.as_view(),
        name='error'
    ),
    url(
        r'^$',
        views.IndexView.as_view(),
        name='index'
    ),
]
if settings.DEBUG:
    urlpatterns.append(
        url(
            r'^debugger$',
            views.DebuggerView.as_view(),
            name='debugger'
        ),
    )
