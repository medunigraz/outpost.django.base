from django.conf import settings
from django.urls import re_path, path

from . import views

app_name = "base"
BASE_PATH = ""

urlpatterns = [
    re_path(
        r"^image/convert(?:\/(?P<format>[\w\d]+))?$",
        views.ImageConvertView.as_view(),
        name="image-convert",
    ),
    re_path(
        r"^icon/(?P<pk>[0-9]+)/(?P<color>[0-9a-f]{6})$",
        views.ColorizedIconView.as_view(),
        name="icon",
    ),
    re_path(
        r"^task/(?P<task>(:?[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}|#))/$",
        views.TaskView.as_view(),
        name="task",
    ),
    re_path(r"^error/(?P<code>\d+)?$", views.ErrorView.as_view(), name="error"),
    re_path(r"^error/(?P<code>\d+)?$", views.ErrorView.as_view(), name="error"),
    path("", views.IndexView.as_view(), name="index"),
]
if settings.DEBUG:
    urlpatterns.append(path("debugger", views.DebuggerView.as_view(), name="debugger"))
