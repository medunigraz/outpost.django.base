import re
from django.contrib.contenttypes.models import ContentType
from django.template import Library
from django.template.defaultfilters import stringfilter
from bs4 import BeautifulSoup

register = Library()


@register.filter
def order_by(queryset, args):
    args = [x.strip() for x in args.split(',')]
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
    bs = BeautifulSoup(value, features='lxml')
    return re.sub(r',[^\s]', r', ', bs.text)
