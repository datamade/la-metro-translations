# TODO: consider whether we should preserve page structure in these.
# TODO: The ocr'd version has them, so it may be worth keeping
SYSTEM_MESSAGE = (
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
