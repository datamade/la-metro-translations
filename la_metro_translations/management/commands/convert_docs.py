from django.core.management.base import BaseCommand

from la_metro_translations.models import DocumentTranslation, TranslationFile
from la_metro_translations.services import DocumentTranslationConverter


class Command(BaseCommand):
    help = "Creates RTF and PDF translation files"

    def handle(self, *args, **options):
        files_to_create = []

        eng_docs_to_process = DocumentTranslation.objects.filter(
            language="english"
        ).exclude(files__format="rtf")

        for doc in eng_docs_to_process:
            files_to_create.append(DocumentTranslationConverter(doc).convert_to_rtf())

        non_eng_rtfs_to_create = DocumentTranslation.objects.exclude(
            language="english"
        ).exclude(files__format="rtf")
        for doc in non_eng_rtfs_to_create:
            files_to_create.append(DocumentTranslationConverter(doc).convert_to_rtf())

        non_eng_pdfs_to_create = DocumentTranslation.objects.exclude(
            language="english"
        ).exclude(files__format="pdf")
        for doc in non_eng_pdfs_to_create:
            files_to_create.append(DocumentTranslationConverter(doc).convert_to_pdf())

        TranslationFile.objects.bulk_create(files_to_create)
