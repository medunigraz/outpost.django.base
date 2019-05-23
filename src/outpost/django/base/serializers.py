from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework import (
    exceptions,
    serializers,
)
from rest_hooks.models import Hook

from . import models


class ContentTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContentType
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = models.Notification
        fields = '__all__'


class TaskSerializer(serializers.BaseSerializer):
    id = serializers.CharField(max_length=256)
    state = serializers.CharField(max_length=256)
    info = serializers.DictField()

    def to_representation(self, obj):
        return {
            'id': obj.id,
            'state': obj.state,
            'info': obj.info
        }


class HookSerializer(serializers.ModelSerializer):
    def validate_event(self, event):
        if event not in settings.HOOK_EVENTS:
            err_msg = f'Unexpected event {event}'
            raise exceptions.ValidationError(detail=err_msg, code=400)
        return event

    class Meta:
        model = Hook
        fields = '__all__'
        read_only_fields = ('user',)
