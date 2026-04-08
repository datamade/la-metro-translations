import json
import re
import time
import logging
import sys

from abc import ABC, abstractmethod
from typing import Union, List, Generator
from .utils import BatchUtils

from django.conf import settings
from django.db.models import QuerySet

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

from la_metro_translations.models import Document, DocumentContent

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
    def batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], dest_language: str
    ) -> Generator[dict] | None:
        pass


class MistralTranslationService(TranslationService):
    @staticmethod
    def translate_text(content: DocumentContent, dest_language: str) -> str | None:
        """
        Translates the markdown of a single source document's content to a
        destination language using Mistral, while aiming to preserve markdown.

        Any base64 encoded images within the string are removed and cached
        before translation, then inserted back in after. This cuts down on
        translation time and cost.
        """
        start_time = time.time()
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        document_id = content.document.document_id
        source_url = content.document.source_url

        modded_text, images_cache = MistralTranslationService.cache_images(
            content.markdown
        )

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
                            f"{dest_language}: {modded_text}"
                        ),
                    },
                ],
            )
        except SDKError as e:
            logger.warning(
                f"Error occurred when translating document to {dest_language}. "
                f"Document ID in BoardAgendas: {document_id} ; "
                f"Document url: {source_url}"
            )
            logger.warning(e)
            logger.warning("Unable to translate. Skipping...")
            return

        data = json.loads(chat_response.model_dump_json())

        try:
            translated_text = data["choices"][0]["message"]["content"]
        except KeyError as e:
            logger.warning(
                f"Error occurred when translating document to {dest_language}. "
                f"Document ID in BoardAgendas: {document_id} ; "
                f"Document url: {source_url}"
            )
            logger.warning(e)
            logger.warning("Response from model:")
            logger.warning(data)
            logger.warning("Unable to translate. Skipping...")
            return

        # Reinsert images where they belong
        translation_with_images = MistralTranslationService.reinsert_cached_images(
            translated_text, images_cache, dest_language, document_id
        )

        logger.info("--- %s seconds to complete ---" % (time.time() - start_time))
        return translation_with_images

    @staticmethod
    def batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], language: str
    ) -> Generator[dict] | None:
        """
        Create a single batch job request to translate multiple documents into
        one language, and return the responses.
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        all_content_images = {}
        timeout_hours = 23

        # Create batch entries
        entries = []
        for content in contents:
            modded_text, images_cache = MistralTranslationService.cache_images(
                source_text=content.markdown
            )
            related_doc = content.document
            doc_custom_id = f"{related_doc.document_type}:{related_doc.document_id}"
            all_content_images[doc_custom_id] = images_cache

            entries.append(
                {
                    # ex. "bill_version:<some-uid>"
                    "custom_id": doc_custom_id,
                    "body": {
                        "messages": [
                            {
                                "role": "system",
                                "content": SYSTEM_MESSAGE,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Translate the following text to "
                                    f"{language}: {modded_text}"
                                ),
                            },
                        ],
                    },
                }
            )

        # Start batch job
        created_job = BatchUtils.start_batch_job(
            client=client,
            entries=entries,
            model="mistral-small-latest",
            endpoint="/v1/chat/completions",
            timeout_hours=timeout_hours,
        )

        # Monitor batch job
        response = BatchUtils.check_batch_job(
            client=client, job_id=created_job.id, timeout_hours=timeout_hours
        )
        if not response:
            return

        # Reinsert images into each translation
        for line in response.iter_lines():
            translation_response = json.loads(line)

            document_type = translation_response["custom_id"].split(":")[0]
            document_id = translation_response["custom_id"].split(":")[1]
            response_body = translation_response["response"]["body"]
            translated_text = response_body["choices"][0]["message"]["content"]

            # Match this translation with its images using a key with
            # the same format as the doc_custom_id set up earlier
            matched_images = all_content_images[f"{document_type}:{document_id}"]

            translation_with_images = MistralTranslationService.reinsert_cached_images(
                translated_text, matched_images, language, document_id
            )
            translation = {
                "document_type": document_type,
                "document_id": document_id,
                "markdown": translation_with_images,
            }

            yield translation

    @staticmethod
    def cache_images(source_text: str) -> tuple[str, dict]:
        """
        Remove images from the extracted text, and replace them with placeholders.
        Then return the modified text, and a dict of all images within
        to be reinserted later.
        """

        # Find image tags containing base64 up to and including first close-parentheses
        img_pattern = r"\!\[img\-\d+\.jpeg\]\(data\:image\/jpeg\;base64.+?(?:\))"
        images_cache = {}
        modded_source_text = source_text

        image_tags = re.findall(img_pattern, source_text)
        for i in image_tags:
            # Cache image tag
            img_label = i[i.find("!") : i.find("]") + 1]
            img_data = i[i.find("(") : i.find(")") + 1]
            images_cache[img_label] = img_data

            # Replace entire image tag with a placeholder, ex. "![img-0.jpeg]()"
            modded_source_text = modded_source_text.replace(i, f"{img_label}()")

        return modded_source_text, images_cache

    @staticmethod
    def reinsert_cached_images(
        translated_text: str, images_cache: dict, language: str, doc_id: str
    ) -> str:
        """
        Reinsert removed/cached images back into the translated document's content.
        """

        text_with_images = translated_text
        for label in images_cache.keys():
            full_image = label + images_cache[label]
            if label not in translated_text:
                logger.warning(
                    f"Warning: {label} is now missing in the {language} translation "
                    f"of Document with a 'document_id' of '{doc_id}'"
                )
            else:
                text_with_images = text_with_images.replace(f"{label}()", full_image)

        return text_with_images

    @staticmethod
    def metered_batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], language: str
    ) -> Generator[dict] | None:
        """
        Create multiple batch job requests to translate documents,
        and return the responses. The batches are split up when
        the total size of the strings involved for all requests reaches a set maximum.
        """
        max_batch_size = 30000000  # 30MB
        sys_msg_size = sys.getsizeof(SYSTEM_MESSAGE)
        curr_batch_size = 0
        curr_batch = []
        batch_num = 1

        for i, content in enumerate(contents):
            # Check size of upcoming request
            curr_batch_size += sys.getsizeof(content.markdown) + sys_msg_size
            curr_batch.append(content)

            # Send batch if we've exceeded max size or at the end of the list
            if curr_batch_size >= max_batch_size or i + 1 >= len(contents):
                logger.info(
                    f"Processing batch #{batch_num} with {len(curr_batch)} contents..."
                )
                yield from MistralTranslationService.batch_translate(
                    curr_batch, language
                )
                curr_batch_size = 0
                curr_batch = []
                batch_num += 1
