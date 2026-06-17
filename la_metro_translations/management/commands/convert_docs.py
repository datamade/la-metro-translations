import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery
from django.db import connections
from tqdm import tqdm

from la_metro_translations.models import DocumentTranslation, TranslationFile
from la_metro_translations.services import (
    DocumentTranslationConverter,
    DocumentTranslationConverterError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates RTF and PDF translation files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--document_translation",
            type=int,
            default=None,
            help="The ID of the document translation to convert.",
        )

    def reset_db_connections(self):
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

    def handle(self, *args, **options):
        """
        Creates up to date RTF and PDF translation files for those that need them.
        """
        document_translation_id = options["document_translation"]

        if document_translation_id:
            self.convert_doc(document_translation_id)

        else:
            self.convert_docs()

    def convert_doc(self, document_translation_id):
        doc = DocumentTranslation.objects.get(id=document_translation_id)
        converter = DocumentTranslationConverter(doc)
        files_to_create = [converter.convert_to_rtf()]
        if doc.language != "eng":
            files_to_create.append(converter.convert_to_pdf())
        self.bulk_create_translation_files(files_to_create)

    def convert_docs(self):
        files_to_create = []
        chunk_size = 500

        # Create RTFs
        up_to_date_rtfs = TranslationFile.objects.filter(
            format="rtf",
            updated_at__gte=OuterRef("updated_at"),
            document_translation=OuterRef("pk"),
        )

        logger.info("Checking for translations that need up to date RTFs...")
        rtf_qs = DocumentTranslation.objects.exclude(
            pk__in=Subquery(up_to_date_rtfs.values("document_translation")),
        ).select_related("document_content__document")
        for doc in tqdm(rtf_qs.iterator(chunk_size=chunk_size), total=rtf_qs.count()):
            self.meter_files_in_memory(files_to_create, chunk_size)
            try:
                rtf_file = DocumentTranslationConverter(doc).convert_to_rtf()
            except DocumentTranslationConverterError as e:
                logger.error(f"Error while converting {doc} to RTF: {e}")
            else:
                files_to_create.append(rtf_file)

        # Create PDFs
        up_to_date_pdfs = TranslationFile.objects.filter(
            format="pdf",
            updated_at__gte=OuterRef("updated_at"),
            document_translation=OuterRef("pk"),
        )

        logger.info("Checking for translations that need up to date PDFs...")
        pdf_qs = (
            DocumentTranslation.objects.exclude(
                pk__in=Subquery(up_to_date_pdfs.values("document_translation"))
            )
            .exclude(language="eng")
            .select_related("document_content__document")
        )
        for doc in tqdm(pdf_qs.iterator(chunk_size=chunk_size), total=pdf_qs.count()):
            self.meter_files_in_memory(files_to_create, chunk_size)
            try:
                pdf_file = DocumentTranslationConverter(doc).convert_to_pdf()
            except DocumentTranslationConverterError as e:
                logger.error(f"Error while converting {doc} to PDF: {e}")
            else:
                files_to_create.append(pdf_file)

        if not files_to_create:
            logger.info("All translations have up to date RTFs and PDFs!")
            return

        self.reset_db_connections()
        self.bulk_create_translation_files(files_to_create)

        logger.info("--- Finished! ---")

    def bulk_create_translation_files(self, files_to_create):
        for file in files_to_create:
            file.updated_at = datetime.now()

        logger.info("Storing files...")
        TranslationFile.objects.bulk_create(
            files_to_create,
            update_conflicts=True,
            unique_fields=["document_translation", "format"],
            update_fields=["file", "updated_at"],
        )

        logger.info(f"Created a total of {len(files_to_create)} up to date files")

    def meter_files_in_memory(self, files_to_create, chunk_size):
        """
        Create files and empty the queue if we've exceeded a reasonable amount
        of files in memory. Prevents Heroku "memory quota vastly exceeded" errors.
        """
        if len(files_to_create) >= chunk_size:
            self.reset_db_connections()
            self.bulk_create_translation_files(files_to_create)
            del files_to_create[:]
