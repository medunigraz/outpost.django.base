from . import api

v1 = [
    (
        r'base/contenttype',
        api.ContentTypeViewSet,
        'base-contenttype'
    ),
    (
        r'base/notification',
        api.NotificationViewSet,
        'base-notification'
    ),
    (
        r'base/task',
        api.TaskViewSet,
        'base-task'
    ),
    (
        r'base/password-strength',
        api.PasswordStrengthViewSet,
        'base-password-strength'
    ),
]
