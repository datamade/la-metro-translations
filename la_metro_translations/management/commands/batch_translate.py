import logging
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import F, Case, When

from la_metro_translations.models import (
    DocumentContent,
    DocumentTranslation,
    StandardTranslations,
)
from la_metro_translations.services import get_translation_service
from la_metro_translations.management.commands.utils import ConnManagerMixin
from la_metro_translations.management.commands.text_utils import (
    BoilerplateError,
    replace_inner_region_with_placeholder,
    replace_placeholder_with_pretranslated_text,
    BOILERPLATE,
    HR,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand, ConnManagerMixin):
    """
    Translate text from document contents into one of the
    supported languages specified by the user.
    """

    help = (
        "Translate all DocumentContents that either do not have a "
        "related DocumentTranslation object in the specificed language, or "
        "have been updated more recently than their DocumentTranslation for "
        "that language, then upsert its DocumentTranslation."
    )

    standard_translations = StandardTranslations.objects.all()

    def add_arguments(self, parser):
        parser.add_argument(
            "language",
            type=str,
            help=(
                "The non-English language you'd like to translate documents into. "
                "Must be one we currently support."
            ),
        )
        parser.add_argument(
            "--document_content",
            type=int,
            default=None,
            help=("The ID of the document content to translate."),
        )
        parser.add_argument(
            "--approval_status",
            type=str,
            default="waiting",
            choices=["waiting", "approved"],
            help=(
                "Approval status to set on created or updated translations. "
                "Defaults to 'waiting'. Pass 'approved' to auto-approve and "
                "trigger file conversion."
            ),
        )

    def _remove_boilerplate(self, contents):
        """
        Remove boilerplate from documents so we don't keep re-translating it.

        Pre-translated boilerplate will be re-inserted in the conversion step.
        """

        for content in contents:

            md_text = content.markdown
            content.processed = md_text
            # Remove page 2 and 3 of event agendas
            if content.document.get_entity_type_display() == "Event":
                try:
                    content.processed = replace_inner_region_with_placeholder(
                        md_text, **BOILERPLATE["agenda_pages_2_and_3_text"]
                    )
                except BoilerplateError as err:
                    raise BoilerplateError(
                        "\n End of page markers not found for document %r"
                        % content.document.document_id
                    ) from err

        DocumentContent.objects.bulk_update(contents, ["processed"])

    def _replace_boilerplate(self, language, text, document_type):
        """
        After translation is returned from LLM, find and replace placeholders inserted
        by the _remove_boilerplate step.
        """

        for key, value in BOILERPLATE.items():

            pretranslated = self.standard_translations.get(language=language)
            if pretranslated is None:
                raise BoilerplateError(
                    f"No standard translations exist for target language: {language}"
                )

            boilerplate = getattr(pretranslated, key)
            if boilerplate == "":  # fields default to ""
                raise BoilerplateError(
                    f"No replacement boilerplate found for {language} {key}"
                )

            if "agenda_pages_2_and_3" in key and document_type == "event_document":
                try:
                    text = replace_placeholder_with_pretranslated_text(
                        text,
                        boilerplate=boilerplate,
                        placeholder=value["placeholder"],
                    )
                except BoilerplateError as err:
                    logger.warning(err)
                    logger.warning(
                        "Could not find placeholder %r in document. Agenda pages 2 and 3 "
                        "appended to beginning of the document instead.",
                        value["placeholder"],
                    )
                    text = boilerplate + HR + text

        return text

    def handle(self, **options):
        approval_status = options["approval_status"]

        supported_languages = [
            (value, display)
            for value, display in DocumentTranslation.LANGUAGE_CHOICES
            if value != "eng"
        ]

        user_language = options["language"].title()
        user_language_value = next(  # ie. "spa"
            (
                value
                for value, display in supported_languages
                if display == user_language
            ),
            None,
        )

        if not user_language_value:
            display_choices = [display for _, display in supported_languages]
            raise ValueError(
                f"This suite does not support translations to {user_language}. "
                f"Currently supported languages are: {', '.join(display_choices)}"
            )

        if document_content_id := options["document_content"]:
            contents = DocumentContent.objects.select_related("document").filter(
                id=document_content_id
            )

            self._remove_boilerplate(contents)

            if not contents.exists():
                raise ValueError(
                    f"Document content with the specified ID '{document_content_id}' "
                    "does not exist"
                )

        else:
            # Get any document contents without translations in this language, or
            # contents that have been updated more recently than their translation.

            events_first = Case(
                When(document__entity_type="event", then=0),
                default=1,
            )
            contents = (
                DocumentContent.objects.select_related("document")
                .exclude(
                    translations__updated_at__gte=F("updated_at"),
                    translations__language=user_language_value,
                )
                .order_by(events_first)
                .distinct()
            )

            self._remove_boilerplate(contents)

        if len(contents) == 0:
            logger.info(f"All Documents have up to date {user_language} translations!")
            return
        else:
            logger.info(
                f"Translating {len(contents)} DocumentContent(s) to {user_language}..."
            )

        translated_contents = {
            t["document_id"]: {
                "document_type": t["document_type"],
                "raw_output": t["markdown"],
            }
            for t in get_translation_service().metered_batch_translate(
                contents, user_language
            )
        }

        # put boilerplate back in before creating DB objects
        for _, t in translated_contents:
            t["processed_output"] = self._replace_boilerplate(
                user_language_value, t["markdown"], t["document_type"]
            )

        self.reset_db_connections()

        now = datetime.now()
        document_translations = []

        for content in contents:
            matched_translation = translated_contents.get(
                content.document.document_id, None
            )

            if not matched_translation:
                logger.warning(
                    f"Translation not found for document {content.document.id} "
                    f"with document ID {content.document.document_id}"
                )
                continue

            document_translations.append(
                DocumentTranslation(
                    document_content=content,
                    language=user_language_value,
                    raw_output=matched_translation["raw_output"],
                    markdown=matched_translation["processed_output"],
                    approval_status=approval_status,
                    updated_at=now,
                )
            )

        new_translations = DocumentTranslation.objects.bulk_create(
            document_translations,
            update_conflicts=True,
            unique_fields=["document_content", "language"],
            update_fields=["markdown", "approval_status", "updated_at"],
        )

        logger.info(
            f"DocumentContents with updated {user_language} translations: "
            f"{len(new_translations)} out of {len(contents)}"
        )

        if approval_status == "approved":
            logger.info("Triggering file conversion for approved translations...")
            call_command("convert_docs")

        logger.info("--- Finished! ---")
