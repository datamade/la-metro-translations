import json
import re
import time
import logging
import sys

from abc import ABC, abstractmethod
from typing import Union, List, Generator
from .utils import BatchUtils, MAX_BATCH_SIZE_BYTES

from django.conf import settings
from django.db.models import QuerySet

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

from la_metro_translations.models import DocumentContent

logger = logging.getLogger(__name__)
with open("la_metro_translations/prompt.txt") as f:
    SYSTEM_MESSAGE = f.read()


class TranslationService(ABC):
    @staticmethod
    @abstractmethod
    def translate_text(content: DocumentContent, dest_language: str) -> str | None:
        pass

    @staticmethod
    @abstractmethod
    def batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], dest_language: str
    ) -> Generator[dict] | None:
        pass

    @staticmethod
    @abstractmethod
    def metered_batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], language: str
    ) -> Generator[dict] | None:
        pass


class DummyTranslationService(TranslationService):
    @staticmethod
    def translate_text(content, dest_language):
        return f"{dest_language} content:\n{content.markdown}"

    @staticmethod
    def batch_translate(contents, dest_language):
        for content in contents:
            yield {
                "document_type": content.document.document_type,
                "document_id": content.document.document_id,
                "markdown": DummyTranslationService.translate_text(
                    content, dest_language
                ),
            }

    @staticmethod
    def metered_batch_translate(contents, dest_language):
        yield from DummyTranslationService.batch_translate(contents, dest_language)


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

        # Create batch entries, set up result map
        entries = []
        result_map = {}
        for content in contents:
            modded_text, images_cache = MistralTranslationService.cache_images(
                source_text=content.markdown
            )
            related_doc = content.document
            doc_custom_id = f"{related_doc.document_type}:{related_doc.document_id}"

            all_content_images[doc_custom_id] = images_cache

            content_chunks = MistralTranslationService.chunk_single_documents(
                modded_text
            )
            result_map[doc_custom_id] = {
                "chunks": {},
                "num_chunks": len(content_chunks),
            }

            for i, chunk in enumerate(content_chunks):
                entries.append(
                    {
                        # ex. "bill_version:<some-uid>:chunk_1"
                        "custom_id": doc_custom_id + f":chunk_{i}",
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
                                        f"{language}: {chunk}"
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

        # Sort the response into the result_map for further processing
        for line in response.iter_lines():
            translation_response = json.loads(line)
            translation_response_id = translation_response["custom_id"]

            raw_document_type = translation_response_id.split(":")[0]
            raw_document_id = translation_response_id.split(":")[1]
            document_chunk_label = translation_response_id.split(":")[2]
            chunk_index = int(document_chunk_label.replace("chunk_", ""))

            try:
                response_body = translation_response["response"]["body"]
                translated_chunk = response_body["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.warning(
                    f"Error parsing batch translation response for "
                    f"{translation_response_id}: {e}. Skipping..."
                )
                continue

            result_map[f"{raw_document_type}:{raw_document_id}"]["chunks"].update(
                {chunk_index: translated_chunk}
            )

        # Rejoin chunked translations, and reinsert images into each translation
        for processed_doc_id in list(result_map.keys()):
            curr_doc = result_map[processed_doc_id]
            document_type = processed_doc_id.split(":")[0]
            document_id = processed_doc_id.split(":")[1]
            chunk_indices = list(curr_doc["chunks"].keys())

            # Toss out document translations that didn't return all chunks
            if len(chunk_indices) != curr_doc["num_chunks"]:
                logger.warning(
                    f"Document with doc_custom_id='{processed_doc_id}' "
                    f"expected {curr_doc['num_chunks']} chunks back, "
                    f"but got {len(chunk_indices)}. "
                    "Refraining from creating an incomplete translation..."
                )
                continue

            # Stitch chunks back together in order
            chunk_indices.sort()
            sorted_chunks = [curr_doc["chunks"][i] for i in chunk_indices]
            full_translation = "".join(sorted_chunks)

            # Match this translation with its images using a key with
            # the same format as the doc_custom_id set up earlier
            matched_images = all_content_images[processed_doc_id]
            translation_with_images = MistralTranslationService.reinsert_cached_images(
                full_translation, matched_images, language, document_id
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
    def chunk_single_documents(content_str: str) -> List[str]:
        """
        Chunks a document's content into groups of pages.

        Intended to avoid coming up against Mistral's max token limit
        for a single document, and ensure the full doc gets translated.

        Each item in the resulting list is a string formed from the grouped pages.

        TODO: implement this into the single translation method
        once that starts getting used
        """

        # Split content string into list of discreet pages with page markers
        pattern = r"[\s\S]*?End of Page \d+"
        split_pages = re.findall(pattern, content_str)

        if not split_pages:
            # Treat the whole string as a single page if there aren't any page markers
            split_pages = [content_str]
        else:
            # Add any valid content after the last page marker as an extra page.
            # Content is not be valid if it's all just whitespace.
            trailing_content = content_str[sum(len(page) for page in split_pages) :]
            if trailing_content.rstrip():
                split_pages.append(trailing_content)

        total_num_pages = len(split_pages)

        # Create chunks of pages as a list of joined strings
        chunk_size = 5
        grouped_pages = []
        leftover_chunk = ""
        for i in range(0, total_num_pages, chunk_size):
            stop_page_index = i + chunk_size
            curr_group = split_pages[i:stop_page_index]

            if leftover_chunk:
                curr_group = [leftover_chunk] + curr_group
                leftover_chunk = ""

            joined_group = "".join(curr_group)

            # If there are more pages past the current group,
            # stop the chunk at the last header found anywhere in the current chunk
            # to prevent us from cutting the chunk mid sentence.
            if stop_page_index < total_num_pages:
                parts = re.split(r"(?=^### )", joined_group, flags=re.MULTILINE)
                if len(parts) > 1:
                    joined_group = "".join(parts[:-1])
                    leftover_chunk = parts[-1]

            grouped_pages.append(joined_group)

        # Remove empty elements
        grouped_pages = [g for g in grouped_pages if g]
        return grouped_pages

    @staticmethod
    def metered_batch_translate(
        contents: Union[QuerySet, List[DocumentContent]], language: str
    ) -> Generator[dict] | None:
        """
        Create multiple batch job requests to translate documents,
        and return the responses. The batches are split up when
        the total size of the strings involved for all requests reaches a set maximum.
        """
        max_batch_size = MAX_BATCH_SIZE_BYTES
        sys_msg_size = sys.getsizeof(SYSTEM_MESSAGE)
        curr_batch_size = 0
        curr_batch = []
        batch_num = 1

        contents = list(contents)
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
