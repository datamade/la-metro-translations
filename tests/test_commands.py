import itertools
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.core.management import call_command as run_command

from conftest import (
    DocumentContentFactory,
    DocumentFactory,
    DocumentTranslationFactory,
    ExtractionConfigFactory,
    TranslationConfigFactory,
)

from la_metro_translations.utils import (
    BOILERPLATE,
    HR,
    BoilerplateError,
)
from la_metro_translations.models import (
    DocumentContent,
    DocumentTranslation,
    TranslationFile,
    TranslationConfig,
)
from la_metro_translations.services.translation import MistralTranslationService

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
PATCH_CONVERT_RESET_DB = (
    "la_metro_translations.management.commands.convert_docs"
    ".Command.reset_db_connections"
)

PATCH_TRANSLATE_SERVICE = (
    "la_metro_translations.management.commands.batch_translate.get_translation_service"
)
PATCH_START_BATCH_JOB = (
    "la_metro_translations.services.translation.BatchUtils.start_batch_job"
)
PATCH_CHECK_BATCH_JOB = (
    "la_metro_translations.services.translation.BatchUtils.check_batch_job"
)


@pytest.fixture(autouse=True)
def no_reset_db_translate():
    with patch(PATCH_TRANSLATE_RESET_DB):
        yield


@pytest.fixture(autouse=True)
def no_reset_db_convert():
    with patch(PATCH_CONVERT_RESET_DB):
        yield


@pytest.fixture
def doc_id_counter():
    counter = itertools.count(1)
    return lambda: next(counter)


@pytest.fixture
def make_translation(doc_id_counter):
    def _make(language="spa"):
        doc = DocumentFactory(document_id=doc_id_counter())
        content = DocumentContentFactory(document=doc)
        return DocumentTranslationFactory(document_content=content, language=language)

    return _make


