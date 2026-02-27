from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from la_metro_translations.models import Document
from la_metro_translations.api.serializers import NotificationSerializer


class DocumentUpdateView(APIView):
    """
    Update or create base Documents with information from the BoardAgendas app.
    """

    def post(self, request):
        serializer = NotificationSerializer(data=request.data)
        if not serializer.is_valid():
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
            ],
        )

        success_msg = {
            "message": f"Success: Document(s) created/updated - {len(created_docs)}"
        }
        return Response(success_msg, status=status.HTTP_201_CREATED)
