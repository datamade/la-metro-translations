# Utility functions for removing and inserting boilerplate text before and after translation.
import re


class BoilerplateError(ValueError):
    """
    Error class for identifying issues detecting unique markers in the text,
    including boundary markers for boilerplate text to be removed, and placeholder text to
    be replaced.
    """


# at the moment, no regex should be in start and end tokens
# regex is handled using constant patterns inside unique_match
BOILERPLATE_INFO: dict[str, dict[str, str]] = {
    "agenda_pages_2_and_3_text": {
        "placeholder": "<AGENDA_PAGE_2_3_PLACEHOLDER>",
        "start": "End of Page 1",
        "end": "End of Page 3",
    }
}

HR = "\n\n---\n\n"


def unique_match(text: str, token: str) -> re.Match:
    """
    Find the starting index of a given token with a stretch of text.
    Raise an error if the token is not unique.
    """
    PAGE_END_PATTERN = r"(?!\d)[\r\n]*"

    if "End of Page" in token:
        token = token + PAGE_END_PATTERN

    matches = list(re.finditer(token, text))
    count = len(matches)
    if count != 1:
        raise BoilerplateError(
            f"Expected exactly one instance of {token!r}, found {count}"
        )
    return matches[0]


def get_marker_matches(text: str, start: str, end: str) -> tuple[re.Match, re.Match]:
    """
    Helper function for removing boilerplate.

    Returns the positions of start and end markers, assuming they are unique
    strings within the given text, and that start comes before end. Complains if
    either of these assumptions don't hold.
    """

    start_match = unique_match(text, start)
    end_match = unique_match(text, end)

    if end_match.start() < start_match.start():
        raise BoilerplateError(f"{end!r} appears before {start!r}")

    return start_match, end_match


def replace_inner_region_with_placeholder(
    text: str, *, start: str, end: str, placeholder: str
) -> str:
    """
    Use to strip out boilerplate before translation and mark for replacement before
    conversion (convert_docs).

    Deleted inner region excludes start string and includes end string.

    If get_marker_indexes returns an error, propagate to caller to handle.
    Insert placeholder only if no error.
    """

    start_match, end_match = get_marker_matches(text, start, end)
    before = text[: start_match.end()]  # don't cut out start string
    after = text[end_match.end() :]  # do cut out end string
    return before + placeholder + "\n\n" + after


def replace_placeholder_with_pretranslated_text(
    text: str, *, boilerplate: str, placeholder: str
) -> str:
    """
    Find placeholder and replace it with pretranslated text, i.e., boilerplate that
    has already been translated.
    """

    pattern = placeholder + r"[\r\n]*"
    match = re.search(pattern, text)
    if match is None:
        raise BoilerplateError()
    before = text[: match.start()]
    after = text[match.end() :]

    return before + HR + boilerplate + HR + after
