import json
import logging
import requests
import time

from typing import Union, List, Generator
from io import StringIO
from datetime import datetime

from django.db.models import QuerySet
from django.conf import settings

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

from la_metro_translations.models import Document

logger = logging.getLogger(__name__)


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
        Create a single batch job request to OCR multiple documents,
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

        # Check response for issues
        if retrieved_job.errors:
            logger.error(f"Errors: {retrieved_job.errors}")

        if retrieved_job.status == "TIMEOUT_EXCEEDED":
            logger.error(
                f"Batch job exceeded timeout of {timeout_hours} hours."
                f"Job ID: {created_job.id}"
            )
            return
        elif retrieved_job.status != "SUCCESS" or not retrieved_job.output_file:
            logger.error(
                f"Batch job has stopped without an output file. "
                f"Status: {retrieved_job.status}; "
                f"Job ID: {created_job.id}"
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

    @staticmethod
    def metered_batch_extract(
        documents: Union[QuerySet, List[Document]],
    ) -> Generator[dict] | None:
        """
        Create multiple batch job requests to OCR documents, and return the responses.
        The batches are split up when the total file size of the contents in the urls
        reaches a set maximum.
        """
        max_batch_size = 30000000  # 30MB
        curr_batch_size = 0
        curr_batch = []
        batch_num = 1

        for i, doc in enumerate(documents):
            # Check file size
            res = requests.head(doc.source_url)
            curr_batch_size += int(res.headers["Content-Length"])
            curr_batch.append(doc)

            # Send batch if we've exceeded max file size or at the end of the list
            if curr_batch_size >= max_batch_size or i + 1 >= len(documents):
                logger.info(
                    f"Processing batch #{batch_num} with {len(curr_batch)} documents..."
                )
                yield from MistralOCRService.batch_extract(curr_batch)
                curr_batch_size = 0
                curr_batch = []
                batch_num += 1
