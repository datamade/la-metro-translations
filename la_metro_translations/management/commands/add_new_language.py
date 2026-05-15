import logging

from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

from la_metro_translations.models import TranslationLanguage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Add a new language for translation.
    """

    help = "Add a new language for translation."

    def add_arguments(self, parser):
        parser.add_argument(
            "language_value",
            type=str,
            help=(
                "The ISO 639 standardized format of the language you'd like to add. "
                "(i.e. 'es', 'zh-hans', etc.)"
            ),
        )
        parser.add_argument(
            "language_name",
            type=str,
            help=(
                "The title-cased display name of the language you'd like to add. "
                "(i.e. 'Spanish', 'Mandarin in Simplified Script', etc.)"
            ),
        )

    def handle(self, **options):
        language_value = options["language_value"]
        language_name = options["language_name"]

        try:
            TranslationLanguage.objects.create(
                value=language_value, display_name=language_name
            )
        except IntegrityError as e:
            logger.error(e)
            logger.error(
                "--- ERROR: A language with the same value or display name "
                "already exists. Please check your inputs and try again. ---"
            )
        else:
            logger.info(
                "Added a new language: "
                f"(value='{language_value}', display_name='{language_name}')."
            )
            logger.info("--- Finished! ---")
