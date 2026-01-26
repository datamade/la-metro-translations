import json
import re
from mistralai import Mistral
from django.conf import settings


class OCRService:
    @staticmethod
    def extract_text(doc_url: str) -> str:
        """
        Passes a url for a document to Mistral's OCR service,
        and returns the doc's extracted text
        """
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": doc_url},
            table_format="markdown",
            include_image_base64=True,
        )
        data = json.loads(ocr_response.model_dump_json())

        # TODO: should probably set up some error handling in case we don't get pages
        pages = data["pages"]
        doc_text = ""
        breakpoint()

        for page in pages:
            # TODO: consider escaping dollar signs
            # so they don't cause unneeded math formatting
            markdown = page["markdown"]

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
    def translate_text(source_text: str, dest_language: str) -> str:
        """
        Translates a string to a destination language using Mistral,
        while aiming to preserve markdown.

        Any base64 encoded images within the string are removed and cached
        before translation, then inserted back in after. This cuts down on
        translation time and cost.
        """
        capitalized_lang = dest_language[0].upper() + dest_language[1:]
        client = Mistral(api_key=settings.MISTRAL_API_KEY)

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

        chat_response = client.chat.complete(
            model="mistral-large-latest",
            # TODO: consider whether we should preserve page structure in these
            # the ocr'd version has em.
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the text provided to the language requested "
                        "by the user. Maintain the text's professional tone, "
                        "while prioritizing returning all the text given. "
                        "Preserve all markdown formatting, image tags, code blocks, "
                        "links, headings, and inline markup. Only change natural "
                        "language; do not modify tags, backticks, URLs, "
                        "or markdown structure. Preserve page structure; "
                        "do not omit Page numbers in the original text. "
                        "If a natural language sentence is incomplete, "
                        "translate it as it is written and do not attempt to fill in "
                        "parts of the sentence."
                    ),
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
        data = json.loads(chat_response.model_dump_json())

        # TODO: consider a try block here and/or where we load the json above
        # Reinsert images where they belong
        translated_string = data["choices"][0]["message"]["content"]
        for label in images_cache.keys():
            full_image = label + images_cache[label]
            if label not in translated_string:
                print(
                    f"Warning: {label} is missing in the {capitalized_lang} translation"
                )
            else:
                translated_string = translated_string.replace(f"{label}()", full_image)

        return translated_string
