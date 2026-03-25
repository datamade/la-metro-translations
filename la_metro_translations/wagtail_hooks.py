from wagtail import hooks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, FieldRowPanel
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.views.generic import IndexView
from wagtail.admin.filters import WagtailFilterSet
from django_filters import CharFilter, ChoiceFilter

from .models import Document, DocumentContent, DocumentTranslation
from .panels import PropertyPanel, RelatedObjectsPanel


class DocumentFilterSet(WagtailFilterSet):
    title = CharFilter(lookup_expr="icontains", label="Title")
    entity_type = ChoiceFilter(
        choices=Document.ENTITY_TYPE_CHOICES, label="Entity Type"
    )

    class Meta:
        model = Document
        fields = ["title", "entity_type", "entity_id"]


class DocumentContentFilterSet(WagtailFilterSet):
    document__title = CharFilter(lookup_expr="icontains", label="Document Name")
    document__entity_type = ChoiceFilter(
        choices=Document.ENTITY_TYPE_CHOICES, label="Entity Type"
    )
    approval_status = ChoiceFilter(
        choices=DocumentContent.APPROVAL_STATUS_CHOICES, label="Approval Status"
    )
    markdown = CharFilter(lookup_expr="icontains", label="Content Search")

    class Meta:
        model = DocumentContent
        fields = [
            "document__title",
            "document__entity_type",
            "approval_status",
            "markdown",
        ]


class DocumentTranslationFilterSet(WagtailFilterSet):
    document_content__document__title = CharFilter(
        lookup_expr="icontains", label="Document Name"
    )
    document_content__document__entity_type = ChoiceFilter(
        choices=Document.ENTITY_TYPE_CHOICES, label="Entity Type"
    )
    language = ChoiceFilter(
        choices=DocumentTranslation.LANGUAGE_CHOICES, label="Language"
    )
    approval_status = ChoiceFilter(
        choices=DocumentTranslation.APPROVAL_STATUS_CHOICES, label="Approval Status"
    )
    markdown = CharFilter(lookup_expr="icontains", label="Translation Search")

    class Meta:
        model = DocumentTranslation
        fields = [
            "document_content__document__title",
            "document_content__document__entity_type",
            "language",
            "approval_status",
            "markdown",
        ]


class DocumentViewSet(ModelViewSet):
    model = Document
    menu_label = "Documents"
    menu_icon = "doc-full"
    menu_order = 200
    add_to_admin_menu = True
    filterset_class = DocumentFilterSet

    list_display = [
        "title",
        "updated_at_display",
        "source_url_display",
        "board_agendas_url_display",
    ]
    list_filter = ["entity_type"]
    search_fields = ["title", "entity_id"]

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("title", read_only=True),
                FieldRowPanel(
                    [
                        FieldPanel("created_at", read_only=True),
                        FieldPanel("updated_at", read_only=True),
                    ]
                ),
                FieldRowPanel(
                    [
                        PropertyPanel("source_url_display", heading="Source URL"),
                        PropertyPanel(
                            "board_agendas_url_display", heading="Board Agendas URL"
                        ),
                    ]
                ),
            ],
            heading="Document Information",
        ),
        MultiFieldPanel(
            [
                RelatedObjectsPanel(
                    "la_metro_translations.DocumentContent",
                    "document",
                    panels=[
                        FieldRowPanel(
                            [
                                PropertyPanel(
                                    "updated_at_display", heading="Updated at"
                                ),
                                PropertyPanel(
                                    "approval_status_display", heading="Approval status"
                                ),
                                PropertyPanel(
                                    "edit_link_display", heading="Detail link"
                                ),
                            ]
                        )
                    ],
                ),
            ],
            heading="Document Content",
        ),
        MultiFieldPanel(
            [
                RelatedObjectsPanel(
                    "la_metro_translations.DocumentTranslation",
                    "document_content__document",
                    panels=[
                        PropertyPanel("language_display"),
                        FieldRowPanel(
                            [
                                PropertyPanel(
                                    "updated_at_display", heading="Updated at"
                                ),
                                PropertyPanel(
                                    "approval_status_display", heading="Approval status"
                                ),
                                PropertyPanel(
                                    "edit_link_display", heading="Detail link"
                                ),
                            ]
                        ),
                    ],
                ),
            ],
            heading="Document Translations",
        ),
    ]


