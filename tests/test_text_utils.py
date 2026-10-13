import pytest
from la_metro_translations.management.commands.batch_translate import (
    replace_inner_region_with_placeholder,
)


class TestReplaceInnerRegion:

    @pytest.fixture(autouse=True)
    def markdown(self, make_document_pages):
        return make_document_pages(5)

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
