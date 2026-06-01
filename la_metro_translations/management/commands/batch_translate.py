import logging
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import F
from django.db import connections

from la_metro_translations.models import (
    DocumentContent,
    DocumentTranslation,
)
from la_metro_translations.services import get_translation_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
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

    def reset_db_connections(self):
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

    def handle(self, **options):
        approval_status = options["approval_status"]

        supported_languages = [
            choice
            for choice in DocumentTranslation.LANGUAGE_CHOICES
            if choice[0] != "en"
        ]

        user_language = options["language"].title()
        user_language_value = next(  # ie. "es"
            (lang[0] for lang in supported_languages if lang[1] == user_language),
            None,
        )
        if not user_language_value:
            display_choices = [choice[1] for choice in supported_languages]
            raise ValueError(
                f"This suite does not support translations to {user_language}. "
                f"Currently supported languages are: {', '.join(display_choices)}"
            )

        if document_content_id := options["document_content"]:
            contents = DocumentContent.objects.select_related("document").filter(
                id=document_content_id
            )

            if not contents.exists():
                raise ValueError(
                    f"Document content with the specified ID '{document_content_id}' "
                    "does not exist"
                )

        else:
            # Get any document contents without translations in this language, or
            # contents that have been updated more recently than their translation.
            contents = (
                DocumentContent.objects.select_related("document")
                .exclude(
                    translations__updated_at__gte=F("updated_at"),
                    translations__language=user_language_value,
                )
                .distinct()
            )

        if len(contents) == 0:
            logger.info(f"All Documents have up to date {user_language} translations!")
            return
        else:
            logger.info(
                f"Translating {len(contents)} DocumentContent(s) to {user_language}..."
            )

        translated_contents = {
            t["document_id"]: t["markdown"]
            for t in get_translation_service().metered_batch_translate(
                contents, user_language
            )
        }

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
                    markdown=matched_translation,
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
