from django.apps import apps
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from wagtail.admin.panels import Panel


class PropertyPanel(Panel):
    def __init__(self, attr, *args, **kwargs):
        self.attr = attr
        super().__init__(*args, **kwargs)

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["attr"] = self.attr
        return kwargs

    class BoundPanel(Panel.BoundPanel):
        def render_html(self, *args):
            value = getattr(self.instance, self.panel.attr, "—")
            if callable(value):
                value = value()
            return format_html(
                """
                <div class="w-field__wrapper">
                    <div class="w-field__input">{}</div>
                </div>
                """,
                value,
            )


class RelatedObjectsPanel(Panel):
    def __init__(self, related_cls, query_path, panels, *args, **kwargs):
        self.related_cls = related_cls
        self.query_path = query_path
        self.child_panels = panels
        super().__init__(*args, **kwargs)

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["related_cls"] = self.related_cls
        kwargs["query_path"] = self.query_path
        kwargs["panels"] = self.child_panels
        return kwargs

    class BoundPanel(Panel.BoundPanel):
        def render_html(self, *args):
            # Don't try to filter related objects for unsaved instances
            if not self.instance.pk:
                return mark_safe("")

            relations = apps.get_model(self.panel.related_cls).objects.filter(
                **{self.panel.query_path: self.instance}
            )

            rows = []
            for obj in relations:
                fields = []
                for child_panel in self.panel.child_panels:
                    # Bind the panel to the related model, then bind to the instance
                    bound = child_panel.bind_to_model(
                        self.panel.related_cls
                    ).get_bound_panel(instance=obj)
                    fields.append(bound.render_html())

                rows.append(mark_safe("".join(fields)))

            return mark_safe("".join(rows))
