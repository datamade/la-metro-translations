import base64
import io
import os
import re
import tempfile
import pypandoc

from PIL import Image as PILImage
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

        # Strip alt text so it doesn't appear as visible text if an image
        # fails to load. Weasyprint handles base64 data URIs natively.
        md_text = re.sub(r"!\[[^\]]+\]", "![]", md_text)

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

    def _image_uri_to_tempfile(self, media_type: str, b64data: str) -> str:
        """Decode a base64 image URI to a temporary PNG file, returning its path.

        Converts to PNG unconditionally unless the source is already PNG, so
        that RTF viewers render \\pngblip rather than \\jpegblip (which Pages
        and some other viewers ignore).
        """
        img_bytes = base64.b64decode(b64data)
        if media_type == "png":
            png_bytes = img_bytes
        else:
            png_buf = io.BytesIO()
            PILImage.open(io.BytesIO(img_bytes)).save(png_buf, format="PNG")
            png_bytes = png_buf.getvalue()

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(png_bytes)
        tmp.close()
        return tmp.name

    def _inject_rtf_font_table(self, rtf: str) -> str:
        """Splice font/encoding declarations into pandoc's existing RTF header.

        Pandoc emits a valid \\rtf1 header but omits a font table, which causes
        some viewers to fall back to a default font and ignore \\pngblip images.
        We insert a minimal font table immediately after the opening \\rtf1 block
        rather than prepending a second header.
        """
        font_table = (
            r"\ansi\ansicpg1252\cocoartf2636\cocoatextscaling0\cocoaplatform0"
            r"{\fonttbl\f0\fnil\fcharset0 Helvetica;}"
        )
        # Pandoc's header always starts with {\rtf1 followed by more control words.
        # Insert the font table right after \rtf1.
        if r"{\rtf1" not in rtf:
            raise DocumentTranslationConverterError("Unexpected RTF output from pandoc")
        return rtf.replace(r"{\rtf1", r"{\rtf1" + font_table, 1)

    def convert_to_rtf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""
        temp_files = []

        try:
            # RTF embeds images as hex, but pandoc only handles file paths — not
            # base64 data URIs. Decode each URI to a temp PNG so pandoc can read it.
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
        except Exception as e:
            raise DocumentTranslationConverterError(f"Conversion failed: {e}")
        finally:
            for path in temp_files:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        out_bytes = self._inject_rtf_font_table(output).encode("utf-8")
        out_io = io.BytesIO(out_bytes)

        filename = self.doc_translation.document_content.document.title
        language = self.doc_translation.language

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
