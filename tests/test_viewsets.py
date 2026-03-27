import pytest
from django.urls import reverse

from conftest import DocumentFactory, DocumentContentFactory, DocumentTranslationFactory


@pytest.mark.django_db
class TestDocumentViewSet:
    def test_document_list_view_empty(self, wagtail_user_client):
        url = reverse("document:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert "There are no documents to display." in response.content.decode()

    def test_document_list_view_loads(self, wagtail_user_client, document):
        url = reverse("document:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert document.title in response.content.decode()

    def test_document_edit_view_loads(self, wagtail_user_client, document):
        url = reverse("document:edit", args=[document.pk])
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert document.title in response.content.decode()

    def test_document_create_view_inaccessible_to_wagtail_user(
        self, wagtail_user_client
    ):
        url = reverse("document:add")
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_delete_view_inaccesible_to_wagtail_user(
        self, wagtail_user_client, document
    ):
        url = reverse("document:delete", args=[document.pk])
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_filtering_works(self, wagtail_user_client, document):
        for i in range(3):
            DocumentFactory(
                title=f"Not A Match {i}",
                entity_type="unknown",
                entity_id=i,
                document_id=i,
            )

        # Test unfiltered results include > 1 document
        url = reverse("document:index")
        response = wagtail_user_client.get(url)
        assert response.status_code == 200
        assert "4 documents" in response.content.decode()

        # Test title filter
        response = wagtail_user_client.get(url, {"title": document.title})
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document.title in response.content.decode()

        # Test entity type filter
        response = wagtail_user_client.get(url, {"entity_type": document.entity_type})
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document.title in response.content.decode()


@pytest.mark.django_db
class TestDocumentContentViewSet:
    def test_document_content_list_view_empty(self, wagtail_user_client):
        url = reverse("document_content:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert "There are no document contents to display." in response.content.decode()

    def test_document_content_list_view_loads(
        self, wagtail_user_client, document_content
    ):
        url = reverse("document_content:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert document_content.document.title in response.content.decode()

    def test_document_content_edit_view_loads(
        self, wagtail_user_client, document_content
    ):
        url = reverse("document_content:edit", args=[document_content.pk])
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert document_content.markdown in response.content.decode()

    def test_document_content_create_view_inaccessible_to_wagtail_user(
        self, wagtail_user_client
    ):
        url = reverse("document_content:add")
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_content_delete_view_inaccessible_to_wagtail_user(
        self, wagtail_user_client, document_content
    ):
        url = reverse("document_content:delete", args=[document_content.pk])
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_content_filtering_works(
        self, wagtail_user_client, document_content
    ):

        for i in range(3):
            doc = DocumentFactory(
                title=f"Not A Match {i}",
                entity_type="unknown",
                entity_id=i,
                document_id=i,
            )
            DocumentContentFactory(
                document=doc,
                markdown=f"Content {i}",
                approval_status="waiting",
            )

        # Test unfiltered results include > 1 document content
        url = reverse("document_content:index")
        response = wagtail_user_client.get(url)
        assert response.status_code == 200
        assert "4 document contents" in response.content.decode()

        # Test document title filter
        response = wagtail_user_client.get(
            url, {"document__title": document_content.document.title}
        )
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document_content.document.title in response.content.decode()

        # Test approval status filter
        response = wagtail_user_client.get(
            url, {"approval_status": document_content.approval_status}
        )
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document_content.document.title in response.content.decode()


@pytest.mark.django_db
class TestDocumentTranslationViewSet:
    def test_document_translation_list_view_empty(self, wagtail_user_client):
        url = reverse("document_translation:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert (
            "There are no document translations to display."
            in response.content.decode()
        )

    def test_document_translation_list_view_loads(
        self, wagtail_user_client, document_translation
    ):
        url = reverse("document_translation:index")
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert (
            document_translation.document_content.document.title
            in response.content.decode()
        )

    def test_document_translation_edit_view_loads(
        self, wagtail_user_client, document_translation
    ):
        url = reverse("document_translation:edit", args=[document_translation.pk])
        response = wagtail_user_client.get(url)

        assert response.status_code == 200
        assert document_translation.markdown in response.content.decode()

    def test_document_translation_create_view_inaccessible_to_wagtail_user(
        self, wagtail_user_client
    ):
        url = reverse("document_translation:add")
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_translation_delete_view_inaccessible_to_wagtail_user(
        self, wagtail_user_client, document_translation
    ):
        url = reverse("document_translation:delete", args=[document_translation.pk])
        response = wagtail_user_client.get(url)
        assert response.status_code == 302

    def test_document_translation_filtering_works(
        self, wagtail_user_client, document_translation
    ):

        for i in range(3):
            doc = DocumentFactory(
                title=f"Not A Match {i}",
                entity_type="unknown",
                entity_id=i,
                document_id=i,
            )
            content = DocumentContentFactory(
                document=doc,
                markdown=f"Content {i}",
                approval_status="approved",
            )
            DocumentTranslationFactory(
                document_content=content,
                markdown=f"Translation {i}",
                language="french",
                approval_status="revision",
            )

        # Test unfiltered results include > 1 document translation
        url = reverse("document_translation:index")
        response = wagtail_user_client.get(url)
        assert response.status_code == 200
        assert "4 document translations" in response.content.decode()

        document = document_translation.document_content.document

        # Test document title filter
        response = wagtail_user_client.get(
            url,
            {"document_content__document__title": document.title},
        )
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document.title in response.content.decode()

        # Test language filter
        response = wagtail_user_client.get(
            url, {"language": document_translation.language}
        )
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document.title in response.content.decode()

        # Test approval status filter
        response = wagtail_user_client.get(
            url, {"approval_status": document_translation.approval_status}
        )
        assert response.status_code == 200
        assert "There is 1 match" in response.content.decode()
        assert document.title in response.content.decode()