@pytest.mark.django_db
class TestBatchTranslateCommand:
    """
    Tests for the batch_translate management command, focused on how the
    --approval_status argument controls translation status and whether
    convert_docs is triggered.
    """

    @pytest.fixture(autouse=True)
    def mock_translate_service(self, document_content):
        with patch(PATCH_TRANSLATE_SERVICE) as mock_service:
            mock_service.return_value.metered_batch_translate.return_value = [
                {
                    "document_id": str(document_content.document.document_id),
                    "markdown": "translated text",
                    "document_type": "bill_document",
                }
            ]
            yield mock_service

    @pytest.mark.parametrize("approval_status", ["waiting", "approved"])
    def test_creates_translations_with_correct_approval_status(
        self, approval_status, document_content, standard_translations
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
        standard_translations,
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
        self, mock_call_command, document_content, standard_translations
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

    def test_chunk_single_documents_groups_pages_by_chunk_size(
        self, make_document_pages, standard_translations
    ):
        content = make_document_pages(55)

        chunks = MistralTranslationService.chunk_single_documents(content)

        assert len(chunks) == 11
        for chunk in chunks:
            assert chunk.count("End of Page") == 5

    def test_chunk_single_documents_returns_single_chunk_for_small_document(
        self, make_document_pages, standard_translations
    ):
        content = make_document_pages(3)

        chunks = MistralTranslationService.chunk_single_documents(content)

        assert len(chunks) == 1
        assert chunks[0].count("End of Page") == 3

    def test_batch_translate_stitches_chunks_in_numeric_order(
        self,
        document_content,
        make_document_pages,
        translation_config,
        standard_translations,
    ):
        """
        Check that chunks are stitched back in actual numeric order (0, 1, 2, ..., 10)
        instead of faux-alphabetized ("0", "1", "10", "2", ...).

        This case would only happen if a document produces more than 10 chunks.
        """
        document_content.markdown = make_document_pages(55)
        document_content.processed = document_content.markdown
        document_content.save()

        doc = document_content.document
        doc_custom_id = f"{doc.document_type}:{doc.document_id}"

        # Deliberately out of numeric order
        chunk_order = [0, 1, 10, 2, 3, 4, 5, 6, 7, 8, 9]
        response_lines = [
            json.dumps(
                {
                    "custom_id": f"{doc_custom_id}:chunk_{i}",
                    "response": {
                        "body": {"choices": [{"message": {"content": f"chunk-{i}-"}}]}
                    },
                }
            )
            for i in chunk_order
        ]

        mock_response = MagicMock()
        mock_response.iter_lines.return_value = response_lines

        with patch(PATCH_START_BATCH_JOB), patch(
            PATCH_CHECK_BATCH_JOB, return_value=mock_response
        ):
            translations = list(
                MistralTranslationService.batch_translate([document_content], "Spanish")
            )

        assert len(translations) == 1
        expected_markdown = "".join(f"chunk-{i}-" for i in range(11))
        assert translations[0]["markdown"] == expected_markdown

    def test_batch_translate_skips_document_missing_chunks(
        self, document_content, make_document_pages, standard_translations
    ):
        """
        Check that we don't create translations when our translation service doesn't
        return all chunks from a single document, instead of creating an incomplete one.
        """
        document_content.markdown = make_document_pages(10)
        document_content.processed = document_content.markdown
        document_content.save()

        doc = document_content.document
        doc_custom_id = f"{doc.document_type}:{doc.document_id}"

        # Expecting 2 chunks from 20 pages (5 pages per chunk), but only return one
        response_lines = [
            json.dumps(
                {
                    "custom_id": f"{doc_custom_id}:chunk_0",
                    "response": {
                        "body": {"choices": [{"message": {"content": "chunk-0-"}}]}
                    },
                }
            )
        ]

        mock_response = MagicMock()
        mock_response.iter_lines.return_value = response_lines

        with patch(PATCH_START_BATCH_JOB), patch(
            PATCH_CHECK_BATCH_JOB, return_value=mock_response
        ):
            translations = list(
                MistralTranslationService.batch_translate([document_content], "Spanish")
            )

        assert translations == []

    @pytest.mark.parametrize(
        "target_translator",
        [choice[0] for choice in TranslationConfig.TARGET_TRANSLATOR_CHOICES],
    )
    def test_translations_use_chosen_llm(
        self, document_content, target_translator, standard_translations
    ):
        """
        Check that translation jobs use the llm chosen by the user
        per the language's config settings.
        """
        TranslationConfigFactory(language="spa", target_translator=target_translator)

        with patch(PATCH_START_BATCH_JOB) as mock_start_batch_job, patch(
            PATCH_CHECK_BATCH_JOB, return_value=None
        ):
            list(
                MistralTranslationService.batch_translate([document_content], "Spanish")
            )

        mock_start_batch_job.assert_called_once()
        assert mock_start_batch_job.call_args.kwargs["model"] == target_translator


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


@pytest.mark.django_db
class TestConvertDocsCommand:
    """
    Tests for the convert_docs management command.

    This focuses on how the command creates RTFs for all DocumentTranslations with out-of-date RTFs,
    and PDFs for all non-English DocumentTranslations with out-of-date PDFs.
    """

    def _set_updated_at(self, obj, dt):
        type(obj).objects.filter(pk=obj.pk).update(updated_at=dt)
        obj.refresh_from_db()

    def _make_translation_file(self, translation, fmt, updated_at=None):
        file = TranslationFile.objects.create(
            document_translation=translation, format=fmt
        )
        if updated_at is not None:
            TranslationFile.objects.filter(pk=file.pk).update(updated_at=updated_at)
        return file

    def test_rtf_created_only_for_translations_without_up_to_date_rtf(
        self, make_translation, mock_converter
    ):
        """
        Only translations missing an RTF or with an outdated RTF (file.updated_at <
        translation.updated_at) should be processed. Translations with a current RTF
        must be skipped.
        """
        now = datetime.now()
        past = now - timedelta(hours=1)

        make_translation()  # creates translation missing an RTF

        outdated_rtf = make_translation()  # RTF exists but is stale
        self._set_updated_at(outdated_rtf, now)
        self._make_translation_file(outdated_rtf, "rtf", updated_at=past)

        up_to_date = make_translation()  # RTF is current
        self._set_updated_at(up_to_date, past)
        self._make_translation_file(up_to_date, "rtf", updated_at=now)

        run_command("convert_docs")

        assert mock_converter.convert_to_rtf.call_count == 2

    def test_pdf_created_only_for_non_english_translations_without_up_to_date_pdf(
        self, make_translation, mock_converter
    ):
        """
        PDFs should only be created for non-English translations that are missing a
        PDF or have an outdated one. English translations and those with a current PDF
        must be skipped.

        This test guards against the exclude() multi-argument bug where
        .exclude(pk__in=..., language="eng") only excluded rows matching BOTH
        conditions simultaneously, causing the queryset to return nearly all rows.
        """
        now = datetime.now()
        past = now - timedelta(hours=1)

        make_translation(language="eng")  # always skip eng, even without a PDF

        make_translation(language="spa")  # creates translation missing a PDF

        outdated = make_translation(language="zho-cn")  # PDF exists but is stale
        self._set_updated_at(outdated, now)
        self._make_translation_file(outdated, "pdf", updated_at=past)

        up_to_date = make_translation(language="kor")  # PDF is current
        self._set_updated_at(up_to_date, past)
        self._make_translation_file(up_to_date, "pdf", updated_at=now)

        run_command("convert_docs")

        assert mock_converter.convert_to_pdf.call_count == 2

    def test_no_files_created_when_all_are_up_to_date(
        self, make_translation, mock_converter
    ):
        """
        When every translation already has a current RTF and PDF, no converter calls
        should be made and bulk_create should not be invoked.
        """
        now = datetime.now()
        past = now - timedelta(hours=1)

        non_eng = make_translation(language="spa")
        self._set_updated_at(non_eng, past)
        self._make_translation_file(non_eng, "rtf", updated_at=now)
        self._make_translation_file(non_eng, "pdf", updated_at=now)

        eng = make_translation(language="eng")
        self._set_updated_at(eng, past)
        self._make_translation_file(eng, "rtf", updated_at=now)

        run_command("convert_docs")

        mock_converter.convert_to_rtf.assert_not_called()
        mock_converter.convert_to_pdf.assert_not_called()
        mock_converter.bulk_create.assert_not_called()

    def test_convert_doc_single_creates_rtf_and_pdf_for_non_english(
        self, make_translation, mock_converter
    ):
        """
        When called with --document_translation <id> for a non-English translation,
        the command should create both an RTF and a PDF.
        """
        translation = make_translation(language="spa")

        run_command("convert_docs", document_translation=translation.pk)

        mock_converter.convert_to_rtf.assert_called_once()
        mock_converter.convert_to_pdf.assert_called_once()


@pytest.mark.django_db
class TestAgendaPagesRemovalAndReplacement:

    placeholder = BOILERPLATE["agenda_pages_2_and_3_text"]["placeholder"]

    @pytest.fixture
    def boilerplate(self, standard_translations):
        return standard_translations.agenda_pages_2_and_3_text

    @pytest.fixture
    def disclaimer(self, standard_translations):
        return standard_translations.disclaimer_text

    @pytest.mark.parametrize(
        "entity_type, document_type, replaced, placeholder_found",
        [
            ("event", "event_document", True, True),  # agenda
            ("bill", "bill_document", False, False),  # bill
            (
                "event",
                "event_document",
                True,
                False,
            ),  # agenda + LLM garbled placeholder
        ],
    )
    def test_batch_translate_removes_and_replaces_agenda_pages_2_3_boilerplate(
        self,
        translation_config,
        make_document_pages,
        boilerplate,
        entity_type,
        document_type,
        replaced,
        placeholder_found,
    ):
        """
        Test that batch_translate does the right thing in trying to remove and replace
        agenda pages 2 and 3. Only working on agendas, and prepending boilerplate when it
        can't find the placeholder to replace.
        """

        markdown = make_document_pages(5)

        document = DocumentFactory(entity_type=entity_type, document_id="889")
        content = DocumentContentFactory(document=document, markdown=markdown)

        md1 = "This should come before the boilerplate\n\n"
        md2 = f"{self.placeholder}\n\n"
        md3 = "This should come after the boilerplate"
        no_placeholder = "There is no placeholder here"

        placeholdered_output = md1 + md2 + md3

        with patch(PATCH_TRANSLATE_SERVICE) as mock_service:

            output = (
                placeholdered_output
                if document_type == "event_document" and placeholder_found
                else no_placeholder
            )

            mock_service.return_value.metered_batch_translate.return_value = [
                {
                    "document_id": str(content.document.document_id),
                    "document_type": document_type,
                    "markdown": output,
                }
            ]

            run_command(
                "batch_translate",
                "Spanish",
            )

        content.refresh_from_db()

        # Agenda processed is modified, and bill is not
        assert (self.placeholder in content.processed) is replaced
        assert ("End of Page 2" not in content.processed) is replaced

        # Markdown remains untouched for both
        assert self.placeholder not in content.markdown
        assert "End of Page 2" in content.markdown

        translation = DocumentTranslation.objects.get(
            document_content=content, language="spa"
        )
        assert translation

        # agenda but placeholder garbled, should prepend boilerplate
        if replaced and not placeholder_found:
            assert translation.raw_output == no_placeholder
            assert translation.markdown == boilerplate + HR + no_placeholder

        # agenda happy path
        elif replaced:
            assert translation.raw_output == placeholdered_output
            assert translation.markdown == md1 + HR + boilerplate + HR + md3

        # not agenda
        elif not replaced:
            assert translation.raw_output == no_placeholder
            assert translation.markdown == no_placeholder

    def test_batch_translate_errors_out_when_page_markers_not_found(
        self, make_document_pages
    ):
        markdown = make_document_pages(1)
        agenda = DocumentFactory(
            entity_type="event", document_type="event_document", document_id="10101"
        )
        DocumentContentFactory(document=agenda, markdown=markdown)

        with pytest.raises(BoilerplateError) as excinfo:
            run_command("batch_translate", "Spanish")

        assert "Expected exactly one instance" in str(excinfo.value.__cause__)
        assert "0" in str(excinfo.value.__cause__)
        assert "End of page markers not found" in str(excinfo.value)
