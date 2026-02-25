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
        num_created = 0
        num_updated = 0
        for doc_details in cleaned_data["documents"]:
            doc_obj, doc_created = Document.objects.update_or_create(
                document_id=doc_details["document_id"], defaults=doc_details
            )
            num_created += 1 if doc_created else 0
            num_updated += 1 if not doc_created else 0

        success_msg = {
            "message": (
                "Success: "
                f"Document(s) created - {num_created}; "
                f"Document(s) updated - {num_updated}"
            )
        }
        return Response(success_msg, status=status.HTTP_201_CREATED)
