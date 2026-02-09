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
class NewDocumentWebhook(View):
    """
    Create a new base Document with information from the BoardAgendas app.
    """

    def post(self, request):
        data = json.loads(request.body)

        # Check authorization
        received_key = data.get("api_key")
        if not received_key:
            response = {
                "message": (
                    "Bad Request: Api key missing. "
                    "Please provide a key in order to notify the suite."
                )
            }
            return HttpResponseBadRequest(json.dumps(response))
        elif received_key != settings.BOARDAGENDAS_API_KEY:
            response = {
                "message": "Unauthorized: Invalid api key. "
                "Double check the key submitted."
            }
            return HttpResponse(json.dumps(response), status=401)

        # Validate fields
        defaults = {
            "document_id": data.get("document_id"),
            "title": data.get("title"),
            "source_url": data.get("source_url"),
            "created_at": data.get("created_at"),  # YYYY-MM-DD
            "document_type": data.get("document_type"),
            "entity_type": data.get("entity_type"),
            "entity_id": data.get("entity_id"),
        }

        missing_keys = [key for key in defaults.keys() if defaults[key] in [None, ""]]
        if missing_keys:
            response = {
                "message": (
                    "Bad Request: Missing attributes. "
                    "Please provide the following field values - "
                    f"{', '.join(missing_keys)}"
                )
            }
            return HttpResponseBadRequest(json.dumps(response))

        # Create document
        new_doc, doc_created = Document.objects.update_or_create(
            document_id=data["document_id"], defaults=defaults
        )

        # Respond
        if doc_created:
            response = {
                "status": 201,
                "content": json.dumps(
                    {"status": "Created", "message": "New document created and saved."}
                ),
            }
        else:
            response = {
                "status": 200,
                "content": json.dumps(
                    {"status": "Success", "message": "Existing document updated."}
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
