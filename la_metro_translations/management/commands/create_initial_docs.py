import io

from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone

from la_metro_translations.models import (
    Document,
    DocumentContent,
    DocumentTranslation,
    TranslationFile,
)


class Command(BaseCommand):
    help = "Create initial translation objects in the DB."

    def create_translation_file(
        self, doc_translation: DocumentTranslation
    ) -> TranslationFile:
        md_text = doc_translation.markdown or ""

        base_filename = doc_translation.document_content.document.title
        language = doc_translation.language
        filename = f"{base_filename}_{language}.md"

        fileobj = io.BytesIO(md_text.encode("utf-8"))

        django_file = InMemoryUploadedFile(
            file=fileobj,
            field_name="file",
            name=filename,
            content_type="text/markdown",
            size=fileobj.getbuffer().nbytes,
            charset=None,
        )

        return TranslationFile.objects.create(
            document_translation=doc_translation, format="md", file=django_file
        )

    def handle(self, *args, **options):
        # Clear database
        for file in TranslationFile.objects.all():
            file.delete()

        Document.objects.all().delete()

        d1 = Document.objects.create(
            document_type="bill_document",
            document_id="test-doc-1",
            title="2015-1915 - FINANCIAL ADVISOR BENCH UTILIZATION REPORT",
            source_url="https://example.org/test1.pdf",
            created_at=timezone.now(),
            updated_at=timezone.now(),
            entity_type="bill",
            entity_id="test-entity-1",
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created Document {d1.document_id} (pk={d1.pk})")
        )

        d2 = Document.objects.create(
            document_type="event_document",
            document_id="test-doc-2",
            title="Operations, Safety, and Customer Experience Committee - 2025-09-18",
            source_url="https://example.org/test2.pdf",
            created_at=timezone.now(),
            updated_at=timezone.now(),
            entity_type="event",
            entity_id="test-entity-2",
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created Document {d2.document_id} (pk={d2.pk})")
        )

        with open(f"la_metro_translations/fixtures/{d1.title}.md") as f:
            text = " ".join(f.readlines())
            c1 = DocumentContent.objects.create(
                document=d1,
                markdown=text,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created DocumentContent (pk={c1.pk}) for"
                    f" Document {d1.document_id}"
                )
            )

        with open(f"la_metro_translations/fixtures/{d2.title}.md") as f:
            text = " ".join(f.readlines())
            c2 = DocumentContent.objects.create(
                document=d2,
                markdown=text,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created DocumentContent (pk={c2.pk}) for"
                    f" Document {d2.document_id}"
                )
            )

        # Create translation instances
        translations = []
        for content in (c1, c2):
            te = DocumentTranslation.objects.create(
                document_content=content,
                language="en",
                markdown=f"# {content.document.title} (EN)\n\nTranslated EN",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created DocumentTranslation (EN) pk={te.pk}")
            )
            ts = DocumentTranslation.objects.create(
                document_content=content,
                language="sp",
                markdown=f"# {content.document.title} (ES)\n\nTraducido ES",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created DocumentTranslation (ES) pk={ts.pk}")
            )
            translations.extend([te, ts])

        # Create translation files
        for trans in translations:
            tf = self.create_translation_file(trans)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created TranslationFile (md) pk={tf.pk} for translation"
                    f" pk={trans.pk}"
                )
            )
