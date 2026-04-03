import pytest

from la_metro_translations.panels import PropertyPanel, RelatedObjectsPanel
from la_metro_translations.models import Document, DocumentContent

from conftest import DocumentTranslationFactory


@pytest.mark.django_db
class TestPropertyPanel:
    """Tests for the PropertyPanel custom panel."""

    def test_bound_panel_render_simple_string(self, document):
        """Test rendering a simple string property."""
        panel = PropertyPanel("title")
        bound_model_panel = panel.bind_to_model(Document)
        bound_panel = bound_model_panel.get_bound_panel(instance=document)
        html = bound_panel.render_html()

        assert document.title in html

    def test_bound_panel_render_callable_property(self, document):
        """Test rendering a callable property (method)."""
        panel = PropertyPanel("source_url_display")
        bound_model_panel = panel.bind_to_model(Document)
        bound_panel = bound_model_panel.get_bound_panel(instance=document)
        html = bound_panel.render_html()

        assert "View original document" in html
        assert "button" in html
        assert document.source_url in html

    def test_bound_panel_render_missing_attribute(self, document):
        """Test rendering when attribute doesn't exist."""
        panel = PropertyPanel("nonexistent_attr")
        bound_model_panel = panel.bind_to_model(Document)
        bound_panel = bound_model_panel.get_bound_panel(instance=document)
        html = bound_panel.render_html()

        assert "—" in html


@pytest.mark.django_db
class TestRelatedObjectsPanel:
    """Tests for the RelatedObjectsPanel custom panel."""

    def test_bound_panel_render_with_related_objects(self, document_content):
        """Test rendering with related objects present."""
        panel = RelatedObjectsPanel(
            "la_metro_translations.Document",
            "content",
            [
                PropertyPanel("edit_link_display"),
                PropertyPanel("source_url_display"),
            ],
        )

        bound_model_panel = panel.bind_to_model(DocumentContent)
        bound_panel = bound_model_panel.get_bound_panel(instance=document_content)
        html = bound_panel.render_html()

        # Should contain rendered content from related document
        assert html.count("Manage document") == 1
        assert html.count("View original document") == 1

    def test_bound_panel_render_no_related_objects(self, document):
        """Test rendering when no related objects exist."""
        panel = RelatedObjectsPanel(
            "la_metro_translations.DocumentContent",
            "document",
            [PropertyPanel("approval_status_display")],
        )

        bound_model_panel = panel.bind_to_model(Document)
        bound_panel = bound_model_panel.get_bound_panel(instance=document)
        html = bound_panel.render_html()

        # Should return empty string for no related objects
        assert html == ""

    def test_bound_panel_render_complex_query_path(self, document_translation):
        """Test rendering with complex query path (document_content__document)."""
        document = document_translation.document_content.document
        DocumentTranslationFactory(
            language="english", document_content=document_translation.document_content
        )

        panel = RelatedObjectsPanel(
            "la_metro_translations.DocumentTranslation",
            "document_content__document",
            [PropertyPanel("language_display")],
        )

        bound_model_panel = panel.bind_to_model(Document)
        bound_panel = bound_model_panel.get_bound_panel(instance=document)
        html = bound_panel.render_html()

        for translation in document.content.translations.all():
            assert html.count(translation.get_language_display()) == 1
