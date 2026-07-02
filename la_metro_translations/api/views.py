from django.conf import settings
from django.db.models import Prefetch
from django.db.models import Case, When

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from la_metro_translations.models import (
    Document,
    DocumentContent,
    DocumentTranslation,
    TranslationFile,
)
from la_metro_translations.api.serializers import NotificationSerializer


class DocumentUpdateView(APIView):
    """
    Update or create base Documents with information from the BoardAgendas app.
    """

    def post(self, request):
        serializer = NotificationSerializer(data=request.data)
        if not serializer.is_valid():
            if serializer.errors.get("api_key"):
                return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cleaned_data = serializer.data

        # Create/update documents
        documents_to_upsert = []
        for doc_details in cleaned_data["documents"]:
            documents_to_upsert.append(Document(**doc_details))

        created_docs = Document.objects.bulk_create(
            documents_to_upsert,
            update_conflicts=True,
            unique_fields=["document_type", "document_id"],
            update_fields=[
                "title",
                "source_url",
                "created_at",
                "updated_at",
                "entity_type",
                "entity_id",
                "entity_slug",
            ],
        )

        success_msg = {
            "message": f"Success: Document(s) created/updated - {len(created_docs)}"
        }
        return Response(success_msg, status=status.HTTP_201_CREATED)


class DocumentFilesView(APIView):
    """
    Return urls for an entity's files and translations.
    """

    def get(self, request):
        api_key = request.query_params.get("api_key")
        if api_key != settings.BOARDAGENDAS_API_KEY:
            error_msg = "Unauthorized: Invalid api key. Double check the key submitted."
            return Response(error_msg, status=status.HTTP_403_FORBIDDEN)

        entity_type = request.query_params.get("entity_type")
        document_id = request.query_params.get("document_id")
        agenda_text_map = {
            "hye": "Օրակարգը ներբեռնել (Արևելահայերեն)",
            "hyw": "Ներբեռնել Օրակարգը (Արևմտահայերէն)",
            "zho-cn": "下载议程 (汉语)",
            "zho-tw": "下載議程 (漢語)",
            "eng": "Download Agenda (English - Accessible)",
            "jpn": "議題をダウンロード (日本語)",
            "kor": "의제 다운로드 (한국어)",
            "rus": "Скачать повестку дня (Русский)",
            "spa": "Descargar Agenda (Español)",
            "vie": "Tải xuống Chương trình (tiếng Việt)",
        }
        board_report_text_map = {
            "hye": "Download Board Report (Արևելահայերեն)",
            "hyw": "Download Board Report (Արևմտահայերէն)",
            "zho-cn": "Download Board Report (汉语)",
            "zho-tw": "Download Board Report (漢語)",
            "eng": "Download Board Report (English - Accessible)",
            "jpn": "Download Board Report (日本語)",
            "kor": "Download Board Report (한국어)",
            "rus": "Download Board Report (Русский)",
            "spa": "Download Board Report (Español)",
            "vie": "Download Board Report (tiếng Việt)",
        }

        link_text_map = (
            agenda_text_map if entity_type == "event" else board_report_text_map
        )

        lang_order = [
            "eng",
            "spa",
            "zho-cn",
            "zho-tw",
            "kor",
            "hye",
            "hyw",
            "vie",
            "rus",
            "jpn",
        ]
        ordered = Case(
            *[
                When(language=language, then=index)
                for index, language in enumerate(lang_order)
            ]
        )

        # Only return relevant related objects
        translation_filter = DocumentTranslation.objects.filter(
            approval_status="approved"
        ).order_by(ordered)
        files_filter = TranslationFile.objects.exclude(
            document_translation__language="eng", format="pdf"
        )
        try:
            content = DocumentContent.objects.prefetch_related(
                Prefetch("translations", translation_filter),
                Prefetch("translations__files", files_filter),
            ).get(document__entity_type=entity_type, document__document_id=document_id)
        except DocumentContent.DoesNotExist:
            error_msg = "Not Found: Matching document does not exist in the suite."
            return Response(error_msg, status=status.HTTP_404_NOT_FOUND)

        file_links = {"pdf": [], "rtf": []}
        for translation in content.translations.all():
            for file in translation.files.all():
                link_details = {
                    "link_text": link_text_map[translation.language],
                    "url": file.get_file_url(),
                }
                file_links[file.format].append(link_details)

        return Response(file_links, status=status.HTTP_200_OK)
