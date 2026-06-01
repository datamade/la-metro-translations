import pytest
from unittest.mock import call, patch

from conftest import (
    DocumentContentFactory,
    DocumentFactory,
    DocumentTranslationFactory,
    ExtractionConfigFactory,
    TranslationConfigFactory,
)
from la_metro_translations.models import DocumentContent

PATCH_CALL_COMMAND = "la_metro_translations.models.call_command"


@pytest.mark.django_db
class TestDocumentContentSave:
    """
    Tests for the DocumentContent.save() hook, which syncs the English
    translation and triggers batch_translate when content is approved.
    """

    @pytest.fixture
    def content_with_english(self, document):
        """Approved content with an English translation already present."""
        content = DocumentContentFactory(document=document, approval_status="approved")
        DocumentTranslationFactory(
            document_content=content, language="en", approval_status="approved"
        )
        return content

    @pytest.mark.parametrize(
        "initial_status,initial_markdown,new_status,new_markdown",
        [
            ("approved", "original", "approved", "changed content"),
            ("waiting", "original", "approved", "original"),
        ],
        ids=["content_changed", "newly_approved"],
    )
    @patch(PATCH_CALL_COMMAND)
    def test_batch_translate_called_on_relevant_change(
        self,
        mock_call_command,
        initial_status,
        initial_markdown,
        new_status,
        new_markdown,
        document,
    ):
        ExtractionConfigFactory()
        content = DocumentContentFactory(
            document=document, approval_status=initial_status, markdown=initial_markdown
        )
        DocumentTranslationFactory(
            document_content=content, language="en", approval_status=initial_status
        )

        content.approval_status = new_status
        content.markdown = new_markdown
        content.save()

        assert mock_call_command.called
        assert mock_call_command.call_args[0][0] == "batch_translate"

    @patch(PATCH_CALL_COMMAND)
    def test_batch_translate_not_called_when_no_change(
        self, mock_call_command, content_with_english
    ):
        ExtractionConfigFactory()
        content_with_english.save()

        mock_call_command.assert_not_called()

    @pytest.mark.parametrize(
        "auto_approve,expected_status",
        [(True, "approved"), (False, "waiting")],
        ids=["auto_approve_on", "auto_approve_off"],
    )
    @patch(PATCH_CALL_COMMAND)
    def test_translation_approval_status_from_language_config(
        self,
        mock_call_command,
        auto_approve,
        expected_status,
        document,
    ):
        config = ExtractionConfigFactory()
        TranslationConfigFactory(
            config=config, language="sp", auto_approve_translations=auto_approve
        )
        content = DocumentContentFactory(
            document=document, approval_status="waiting", markdown="original"
        )
        DocumentTranslationFactory(
            document_content=content, language="en", approval_status="waiting"
        )

        content.approval_status = "approved"
        content.save()

        assert mock_call_command.call_args.kwargs["approval_status"] == expected_status

    @patch(PATCH_CALL_COMMAND)
    def test_translation_approval_status_defaults_to_waiting_without_language_config(
        self, mock_call_command, document
    ):
        ExtractionConfigFactory()  # no TranslationConfig rows
        content = DocumentContentFactory(
            document=document, approval_status="waiting", markdown="original"
        )
        DocumentTranslationFactory(
            document_content=content, language="en", approval_status="waiting"
        )

        content.approval_status = "approved"
        content.save()

        assert mock_call_command.call_args.kwargs["approval_status"] == "waiting"

    @patch(PATCH_CALL_COMMAND)
    def test_revision_marks_translations_and_does_not_call_batch_translate(
        self, mock_call_command, content_with_english
    ):
        spanish = DocumentTranslationFactory(
            document_content=content_with_english,
            language="sp",
            approval_status="approved",
        )

        content_with_english.approval_status = "revision"
        content_with_english.save()

        mock_call_command.assert_not_called()
        spanish.refresh_from_db()
        assert spanish.approval_status == "revision"

    @patch(PATCH_CALL_COMMAND)
    def test_new_object_does_not_trigger_translation(self, mock_call_command, document):
        DocumentContentFactory(document=document, approval_status="approved")
        mock_call_command.assert_not_called()

    @patch(PATCH_CALL_COMMAND)
    def test_english_translation_synced_on_content_change(
        self, mock_call_command, content_with_english
    ):
        ExtractionConfigFactory()
        content_with_english.markdown = "updated markdown"
        content_with_english.save()

        english = content_with_english.translations.get(language="en")
        assert english.markdown == "updated markdown"


