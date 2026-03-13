import json
import re
import logging
import requests

from typing import Union, List, Generator
from utils import BatchUtils

from django.db.models import QuerySet
from django.conf import settings

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

from la_metro_translations.models import Document

logger = logging.getLogger(__name__)


class MistralOCRService:
    @staticmethod
    def extract_text(document: Document) -> str | None:
        """
        Passes a url for a document to Mistral's OCR service,
        and returns the document's extracted text
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        document_url = document.source_url

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

        doc_text = MistralOCRService.process_pages(pages, document.document_type)
        return doc_text

    @staticmethod
    def batch_extract(
        documents: Union[QuerySet, List[Document]],
    ) -> Generator[dict] | None:
        """
        Create a single batch job request to OCR multiple documents,
        and return the responses.
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        timeout_hours = 23

        # Create batch entries
        entries = []
        for doc in documents:
            entries.append(
                {
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
            )

        # Start batch job
        created_job = BatchUtils.start_batch_job(
            client=client,
            entries=entries,
            model="mistral-ocr-latest",
            endpoint="/v1/ocr",
            timeout_hours=timeout_hours,
        )

        # Monitor batch job
        response = BatchUtils.check_batch_job(
            client=client, job_id=created_job.id, timeout_hours=timeout_hours
        )
        if not response:
            return

        # Standardize output
        for line in response.iter_lines():
            extraction_response = json.loads(line)
            document_type = extraction_response["custom_id"].split(":")[0]
            document_id = extraction_response["custom_id"].split(":")[1]
            full_markdown = MistralOCRService.process_pages(
                extraction_response["response"]["body"]["pages"], document_type
            )
            extraction = {
                "document_type": document_type,
                "document_id": document_id,
                "markdown": full_markdown,
            }

            yield extraction

    @staticmethod
    def process_pages(pages: List[dict], document_type: str) -> str:
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
                """
                Mistral's OCR model currently does not provide
                placeholders for extracted links. However, it does list them
                in the order it finds them. So we'll use patterns in documents
                to put them back where they belong.

                If the document is an agenda, reinsert attachment and bill links
                directly onto their original text since those are made
                using a set template/pattern.

                If the document is a board report, append hyperlinks to the
                end of each page since those do not have a pattern.
                """

                # Replace legistar link text when found
                legistar_link = "http://www.legistar.com/"
                if legistar_link in page["hyperlinks"]:
                    legistar_text = "powered by Legistar™"
                    full_legistar_tag = f"[{legistar_text}]({legistar_link})"
                    markdown = markdown.replace(legistar_text, full_legistar_tag)
                    page["hyperlinks"].remove(legistar_link)

                if document_type == "event_document":
                    # Blocks that start with "Attachments:", and end with newlines
                    attmt_pattern = r"(?:\*\*)?Attachments:(?:\*\*)?\s*(.+?)(?=\n\n|$)"
                    attmt_blocks = re.findall(attmt_pattern, markdown, re.DOTALL)

                    # Text representing a board report link e.g. 2341-8907
                    bill_pattern = r"(?:\s+)(\d{4}-\d{4})"
                    bill_labels = re.findall(bill_pattern, markdown)

                    # Separate attachment links and board report links
                    attmt_links = []
                    bill_links = []
                    for link in page["hyperlinks"]:
                        (
                            bill_links.append(link)
                            if "matter.aspx" in link
                            else attmt_links.append(link)
                        )

                    # Process each big block of attachments as single labels
                    for original_block in attmt_blocks:
                        hyperlinked_block = original_block
                        attmt_labels = original_block.split("\n")

                        # Push new link tags into the temporary hyperlinked block
                        for attmt_label in attmt_labels:
                            full_attmt_tag = f"[{attmt_label}]({attmt_links[0]})"
                            hyperlinked_block = hyperlinked_block.replace(
                                attmt_label, full_attmt_tag
                            )
                            del attmt_links[0]

                        # Push hyperlinked blocks into original markdown as a whole
                        # to prevent identical blocks from having mismatched links
                        markdown = markdown.replace(
                            original_block, hyperlinked_block, 1
                        )

                    # Process board report labels
                    for bill_label in bill_labels:
                        full_bill_tag = f"[{bill_label}]({bill_links[0]})"
                        markdown = markdown.replace(bill_label, full_bill_tag, 1)
                        del bill_links[0]

                    # Include any extra links that weren't matched
                    if leftover_links := attmt_links + bill_links:
                        markdown += "\n\nExtra links:"
                        for i, link in enumerate(leftover_links):
                            markdown += f"\n- Hyperlink {i+1}: {link}"
                else:
                    # For other document types, insert links at the end of each page
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
