import os
import json

from django.shortcuts import render
from django.views.generic import View
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from la_metro_translations.models import Document


@method_decorator(csrf_exempt, "dispatch")
class UpdateDocumentsWebhook(View):
    """
    Update or create base Documents with information from the BoardAgendas app.
    """

    def post(self, request):
        data = json.loads(request.body)
        errors = {"errors": []}

        # Check authorization
        received_key = data.get("api_key")
        if not received_key:
            errors["errors"].append(
                {
                    "message": (
                        "Bad Request: 'api_key' field missing. "
                        "Please provide a key in order to notify the suite."
                    )
                }
            )
            return HttpResponseBadRequest(json.dumps(errors))
        elif received_key != settings.BOARDAGENDAS_API_KEY:
            errors["errors"].append(
                {
                    "message": (
                        "Unauthorized: Invalid api key. Double check the key submitted."
                    )
                }
            )
            return HttpResponse(status=401, content=json.dumps(errors))

        # Check presence of documents
        documents_data = data.get("documents")
        if not documents_data:
            errors["errors"].append(
                {
                    "message": (
                        "Bad Request: 'documents' field missing. "
                        "Please provide a list of documents."
                    )
                }
            )
            return HttpResponseBadRequest(json.dumps(errors))

        # Validate document fields
        missing_values = []
        expected_fields = [
            "title",
            "source_url",
            "created_at",  # YYYY-MM-DD
            "updated_at",  # YYYY-MM-DD
            "document_type",
            "document_id",
            "entity_type",
            "entity_id",
        ]
        for doc_details in documents_data:
            missing_values.extend(
                [f for f in expected_fields if doc_details.get(f) in [None, ""]]
            )

        missing_values = set(missing_values)
        if len(set(missing_values)) > 0:
            errors["errors"].append(
                {
                    "message": (
                        "Bad Request: Some documents had fields/values missing. "
                        "Ensure the following fields are populated in each document - "
                        f"{', '.join(missing_values)}"
                    )
                }
            )
            return HttpResponseBadRequest(json.dumps(errors))

        # Create/update documents
        num_created = 0
        num_updated = 0
        for doc_details in documents_data:
            doc_obj, doc_created = Document.objects.update_or_create(
                document_id=doc_details["document_id"], defaults=doc_details
            )
            num_created += 1 if doc_created else 0
            num_updated += 1 if not doc_created else 0

        # Respond
        response = {
            "status": 201,
            "content": json.dumps(
                {
                    "message": (
                        "Success: "
                        f"Document(s) created - {num_created}; "
                        f"Document(s) updated - {num_updated}"
                    )
                }
            ),
        }

        return HttpResponse(**response)


def robots_txt(request):
    return render(
        request,
        "la_metro_translations/robots.txt",
        {"ALLOW_CRAWL": True if os.getenv("ALLOW_CRAWL") == "True" else False},
        content_type="text/plain",
    )


def page_not_found(request, exception, template_name="404.html"):
    return render(request, template_name, status=404)


def server_error(request, template_name="500.html"):
    return render(request, template_name, status=500)
