import hashlib

from django import forms
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor
from django.dispatch import Signal
from django.utils.encoding import force_text

# Taken from:
# https://stackoverflow.com/questions/31426010/better-arrayfield-admin-widget


class ChoiceArrayField(ArrayField):
    """
    A field that allows us to store an array of choices.
    Uses Django's Postgres ArrayField
    and a MultipleChoiceField for its formfield.
    """

    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.MultipleChoiceField,
            'choices': self.base_field.choices,
        }
        defaults.update(kwargs)
        # Skip our parent's formfield implementation completely as we don't
        # care for it.
        # pylint:disable=bad-super-call
        return super(ArrayField, self).formfield(**defaults)


def _hash_field_name(name):
    return '{name}_hash'.format(name=name)


def _filter_fields(include, exclude):
    def _filter(field):
        if exclude:
            if field.name in exclude:
                return False
        if include:
            if field.name in include:
                return True
        return True
    return _filter


def _get_hash(algorithm, obj, fields):
    bucket = hashlib.new(algorithm)
    for f in fields:
        bucket.update(force_text(f.value_from_object(obj)).encode('utf-8'))
    return bucket.digest()


foreign_data_changed = Signal(providing_args=['instance', 'field'])


class ForeignDataWrapperDescriptor(ForwardManyToOneDescriptor):

    def __init__(self, field, name, algorithm, filter_instance):
        super(ForeignDataWrapperDescriptor, self).__init__(field)
        self.hash_field_name = _hash_field_name(self.field.name)
        self.algorithm = algorithm
        self.filter_instance = filter_instance

    def __get__(self, instance, cls=None):
        rel = super(ForeignDataWrapperDescriptor, self).__get__(instance, cls)

        def _is_dirty(obj):
            hashsum_old = getattr(obj, self.hash_field_name, None)
            fields = filter(self.filter_instance, obj._meta.fields)
            hashsum_new = _get_hash(self.algorithm, fields)
            return hashsum_old != hashsum_new

        setattr(rel, 'is_dirty', _is_dirty)
        return rel


class ForeignDataWrapperKey(models.ForeignKey):

    def __init__(self, to, fields=None, exclude=None, algorithm='sha256',
                 *args, **kwargs):
        self.fields = fields
        self.exclude = exclude
        self.algorithm = algorithm
        self.blank = kwargs.get('blank', False)
        self.null = kwargs.get('null', False)
        kwargs['related_name'] = '+'
        super(ForeignDataWrapperKey, self).__init__(to, *args, **kwargs)

    def contribute_to_class(self, cls, name):
        if not cls._meta.abstract:
            hash_field = models.BinaryField(
                editable=False,
                blank=self.blank,
                null=self.null
            )
            hash_field.creation_counter = self.creation_counter + 1
            cls.add_to_class(_hash_field_name(name), hash_field)
        super(ForeignDataWrapperKey, self).contribute_to_class(cls, name)

        setattr(
            cls,
            self.name,
            ForeignDataWrapperDescriptor(
                self,
                name,
                self.algorithm,
                _filter_fields(self.fields, self.exclude)
            )
        )

    def pre_save(self, model_instance, add):
        val = super(ForeignDataWrapperKey, self).pre_save(model_instance, add)
        if val is not None:
            filter_instance = _filter_fields(self.fields, self.exclude)
            rel = self.related_model.objects.get(pk=val)
            fields = filter(filter_instance, rel._meta.fields)
            hashsum = _get_hash(self.algorithm, rel, fields)
        else:
            hashsum = None
        if getattr(model_instance, _hash_field_name(self.name)) != hashsum:
            foreign_data_changed.send(
                sender=self.__class__,
                instance=model_instance,
                field=self.name
            )
        setattr(model_instance, _hash_field_name(self.name), hashsum)
        return val


class ModifyingFieldDescriptor(object):
    """
    Modifies a field when set using the field's (overriden) .to_python()
    method.
    """
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            raise AttributeError('Can only be accessed via an instance.')
        return instance.__dict__[self.field.name]

    def __set__(self, instance, value):
        instance.__dict__[self.field.name] = self.field.to_python(value)


class LowerCaseCharField(models.CharField):

    def to_python(self, value):
        value = super(LowerCaseCharField, self).to_python(value)
        if isinstance(value, str):
            return value.lower()
        return value

    def contribute_to_class(self, cls, name):
        super(LowerCaseCharField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, ModifyingFieldDescriptor(self))
