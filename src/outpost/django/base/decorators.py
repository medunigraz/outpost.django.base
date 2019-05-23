from functools import wraps
from locale import setlocale

from django.contrib.auth import authenticate, login
from django.db.models.signals import (
    post_delete,
    post_init,
    post_save,
    pre_delete,
    pre_init,
    pre_save,
)


def signal_connect(cls):
    """
    Class decorator that automatically connects pre_save / post_save signals on
    a model class to its pre_save() / post_save() methods.
    """

    def connect(signal, func):
        cls.func = staticmethod(func)

        @wraps(func)
        def wrapper(sender, *args, **kwargs):
            return func(kwargs.get("instance"), *args, **kwargs)

        signal.connect(wrapper, sender=cls)
        return wrapper

    if hasattr(cls, "post_delete"):
        cls.post_delete = connect(post_delete, cls.post_delete)

    if hasattr(cls, "post_init"):
        cls.post_init = connect(post_init, cls.post_init)

    if hasattr(cls, "post_save"):
        cls.post_save = connect(post_save, cls.post_save)

    if hasattr(cls, "pre_delete"):
        cls.pre_delete = connect(pre_delete, cls.pre_delete)

    if hasattr(cls, "pre_init"):
        cls.pre_init = connect(pre_init, cls.pre_init)

    if hasattr(cls, "pre_save"):
        cls.pre_save = connect(pre_save, cls.pre_save)

    return cls


def signal_skip(func):
    @wraps(func)
    def _decorator(sender, instance, **kwargs):
        if hasattr(instance, "skip_signal"):
            return None
        instance.skip_signal = True
        return func(sender, instance, **kwargs)

    return _decorator


def locale(cat, loc):
    def _decorator(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            orig = setlocale(cat, loc)
            value = func(*args, **kwargs)
            setlocale(cat, orig)
            return value

        return _wrapper

    return _decorator


def docstring_format(*args, **kwargs):
    def _decorator(obj):
        if getattr(obj, "__doc__", None):
            obj.__doc__ = obj.__doc__.format(*args, **kwargs)
        return obj

    return _decorator


def http_basic_auth(func):
    @wraps(func)
    def _decorator(request, *args, **kwargs):
        if request.META.has_key("HTTP_AUTHORIZATION"):
            authmeth, auth = request.META["HTTP_AUTHORIZATION"].split(" ", 1)
            if authmeth.lower() == "basic":
                auth = auth.strip().decode("base64")
                username, password = auth.split(":", 1)
                user = authenticate(username=username, password=password)
                if user:
                    login(request, user)
        return func(request, *args, **kwargs)

    return _decorator
