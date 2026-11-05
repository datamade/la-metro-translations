import pytest
from la_metro_translations.utils import (
    BoilerplateError,
    replace_inner_region_with_placeholder,
    replace_placeholder_with_pretranslated_text,
    unique_match,
)


@pytest.fixture
def markdown(make_document_pages):
    return make_document_pages(5)


class TestUniqueMatch:

    def test_unique_match_errors_when_no_match(self):
        with pytest.raises(BoilerplateError, match="0"):
            unique_match(text="cat", token="not")

    def test_unique_match_errors_when_more_than_one_match(self):
        with pytest.raises(BoilerplateError, match="4"):
            unique_match(text="notnotnotnot", token="not")

    def test_unique_match_finds_unique_match(self):
        match = unique_match(text="not a cat", token="not")
        assert match.start() == 0
        assert match.end() == 3

    def test_unique_match_does_not_allow_extra_digits_after_page_numbers(self):
        with pytest.raises(BoilerplateError, match="0"):
            unique_match(text="End of Page 13", token="End of Page 1")

    @pytest.mark.parametrize(
        "line_ending",
        [
            (""),
            ("\n\n"),
            ("\r\n"),
            ("\r\n\r\n"),
        ],
    )
    def test_unique_match_finds_page_endings_with_any_line_endings(self, line_ending):
        match = unique_match(
            text=f"Here's some text before the End of Page 1{line_ending}",
            token="End of Page 1",
        )
        assert match[0] == f"End of Page 1{line_ending}"


class TestReplaceInnerRegion:

    def test_replace_inner_region_works_with_valid_markers(self, markdown):
        result = replace_inner_region_with_placeholder(
            markdown,
            placeholder="PLACEHOLDER",
            start="End of Page 1\n\n",
            end="End of Page 3",
        )
        remaining = [
            "End of Page 1\n\n",
            "Some text body for page 1",
            "Some text body for page 4",
            "Some text body for page 5",
            "End of Page 4\n\n",
            "End of Page 5\n\n",
        ]
        deleted = [
            "End of Page 2",
            "Some text body for page 2",
            "Some text body for page 3",
            "End of Page 3",
        ]

        for str in remaining:
            assert str in result

        assert "PLACEHOLDER" in result

        for str in deleted:
            assert str not in result

    def test_replace_inner_region_with_missing_marker(self, markdown):
        with pytest.raises(BoilerplateError) as excinfo:
            replace_inner_region_with_placeholder(
                markdown,
                placeholder="PLACEHOLDER",
                start="End of Page 1\n\n",
                end="End of Page 6",
            )

        assert "exactly one instance" in str(excinfo.value)
        assert "0" in str(excinfo.value)

    def test_replace_inner_region_with_non_unique_markers(self, markdown):
        with pytest.raises(BoilerplateError) as excinfo:
            replace_inner_region_with_placeholder(
                markdown,
                placeholder="PLACEHOLDER",
                start="text body for",
                end="End of Page 4",
            )

        assert "exactly one instance" in str(excinfo.value)
        assert "5" in str(excinfo.value)

    def test_replace_inner_region_with_out_of_order_markers(self, markdown):
        with pytest.raises(BoilerplateError, match="appears before"):

            replace_inner_region_with_placeholder(
                markdown,
                placeholder="PLACEHOLDER",
                start="End of Page 3",
                end="End of Page 1",
            )


class TestReplacePlaceholder:

    PLACEHOLDER = "<PLACEHOLDER>"

    @pytest.fixture
    def placeholdered(self, markdown):
        def build(line_ending="\n\n"):
            return replace_inner_region_with_placeholder(
                markdown,
                start="End of Page 1\n\n",
                end="End of Page 3\n\n",
                placeholder=self.PLACEHOLDER + line_ending,
            )

        return build

    @pytest.mark.parametrize("line_endings", ["\r\n", "", "\n", "\r\n\r\n"])
    def test_replace_placeholder_finds_placeholder_and_replaces(
        self, placeholdered, line_endings
    ):

        text = placeholdered(line_endings)
        boilerplate = "this is some boilerplate"
        output = replace_placeholder_with_pretranslated_text(
            text, placeholder=self.PLACEHOLDER, boilerplate=boilerplate
        )

        assert self.PLACEHOLDER + line_endings not in output
        assert self.PLACEHOLDER not in output
        assert boilerplate in output

    def test_replace_placeholder_with_no_placeholder_found(self, placeholdered):
        with pytest.raises(BoilerplateError):
            replace_placeholder_with_pretranslated_text(
                placeholdered(),
                placeholder="<MARCADOR DE POSICIÓN>",
                boilerplate="it translated the placeholder into spanish :(",
            )