@pytest.mark.django_db
class TestExtractionConfigSave:
    """
    Tests for the ExtractionConfig.save() catch-up logic, which approves
    waiting content and triggers translation when auto_approve_extractions
    is switched on.
    """

    @pytest.mark.parametrize(
        "initial_status,expected_after",
        [
            ("waiting", "approved"),
            ("revision", "revision"),
        ],
        ids=["waiting_gets_approved", "revision_unchanged"],
    )
    @patch(PATCH_CALL_COMMAND)
    def test_catch_up_content_status_on_flip(
        self, mock_call_command, initial_status, expected_after, document
    ):
        config = ExtractionConfigFactory(auto_approve_extractions=False)
        DocumentContentFactory(document=document, approval_status=initial_status)

        config.auto_approve_extractions = True
        config.save()

        assert (
            DocumentContent.objects.get(document=document).approval_status
            == expected_after
        )

    @patch(PATCH_CALL_COMMAND)
    def test_catch_up_does_not_run_when_already_auto_approved(
        self, mock_call_command, document
    ):
        config = ExtractionConfigFactory(auto_approve_extractions=True)
        DocumentContentFactory(document=document, approval_status="waiting")

        config.save()  # no change to auto_approve_extractions

        assert (
            DocumentContent.objects.get(document=document).approval_status == "waiting"
        )
        mock_call_command.assert_not_called()

    @patch(PATCH_CALL_COMMAND)
    def test_catch_up_triggers_batch_translate_per_language_config(
        self, mock_call_command
    ):
        config = ExtractionConfigFactory(auto_approve_extractions=False)
        TranslationConfigFactory(
            config=config, language="sp", auto_approve_translations=True
        )

        config.auto_approve_extractions = True
        config.save()

        mock_call_command.assert_any_call(
            "batch_translate", "Spanish", approval_status="approved"
        )


@pytest.mark.django_db
class TestTranslationConfigSave:
    """
    Tests for the TranslationConfig.save() catch-up logic, which approves
    waiting translations and triggers file conversion when
    auto_approve_translations is switched on for a language.
    """

    @patch(PATCH_CALL_COMMAND)
    def test_catch_up_on_flip_approves_waiting_not_revision(
        self, mock_call_command, extraction_config
    ):
        lang_config = TranslationConfigFactory(
            config=extraction_config, language="sp", auto_approve_translations=False
        )

        doc_a = DocumentFactory(document_id="doc-a")
        content_a = DocumentContentFactory(document=doc_a, approval_status="approved")
        waiting = DocumentTranslationFactory(
            document_content=content_a, language="sp", approval_status="waiting"
        )

        doc_b = DocumentFactory(document_id="doc-b")
        content_b = DocumentContentFactory(document=doc_b, approval_status="approved")
        revision = DocumentTranslationFactory(
            document_content=content_b, language="sp", approval_status="revision"
        )

        lang_config.auto_approve_translations = True
        lang_config.save()

        # batch_translate and convert_docs should both be called
        assert call("batch_translate", "Spanish", approval_status="approved") in (
            mock_call_command.call_args_list
        )
        assert call("convert_docs") in mock_call_command.call_args_list

        # waiting translation approved; revision left alone
        waiting.refresh_from_db()
        assert waiting.approval_status == "approved"
        revision.refresh_from_db()
        assert revision.approval_status == "revision"

    @patch(PATCH_CALL_COMMAND)
    def test_catch_up_does_not_run_when_already_auto_approved(
        self, mock_call_command, extraction_config, document_content
    ):
        lang_config = TranslationConfigFactory(
            config=extraction_config, language="sp", auto_approve_translations=True
        )
        waiting = DocumentTranslationFactory(
            document_content=document_content, language="sp", approval_status="waiting"
        )

        lang_config.save()  # no change to auto_approve_translations

        waiting.refresh_from_db()
        assert waiting.approval_status == "waiting"
        mock_call_command.assert_not_called()
