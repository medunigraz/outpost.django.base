class Plugin(object):

    @classmethod
    def qualified(cls):
        return f'{cls.__module__}.{cls.__qualname__}'

    @classmethod
    def all(cls):
        return cls.__subclasses__()
