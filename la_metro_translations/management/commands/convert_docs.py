import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from la_metro_translations.models import DocumentTranslation, TranslationFile
from la_metro_translations.services import (
    DocumentTranslationConverter,
    DocumentTranslationConverterError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates RTF and PDF translation files"

    def handle(self, *args, **options):
        """
        Creates up to date RTF and PDF translation files for those that need them.
        """
        files_to_create = []

        # Create RTFs
        up_to_date_rtfs = TranslationFile.objects.filter(
            format="rtf",
            updated_at__gte=OuterRef("updated_at"),
            document_translation=OuterRef("pk"),
        )

        eng_rtfs_to_create = DocumentTranslation.objects.filter(language="en").exclude(
            pk__in=Subquery(up_to_date_rtfs.values("document_translation"))
        )

        non_eng_rtfs_to_create = DocumentTranslation.objects.exclude(
            language="en"
        ).exclude(pk__in=Subquery(up_to_date_rtfs.values("document_translation")))

        all_rtfs_to_create = eng_rtfs_to_create.union(non_eng_rtfs_to_create)
        for doc in all_rtfs_to_create:
            try:
                rtf_file = DocumentTranslationConverter(doc).convert_to_rtf()
            except DocumentTranslationConverterError as e:
                logger.error(f"Error while converting {doc}: {e}")
            else:
                files_to_create.append(rtf_file)

        # Create PDFs
        up_to_date_pdfs = TranslationFile.objects.filter(
            format="pdf",
            updated_at__gte=OuterRef("updated_at"),
            document_translation=OuterRef("pk"),
        )

        non_eng_pdfs_to_create = DocumentTranslation.objects.exclude(
            language="en"
        ).exclude(pk__in=Subquery(up_to_date_pdfs.values("document_translation")))
        for doc in non_eng_pdfs_to_create:
            try:
                pdf_file = DocumentTranslationConverter(doc).convert_to_pdf()
            except DocumentTranslationConverterError as e:
                logger.error(f"Error while converting {doc}: {e}")
            else:
                files_to_create.append(pdf_file)

        if not files_to_create:
            logger.info("All translations have up to date RTFs and PDFs!")
            return

        for file in files_to_create:
            file.updated_at = datetime.now()

        TranslationFile.objects.bulk_create(
            files_to_create,
            update_conflicts=True,
            unique_fields=["document_translation", "format"],
            update_fields=["file", "updated_at"],
        )

        logger.info(
            f"Created a total of {len(files_to_create)} up to date rtfs and pdfs"
        )
        logger.info("--- Finished! ---")
