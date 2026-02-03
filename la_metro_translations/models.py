from django.db import models

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
    created_at = models.DateField(
        blank=True,
        null=True,
        help_text=(
            "Date this original document was created, as per the BoardAgendas app."
        ),
    )
    document_type = models.CharField(
        choices=DOCUMENT_TYPE_CHOICES, blank=True, null=True
    )
    document_id = models.CharField(
        blank=True,
        null=True,
        help_text="Primary key of this document in the BoardAgendas app.",
    )
    entity_type = models.CharField(choices=ENTITY_TYPE_CHOICES, blank=True, null=True)
    entity_id = models.CharField(
        blank=True,
        null=True,
        help_text="Primary key of this entity in the BoardAgendas app.",
    )


class DocumentContent(models.Model):
    """
    The extracted, untranslated content from a document, saved as markdown.
    """

    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Review"),
        ("adjustment", "Needs Adjustment"),
    ]

    markdown = models.TextField()
    approval_status = models.CharField(
        choices=APPROVAL_STATUS_CHOICES, default="waiting"
    )
    created_at = models.DateField(
        auto_now_add=True, help_text="Date this content was created in this app."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date this content was last updated in this app."
    )
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="content"
    )


class DocumentTranslation(models.Model):
    """
    The translated version of a document's extracted content.
    """

    LANGUAGE_CHOICES = [
        # TODO: add more when pilot languages are decided
        ("spanish", "Spanish"),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Review"),
        ("adjustment", "Needs Adjustment"),
    ]

    markdown = models.TextField()
    language = models.CharField(choices=LANGUAGE_CHOICES)
    approval_status = models.CharField(
        choices=APPROVAL_STATUS_CHOICES, default="waiting"
    )
    created_at = models.DateField(
        auto_now_add=True, help_text="Date this translation was created in this app."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date this translation was last updated in this app."
    )
    document_content = models.ForeignKey(
        DocumentContent, on_delete=models.CASCADE, related_name="translation"
    )


class DocumentContentFile(models.Model):
    """
    A version of a document's original content, uploaded to cloud storage.
    """

    FORMAT_CHOICES = [
        ("md", "md"),
        ("rtf", "rtf"),
        ("pdf", "pdf"),
    ]

    format = models.CharField(choices=FORMAT_CHOICES)
    url = models.URLField(blank=True, null=True)
    document_content = models.ForeignKey(
        DocumentContent, on_delete=models.CASCADE, related_name="file"
    )


class DocumentTranslationFile(models.Model):
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
        DocumentTranslation, on_delete=models.CASCADE, related_name="file"
    )
