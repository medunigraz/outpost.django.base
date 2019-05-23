from django.dispatch import Signal

materialized_view_refreshed = Signal(
    providing_args=['name', 'model']
)
