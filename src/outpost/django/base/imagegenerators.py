from imagekit import (
    ImageSpec,
    register,
)
from imagekit.processors import ResizeToFill


class Background(ImageSpec):
    processors = [ResizeToFill(1920, 1200)]
    format = 'JPEG'
    options = {'quality': 60}


register.generator('outpost:base:background', Background)
