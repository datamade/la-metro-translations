import os

from django.http import JsonResponse
from django.shortcuts import render
from wagtail.admin.auth import require_admin_access

from la_metro_translations.celery import debug_task


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


@require_admin_access
def trigger_debug_task(request):
    result = debug_task.delay()
    return JsonResponse({"task_id": result.id})
