import logging

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
    Extract text from documents that need content, and create/update related objects."
    """

    help = (
        "Perform OCR text extraction on all Documents that either do not have a "
        "related DocumentContent object or have been updated more recently than their "
        "DocumentContent, then create english DocumentTranslation and TranslationFiles."
    )

    def handle(self, *args, **kwargs):
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

        extractions = MistralOCRService.batch_extract(documents)
        contents_updated = 0

        for result in extractions:
            document = Document.objects.get(
                document_type=result["document_type"],
                document_id=result["document_id"],
            )
            document_content, _ = DocumentContent.objects.update_or_create(
                document=document, defaults={"markdown": result["markdown"]}
            )
            english_translation, _ = DocumentTranslation.objects.update_or_create(
                document_content=document_content,
                language="english",
                defaults={"markdown": document_content.markdown},
            )
            TranslationFile.objects.update_or_create(
                format="pdf",
                url=document.source_url,
                document_translation=english_translation,
            )
            contents_updated += 1

        logger.info(
            "Documents with new related content objects: "
            f"{contents_updated} out of {len(documents)}"
        )
        logger.info("--- Finished! ---")
