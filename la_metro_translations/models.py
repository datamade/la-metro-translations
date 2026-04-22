import re

from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.conf import settings

from wagtail.images.blocks import ImageChooserBlock  # noqa


def camel_to_snake(name):
    """
    Inserts an underscore before all uppercase letters
    that are not at the start of the string
    """
    s = re.sub("(?<!^)(?=[A-Z])", "_", name)
    return s.lower()


class AdminDisplayMixin:
    def approval_status_display(self):
        if getattr(self, "approval_status", False):
            status_colors = {
                "approved": "green",
                "waiting": "orange",
                "revision": "red",
            }
            color = status_colors.get(self.approval_status, "gray")

            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                self.get_approval_status_display(),
            )

    approval_status_display.short_description = "Approval Status"

    def created_at_display(self):
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M")  # noqa
        return "-"

    created_at_display.short_description = "Created At"

    def updated_at_display(self):
        if self.updated_at:
            return self.updated_at.strftime("%Y-%m-%d %H:%M")  # noqa
        return "-"

    updated_at_display.short_description = "Updated At"

    def edit_link_display(self):
        edit_url = reverse(
            f"{camel_to_snake(self._meta.object_name)}:edit", args=[self.pk]  # noqa
        )
        return format_html(
            "<a href='{}' class='button button-small'>Manage {}</a>",
            edit_url,
            self._meta.verbose_name,
        )

    edit_link_display.short_description = "Edit Link"


class Document(AdminDisplayMixin, models.Model):
    """
    Details on an original source document.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "document_id"],
                name="unique_document",
            )
        ]
        ordering = ["entity_type", "title"]

    DOCUMENT_TYPE_CHOICES = [
        ("event_document", "EventDocument"),
        ("bill_document", "BillDocument"),
        ("bill_version", "BillVersion"),
    ]
    ENTITY_TYPE_CHOICES = [
        ("event", "Event"),
        ("bill", "Bill"),
    ]

    title = models.CharField()
    source_url = models.URLField(help_text="Link to the original pdf document.")
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=(
            "Date this original document was created, as per the BoardAgendas app."
        ),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
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
    entity_slug = models.CharField(
        help_text="Slug to view this entity on the BoardAgendas app",
    )

    def __str__(self):
        return f"{self.get_entity_type_display()} - {self.title}"

    def board_agendas_url_display(self):
        if self.entity_type == "bill":
            route = "board-report"
        elif self.entity_type == "event":
            route = "event"
        else:
            return ""

        entity_url = f"{settings.BOARDAGENDAS_URL}/{route}/{self.entity_slug}/"  # noqa
        return format_html(
            """
            <a href='{}' target='_blank' class='button button-small button-secondary'>
                View related {}
            </a>
            """,
            entity_url,
            self.entity_type,
        )

    board_agendas_url_display.short_description = "Board Agendas URL"

    def source_url_display(self):
        if not self.source_url:
            return ""

        return format_html(
            """
            <a href='{}' target='_blank' class='button button-small button-secondary'>
                View original document
            </a>
            """,
            self.source_url,
        )

    source_url_display.short_description = "Source URL"


class DocumentContent(AdminDisplayMixin, models.Model):
    """
    The extracted, untranslated content from a document, saved as markdown.
    """

    class Meta:
        ordering = ["-updated_at"]

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
        return (
            f"Content for {self.document.title} ({self.get_approval_status_display()})"
        )

    def document_title(self):
        return self.document.title

    document_title.short_description = "Title"


class DocumentTranslation(AdminDisplayMixin, models.Model):
    """
    The translated version of a document's extracted content.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_content", "language"],
                name="unique_translation",
            )
        ]
        ordering = ["-updated_at"]

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("sp", "Spanish"),
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
        language = self.get_language_display()
        title = self.document_content.document.title
        return (
            f"{language} translation for {title} ({self.get_approval_status_display()})"
        )

    def document_title(self):
        return self.document_content.document.title

    document_title.short_description = "Document Name"

    def language_display(self):
        return format_html(
            "<h3 style='font-weight: bold;'>{}</h3>", self.get_language_display()
        )

    language_display.short_description = "Language"


def translation_file_path(instance, filename):
    year = instance.document_translation.document_content.document.created_at.year
    doc_status = instance.document_translation.document_content.approval_status

    if doc_status == "approved":
        top_dir = "Published"
    else:
        top_dir = "Unpublished"

    return f"{top_dir}/{year}/{filename}"


class TranslationFile(models.Model):
    """
    A version of a document's translation, uploaded to cloud storage.

    If this is a pdf version of an english translation, the file field will be empty.
    Use get_file() to see the original Document's source_url for that file version.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_translation", "format"],
                name="unique_file",
            )
        ]

    FORMAT_CHOICES = [
        ("md", "Markdown"),
        ("rtf", "RTF"),
        ("pdf", "PDF"),
    ]

    format = models.CharField(choices=FORMAT_CHOICES)
    file = models.FileField(upload_to=translation_file_path, blank=True, null=True)
    document_translation = models.ForeignKey(
        DocumentTranslation, on_delete=models.CASCADE, related_name="files"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date this object was created in this app."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date this object was last updated in this app."
    )

    def __str__(self):
        language = self.document_translation.get_language_display()
        title = self.document_translation.document_content.document.title
        return f"{language} translation file for {title} ({self.format})"

    def delete(self):
        self.file.delete(save=False)
        super().delete()

    def get_file(self):
        if self.format == "pdf" and self.document_translation.language == "en":
            return self.document_translation.document_content.document.source_url

        return self.file
