import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import F

from la_metro_translations.models import (
    DocumentContent,
    DocumentTranslation,
)
from la_metro_translations.services import MistralTranslationService

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

    def handle(self, **options):
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

        translations = list(
            MistralTranslationService.metered_batch_translate(contents, user_language)
        )

        now = datetime.now()
        translations_to_upsert = []
        for content in contents:
            matched_translation = {}
            for translation in translations:
                if (
                    translation["document_type"] == content.document.document_type
                    and translation["document_id"] == content.document.document_id
                ):
                    matched_translation = translation
                    break

            if not matched_translation:
                continue

            translations_to_upsert.append(
                DocumentTranslation(
                    document_content=content,
                    language=user_language_value,
                    markdown=matched_translation["markdown"],
                    updated_at=now,
                )
            )

        new_translations = DocumentTranslation.objects.bulk_create(
            translations_to_upsert,
            update_conflicts=True,
            unique_fields=["document_content", "language"],
            update_fields=["markdown", "updated_at"],
        )

        logger.info(
            f"DocumentContents with updated {user_language} translations: "
            f"{len(new_translations)} out of {len(contents)}"
        )
        logger.info("--- Finished! ---")
