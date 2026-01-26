import json
import re
import time

from django.conf import settings
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from la_metro_translations.models import SourceDoc


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
            print("Error occurred when OCR'ing document. " f"Document url: {doc_url}")
            print(e)
            print("Unable to OCR. Skipping...")
            return

        data = json.loads(ocr_response.model_dump_json())

        try:
            pages = data["pages"]
        except KeyError as e:
            print("Error occurred when OCR'ing document. " f"Document url: {doc_url}")
            print(e)
            print("Response from model:")
            print(data)
            print("Unable to OCR. Skipping...")
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
    def translate_text(source_doc: SourceDoc, dest_language: str) -> str | None:
        """
        Translates a string to a destination language using Mistral,
        while aiming to preserve markdown.

        Any base64 encoded images within the string are removed and cached
        before translation, then inserted back in after. This cuts down on
        translation time and cost.
        """
        start_time = time.time()
        capitalized_lang = dest_language[0].upper() + dest_language[1:]
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        # Find image tags containing base64 up to and including first close-parentheses
        img_pattern = r"\!\[img\-\d+\.jpeg\]\(data\:image\/jpeg\;base64.+?(?:\))"
        images_cache = {}
        source_text = source_doc.markdown
        modded_source_text = source_text

        image_tags = re.findall(img_pattern, source_text)
        for i in image_tags:
            # Cache image tag
            img_label = i[i.find("!") : i.find("]") + 1]
            img_data = i[i.find("(") : i.find(")") + 1]
            images_cache[img_label] = img_data

            # Replace entire image tag with a placeholder, ex. "![img-0.jpeg]()"
            modded_source_text = modded_source_text.replace(i, f"{img_label}()")

        # TODO: consider whether we should preserve page structure in these.
        # TODO: The ocr'd version has them, so it may be worth keeping
        system_msg = (
            "Translate the text provided to the language requested by the user. "
            "Maintain the text's professional tone, while prioritizing returning "
            "all the text given. "
            "Do not translate any acronyms found in the original text. "
            "Preserve all markdown formatting, image tags, code blocks, links, "
            "headings, and inline markup. "
            "Preserve page structure; do not omit Page numbers in the original text. "
            "Only change natural language; do not modify tags, backticks, URLs, "
            "or markdown structure. "
            "If a natural language sentence is incomplete, translate it as it is "
            "written and do not attempt to fill in parts of the sentence."
        )

        try:
            chat_response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {
                        "role": "system",
                        "content": system_msg,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Translate the following text to "
                            f"{capitalized_lang}: {modded_source_text}"
                        ),
                    },
                ],
            )
        except SDKError as e:
            print(
                "Error occurred when translating document. "
                f"Language: {capitalized_lang}; "
                f"Document ID: {source_doc.doc_id}"
            )
            print(e)
            print("Unable to translate. Skipping...")
            return

        data = json.loads(chat_response.model_dump_json())

        try:
            translated_string = data["choices"][0]["message"]["content"]
        except KeyError as e:
            print("Error occurred when translating document.")
            print(f"Language: {capitalized_lang}; " f"Document ID: {source_doc.doc_id}")
            print(e)
            print("Response from model:")
            print(data)
            print("Unable to translate. Skipping...")
            return

        # Reinsert images where they belong
        for label in images_cache.keys():
            full_image = label + images_cache[label]
            if label not in translated_string:
                print(
                    f"Warning: {label} is missing in the {capitalized_lang} translation"
                )
            else:
                translated_string = translated_string.replace(f"{label}()", full_image)

        print("--- %s seconds to complete ---" % (time.time() - start_time))
        return translated_string