class DocumentContentViewSet(ModelViewSet):
    model = DocumentContent
    menu_label = "Document Content"
    menu_icon = "edit"
    menu_order = 201
    add_to_admin_menu = True
    filterset_class = DocumentContentFilterSet

    list_display = [
        "document_title",
        "approval_status_display",
        "updated_at_display",
    ]
    list_filter = ["approval_status", "document__entity_type"]
    search_fields = ["document__title", "markdown"]

    panels = [
        MultiFieldPanel(
            [
                RelatedObjectsPanel(
                    "la_metro_translations.Document",
                    "content",
                    panels=[
                        FieldRowPanel(
                            [
                                PropertyPanel(
                                    "created_at_display", heading="Created at"
                                ),
                                PropertyPanel(
                                    "updated_at_display", heading="Updated at"
                                ),
                                PropertyPanel("edit_link_display"),
                                PropertyPanel("source_url_display"),
                            ]
                        )
                    ],
                ),
            ],
            heading="Document",
        ),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("created_at", read_only=True),
                        FieldPanel("updated_at", read_only=True),
                    ]
                ),
                FieldPanel("approval_status"),
                FieldPanel("markdown"),
            ],
            heading="Document Content",
        ),
        MultiFieldPanel(
            [
                RelatedObjectsPanel(
                    "la_metro_translations.DocumentTranslation",
                    "document_content",
                    panels=[
                        PropertyPanel("language_display"),
                        FieldRowPanel(
                            [
                                PropertyPanel(
                                    "updated_at_display", heading="Updated at"
                                ),
                                PropertyPanel(
                                    "approval_status_display", heading="Approval status"
                                ),
                                PropertyPanel(
                                    "edit_link_display", heading="Detail link"
                                ),
                            ]
                        ),
                    ],
                ),
            ],
            heading="Document Translations",
        ),
    ]


class DocumentTranslationIndexView(IndexView):
    def get_queryset(self):
        return super().get_queryset()
        # return super().get_queryset().exclude(language="english")


class DocumentTranslationViewSet(ModelViewSet):
    model = DocumentTranslation
    index_view_class = DocumentTranslationIndexView
    menu_label = "Document Translations"
    menu_icon = "globe"
    menu_order = 202
    add_to_admin_menu = True
    filterset_class = DocumentTranslationFilterSet

    list_display = [
        "document_title",
        "language_display",
        "approval_status_display",
        "updated_at_display",
    ]
    list_filter = [
        "language",
        "approval_status",
        "document_content__document__entity_type",
    ]
    search_fields = ["document_content__document__title", "markdown"]

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("document_content", read_only=True),
                FieldRowPanel(
                    [
                        FieldPanel("language", read_only=True),
                        FieldPanel("approval_status"),
                    ]
                ),
            ],
            heading="Translation Information",
        ),
        FieldPanel("markdown"),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("created_at", read_only=True),
                        FieldPanel("updated_at", read_only=True),
                    ]
                ),
            ],
            heading="Timestamps",
        ),
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, "object") and self.object:
            context["source_url"] = self.object.document_content.document.source_url
            context["document"] = self.object.document_content.document
        return context


@hooks.register("register_admin_viewset")
def register_document_viewset():
    return DocumentViewSet("document")


@hooks.register("register_admin_viewset")
def register_document_content_viewset():
    return DocumentContentViewSet("document_content")


@hooks.register("register_admin_viewset")
def register_document_translation_viewset():
    return DocumentTranslationViewSet("document_translation")


@hooks.register("construct_main_menu")
def hide_all_but_modeladmin_and_settings(request, menu_items):
    signatures = (
        lambda x: "django.forms.widgets" in x.__module__,
        lambda x: x.name == "settings",
    )
    menu_items[:] = [mi for mi in menu_items if any(sig(mi) for sig in signatures)]
