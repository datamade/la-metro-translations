import io
import os
import re
import pypandoc

from weasyprint import HTML

from django.core.files.uploadedfile import InMemoryUploadedFile

from la_metro_translations.models import TranslationFile, DocumentTranslation


class DocumentTranslationConverterError(Exception):
    pass


class DocumentTranslationConverter:
    def __init__(self, doc_translation: DocumentTranslation):
        if not isinstance(doc_translation, DocumentTranslation):
            raise DocumentTranslationConverterError(
                "Must pass a DocumentTranslation instance."
            )

        self.doc_translation = doc_translation
        self.doc_css_path = (
            os.path.dirname(os.path.abspath(__file__))
            + "/../static/css/converted_docs.css"
        )

    def convert_to_pdf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""

        # Strip alt text.
        md_text = re.sub(r"!\[[^]]+\]", "![]", md_text)

        try:
            # Pypandoc requires PDFs to be written to the filesystem so
            # we can first convert the markdown to HTML and then use
            # weasyprint to convert the HTML to PDF in memory
            html = pypandoc.convert_text(
                md_text, to="html", format="markdown-yaml_metadata_block"
            )
            pdf_bytes = HTML(string=html, base_url=".").write_pdf(
                stylesheets=[self.doc_css_path]
            )
        except Exception as e:
            raise DocumentTranslationConverterError(f"Conversion failed: {e}")

        filename = self.doc_translation.document_content.document.title
        language = self.doc_translation.language

        buffer = io.BytesIO()
        buffer.write(pdf_bytes)
        buffer.seek(0)

        django_file = InMemoryUploadedFile(
            file=buffer,
            field_name="file",
            name=f"{filename}_{language}.pdf",
            content_type="application/pdf",
            size=buffer.getbuffer().nbytes,
            charset=None,
        )

        return TranslationFile(
            document_translation=self.doc_translation, format="pdf", file=django_file
        )

    def convert_to_rtf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""

        md_text = re.sub(r"!\[.*?\]\(data:image/[^)]+\)", "Image", md_text)

        try:
            output = pypandoc.convert_text(
                md_text, to="rtf", format="markdown-yaml_metadata_block"
            )
            out_bytes = (
                output
                if isinstance(output, (bytes, bytearray))
                else str(output).encode("utf-8")
            )
        except Exception as e:
            raise DocumentTranslationConverterError(f"Conversion failed: {e}")

        filename = self.doc_translation.document_content.document.title
        language = self.doc_translation.language

        # Add encoding strings to make sure file renders correctly
        pre_bytes = (
            r"{\rtf1\ansi\ansicpg1252\cocoartf2636\cocoatextscaling0"
            r"\cocoaplatform0{\fonttbl\f0\fnil\fcharset0 Helvetica;}"
        ).encode("utf-8")
        post_bytes = r"}".encode("utf-8")
        final_bytes = pre_bytes + out_bytes + post_bytes

        out_io = io.BytesIO(final_bytes)

        django_file = InMemoryUploadedFile(
            file=out_io,
            field_name="file",
            name=f"{filename}_{language}.rtf",
            content_type="application/rtf",
            size=out_io.getbuffer().nbytes,
            charset="utf-8",
        )

        return TranslationFile(
            document_translation=self.doc_translation, format="rtf", file=django_file
        )
