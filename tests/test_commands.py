import pytest
from unittest.mock import patch

from django.core.management import call_command as run_command

from conftest import (
    DocumentFactory,
    DocumentTranslationFactory,
    ExtractionConfigFactory,
    TranslationConfigFactory,
)
from la_metro_translations.models import DocumentContent, DocumentTranslation

PATCH_OCR = (
    "la_metro_translations.management.commands.batch_extract"
    ".MistralOCRService.metered_batch_extract"
)
PATCH_EXTRACT_CALL_COMMAND = (
    "la_metro_translations.management.commands.batch_extract.call_command"
)
PATCH_TRANSLATE_CALL_COMMAND = (
    "la_metro_translations.management.commands.batch_translate.call_command"
)
PATCH_TRANSLATE_RESET_DB = (
    "la_metro_translations.management.commands.batch_translate"
    ".Command.reset_db_connections"
)
PATCH_EXTRACT_RESET_DB = (
    "la_metro_translations.management.commands.batch_extract"
    ".Command.reset_db_connections"
)


@pytest.mark.django_db
class TestBatchTranslateCommand:
    """
    Tests for the batch_translate management command, focused on how the
    --approval_status argument controls translation status and whether
    convert_docs is triggered.
    """

    @pytest.fixture(autouse=True)
    def no_reset_db(self):
        with patch(PATCH_TRANSLATE_RESET_DB):
            yield

    @pytest.mark.parametrize("approval_status", ["waiting", "approved"])
    def test_creates_translations_with_correct_approval_status(
        self, approval_status, document_content
    ):
        with patch(PATCH_TRANSLATE_CALL_COMMAND):
            run_command(
                "batch_translate",
                "Spanish",
                approval_status=approval_status,
                document_content=document_content.id,
            )

        translation = DocumentTranslation.objects.get(
            document_content=document_content, language="spa"
        )
        assert translation.approval_status == approval_status

    @pytest.mark.parametrize(
        "approval_status,expect_convert_docs",
        [("waiting", False), ("approved", True)],
        ids=["waiting_no_convert", "approved_triggers_convert"],
    )
    @patch(PATCH_TRANSLATE_CALL_COMMAND)
    def test_convert_docs_triggered_only_when_approved(
        self,
        mock_call_command,
        approval_status,
        expect_convert_docs,
        document_content,
    ):
        run_command(
            "batch_translate",
            "Spanish",
            approval_status=approval_status,
            document_content=document_content.id,
        )

        if expect_convert_docs:
            mock_call_command.assert_called_once_with("convert_docs")
        else:
            mock_call_command.assert_not_called()

    @patch(PATCH_TRANSLATE_CALL_COMMAND)
    def test_approval_status_updated_on_conflict(
        self, mock_call_command, document_content
    ):
        DocumentTranslationFactory(
            document_content=document_content,
            language="spa",
            approval_status="approved",
        )

        run_command(
            "batch_translate",
            "Spanish",
            approval_status="waiting",
            document_content=document_content.id,
        )

        translation = DocumentTranslation.objects.get(
            document_content=document_content, language="spa"
        )
        assert translation.approval_status == "waiting"


@pytest.mark.django_db
class TestBatchExtractCommand:
    """
    Tests for the batch_extract management command, focused on how
    ExtractionConfig controls the approval status of created content and
    whether batch_translate is triggered downstream.
    """

    @pytest.fixture(autouse=True)
    def no_reset_db(self):
        with patch(PATCH_EXTRACT_RESET_DB):
            yield

    @pytest.fixture
    def document_without_content(self):
        doc = DocumentFactory(document_id="test-doc-1")
        return doc

    @pytest.fixture
    def extraction_result(self, document_without_content):
        return [
            {
                "document_type": document_without_content.document_type,
                "document_id": document_without_content.document_id,
                "markdown": "Extracted content",
            }
        ]

    @pytest.mark.parametrize(
        "auto_approve,expected_status",
        [(True, "approved"), (False, "waiting")],
        ids=["auto_approve_on", "auto_approve_off"],
    )
    @patch(PATCH_EXTRACT_CALL_COMMAND)
    @patch(PATCH_OCR)
    def test_content_and_english_translation_status_matches_config(
        self,
        mock_ocr,
        mock_call_command,
        auto_approve,
        expected_status,
        document_without_content,
        extraction_result,
    ):
        mock_ocr.return_value = extraction_result
        ExtractionConfigFactory(auto_approve_extractions=auto_approve)

        run_command("batch_extract")

        content = DocumentContent.objects.get(document=document_without_content)
        assert content.approval_status == expected_status

        en_translation = DocumentTranslation.objects.get(
            document_content=content, language="eng"
        )
        assert en_translation.approval_status == expected_status

    @patch(PATCH_EXTRACT_CALL_COMMAND)
    @patch(PATCH_OCR)
    def test_triggers_batch_translate_per_language_config_when_auto_approve(
        self,
        mock_ocr,
        mock_call_command,
        document_without_content,
        extraction_result,
    ):
        mock_ocr.return_value = extraction_result
        config = ExtractionConfigFactory(auto_approve_extractions=True)
        TranslationConfigFactory(
            config=config, language="spa", auto_approve_translations=True
        )

        run_command("batch_extract")

        mock_call_command.assert_called_once_with(
            "batch_translate", "Spanish", approval_status="approved"
        )

    @patch(PATCH_EXTRACT_CALL_COMMAND)
    @patch(PATCH_OCR)
    def test_does_not_trigger_batch_translate_when_moderated(
        self,
        mock_ocr,
        mock_call_command,
        document_without_content,
        extraction_result,
    ):
        mock_ocr.return_value = extraction_result
        ExtractionConfigFactory(auto_approve_extractions=False)

        run_command("batch_extract")

        mock_call_command.assert_not_called()
