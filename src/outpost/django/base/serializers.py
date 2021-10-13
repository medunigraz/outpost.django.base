import base64
import imghdr
import uuid
from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.contenttypes.models import ContentType
from rest_framework import exceptions, serializers
#from rest_hooks.models import Hook

from . import models


class ContentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = "__all__"


class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = models.Notification
        fields = "__all__"


class TaskSerializer(serializers.BaseSerializer):
    id = serializers.CharField(max_length=256)
    state = serializers.CharField(max_length=256)
    info = serializers.DictField()

    def to_representation(self, obj):
        return {"id": obj.id, "state": obj.state, "info": obj.info}


#class HookSerializer(serializers.ModelSerializer):
#    def validate_event(self, event):
#        if event not in settings.HOOK_EVENTS:
#            err_msg = f"Unexpected event {event}"
#            raise exceptions.ValidationError(detail=err_msg, code=400)
#        return event
#
#    class Meta:
#        model = Hook
#        fields = "__all__"
#        read_only_fields = ("user",)


class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, data):

        if isinstance(data, str):
            if 'data:' in data and ';base64,' in data:
                header, data = data.split(';base64,')

            try:
                decoded_file = base64.b64decode(data)
            except TypeError:
                self.fail('invalid_image')

            file_name = str(uuid.uuid4())
            file_extension = self.get_file_extension(file_name, decoded_file)
            complete_file_name = f"{file_name}.{file_extension}"
            data = ContentFile(decoded_file, name=complete_file_name)

        return super().to_internal_value(data)

    def get_file_extension(self, file_name, decoded_file):

        extension = imghdr.what(file_name, decoded_file)
        extension = "jpg" if extension == "jpeg" else extension

        return extension
