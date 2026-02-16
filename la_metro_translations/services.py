import json
import re
import time
import logging

from django.conf import settings
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from la_metro_translations.models import Document

logger = logging.getLogger(__name__)
with open("la_metro_translations/prompt.txt") as f:
    SYSTEM_MESSAGE = f.read()


class OCRService:
    @staticmethod
    def extract_text(doc_url: str) -> str | None:
        """
        Passes a url for a document to Mistral's OCR service,
        and returns the doc's extracted text
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={"type": "document_url", "document_url": doc_url},
                table_format="markdown",
                include_image_base64=True,
            )
        except SDKError as e:
            logger.warning(
                "Error occurred when OCR'ing document. " f"Document url: {doc_url}"
            )
            logger.warning(e)
            logger.warning("Unable to OCR. Skipping...")
            return

        data = json.loads(ocr_response.model_dump_json())

        try:
            pages = data["pages"]
        except KeyError as e:
            logger.warning(
                "Error occurred when OCR'ing document. " f"Document url: {doc_url}"
            )
            logger.warning(e)
            logger.warning("Response from model:")
            logger.warning(data)
            logger.warning("Unable to OCR. Skipping...")
            return

        doc_text = ""

        for page in pages:
            markdown = page["markdown"]

            # Unescaped dollar signs cause unintended math formatting
            markdown = markdown.replace("$", "\\$")

            # Insert extracted tables and images
            for table in page["tables"]:
                table_content = table["content"]

                # Replace bracketed version
                markdown = markdown.replace(f"[{table['id']}]", table_content)
                # Remove parenthesesed version
                markdown = markdown.replace(f"({table['id']})", "")

            for image in page["images"]:
                # Leave the bracketed version, but replace parenthesesed version
                markdown = markdown.replace(
                    f"({image['id']})", f"({image['image_base64']})"
                )

            doc_text += f"{markdown}\n\nEnd of Page {page['index']+1}\n\n"

        return doc_text


class TranslationService:
    @staticmethod
    def translate_text(document: Document, dest_language: str) -> str | None:
        """
        Translates the markdown of a source doc to a destination language using Mistral,
        while aiming to preserve markdown.

        Any base64 encoded images within the string are removed and cached
        before translation, then inserted back in after. This cuts down on
        translation time and cost.
        """
        start_time = time.time()
        formatted_lang = dest_language.title()
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        # Find image tags containing base64 up to and including first close-parentheses
        img_pattern = r"\!\[img\-\d+\.jpeg\]\(data\:image\/jpeg\;base64.+?(?:\))"
        images_cache = {}
        source_text = document.content.markdown
        modded_source_text = source_text

        image_tags = re.findall(img_pattern, source_text)
        for i in image_tags:
            # Cache image tag
            img_label = i[i.find("!") : i.find("]") + 1]
            img_data = i[i.find("(") : i.find(")") + 1]
            images_cache[img_label] = img_data

            # Replace entire image tag with a placeholder, ex. "![img-0.jpeg]()"
            modded_source_text = modded_source_text.replace(i, f"{img_label}()")

        try:
            chat_response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MESSAGE,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Translate the following text to "
                            f"{formatted_lang}: {modded_source_text}"
                        ),
                    },
                ],
            )
        except SDKError as e:
            logger.warning(
                f"Error occurred when translating document to {formatted_lang}. "
                f"Document ID in BoardAgendas: {document.document_id} ; "
                f"Document url: {document.source_url}"
            )
            logger.warning(e)
            logger.warning("Unable to translate. Skipping...")
            return

        data = json.loads(chat_response.model_dump_json())

        try:
            translated_string = data["choices"][0]["message"]["content"]
        except KeyError as e:
            logger.warning(
                f"Error occurred when translating document to {formatted_lang}. "
                f"Document ID in BoardAgendas: {document.document_id} ; "
                f"Document url: {document.source_url}"
            )
            logger.warning(e)
            logger.warning("Response from model:")
            logger.warning(data)
            logger.warning("Unable to translate. Skipping...")
            return

        # Reinsert images where they belong
        for label in images_cache.keys():
            full_image = label + images_cache[label]
            if label not in translated_string:
                logger.warning(
                    f"Warning: {label} is missing in the {formatted_lang} translation"
                )
            else:
                translated_string = translated_string.replace(f"{label}()", full_image)

        logger.info("--- %s seconds to complete ---" % (time.time() - start_time))
        return translated_string
