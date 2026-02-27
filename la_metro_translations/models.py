from django.db import models
from django.utils.html import format_html

from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail.admin.panels import FieldPanel

from la_metro_translations.blocks import ReactBlock


class StaticPage(Page):
    include_in_dump = True

    body = StreamField(
        [
            ("content", blocks.RichTextBlock()),
            ("image", ImageChooserBlock()),
            ("react_block", ReactBlock()),
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    def get_template(self, request, *args, **kwargs):
        if self.slug == "home":
            return "la_metro_translations/home_page.html"
        else:
            return "la_metro_translations/static_page.html"


class ExampleModel(models.Model):
    include_in_dump = True

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class DetailPage(Page):
    """
    Need a detail page for your Django model instance/s? Try this!
    Delete this model and its subclasses if you don't need detail pages.
    User entered and editable data should live as attributes on a model's DetailPage;
    immutable data should be attached to the corresponding model instance.
    """

    include_in_dump = True

    class Meta:
        abstract = True

    body = StreamField(
        [
            ("content", blocks.RichTextBlock()),
            ("image", ImageChooserBlock()),
            ("react_block", ReactBlock()),
        ],
        blank=True,
    )

    def save(self, *args, **kwargs):
        title = str(self.object)
        for attr in ("title", "draft_title"):
            setattr(self, attr, title)
        super().save(*args, **kwargs)


class ExampleModelDetailPage(DetailPage):
    object = models.ForeignKey(
        "ExampleModel",
        blank=False,
        null=True,
        on_delete=models.SET_NULL,
    )
    content_panels = [
        FieldPanel("object"),
        FieldPanel("body"),
    ]

    def get_context(self, request, *args, **kwargs):
        """
        By default, Wagtail will look for a template named a snake-case
        version of the page model name, e.g., example_model_detail_page.html
        """
        context = super().get_context(request, *args, **kwargs)
        # Add additional context for your template, if needed.
        return context


class Document(models.Model):
    """
    Details on an original source document.
    """

    DOCUMENT_TYPE_CHOICES = [
        ("event_document", "EventDocument"),
        ("bill_document", "BillDocument"),
    ]
    ENTITY_TYPE_CHOICES = [
        ("event", "Event"),
        ("bill", "Bill"),
    ]

    title = models.CharField()
    source_url = models.URLField(help_text="Link to the original pdf document.")
    created_at = models.DateTimeField(
        help_text=(
            "Date this original document was created, as per the BoardAgendas app."
        ),
    )
    updated_at = models.DateTimeField(
        help_text=(
            "Date this original document was updated, as per the BoardAgendas app."
        ),
    )
    document_type = models.CharField(choices=DOCUMENT_TYPE_CHOICES)
    document_id = models.CharField(
        help_text="Primary key of this document in the BoardAgendas app.",
    )
    entity_type = models.CharField(choices=ENTITY_TYPE_CHOICES)
    entity_id = models.CharField(
        help_text="Primary key of this entity in the BoardAgendas app.",
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["entity_type", "title"]

    def entity_display(self):
        if self.entity_type:
            return self.get_entity_type_display()
        return "-"

    entity_display.short_description = "Entity"

    def updated_at_display(self):
        if self.updated_at:
            return self.updated_at.strftime("%Y-%m-%d %H:%M")
        return "-"

    updated_at_display.short_description = "Last updated"


class DocumentContent(models.Model):
    """
    The extracted, untranslated content from a document, saved as markdown.
    """

    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Initial Review"),
        ("revision", "Needs Revision"),
    ]

    markdown = models.TextField()
    approval_status = models.CharField(
        choices=APPROVAL_STATUS_CHOICES, default="waiting"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date this content was created in this app."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date this content was last updated in this app."
    )
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="content"
    )

    def __str__(self):
        return f"{self.document.title} - Content"

    class Meta:
        ordering = ["-updated_at"]

    def document_title(self):
        return self.document.title

    document_title.short_description = "Document Name"

    def approval_status_display(self):
        status_colors = {"approved": "green", "waiting": "orange", "revision": "red"}
        color = status_colors.get(self.approval_status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            self.get_approval_status_display(),
        )

    approval_status_display.short_description = "Approval Status"

    def entity_display(self):
        if self.document.entity_type:
            return self.document.get_entity_type_display()
        return "-"

    entity_display.short_description = "Entity"

    def document_updated_display(self):
        if self.document.updated_at:
            return self.document.updated_at.strftime("%Y-%m-%d %H:%M")
        return "-"

    document_updated_display.short_description = "Document Updated"

    def content_updated_display(self):
        return self.updated_at.strftime("%Y-%m-%d %H:%M")

    content_updated_display.short_description = "Content Updated"


class DocumentTranslation(models.Model):
    """
    The translated version of a document's extracted content.
    """

    LANGUAGE_CHOICES = [
        ("english", "English"),
        ("spanish", "Spanish"),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Initial Review"),
        ("revision", "Needs Revision"),
    ]

    markdown = models.TextField()
    language = models.CharField(choices=LANGUAGE_CHOICES)
    approval_status = models.CharField(
        choices=APPROVAL_STATUS_CHOICES, default="waiting"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date this translation was created in this app."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date this translation was last updated in this app."
    )
    document_content = models.ForeignKey(
        DocumentContent, on_delete=models.CASCADE, related_name="translations"
    )

    def __str__(self):
        return f"{self.document_content.document.title} - {self.get_language_display()}"

    class Meta:
        ordering = ["-updated_at"]

    def document_title(self):
        return self.document_content.document.title

    document_title.short_description = "Document Name"

    def language_display(self):
        return self.get_language_display()

    language_display.short_description = "Language"

    def approval_status_display(self):
        status_colors = {"approved": "green", "waiting": "orange", "revision": "red"}
        color = status_colors.get(self.approval_status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            self.get_approval_status_display(),
        )

    approval_status_display.short_description = "Approval Status"

    def content_updated_display(self):
        return self.document_content.updated_at.strftime("%Y-%m-%d %H:%M")

    content_updated_display.short_description = "Content Updated"

    def translation_updated_display(self):
        return self.updated_at.strftime("%Y-%m-%d %H:%M")

    translation_updated_display.short_description = "Translation Updated"


class TranslationFile(models.Model):
    """
    A version of a document's translation, uploaded to cloud storage.
    """

    FORMAT_CHOICES = [
        ("md", "md"),
        ("rtf", "rtf"),
        ("pdf", "pdf"),
    ]

    format = models.CharField(choices=FORMAT_CHOICES)
    url = models.URLField(blank=True, null=True)
    document_translation = models.ForeignKey(
        DocumentTranslation, on_delete=models.CASCADE, related_name="files"
    )
