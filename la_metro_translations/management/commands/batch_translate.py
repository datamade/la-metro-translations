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
        # TODO: fill out
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
        """
        TODO: make this method just responsible for one language at a time,
        and have a github action do the legwork of running this for multiple languages
        """
        supported_languages = [
            choice[0]
            for choice in DocumentTranslation.LANGUAGE_CHOICES
            if choice[0] != "english"
        ]

        user_language = options["language"].lower()
        if user_language not in supported_languages:
            raise ValueError(
                f"This suite does not support translations to {user_language}. "
                f"Currently supported languages are: {', '.join(supported_languages)}"
            )

        # Get any document contents without translations in this language, or
        # contents that have been updated more recently than their translations.
        contents = (
            DocumentContent.objects.select_related("document")
            .exclude(
                translations__updated_at__gte=F("updated_at"),
                translations__language=user_language,
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

        # TODO: use metered_batch_translate() when that's written
        translations = MistralTranslationService.batch_translate(
            contents, [user_language]
        )

        now = datetime.now()
        translations_to_upsert = []
        for content in contents:
            curr_translation = next(
                (
                    translation
                    for translation in translations
                    if translation["document_type"] == content.document.document_type
                    and translation["document_id"] == content.document.document_id
                ),
                None,
            )

            if not curr_translation:
                continue

            translations_to_upsert.append(
                DocumentTranslation(
                    document_content=content,
                    language=user_language,
                    markdown=curr_translation["markdown"],
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
