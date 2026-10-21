import io
import os
import re
import logging
from django.db.models import QuerySet
import pypandoc

from weasyprint import HTML

from django.core.files.uploadedfile import InMemoryUploadedFile

from la_metro_translations.management.commands.text_utils import (
    BOILERPLATE,
    BoilerplateError,
    replace_placeholder_with_pretranslated_text,
    HR,
)
from la_metro_translations.models import (
    TranslationFile,
    DocumentTranslation,
)

logger = logging.getLogger(__name__)


class DocumentTranslationConverterError(Exception):
    pass


class DocumentTranslationConverter:
    def __init__(
        self, doc_translation: DocumentTranslation, standard_translations: QuerySet
    ):
        if not isinstance(doc_translation, DocumentTranslation):
            raise DocumentTranslationConverterError(
                "Must pass a DocumentTranslation instance."
            )

        self.doc_translation = doc_translation
        self.doc_css_path = (
            os.path.dirname(os.path.abspath(__file__))
            + "/../static/css/converted_docs.css"
        )
        self.is_agenda = (
            doc_translation.document_content.document.entity_type == "event"
        )
        self.standard_translations = standard_translations

    def _prepend_disclaimer(self, language, text):
        # All documents also get "translated" into English with no disclaimer
        # Shortcircuit in that case
        if language == "eng":
            return text

        pretranslated = self.standard_translations.get(language=language)
        if pretranslated is None:
            raise DocumentTranslationConverterError(
                f"No standard translations exist for target language: {language}"
            )

        disclaimer = pretranslated.disclaimer_text
        if disclaimer == "":
            logger.info(f"No disclaimer found for {language}")
            return text
        else:
            formatted_disclaimer = f"{disclaimer}{HR}"
            return formatted_disclaimer + text

    def _replace_boilerplate(self, language, text):

        for key, value in BOILERPLATE.items():

            pretranslated = self.standard_translations.get(language=language)
            if pretranslated is None:
                raise DocumentTranslationConverterError(
                    f"No standard translations exist for target language: {language}"
                )

            boilerplate = getattr(pretranslated, key)
            if boilerplate == "":  # fields default to ""
                raise DocumentTranslationConverterError(
                    f"No replacement boilerplate found for {language} {key}"
                )

            if "agenda_pages_2_and_3" in key and self.is_agenda:
                try:
                    text = replace_placeholder_with_pretranslated_text(
                        text,
                        boilerplate=boilerplate,
                        placeholder=value["placeholder"],
                    )
                except BoilerplateError as err:
                    logger.warning(err)
                    logger.warning(
                        "Could not find placeholder %r in document. Agenda pages 2 and 3"
                        "appended to beginning of the document instead.",
                        value["placeholder"],
                    )
                    text = boilerplate + HR + text

        return text

    def convert_to_pdf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""

        # Strip alt text.
        md_text = re.sub(r"!\[[^]]+\]", "![]", md_text)

        language = self.doc_translation.language
        md_text = self._replace_boilerplate(language, md_text)
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

    def insert_image_placeholder_text(self, text):

        IMAGE_REMOVED_MAP = {
            "eng": "Image removed",
            "spa": "Imagen eliminada",
            "zho-cn": "图片已删除",
            "zho-tw": "圖片已刪除",
            "kor": "이미지가 삭제됨",
            "hye": "Նկարը հեռացվել է",
            "hyw": "Նկարը ջնջվել է",
            "vie": "Hình ảnh đã bị xóa",
            "rus": "Изображение удалено",
            "jpn": "画像が削除されました",
        }

        METRO_LOGO_MAP = {
            "eng": "Metro logo removed",
            "spa": "Imagen del logotipo de Metro",
            "zho-cn": "Metro标志",
            "zho-tw": "Metro標誌",
            "kor": "Metro 로고 이미지",
            "hye": "Metro-ի լոգոյի պատկեր",
            "hyw": "Մեթրոյի լոկոյի պատկեր",
            "vie": "Hình ảnh logo của Metro",
            "rus": "Изображение логотипа Метро",
            "jpn": "メトロのロゴ画像",
        }

        # For agendas, mark the first image as the Metro logo
        language = str(self.doc_translation.language)
        image_removed_text = IMAGE_REMOVED_MAP[language]
        metro_logo_text = METRO_LOGO_MAP[language]
        if self.is_agenda:
            return re.sub(
                r"!\[(.*?)\]\(data:image/[^)]+\)",
                lambda m: (
                    metro_logo_text
                    if "img-0" in m.group(1).lower()
                    else image_removed_text
                ),
                text,
            )

        # For board reports, just replace all images with placeholder
        else:
            return re.sub(r"!\[.*?\]\(data:image/[^)]+\)", image_removed_text, text)

    def convert_to_rtf(self) -> TranslationFile:
        md_text = self.doc_translation.markdown or ""

        md_text = self.insert_image_placeholder_text(md_text)

        language = self.doc_translation.language
        md_text = self._replace_boilerplate(language, md_text)
        md_text = self._prepend_disclaimer(language, md_text)

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
