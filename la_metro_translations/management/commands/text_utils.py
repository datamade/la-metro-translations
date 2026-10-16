# Utility functions for removing and inserting boilerplate text before and after translation.
import logging
from la_metro_translations.models import StandardTranslations

logger = logging.getLogger(__name__)


BOILERPLATE: dict[str, dict[str, str]] = {
    "agenda_pages_2_and_3_text": {
        "placeholder": "<AGENDA_PAGE_2_3_PLACEHOLDER>",
        "start": "End of Page 1\n\n",
        "end": "End of Page 3\n\n",
    }
}


def get_marker_indexes(text: str, start: str, end: str) -> tuple[int, int]:
    """
    Helper function for removing and inserting boilerplate.

    Returns the positions of start and end markers, assuming they are unique
    strings within the given text, and that start comes before end. Complains if
    either of these assumptions don't hold.
    """
    for marker in (start, end):
        count = text.count(marker)
        if count != 1:
            raise ValueError(f"Expected exactly one {marker!r}, found {count}")

    start_index = text.index(start)
    end_index = text.index(end)

    if end_index < start_index:
        raise ValueError(f"{end!r} appears before {start!r}")

    return start_index, end_index


def replace_inner_region_with_placeholder(
    text: str, *, start: str, end: str, placeholder: str
) -> str:
    """
    Use to strip out boilerplate before translation and mark for replacement before
    conversion.

    Deleted inner region excludes start string but includes end string.

    If get_marker_indexes returns an error, log error and proceed, returning
    original text as before. Insert placeholder only if no error.
    """

    try:
        start_index, end_index = get_marker_indexes(text, start, end)
        before = text[: start_index + len(start)]  # don't cut out start string
        after = text[end_index + len(end) :]  # do cut out end string
        return before + placeholder + after

    except ValueError as err:
        logger.error(err)
        return text


def replace_placeholder_with_pretranslated_text(
    text: str, *, language: str, placeholder: str, boilerplate_field: str
) -> str:

    boilerplate = None
    start_index = text.index(placeholder)
    end_index = start_index + len(placeholder)
    before = text[:start_index]
    after = text[end_index:]

    try:
        pretranslated = StandardTranslations.objects.filter(language=language)
        boilerplate = getattr(pretranslated, boilerplate_field)

    except StandardTranslations.DoesNotExist as e:
        raise Exception("No standard translations exist for this language") from e

    if boilerplate is None:
        raise Exception("No replacement boilerplate found")

    return before + boilerplate + after
