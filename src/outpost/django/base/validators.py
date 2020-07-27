import logging
from zipfile import BadZipFile, ZipFile

import asyncssh
import entrypoints
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework.compat import unicode_to_repr
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.utils.representation import smart_repr

logger = logging.getLogger(__name__)


class EntryThrottleValidator(object):
    """
    """

    def __init__(self, queryset, search, field, delta):
        self.queryset = queryset
        self.search = search
        self.field = field
        self.delta = delta

    def set_context(self, serializer):
        """
        This hook is called by the serializer instance,
        prior to the validation call being made.
        """
        # Determine the existing instance, if this is an update operation.
        self.instance = getattr(serializer, "instance", None)

    def __call__(self, attrs):
        if self.instance:
            return
        kwargs = {self.search: attrs.get(self.search)}
        try:
            latest = self.queryset.filter(**kwargs).latest(self.field)
            if getattr(latest, self.field) + self.delta > timezone.now():
                raise APIValidationError(_("Requests coming in too fast"))
        except self.queryset.model.DoesNotExist:
            return

    def __repr__(self):
        return unicode_to_repr(
            "<%s(queryset=%s)>" % (self.__class__.__name__, smart_repr(self.queryset))
        )


@deconstructible
class PublicKeyValidator(object):
    """
    """

    message = _("Could not parse public key")
    code = "invalid"

    def __call__(self, value):
        value = force_text(value)
        try:
            asyncssh.import_public_key(value)
        except asyncssh.public_key.KeyImportError:
            logger.debug(f"Import of public key failed: {value}")
            raise ValidationError(self.message, code=self.code)

    def __eq__(self, other):
        return (
            isinstance(other, PublicKeyValidator)
            and (self.message == other.message)
            and (self.code == other.code)
        )


@deconstructible
class PrivateKeyValidator(object):
    """
    """

    message = _("Could not parse private key")
    code = "invalid"

    def __call__(self, value):
        value = force_text(value)
        try:
            asyncssh.import_private_key(value)
        except asyncssh.public_key.KeyImportError:
            logger.debug(f"Import of private key failed: {value}")
            raise ValidationError(self.message, code=self.code)

    def __eq__(self, other):
        return (
            isinstance(other, PrivateKeyValidator)
            and (self.message == other.message)
            and (self.code == other.code)
        )


@deconstructible
class PythonEntryPointsFileValidator(object):
    """
    """

    message = _("No valid entry points found")
    code = "invalid"

    def __init__(self, names, condition=any):
        self.names = names
        self.condition = condition

    def __call__(self, data):
        if type(data.file) is TemporaryUploadedFile:
            path = data.file.temporary_file_path()
        else:
            path = data.path
        eps = (entrypoints.get_group_named(n, [path]) for n in self.names)
        if not self.condition(eps):
            raise ValidationError(self.message, code=self.code)
