import json
import re
import time
import logging

from abc import ABC, abstractmethod
from typing import Union, List

from django.conf import settings
from django.db.models import QuerySet

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

from la_metro_translations.models import Document

logger = logging.getLogger(__name__)
with open("la_metro_translations/prompt.txt") as f:
    SYSTEM_MESSAGE = f.read()


class TranslationService(ABC):
    @staticmethod
    @abstractmethod
    def translate_text(document: Document, dest_language: str) -> str | None:
        pass

    @staticmethod
    @abstractmethod
    def batch_translate(documents: list, dest_language: str) -> list:
        pass


class MistralTranslationService(TranslationService):
    @staticmethod
    def translate_text(document: Document, dest_language: str) -> str | None:
        """
        Translates the markdown of a single source document to a destination language
        using Mistral, while aiming to preserve markdown.

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

    @staticmethod
    def batch_translate(documents: Union[QuerySet, List[Document]], dest_language: str):
        return
