import re

from django.conf import settings
from la_metro_translations.backends import get_backend
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.formats import date_format

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.contrib.settings.models import BaseGenericSetting
from wagtail.images.blocks import ImageChooserBlock  # noqa
from wagtail.models import Orderable
from wagtailmarkdown.fields import MarkdownField


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
    updated_at_display.admin_order_field = "updated_at"

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

    markdown = MarkdownField()
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

    def save(self, *args, **kwargs):
        if self.pk:
            original_obj = type(self).objects.get(pk=self.pk)

            super().save(*args, **kwargs)

            # Sync English translation content and status with document content & status
            english_translation = self.translations.filter(language="eng")

            if english_translation.exists():
                english_translation.update(
                    markdown=self.markdown, approval_status=self.approval_status
                )

            # If document content needs revision, so do translations
            if self.approval_status == "revision":
                self.translations.exclude(language="eng").update(
                    approval_status="revision"
                )

            # If document content has changed, or if document content is newly approved,
            # trigger translation with approval status determined by language config
            elif self.approval_status == "approved":

                content_changed = original_obj.markdown != self.markdown
                content_approved = original_obj.approval_status != "approved"

                if content_changed or content_approved:
                    config = ExtractionConfig.load()

                    for (
                        language_code,
                        language_display,
                    ) in DocumentTranslation.LANGUAGE_CHOICES:
                        if language_code == "eng":
                            continue

                        lang_config = config.language_configs.filter(
                            language=language_code
                        ).first()
                        translation_approval_status = (
                            "approved"
                            if lang_config and lang_config.auto_approve_translations
                            else "waiting"
                        )

                        get_backend().start_job(
                            "batch_translate",
                            language_display,
                            document_content=self.id,
                            approval_status=translation_approval_status,
                        )

        else:
            return super().save(*args, **kwargs)

    def document_title(self):
        return self.document.title

    document_title.short_description = "Title"

    def file_formats_display(self):
        files_btn_fragment = (
            "<a class='button'"
            "style='width: stretch; font-weight: bold; text-align: center;'"
            "target='_blank' href='{}'>{}</a>"
        )
        files_btns = files_btn_fragment.format(self.document.source_url, "Original PDF")

        try:
            rtf = self.translations.get(language="eng").files.get(format="rtf")
        except (DocumentTranslation.DoesNotExist, TranslationFile.DoesNotExist):
            pass
        else:
            files_btns += files_btn_fragment.format(
                rtf.get_file_url(), rtf.format.upper()
            )

        return format_html(
            "<div style='display: flex; justify-content: space-between'>{}</div>",
            mark_safe(files_btns),
        )

    file_formats_display.short_description = "File Formats"


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

    # Language codes based on ISO 639-3 standards
    LANGUAGE_CHOICES = [
        ("hye", "Armenian (Eastern)"),
        ("hyw", "Armenian (Western)"),
        ("zho-cn", "Chinese (Simplified)"),
        ("zho-tw", "Chinese (Traditional)"),
        ("eng", "English (Accessibility)"),
        ("jpn", "Japanese"),
        ("kor", "Korean"),
        ("rus", "Russian"),
        ("spa", "Spanish"),
        ("vie", "Vietnamese"),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("approved", "Approved for Publishing"),
        ("waiting", "Waiting for Initial Review"),
        ("revision", "Needs Revision"),
    ]

    markdown = MarkdownField()
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

    def save(self, *args, **kwargs):
        if self.pk:
            original_obj = type(self).objects.get(pk=self.pk)
            super().save(*args, **kwargs)

            # Create files for translations if content changes or status
            # changes to approved
            if self.approval_status == "approved":
                content_changed = original_obj.markdown != self.markdown
                content_approved = original_obj.approval_status != "approved"

                if content_changed or content_approved:
                    get_backend().start_job(
                        "convert_docs", document_translation=self.id
                    )

        else:
            return super().save(*args, **kwargs)

    def approval_status_display(self):
        if self.document_content.approval_status == "approved":
            return super().approval_status_display()

        return mark_safe("<em>Pending</em>")

    def edit_link_display(self):
        if self.document_content.approval_status == "approved":
            if self.language == "eng":
                edit_url = reverse(
                    f"{camel_to_snake(DocumentContent._meta.object_name)}:edit",
                    args=[self.document_content.pk],
                )
                return format_html(
                    "<a href='{}' class='button button-small'>Manage {}</a>",
                    edit_url,
                    self._meta.verbose_name,
                )

            else:
                return super().edit_link_display()

        return mark_safe("<em>Pending</em>")

    def document_title(self):
        return self.document_content.document.title

    document_title.short_description = "Document Name"

    def language_display(self):
        return format_html(
            "<h3 style='font-weight: bold;'>{}</h3>", self.get_language_display()
        )

    language_display.short_description = "Language"

    def file_formats_display(self):
        latest_file = self.files.order_by("-updated_at").first()
        conversion_date = latest_file.updated_at if latest_file else None
        conversion_date_str = (
            date_format(conversion_date, "N j, Y, P") if conversion_date else None
        )
        conversion_message = (
            f"Generated {conversion_date_str}"
            if conversion_date_str
            else "No PDF or RTF files have been generated for this translation."
        )

        if getattr(self, "files", False):
            files_btns = ""
            for f in self.files.all():
                files_btns += (
                    "<a class='button'"
                    "style='flex: 1; font-weight: bold; text-align: center;'"
                    f"target='_blank' href='{f.get_file_url()}'>{f.format.upper()}</a>"
                )

            return format_html(
                "<div style='display: flex; gap: 0.5rem;'>{}</div>"
                "<div class='help' style='margin-top: .5rem'>{}</div>",
                mark_safe(files_btns),
                conversion_message,
            )

        return mark_safe(
            "<p>This translation is not yet available in other file formats.</p>"
        )

    file_formats_display.short_description = "File Formats"

    @staticmethod
    def get_language_priority():
        return [
            "eng",
            "spa",
            "zho-cn",
            "zho-tw",
            "kor",
            "hye",
            "hyw",
            "vie",
            "rus",
            "jpn",
        ]


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
    Use get_file_url() to see the original Document's source_url for that file version.
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
    file = models.FileField(
        upload_to=translation_file_path, blank=True, null=True, max_length=255
    )
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

    def get_file_url(self):
        if self.format == "pdf" and self.document_translation.language == "eng":
            return self.document_translation.document_content.document.source_url

        return self.file.url


