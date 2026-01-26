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


class DocumentBase(models.Model):
    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Review"),
        ("adjustment", "Needs Adjustment"),
    ]

    approval_status = models.CharField(
        choices=APPROVAL_STATUS_CHOICES, default="waiting"
    )
    updated_at = models.DateTimeField(null=True, blank=True)
    # TODO: may not be needed down the road
    markdown = models.TextField(null=True, blank=True)
    # TODO: consider changing urlfields into django-storages fields once S3 is set up
    md_version = models.URLField(blank=True, null=True)
    rtf_version = models.URLField(blank=True, null=True)

    class Meta:
        abstract = True


class SourceDoc(DocumentBase):
    METRO_DOC_TYPE_CHOICES = [
        ("agenda", "Agenda"),
        ("board_report", "Board Report"),
    ]

    title = models.CharField()
    created_at = models.DateField(blank=True, null=True)
    metro_doc_type = models.CharField(
        choices=METRO_DOC_TYPE_CHOICES, blank=True, null=True
    )
    doc_id = models.CharField(unique=True, blank=True, null=True)
    source_url = models.URLField(
        help_text=(
            "Link to the original document. Since they are uploaded as pdfs, "
            "this field can serve as the pdf version."
        )
    )


class TranslatedDoc(DocumentBase):
    LANGUAGE_CHOICES = [
        # TODO: add more when pilot languages are decided
        ("es", "Spanish"),
    ]

    language = models.CharField(choices=LANGUAGE_CHOICES)
    pdf_version = models.URLField(null=True, blank=True)
    source_doc = models.ForeignKey(
        SourceDoc, on_delete=models.CASCADE, related_name="translations"
    )
