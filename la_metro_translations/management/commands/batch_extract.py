import logging

from django.core.management.base import BaseCommand

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
    Extract text from documents that still need content, and create related objects."
    """

    help = (
        "Perform OCR text extraction on all Documents that do not yet have "
        "a related DocumentContent object, then create an"
        "English DocumentTranslation and TranslationFiles."
    )

    def handle(self, *args, **kwargs):
        documents = Document.objects.filter(content__isnull=True)
        if len(documents) == 0:
            logger.info("All Documents currently have content! Not performing OCR.")
            return
        else:
            logger.info(f"Performing OCR on {len(documents)} Document(s)...")

        extractions = MistralOCRService.batch_extract(documents)
        contents_created = 0
        extractions_skipped = 0

        for result in extractions:
            try:
                document = Document.objects.get(
                    document_type=result["document_type"],
                    document_id=result["document_id"],
                )
            except Document.DoesNotExist:
                logger.error(
                    "Document.DoesNotExist: Could not find a matching Document with "
                    f"document_type={result['document_type']} and "
                    f"document_id={result['document_id']}; Skipping..."
                )
                extractions_skipped += 1
                continue

            document_content = DocumentContent.objects.create(
                markdown=result["markdown"], document=document
            )
            english_translation = DocumentTranslation.objects.create(
                markdown=document_content.markdown,
                language="english",
                document_content=document_content,
            )
            TranslationFile.objects.create(
                format="pdf",
                url=document.source_url,
                document_translation=english_translation,
            )
            contents_created += 1
            # TODO: create rtf and md versions of the file, upload to s3, store urls

        failed_documents = documents.filter(content__isnull=True)
        logger.info(f"Documents with new related content objects: {contents_created}")
        if extractions_skipped:
            logger.error(f"Extractions w/o matching documents: {extractions_skipped}")
        if len(failed_documents):
            logger.error(
                "Documents that still do not have content objects: "
                f"{len(failed_documents)}"
            )

        logger.info("--- Finished! ---")
