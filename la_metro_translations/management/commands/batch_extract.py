import logging
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q, F
from django.db import connections

from la_metro_translations.models import (
    Document,
    DocumentContent,
    DocumentTranslation,
    ExtractionConfig,
    TranslationConfig,
    TranslationFile,
)
from la_metro_translations.services import MistralOCRService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Extract text from documents that need content, and create/update related objects.
    """

    help = (
        "Perform OCR text extraction on all Documents that either do not have a "
        "related DocumentContent object or have been updated more recently than their "
        "DocumentContent, then upsert english DocumentTranslation and TranslationFiles."
    )

    def reset_db_connections(self):
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

    def handle(self, **options):
        # Get any documents without content, or
        # documents that have been updated more recently than their content.
        documents = Document.objects.filter(
            Q(content__isnull=True) | Q(content__updated_at__lt=F("updated_at"))
        ).distinct()
        if len(documents) == 0:
            logger.info("All Documents have up to date content! Not performing OCR.")
            return
        else:
            logger.info(f"Performing OCR on {len(documents)} Document(s)...")

        extractions = list(MistralOCRService.metered_batch_extract(documents))
        now = datetime.now()
        extraction_config = ExtractionConfig.load()
        extraction_status = (
            "approved" if extraction_config.auto_approve_extractions else "waiting"
        )

        # Update DocumentContents
        contents_to_upsert = []
        for doc in documents:
            matched_extraction = {}
            for extr in extractions:
                if (
                    extr["document_type"] == doc.document_type
                    and extr["document_id"] == doc.document_id
                ):
                    matched_extraction = extr
                    break

            if not matched_extraction:
                continue

            contents_to_upsert.append(
                DocumentContent(
                    document=doc,
                    markdown=matched_extraction["markdown"],
                    approval_status=extraction_status,
                    updated_at=now,
                )
            )

        self.reset_db_connections()

        new_contents = DocumentContent.objects.bulk_create(
            contents_to_upsert,
            update_conflicts=True,
            unique_fields=["document"],
            update_fields=["markdown", "approval_status", "updated_at"],
        )

        # Update English DocumentTranslations
        english_translations_to_upsert = []
        for content in new_contents:
            english_translations_to_upsert.append(
                DocumentTranslation(
                    document_content=content,
                    language="en",
                    markdown=content.markdown,
                    approval_status=extraction_status,
                    updated_at=now,
                )
            )
        new_english_translations = DocumentTranslation.objects.bulk_create(
            english_translations_to_upsert,
            update_conflicts=True,
            unique_fields=["document_content", "language"],
            update_fields=["markdown", "approval_status", "updated_at"],
        )

        # Update TranslationFiles
        files_to_upsert = []
        for translation in new_english_translations:
            files_to_upsert.append(
                TranslationFile(
                    document_translation=translation,
                    file=None,
                    format="pdf",
                    updated_at=now,
                )
            )
        TranslationFile.objects.bulk_create(
            files_to_upsert,
            update_conflicts=True,
            unique_fields=["document_translation", "format"],
            update_fields=["updated_at"],
        )

        logger.info(
            "Documents with updated related content objects: "
            f"{len(new_contents)} out of {len(documents)}"
        )

        if extraction_config.auto_approve_extractions:
            for translation_config in TranslationConfig.objects.filter(
                config=extraction_config
            ):
                language_str = dict(DocumentTranslation.LANGUAGE_CHOICES)[
                    translation_config.language
                ]
                translation_approval_status = (
                    "approved"
                    if translation_config.auto_approve_translations
                    else "waiting"
                )
                logger.info(
                    f"Triggering {language_str} translations "
                    f"(approval_status={translation_approval_status})..."
                )
                call_command(
                    "batch_translate",
                    language_str,
                    approval_status=translation_approval_status,
                )

        logger.info("--- Finished! ---")
