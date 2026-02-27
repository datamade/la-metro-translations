from wagtail import hooks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, FieldRowPanel
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.views.generic import IndexView
from wagtail.admin.filters import WagtailFilterSet
from django_filters import CharFilter, ChoiceFilter

from .models import Document, DocumentContent, DocumentTranslation


class DocumentFilterSet(WagtailFilterSet):
    title = CharFilter(lookup_expr='icontains', label='Title')
    entity_type = ChoiceFilter(choices=Document.ENTITY_TYPE_CHOICES, label='Entity Type')

    class Meta:
        model = Document
        fields = ['title', 'entity_type']


class DocumentContentFilterSet(WagtailFilterSet):
    document__title = CharFilter(lookup_expr='icontains', label='Document Name')
    document__entity_type = ChoiceFilter(choices=Document.ENTITY_TYPE_CHOICES, label='Entity Type')
    approval_status = ChoiceFilter(choices=DocumentContent.APPROVAL_STATUS_CHOICES, label='Approval Status')
    markdown = CharFilter(lookup_expr='icontains', label='Content Search')

    class Meta:
        model = DocumentContent
        fields = ['document__title', 'document__entity_type', 'approval_status', 'markdown']


class DocumentTranslationFilterSet(WagtailFilterSet):
    document_content__document__title = CharFilter(lookup_expr='icontains', label='Document Name')
    document_content__document__entity_type = ChoiceFilter(choices=Document.ENTITY_TYPE_CHOICES, label='Entity Type')
    language = ChoiceFilter(choices=DocumentTranslation.LANGUAGE_CHOICES, label='Language')
    approval_status = ChoiceFilter(choices=DocumentTranslation.APPROVAL_STATUS_CHOICES, label='Approval Status')
    markdown = CharFilter(lookup_expr='icontains', label='Translation Search')

    class Meta:
        model = DocumentTranslation
        fields = ['document_content__document__title', 'document_content__document__entity_type', 'language', 'approval_status', 'markdown']


class DocumentIndexView(IndexView):
    template_name = 'wagtailadmin/generic/document_index.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('content').order_by('entity_type', 'title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Group documents by entity type
        grouped_documents = {}
        for doc in context['object_list']:
            entity_type = doc.get_entity_type_display() if doc.entity_type else 'Unknown'
            if entity_type not in grouped_documents:
                grouped_documents[entity_type] = []
            grouped_documents[entity_type].append(doc)
        context['grouped_documents'] = grouped_documents
        return context


class DocumentViewSet(ModelViewSet):
    model = Document
    menu_label = 'Documents'
    menu_icon = 'doc-full'
    menu_order = 200
    add_to_admin_menu = True
    filterset_class = DocumentFilterSet
    index_view_class = DocumentIndexView
    edit_template_name = 'wagtailadmin/generic/document_edit.html'

    list_display = ['title', 'entity_display', 'document_type', 'updated_at_display']
    list_filter = ['entity_type', 'document_type']
    search_fields = ['title']

    panels = [
        MultiFieldPanel([
            FieldPanel('title', read_only=True),
            FieldRowPanel([
                FieldPanel('entity_type', read_only=True),
                FieldPanel('document_type', read_only=True),
            ]),
        ], heading='Document Information'),
        MultiFieldPanel([
            FieldPanel('source_url', read_only=True),
            FieldRowPanel([
                FieldPanel('created_at', read_only=True),
                FieldPanel('updated_at', read_only=True),
            ]),
        ], heading='Source Information'),
        MultiFieldPanel([
            FieldPanel('document_id', read_only=True),
            FieldPanel('entity_id', read_only=True),
        ], heading='External References'),
    ]

    def get_context_data(self, **kwargs):
        print("firing documentviewset get_context_data")
        context = super().get_context_data(**kwargs)
        print(self, kwargs)
        if hasattr(self, 'object') and self.object:
            # Add related content and translations for easy access
            try:
                context['document_content'] = self.object.content
                context['document_translations'] = self.object.content.translations.all()
            except DocumentContent.DoesNotExist:
                context['document_content'] = None
                context['document_translations'] = []
        return context


class DocumentContentViewSet(ModelViewSet):
    model = DocumentContent
    menu_label = 'Document Content'
    menu_icon = 'edit'
    menu_order = 201
    add_to_admin_menu = True
    filterset_class = DocumentContentFilterSet
    edit_template_name = 'wagtailadmin/generic/document_content_edit.html'

    list_display = ['document_title', 'approval_status_display', 'entity_display', 'document_updated_display', 'content_updated_display']
    list_filter = ['approval_status', 'document__entity_type']
    search_fields = ['document__title', 'markdown']

    panels = [
        MultiFieldPanel([
            FieldPanel('document', read_only=True),
            FieldPanel('approval_status'),
        ], heading='Content Information'),
        FieldPanel('markdown'),
        MultiFieldPanel([
            FieldRowPanel([
                FieldPanel('created_at', read_only=True),
                FieldPanel('updated_at', read_only=True),
            ]),
        ], heading='Timestamps'),
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'object') and self.object:
            context['source_url'] = self.object.document.source_url
            context['translations'] = self.object.translations.all()
        return context


class DocumentTranslationIndexView(IndexView):
    def get_queryset(self):
        return super().get_queryset().exclude(language="english")


class DocumentTranslationViewSet(ModelViewSet):
    model = DocumentTranslation
    index_view_class = DocumentTranslationIndexView
    menu_label = 'Document Translations'
    menu_icon = 'globe'
    menu_order = 202
    add_to_admin_menu = True
    filterset_class = DocumentTranslationFilterSet
    edit_template_name = 'wagtailadmin/generic/document_translation_edit.html'

    list_display = ['document_title', 'language_display', 'approval_status_display', 'content_updated_display', 'translation_updated_display']
    list_filter = ['language', 'approval_status', 'document_content__document__entity_type']
    search_fields = ['document_content__document__title', 'markdown']

    panels = [
        MultiFieldPanel([
            FieldPanel('document_content', read_only=True),
            FieldRowPanel([
                FieldPanel('language', read_only=True),
                FieldPanel('approval_status'),
            ]),
        ], heading='Translation Information'),
        FieldPanel('markdown'),
        MultiFieldPanel([
            FieldRowPanel([
                FieldPanel('created_at', read_only=True),
                FieldPanel('updated_at', read_only=True),
            ]),
        ], heading='Timestamps'),
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'object') and self.object:
            context['source_url'] = self.object.document_content.document.source_url
            context['document'] = self.object.document_content.document
        return context


@hooks.register('register_admin_viewset')
def register_document_viewset():
    return DocumentViewSet('document')


@hooks.register('register_admin_viewset')
def register_document_content_viewset():
    return DocumentContentViewSet('document_content')


@hooks.register('register_admin_viewset')
def register_document_translation_viewset():
    return DocumentTranslationViewSet('document_translation')