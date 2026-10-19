import pytest
from la_metro_translations.management.commands.text_utils import (
    BoilerplateError,
    replace_inner_region_with_placeholder,
    replace_placeholder_with_pretranslated_text,
)


@pytest.fixture
def markdown(make_document_pages):
    return make_document_pages(5)


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
        with pytest.raises(BoilerplateError) as excinfo:

            replace_inner_region_with_placeholder(
                markdown,
                placeholder="PLACEHOLDER",
                start="End of Page 3",
                end="End of Page 1",
            )

            assert "appears before" in str(excinfo.value)


class TestReplacePlaceholder:

    PLACEHOLDER = "<PLACEHOLDER>"

    @pytest.fixture
    def placeholdered(self, markdown):
        return replace_inner_region_with_placeholder(
            markdown,
            start="End of Page 1\n\n",
            end="End of Page 3\n\n",
            placeholder=self.PLACEHOLDER,
        )

    def test_replace_placeholder_with_placeholder_found(self, placeholdered):
        boilerplate = "this is some boilerplate"
        output = replace_placeholder_with_pretranslated_text(
            placeholdered, placeholder=self.PLACEHOLDER, boilerplate=boilerplate
        )

        assert self.PLACEHOLDER not in output
        assert boilerplate in output

    def test_replace_placeholder_with_no_placeholder_found(self, placeholdered):
        with pytest.raises(BoilerplateError) as excinfo:
            replace_placeholder_with_pretranslated_text(
                placeholdered,
                placeholder="<MARCADOR DE POSICIÓN>",
                boilerplate="it translated the placeholder into spanish :(",
            )

            assert "exactly one instance" in str(excinfo.value)
            assert "0" in str(excinfo.value)
