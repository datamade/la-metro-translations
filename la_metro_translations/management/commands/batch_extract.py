import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q, F

from la_metro_translations.models import (
    Document,
    DocumentContent,
    DocumentTranslation,
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
                    updated_at=now,
                )
            )
        new_contents = DocumentContent.objects.bulk_create(
            contents_to_upsert,
            update_conflicts=True,
            unique_fields=["document"],
            update_fields=["markdown", "updated_at"],
        )

        # Update English DocumentTranslations
        english_translations_to_upsert = []
        for content in new_contents:
            english_translations_to_upsert.append(
                DocumentTranslation(
                    document_content=content,
                    language="english",
                    markdown=content.markdown,
                    updated_at=now,
                )
            )
        new_english_translations = DocumentTranslation.objects.bulk_create(
            english_translations_to_upsert,
            update_conflicts=True,
            unique_fields=["document_content", "language"],
            update_fields=["markdown", "updated_at"],
        )

        # Update TranslationFiles
        files_to_upsert = []
        for translation in new_english_translations:
            files_to_upsert.append(
                TranslationFile(
                    document_translation=translation,
                    url=translation.document_content.document.source_url,
                    format="pdf",
                )
            )
        TranslationFile.objects.bulk_create(
            files_to_upsert,
            update_conflicts=True,
            unique_fields=["document_translation", "format"],
            update_fields=["url"],
        )

        logger.info(
            "Documents with updated related content objects: "
            f"{len(new_contents)} out of {len(documents)}"
        )
        logger.info("--- Finished! ---")
