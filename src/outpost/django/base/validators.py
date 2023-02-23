import logging
from collections.abc import Iterable
import entrypoints
import asyncssh
import mimetypes
import pint
from os.path import normpath
from pathlib import PurePath
from zipfile import ZipFile, BadZipFile
from croniter import croniter
from PIL import Image
from purl import URL
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.utils.representation import smart_repr

logger = logging.getLogger(__name__)


class EntryThrottleValidator(object):
    """"""

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


@deconstructible
class PublicKeyValidator(object):
    """"""

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
    """"""

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
    """"""

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


@deconstructible
class CronValidator(object):
    """
    Validate cron style strings using croniter library.
    """

    message = _("Not a valid cron string")
    code = "invalid"

    def __call__(self, data):
        if not croniter.is_valid(data):
            raise ValidationError(self.message, code=self.code)


@deconstructible
class NormalizedPathValidator(object):
    """
    Validate normalized paths
    """

    def __call__(self, data: str):
        if normpath(data) != data:
            raise ValidationError(_("Path is not normalized"), code="not_normalized")


@deconstructible
class RelativePathValidator(object):
    """"""

    def __call__(self, data: str):
        path = PurePath(data)
        if path.is_absolute():
            raise ValidationError(_("Absolute paths not allowed"), code="no_absolute")
        if ".." in path.parts:
            raise ValidationError(
                _("No parent directory references allowed"), code="no_parent_references"
            )


@deconstructible
class AbsolutePathValidator(object):
    """
    Validate absolute paths
    """

    def __call__(self, data: str):
        if not PurePath(data).is_absolute():
            raise ValidationError(_("Path is not absolute"), code="not_absolute")


@deconstructible
class FileValidator:
    """
    Validator for files, checking the extension and mimetype.
    Initialization parameters:
        extensions: iterable with allowed file extensions
            ie. ('txt', 'doc')
        mimetypes: iterable with allowed mimetypes
            ie. ('image/png', )
    Usage example::
        MyModel(models.Model):
            myfile = FileField(
                validators=(
                    FileValidator(mimetypes=['audio/flac'], ...),
                ),
            )
    """

    extension_message = _(
        "Extension '%(extension)s' not allowed. Allowed extensions are: '%(extensions)s.'"
    )
    mimetype_message = _(
        "MIME type '%(mimetype)s' is not valid. Allowed types are: %(mimetypes)s."
    )

    def __init__(self, extensions=None, mimetypes=None):
        self.extensions = extensions
        self.mimetypes = mimetypes

    def __call__(self, value):
        """
        Check the extension and content type.
        """

        # Check the extension
        ext = PurePath(value.name).suffix.lstrip(".")
        if self.extensions and ext not in self.extensions:
            message = self.extension_message % {
                "extension": ext,
                "extensions": ", ".join(self.extensions),
            }

            raise ValidationError(message)

        # Check the content type
        mimetype, _ = mimetypes.guess_type(value.name)
        if mimetype and self.mimetypes and mimetype not in self.mimetypes:
            message = self.mimetype_message % {
                "mimetype": mimetype,
                "mimetypes": ", ".join(self.mimetypes),
            }

            raise ValidationError(message)


@deconstructible
class ImageValidator:
    """
    Validator for images, checking the format and dimensions.
    Initialization parameters:
        formats: iterable with allowed image formats
            ie. ('jpeg', 'png')
        modes: iterable with allowed image formats
            ie. ('rgb',)
        width: integer or integer range for allowed width
            ie. 1920 or range(1280, 1920)
        height: integer or integer range for allowed height
            ie. 1080 or range(720, 1080)
    Usage example::
        MyModel(models.Model):
            myfile = FileField(
                validators=(
                    ImageValidator(
                        formats=("png", "jpeg"),
                        width=range(1280, 4096),
                        height=range(720, 2160)
                    ),
                ),
            )
    """

    format_message = _(
        "Format '%(format)s' not allowed. Allowed formats are: '%(formats)s.'"
    )
    mode_message = _("Mode '%(mode)s' not allowed. Allowed modes are: '%(modes)s.'")
    width_message = _(
        "Width of %(width)s pixels is not within bounds. Should have width of %(allowed)s pixels."
    )
    height_message = _(
        "Height of %(height)s pixels is not within bounds. Should have height of %(allowed)s pixels."
    )

    def __init__(self, formats=[], modes=[], width=None, height=None):
        self.formats = [f.upper() for f in formats]
        self.modes = [m.upper() for m in modes]
        self.width = width
        self.height = height

    def __call__(self, value):
        """
        Check format, mode, width and height.
        """
        image = Image.open(value.file)

        if self.formats and image.format.upper() not in self.formats:
            message = self.format_message % {
                "format": image.format.upper(),
                "formats": ", ".join(self.formats),
            }

            raise ValidationError(message)

        if self.modes and image.mode.upper() not in self.modes:
            message = self.mode_message % {
                "mode": image.mode.upper(),
                "modes": ", ".join(self.modes),
            }

            raise ValidationError(message)

        if self.width:
            if type(self.width) == int:
                if image.width != self.width:
                    message = self.width_message % {
                        "width": image.width,
                        "allowed": self.width,
                    }
                    raise ValidationError(message)
            if type(self.width) == range:
                if image.width not in self.width:
                    message = self.width_message % {
                        "width": image.width,
                        "allowed": f"{self.width.start}-{self.width.stop}",
                    }
                    raise ValidationError(message)

        if self.height:
            if type(self.height) == int:
                if image.height != self.height:
                    message = self.height_message % {
                        "height": image.height,
                        "allowed": self.height,
                    }
                    raise ValidationError(message)
            if type(self.height) == range:
                if image.height not in self.height:
                    message = self.height_message % {
                        "height": image.height,
                        "allowed": f"{self.height.start}-{self.height.stop}",
                    }
                    raise ValidationError(message)


@deconstructible
class RedisURLValidator(object):
    """
    Validate Redis URLs.
    """

    def __call__(self, data: str):
        try:
            url = URL(data)
        except ValueError:
            raise ValidationError(_("URL cannot be parsed"), code="parse_error")
        if url.has_query_param("db"):
            if not url.query_param("db").isdigit():
                raise ValidationError(_("Invalid port specified"), code="invalid_port")
        if url.scheme() == "unix":
            if url.host():
                raise ValidationError(
                    _("Hostname not supported for unix domain sockets"),
                    code="unix_domain_socket_hostname",
                )
            if url.port():
                raise ValidationError(
                    _("Port not supported for unix domain sockets"),
                    code="unix_domain_socket_port",
                )
            if not url.path():
                raise ValidationError(
                    _("No path specified for unix domain socket"),
                    code="unix_domain_socket_path",
                )
        if url.scheme() in ("redis", "redis+tls"):
            if not url.host():
                raise ValidationError(_("No host specified"), code="host_missing")


@deconstructible
class UnitValidator(object):
    """
    Validate physical quantities.
    """

    ureg = pint.UnitRegistry()

    def __init__(self, unit):
        self.unit = self.ureg(unit).to_base_units().units

    def __call__(self, data: str):
        try:
            if self.ureg(data).to_base_units().units == self.unit:
                raise ValidationError(
                    _("Incompatible unit specified"), code="incompatible_unit"
                )
        except pint.UndefinedUnitError:
            raise ValidationError(_("Invalid unit specified"), code="invalid_unit")
