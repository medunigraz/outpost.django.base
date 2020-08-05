from crispy_forms.bootstrap import UneditableField, StrictButton

class StaticField(UneditableField):

    template = "%s/layout/staticfield.html"


class IconButton(StrictButton):

    template = "%s/layout/iconbutton.html"

    def __init__(self, icon: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.icon = icon


class LinkIconButton(IconButton):

    template = "%s/layout/linkiconbutton.html"

    def __init__(self, href: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.href = href
