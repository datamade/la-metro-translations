import pytest
from la_metro_translations.management.commands.text_utils import (
    BOILERPLATE,
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
        result = replace_inner_region_with_placeholder(
            markdown,
            placeholder="PLACEHOLDER",
            start="End of Page 1\n\n",
            end="End of Page 6",
        )

        assert "PLACEHOLDER" not in result
        assert result == markdown

    def test_replace_inner_region_with_non_unique_markers(self, markdown):
        result = replace_inner_region_with_placeholder(
            markdown,
            placeholder="PLACEHOLDER",
            start="text body for",
            end="End of Page 4",
        )

        assert "PLACEHOLDER" not in result
        assert result == markdown

    def test_replace_inner_region_with_out_of_order_markers(self, markdown):
        result = replace_inner_region_with_placeholder(
            markdown,
            placeholder="PLACEHOLDER",
            start="End of Page 3",
            end="End of Page 1",
        )

        assert "PLACEHOLDER" not in result
        assert result == markdown


class TestReplacePlaceholder:

    boilerplate_field = "agenda_pages_2_and_3_text"
    boilerplate_info = BOILERPLATE[boilerplate_field]

    @pytest.fixture
    def placeholdered(self, markdown):
        return replace_inner_region_with_placeholder(markdown, **self.boilerplate_info)

    @pytest.mark.django_db
    def test_replace_placeholder_with_valid_markers_and_existing_translation(
        self, placeholdered, standard_translations
    ):
        pretranslated = standard_translations
        placeholder = self.boilerplate_info["placeholder"]
        output = replace_placeholder_with_pretranslated_text(
            placeholdered,
            language="spa",
            placeholder=placeholder,
            boilerplate_field=self.boilerplate_field,
        )

        assert placeholder not in output
        assert getattr(pretranslated, self.boilerplate_field) in output

    @pytest.mark.django_db
    def test_replace_placeholder_with_valid_markers_and_no_translation(
        self, placeholdered, standard_translations
    ):
        pretranslated = standard_translations
        placeholder = self.boilerplate_info["placeholder"]
        output = replace_placeholder_with_pretranslated_text(
            placeholdered,
            language="spa",
            placeholder=placeholder,
            boilerplate_field=self.boilerplate_field,
        )

        assert placeholder not in output
        assert getattr(pretranslated, self.boilerplate_field) in output