class ExtractionConfig(BaseGenericSetting, ClusterableModel):
    """
    Global configuration for the document processing pipeline.

    Controls whether extracted content and translations are automatically
    approved, or held for human review before proceeding.
    """

    auto_approve_extractions = models.BooleanField(
        default=True,
        help_text=(
            "Automatically approve extracted document content for translation. "
            "Content marked as Needs Revision will not be auto-approved."
        ),
    )

    panels = [
        FieldPanel("auto_approve_extractions"),
        InlinePanel(
            "language_configs",
            heading="Language Translation Settings",
            help_text=(
                "Configure auto-approval for each supported translation language. "
                "Add one row per language."
            ),
        ),
    ]

    class Meta:
        verbose_name = "Extraction Configuration"

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            super().save(*args, **kwargs)

            # When auto_approve_extractions is turned on, catch up all waiting
            # content (but never touch revision content).
            if not original.auto_approve_extractions and self.auto_approve_extractions:
                DocumentContent.objects.filter(approval_status="waiting").update(
                    approval_status="approved"
                )
                DocumentTranslation.objects.filter(
                    language="eng", approval_status="waiting"
                ).update(approval_status="approved")

                # For each configured language, translate any content that hasn't
                # been translated yet, then approve existing waiting translations.
                # Note: TranslationConfig children may not have been committed
                # yet if this save was triggered by a Wagtail admin form submission
                # that also changed language configs. In that case,
                # TranslationConfig.save() will handle the language catch-up
                # independently once each child is committed.
                for lang_config in TranslationConfig.objects.filter(config=self):
                    language_display = dict(DocumentTranslation.LANGUAGE_CHOICES)[
                        lang_config.language
                    ]
                    translation_approval_status = (
                        "approved"
                        if lang_config.auto_approve_translations
                        else "waiting"
                    )
                    get_backend().start_job(
                        "batch_translate",
                        language_display,
                        approval_status=translation_approval_status,
                    )
                    if lang_config.auto_approve_translations:
                        DocumentTranslation.objects.filter(
                            language=lang_config.language,
                            approval_status="waiting",
                        ).update(approval_status="approved")
                        get_backend().start_job("convert_docs")
        else:
            super().save(*args, **kwargs)


class TranslationConfig(Orderable):
    """
    Per-language configuration for translation approval.
    Managed as an inline on ExtractionConfig.
    """

    NON_ENGLISH_LANGUAGE_CHOICES = [
        choice for choice in DocumentTranslation.LANGUAGE_CHOICES if choice[0] != "eng"
    ]

    config = ParentalKey(
        ExtractionConfig,
        on_delete=models.CASCADE,
        related_name="language_configs",
    )
    language = models.CharField(choices=NON_ENGLISH_LANGUAGE_CHOICES)
    auto_approve_translations = models.BooleanField(
        default=True,
        help_text=(
            "Automatically approve machine translations in this language. "
            "Translations marked as Needs Revision will not be auto-approved."
        ),
    )

    class Meta(Orderable.Meta):
        unique_together = [("config", "language")]

    def __str__(self):
        return (
            f"{self.get_language_display()} translation auto-approve: "
            f"{'on' if self.auto_approve_translations else 'off'}"
        )

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            super().save(*args, **kwargs)

            # When auto_approve_translations is turned on for this language, catch up:
            # translate any content that hasn't been translated yet (approved from
            # the start), then approve any translations that already exist but are
            # waiting for review.
            if (
                not original.auto_approve_translations
                and self.auto_approve_translations
            ):
                language_display = dict(DocumentTranslation.LANGUAGE_CHOICES)[
                    self.language
                ]
                get_backend().start_job(
                    "batch_translate", language_display, approval_status="approved"
                )
                DocumentTranslation.objects.filter(
                    language=self.language,
                    approval_status="waiting",
                ).update(approval_status="approved")
                get_backend().start_job("convert_docs")
        else:
            super().save(*args, **kwargs)


class Disclaimer(models.Model):
    language = models.CharField(choices=DocumentTranslation.LANGUAGE_CHOICES)
    disclaimer_text = models.TextField()

    def __str__(self):
        return f"{self.get_language_display()} [{self.language}] Disclaimer"

    class Meta:
        ordering = ["language"]
