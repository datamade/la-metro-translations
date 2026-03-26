import re

from django.db import models
from django.urls import reverse
from django.utils.html import format_html

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
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "document_id"],
                name="unique_document",
            )
        ]
        ordering = ["entity_type", "title"]

    def board_agendas_url_display(self):
        if self.entity_type == "bill":
            route = "board-report"
        elif self.entity_type == "event":
            route = "event"
        # TODO: Update board agendas hook to post slug
        entity_url = f"https://boardagendas.metro.net/{route}/{self.entity_id}/"  # noqa
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

    document_title.short_description = "Title"


class DocumentTranslation(AdminDisplayMixin, models.Model):
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
        constraints = [
            models.UniqueConstraint(
                fields=["document_content", "language"],
                name="unique_translation",
            )
        ]
        ordering = ["-updated_at"]

    def document_title(self):
        return self.document_content.document.title

    document_title.short_description = "Document Name"

    def language_display(self):
        return format_html(
            "<h3 style='font-weight: bold;'>{}</h3>", self.get_language_display()
        )

    language_display.short_description = "Language"
    class Meta:
        


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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_translation", "format"],
                name="unique_file",
            )
        ]
