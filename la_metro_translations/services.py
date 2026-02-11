import json
import re
import time
import logging

from typing import Union, List, Generator
from abc import ABC, abstractmethod
from io import StringIO

from django.conf import settings
from django.db.models import QuerySet
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from la_metro_translations.models import Document

logger = logging.getLogger(__name__)
with open("la_metro_translations/prompt.txt") as f:
    SYSTEM_MESSAGE = f.read()


class MistralOCRService:
    @staticmethod
    def extract_text(document_url: str) -> str | None:
        """
        Passes a url for a document to Mistral's OCR service,
        and returns the document's extracted text
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={"type": "document_url", "document_url": document_url},
                table_format="markdown",
                include_image_base64=True,
            )
        except SDKError as e:
            logger.warning(
                "Error occurred when OCR'ing document. " f"Document url: {document_url}"
            )
            logger.warning(e)
            logger.warning("Unable to OCR. Skipping...")
            return

        data = json.loads(ocr_response.model_dump_json())

        try:
            pages = data["pages"]
        except KeyError as e:
            logger.warning(
                "Error occurred when OCR'ing document. " f"Document url: {document_url}"
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

    @staticmethod
    def batch_extract(documents: Union[QuerySet, List[Document]]) -> Generator[dict]:
        """
        OCR multiple documents using a batch job request.
        """
        start_time = time.time()
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        # Create batch file
        batch_file = StringIO()
        for doc in documents:
            entry = {
                "custom_id": str(doc.document_id),
                "body": {
                    "document": {
                        "type": "document_url",
                        "document_url": doc.source_url,
                    },
                    "table_format": "markdown",
                    "include_image_base64": True,
                },
            }
            batch_file.write(json.dumps(entry) + "\n")

        # Upload batch file
        # TODO: uniquely name these files
        batch_file_name = "tester1.jsonl"
        batch_data = client.files.upload(
            file={"file_name": batch_file_name, "content": batch_file.getvalue()},
            purpose="batch",
        )
        batch_file.close()

        # Create/start batch job
        created_job = client.batch.jobs.create(
            input_files=[batch_data.id],
            model="mistral-ocr-latest",
            endpoint="/v1/ocr",
            # TODO: remember to change
            metadata={"job_type": "testing"},
        )

        retrieved_job = client.batch.jobs.get(job_id=created_job.id)
        check_interval = 30

        logger.info(f"Job sent. Current status: {retrieved_job.status}")
        logger.info(
            f"Job status will be refreshed every {check_interval} "
            "seconds until complete."
        )

        while retrieved_job.status in ["QUEUED", "RUNNING"]:
            time.sleep(check_interval)
            retrieved_job = client.batch.jobs.get(job_id=created_job.id)
            total_reqs = retrieved_job.total_requests
            succeeded_reqs = retrieved_job.succeeded_requests
            failed_reqs = retrieved_job.failed_requests

            logger.info(f"Status: {retrieved_job.status}")
            logger.info(f"Total requests: {total_reqs}")
            logger.info(f"Successful requests: {succeeded_reqs}")
            logger.info(f"Failed requests: {failed_reqs}")
            logger.info(
                "Percent done: "
                f"{round((succeeded_reqs + failed_reqs) / total_reqs, 4) * 100}%"
            )

            if retrieved_job.status not in ["QUEUED", "RUNNING"]:
                break
            else:
                logger.info(f"Checking again in {check_interval} seconds")
                logger.info("=====")

        logger.info("Downloading file(s)...")
        response = client.files.download(file_id=retrieved_job.output_file)
        logger.info(
            "--- Downloaded! Job took %s seconds to complete. ---"
            % (time.time() - start_time)
        )

        for line in response.iter_lines():
            yield json.loads(line)


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
