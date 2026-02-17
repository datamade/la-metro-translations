import json
import re
import time
import logging

from typing import Union, List, Generator
from abc import ABC, abstractmethod
from io import StringIO
from datetime import datetime

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

        doc_text = MistralOCRService.process_pages(pages)
        return doc_text

    @staticmethod
    def batch_extract(
        documents: Union[QuerySet, List[Document]],
    ) -> Generator[dict] | None:
        """
        OCR multiple documents using a batch job request,
        and return the responses.
        """
        start_time = time.time()
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        # Create batch file
        batch_file = StringIO()
        for doc in documents:
            entry = {
                "custom_id": f"{doc.document_type}:{doc.document_id}",
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
        batch_timestamp = datetime.now().strftime("batch__%Y-%m-%d__%H-%M")
        batch_data = client.files.upload(
            file={
                "file_name": f"{batch_timestamp}.jsonl",
                "content": batch_file.getvalue(),
            },
            purpose="batch",
        )
        batch_file.close()

        # Create and start batch job
        timeout_hours = 23
        created_job = client.batch.jobs.create(
            input_files=[batch_data.id],
            model="mistral-ocr-latest",
            endpoint="/v1/ocr",
            timeout_hours=timeout_hours,
        )

        retrieved_job = client.batch.jobs.get(job_id=created_job.id)
        check_interval = 60

        logger.info(
            "Batch job created! It will be checked every "
            f"{check_interval} seconds until complete..."
        )

        while retrieved_job.status in ["QUEUED", "RUNNING"]:
            time.sleep(check_interval)
            retrieved_job = client.batch.jobs.get(job_id=created_job.id)
            total_reqs = retrieved_job.total_requests
            succeeded_reqs = retrieved_job.succeeded_requests
            failed_reqs = retrieved_job.failed_requests

            logger.info(f"Status: {retrieved_job.status}")
            logger.info(f"Successful requests: {succeeded_reqs} out of {total_reqs}")
            logger.info(f"Failed requests: {failed_reqs} out of {total_reqs}")
            logger.info(
                "Percent done: "
                f"{round((succeeded_reqs + failed_reqs) / total_reqs, 1) * 100}%"
            )
            minutes_elapsed = round((time.time() - start_time) / 60, 1)

            if retrieved_job.status in ["QUEUED", "RUNNING"]:
                logger.info(f"Time elapsed: {minutes_elapsed} minutes...")
                logger.info("=======")

        if retrieved_job.status == "TIMEOUT_EXCEEDED":
            logger.error(
                f"Batch job exceeded timeout of {timeout_hours} hours."
                f"Job id: {created_job.id}"
            )
            return
        elif retrieved_job.status != "SUCCESS":
            logger.error(
                f"Batch job has stopped with status: {retrieved_job.status}"
                f"Job id: {created_job.id}"
            )
            return

        logger.info("Downloading file(s)...")
        response = client.files.download(file_id=retrieved_job.output_file)
        logger.info(f"--- Batch job finished in {minutes_elapsed} minutes. ---")

        # Standardize output
        for line in response.iter_lines():
            extraction_response = json.loads(line)
            full_markdown = MistralOCRService.process_pages(
                extraction_response["response"]["body"]["pages"]
            )
            document_type = extraction_response["custom_id"].split(":")[0]
            document_id = extraction_response["custom_id"].split(":")[1]
            extraction = {
                "document_type": document_type,
                "document_id": document_id,
                "markdown": full_markdown,
            }

            yield extraction

    @staticmethod
    def process_pages(pages: List[dict]) -> str:
        """
        Reinserts tables, images, and links into the markdown of each page.
        """

        doc_text = ""

        for page in pages:
            markdown = page["markdown"]

            # Unescaped dollar signs cause unintended math formatting
            markdown = markdown.replace("$", "\\$")

            # Insert extracted tables, images, and links
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

            if len(page["hyperlinks"]) > 0:
                # Add links to the end of each page,
                # since Mistral does not provide placeholders for extracted links
                markdown += "\n\nRelevant hyperlinks:"
                for i, link in enumerate(page["hyperlinks"]):
                    markdown += f"\n- Hyperlink {i+1}: {link}"

            doc_text += f"{markdown}\n\nEnd of Page {page['index']+1}\n\n"

        return doc_text


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
