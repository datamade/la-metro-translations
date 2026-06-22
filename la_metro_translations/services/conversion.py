import base64
import io
import os
import re
import tempfile
import pypandoc

from weasyprint import HTML

from django.core.files.uploadedfile import InMemoryUploadedFile

from la_metro_translations.models import (
    Disclaimer,
    TranslationFile,
    DocumentTranslation,
)


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

    def _prepend_disclaimer(self, language, text):
        try:
            disclaimer = Disclaimer.objects.get(language=language)
        except Disclaimer.DoesNotExist:
            raise DocumentTranslationConverterError(
                f"No disclaimer found for target language: {language}"
            )
        formatted_disclaimer = f"{disclaimer.disclaimer_text}\n\n---\n\n"
        return formatted_disclaimer + text

    def convert_to_pdf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""

        # Strip alt text.
        md_text = re.sub(r"!\[[^]]+\]", "![]", md_text)

        language = self.doc_translation.language
        md_text = self._prepend_disclaimer(language, md_text)

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

    def _image_uri_to_tempfile(self, media_type: str, b64data: str) -> str:
        """Decode a base64 image URI to a temporary file, returning its path."""
        img_bytes = base64.b64decode(b64data)
        tmp = tempfile.NamedTemporaryFile(suffix=f".{media_type}", delete=False)
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name

    def convert_to_rtf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""
        temp_files = []

        language = self.doc_translation.language
        md_text = self._prepend_disclaimer(language, md_text)

        try:
            # RTF embeds images as hex, but pandoc only handles file paths — not
            # base64 data URIs. Decode each URI to a temp file so pandoc can read it.
            pattern = r"!\[.*?\]\(data:image/(\w+);base64,([^)]+)\)"

            def replace_with_tempfile(match):
                media_type = match.group(1)
                b64data = match.group(2)
                path = self._image_uri_to_tempfile(media_type, b64data)
                temp_files.append(path)
                # Use empty alt text so pandoc doesn't emit the filename as a
                # visible text paragraph below the embedded \pict block.
                return f"![]({path})"

            md_text = re.sub(pattern, replace_with_tempfile, md_text)

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
        finally:
            for path in temp_files:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        filename = self.doc_translation.document_content.document.title

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
