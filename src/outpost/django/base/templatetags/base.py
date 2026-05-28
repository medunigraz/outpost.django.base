import logging
import re

from bleach import clean
from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.template import Library
from django.template.defaultfilters import stringfilter
from django.template.loader import (
    TemplateDoesNotExist,
    get_template,
)
from django.utils.safestring import mark_safe

from ..conf import settings

logger = logging.getLogger(__name__)
register = Library()


@register.filter
def order_by(queryset, args):
    args = [x.strip() for x in args.split(",")]
    return queryset.order_by(*args)


@register.simple_tag
def content_type(obj):
    return ContentType.objects.get_for_model(obj)


@register.filter
@stringfilter
def split(value, splitter):
    return value.split(splitter)


@register.filter
@stringfilter
def sanitize(value):
    bs = BeautifulSoup(value, features="lxml")
    return re.sub(r",[^\s]", r", ", bs.text)


@register.filter
@stringfilter
def bleach(value):
    return clean(value, strip=True)


@register.filter
@stringfilter
def truncate_words(value, limit):
    return " ".join([w[:limit] for w in value.split(" ")])


@register.simple_tag(takes_context=True)
def navigation(context):
    templates = []
    installed = list(apps.app_configs.keys())
    for name in reversed(settings.BASE_NAVIGATION_ORDER):
        installed.insert(0, installed.pop(installed.index(name)))
    for name in installed:
        try:
            templates.append(get_template(f"{name}/nav.html"))
        except TemplateDoesNotExist:
            pass
        else:
            logger.debug(f"Found navigation template inside {name}")
    return mark_safe("\n".join((t.render(context.flatten()) for t in templates)))
