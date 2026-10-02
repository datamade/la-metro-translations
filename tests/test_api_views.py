import pytest

from rest_framework.test import APIRequestFactory
from la_metro_translations.api.views import DocumentFilesView
from django.conf import settings

from tests.conftest import (
    DocumentTranslationFactory,
    LinkTextFactory,
    TranslationFileFactory,
)


@pytest.fixture
def document_files_response(document_content):
    def get():
        view = DocumentFilesView.as_view()
        keys = ["entity_type", "document_id"]
        params = {key: getattr(document_content.document, key) for key in keys}
        params.update({"api_key": settings.BOARDAGENDAS_API_KEY})
        request = APIRequestFactory().get(
            "/document_files/", data=params, format="json"
        )

        return view(request)

    return get


@pytest.mark.django_db
class TestDocumentFilesAPIView:

    def test_document_files_api_request_succeeds(self, document_files_response):
        response = document_files_response()
        assert response.status_code == 200

    def test_document_files_api_unapproved_translations_not_included(
        self, document_content, document_files_response, document_translation, link_text
    ):

        assert document_translation in document_content.translations.filter(
            language="spa"
        )

        assert document_translation.approval_status == "waiting"
        assert link_text.language == "spa"

        response = document_files_response()
        assert response.data == {"pdf": [], "rtf": []}

    def test_document_files_api_response_attributes(
        self, document_files_response, document_content
    ):

        # create link text
        link_source_data = {
            "language": "hye",
            "board_report_download_text": "hye - board report",
            "agenda_download_text": "hye - agenda",
        }

        LinkTextFactory(**link_source_data)

        # create translation
        hye = DocumentTranslationFactory(
            approval_status="approved",
            language="hye",
            document_content=document_content,
        )

        file_source_data = {
            "document_translation": hye,
            "format": "pdf",
            "file": "hye.pdf",
        }

        # create translation file
        TranslationFileFactory(**file_source_data)

        response = document_files_response()
        pdf_data = response.data["pdf"]
        assert len(pdf_data) == 1
        rtf_data = response.data["rtf"]
        assert len(rtf_data) == 0

        hye_response = pdf_data[0]
        assert len(hye_response) == 3

        assert hye_response["language"] == "Armenian (Eastern)"
        assert (
            hye_response["link_text"] == link_source_data["board_report_download_text"]
        )
        assert hye_response["url"] == "/media/" + file_source_data["file"]
